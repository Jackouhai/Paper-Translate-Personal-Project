#!/usr/bin/env python3
"""Reference-free RUBRIC-MQM judge for English -> Vietnamese translation.

Input files (one aligned segment per physical line):
  test.en
  gemma_promt.vi

Install:
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -U google-genai pydantic

Run:
  export GEMINI_API_KEY="YOUR_KEY"
  python gemini_mqm_judge.py --input-dir /path/to/data --limit 5
  python gemini_mqm_judge.py --input-dir /path/to/data

Outputs are written under <input-dir>/mqm_results by default.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError, model_validator


Category = Literal[
    "MISTRANSLATION",
    "OMISSION",
    "ADDITION",
    "UNTRANSLATED",
    "GRAMMAR",
    "PUNCTUATION",
    "WORD_ORDER",
    "INCONSISTENCY",
    "TERMINOLOGY",
    "SOURCE_ISSUE",
    "SCIENTIFIC_NOTATION",
    "CITATION_REFERENCE",
    "ACADEMIC_STYLE",
]
Severity = Literal["MINOR", "MAJOR", "CRITICAL"]

PENALTY = {"MINOR": 1, "MAJOR": 5, "CRITICAL": 10}
RETRYABLE_CODES = {408, 409, 429, 500, 502, 503, 504}
NON_RETRYABLE_CODES = {400, 401, 403, 404}


class MQMError(BaseModel):
    category: Category
    severity: Severity
    source_span: str = Field(
        default="",
        description="Exact problematic source span; especially useful for omissions.",
    )
    candidate_span: str = Field(
        default="",
        description="Exact problematic candidate span; empty if content was omitted.",
    )
    explanation: str = Field(description="Concise explanation in Vietnamese.")
    suggested_correction: str = Field(
        default="",
        description="A concise Vietnamese correction when applicable.",
    )


class SegmentJudgment(BaseModel):
    errors: list[MQMError] = Field(default_factory=list)
    no_error: bool
    summary: str = Field(description="Concise overall assessment in Vietnamese.")

    @model_validator(mode="after")
    def check_no_error(self) -> "SegmentJudgment":
        if self.no_error != (len(self.errors) == 0):
            raise ValueError("no_error must be true exactly when errors is empty")
        return self


SYSTEM_INSTRUCTION = """
You are an expert evaluator of English-to-Vietnamese scientific translation.
Apply a reference-free, span-level MQM rubric. Compare the Vietnamese candidate
directly with the English source. There is no human reference.

Return every independent, meaningful error, but do not invent errors. A valid
paraphrase is not an error. Do not reward literal wording or verbosity. Use
NO-ERROR behavior by returning errors=[] and no_error=true when the translation
is fully acceptable.

Categories:
- MISTRANSLATION: incorrect meaning, relation, negation, modality, entity, or claim.
- OMISSION: meaningful source content is absent.
- ADDITION: unsupported meaning is introduced.
- UNTRANSLATED: source-language content that should be translated remains.
- GRAMMAR: Vietnamese grammar or agreement problem.
- PUNCTUATION: punctuation error that affects quality or interpretation.
- WORD_ORDER: unnatural or misleading Vietnamese ordering.
- INCONSISTENCY: inconsistency visible within this segment only. Do not infer
  document-level inconsistency from one isolated segment.
- TERMINOLOGY: incorrect scientific/technical term in context.
- SOURCE_ISSUE: the English source itself is malformed, ambiguous, or corrupted.
- SCIENTIFIC_NOTATION: changed or malformed number, unit, symbol, variable,
  formula, superscript/subscript meaning, sign, or mathematical notation.
- CITATION_REFERENCE: changed/missing citation or Figure/Table/Equation/Section reference.
- ACADEMIC_STYLE: clearly unsuitable academic Vietnamese, not merely a stylistic preference.

Severity:
- MINOR: localized issue; meaning and scientific conclusion remain intact.
- MAJOR: substantial loss/distortion, important terminology error, or serious readability issue.
- CRITICAL: reverses or corrupts a central scientific claim, result, number, unit,
  equation, safety-relevant statement, or conclusion.

Annotation rules:
1. Use exact spans when possible. For omission, candidate_span may be empty.
2. Avoid double-counting one underlying problem under multiple categories;
   choose its primary category.
3. Punctuation or style differences that are acceptable Vietnamese receive no error.
4. Explain decisions briefly in Vietnamese.
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gemini reference-free RUBRIC-MQM judge (EN -> VI)."
    )
    parser.add_argument("--input-dir", type=Path, default=Path("."))
    parser.add_argument("--source", default="test.en")
    parser.add_argument("--candidate", default="gemma_promt.vi")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--model", default="gemini-3.5-flash")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only judge the first N segments; useful for a pilot run.")
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--request-delay", type=float, default=1.0,
                        help="Minimum pause after each successful API call.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Replace existing outputs instead of resuming.")
    return parser.parse_args()


def read_physical_lines(path: Path) -> list[str]:
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file: {path}")
    # splitlines preserves alignment: blank physical lines are retained.
    return path.read_text(encoding="utf-8-sig").splitlines()


def load_dataset(source_path: Path, candidate_path: Path) -> list[dict]:
    sources = read_physical_lines(source_path)
    candidates = read_physical_lines(candidate_path)
    if len(sources) != len(candidates):
        raise ValueError(
            "Hai file không cùng số dòng: "
            f"{source_path.name}={len(sources)}, "
            f"{candidate_path.name}={len(candidates)}"
        )

    dataset: list[dict] = []
    for line_id, (source, candidate) in enumerate(zip(sources, candidates), 1):
        source, candidate = source.strip(), candidate.strip()
        if not source:
            raise ValueError(f"{source_path.name} có dòng trống tại dòng {line_id}")
        if not candidate:
            raise ValueError(f"{candidate_path.name} có dòng trống tại dòng {line_id}")
        dataset.append({"id": line_id, "source": source, "candidate": candidate})
    return dataset


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def user_prompt(sample: dict) -> str:
    return (
        "Evaluate this single aligned segment.\n\n"
        "<ENGLISH_SOURCE>\n"
        f"{sample['source']}\n"
        "</ENGLISH_SOURCE>\n\n"
        "<VIETNAMESE_CANDIDATE>\n"
        f"{sample['candidate']}\n"
        "</VIETNAMESE_CANDIDATE>"
    )


def status_code(error: Exception) -> int | None:
    for name in ("code", "status_code"):
        value = getattr(error, name, None)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            pass
    return None


def call_judge(
    client: genai.Client,
    model: str,
    sample: dict,
    max_retries: int,
) -> SegmentJudgment:
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=user_prompt(sample),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=SegmentJudgment,
                ),
            )
            if response.parsed is not None:
                if isinstance(response.parsed, SegmentJudgment):
                    return response.parsed
                return SegmentJudgment.model_validate(response.parsed)
            if not response.text:
                raise RuntimeError("Gemini không trả về nội dung.")
            return SegmentJudgment.model_validate_json(response.text)
        except (Exception, ValidationError) as error:
            last_error = error
            code = status_code(error)
            if code in NON_RETRYABLE_CODES or attempt == max_retries - 1:
                break
            # Unknown transport/schema failures and documented transient codes
            # are retried with exponential backoff and jitter.
            if code is not None and code not in RETRYABLE_CODES:
                break
            delay = min(60.0, 2 ** attempt) + random.uniform(0, 0.5)
            print(f"  Lỗi tạm thời ({error}); thử lại sau {delay:.1f}s", file=sys.stderr)
            time.sleep(delay)
    raise RuntimeError(f"Judge thất bại sau {max_retries} lần: {last_error}")


def record_from(sample: dict, judgment: SegmentJudgment, model: str) -> dict:
    errors = [item.model_dump() for item in judgment.errors]
    penalty = sum(PENALTY[item["severity"]] for item in errors)
    return {
        "id": sample["id"],
        "source": sample["source"],
        "candidate": sample["candidate"],
        "source_sha256": text_hash(sample["source"]),
        "candidate_sha256": text_hash(sample["candidate"]),
        "no_error": judgment.no_error,
        "errors": errors,
        "error_count": len(errors),
        "penalty": penalty,
        "segment_score": max(0, 100 - penalty),
        "summary": judgment.summary,
        "judge_model": model,
    }


def read_existing(path: Path) -> dict[int, dict]:
    records: dict[int, dict] = {}
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                records[int(record["id"])] = record
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
                raise ValueError(f"JSONL cũ lỗi tại dòng {line_no}: {error}") from error
    return records


def verify_resume(existing: dict[int, dict], dataset: list[dict], model: str) -> None:
    by_id = {sample["id"]: sample for sample in dataset}
    for line_id, record in existing.items():
        sample = by_id.get(line_id)
        if sample is None:
            continue
        same = (
            record.get("source_sha256") == text_hash(sample["source"])
            and record.get("candidate_sha256") == text_hash(sample["candidate"])
            and record.get("judge_model") == model
        )
        if not same:
            raise ValueError(
                f"Kết quả cũ không khớp dữ liệu/model tại id={line_id}. "
                "Dùng --overwrite hoặc chọn --output-dir khác."
            )


def write_csv(records: list[dict], path: Path) -> None:
    fields = [
        "id", "source", "candidate", "no_error", "error_count", "penalty",
        "segment_score", "categories", "severities", "summary", "judge_model",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = {key: record.get(key, "") for key in fields}
            row["categories"] = " | ".join(e["category"] for e in record["errors"])
            row["severities"] = " | ".join(e["severity"] for e in record["errors"])
            writer.writerow(row)


def build_summary(records: list[dict], total_dataset_size: int, model: str) -> dict:
    categories: Counter[str] = Counter()
    severities: Counter[str] = Counter()
    for record in records:
        for error in record["errors"]:
            categories[error["category"]] += 1
            severities[error["severity"]] += 1

    n = len(records)
    total_errors = sum(categories.values())
    candidate_words = sum(len(r["candidate"].split()) for r in records)
    no_error_count = sum(bool(r["no_error"]) for r in records)
    return {
        "judge_model": model,
        "evaluation_type": "reference-free span-level adapted RUBRIC-MQM",
        "dataset_segments": total_dataset_size,
        "evaluated_segments": n,
        "failed_or_pending_segments": total_dataset_size - n,
        "no_error_segments": no_error_count,
        "no_error_rate_percent": round(100 * no_error_count / n, 4) if n else None,
        "total_errors": total_errors,
        "candidate_word_count": candidate_words,
        "errors_per_1000_candidate_words": (
            round(1000 * total_errors / candidate_words, 4) if candidate_words else None
        ),
        "mean_errors_per_segment": round(total_errors / n, 4) if n else None,
        "mean_penalty_per_segment": (
            round(sum(r["penalty"] for r in records) / n, 4) if n else None
        ),
        "mean_segment_score": (
            round(sum(r["segment_score"] for r in records) / n, 4) if n else None
        ),
        "errors_by_category": dict(sorted(categories.items())),
        "errors_by_severity": dict(sorted(severities.items())),
        "penalty_weights": PENALTY,
    }


def main() -> int:
    args = parse_args()
    if args.limit is not None and args.limit <= 0:
        raise ValueError("--limit phải lớn hơn 0")
    if args.max_retries <= 0 or args.request_delay < 0:
        raise ValueError("--max-retries phải > 0 và --request-delay phải >= 0")
    if not os.getenv("GEMINI_API_KEY"):
        raise EnvironmentError("Chưa có biến môi trường GEMINI_API_KEY")

    input_dir = args.input_dir.expanduser().resolve()
    source_path = input_dir / args.source
    candidate_path = input_dir / args.candidate
    output_dir = (args.output_dir or input_dir / "mqm_results").expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_path = output_dir / "mqm_details.jsonl"
    failed_path = output_dir / "mqm_failed.jsonl"
    summary_path = output_dir / "mqm_summary.json"
    csv_path = output_dir / "mqm_segments.csv"

    dataset = load_dataset(source_path, candidate_path)
    selected = dataset[: args.limit] if args.limit is not None else dataset
    if args.overwrite:
        for path in (detail_path, failed_path, summary_path, csv_path):
            path.unlink(missing_ok=True)

    existing = read_existing(detail_path)
    verify_resume(existing, dataset, args.model)
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    print(f"Tổng dữ liệu: {len(dataset)} segment")
    print(f"Phạm vi lần chạy này: {len(selected)} segment")
    print(f"Đã hoàn thành trước đó: {len(existing)} segment")
    with detail_path.open("a", encoding="utf-8") as detail, failed_path.open(
        "a", encoding="utf-8"
    ) as failed:
        for position, sample in enumerate(selected, 1):
            if sample["id"] in existing:
                continue
            print(f"[{position}/{len(selected)}] Chấm id={sample['id']}...")
            try:
                judgment = call_judge(
                    client, args.model, sample, args.max_retries
                )
                record = record_from(sample, judgment, args.model)
                detail.write(json.dumps(record, ensure_ascii=False) + "\n")
                detail.flush()
                existing[sample["id"]] = record
                print(
                    f"  score={record['segment_score']}, "
                    f"errors={record['error_count']}"
                )
                if args.request_delay:
                    time.sleep(args.request_delay)
            except Exception as error:
                failure = {"id": sample["id"], "error": str(error)}
                failed.write(json.dumps(failure, ensure_ascii=False) + "\n")
                failed.flush()
                print(f"  THẤT BẠI: {error}", file=sys.stderr)

    records = sorted(existing.values(), key=lambda item: item["id"])
    write_csv(records, csv_path)
    summary = build_summary(records, len(dataset), args.model)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\nKết quả:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nChi tiết JSONL: {detail_path}")
    print(f"Bảng segment CSV: {csv_path}")
    print(f"Tổng hợp JSON: {summary_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError, EnvironmentError) as error:
        print(f"LỖI: {error}", file=sys.stderr)
        raise SystemExit(2)
