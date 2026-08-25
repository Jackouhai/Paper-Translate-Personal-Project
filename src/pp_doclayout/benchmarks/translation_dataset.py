"""Build a vLLM custom dataset from parsed PP-DocLayout projects."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

from ..policies.translation_policy import should_translate
from ..translators.gemma import GemmaTranslator


class TranslationPromptBuilder(Protocol):
    def build_translation_prompt(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "vi",
    ) -> str: ...

    def get_max_tokens_for_text(self, text: str) -> int: ...


def _page_json_paths(project_dir: Path) -> list[Path]:
    def page_number(path: Path) -> int:
        match = re.search(r"_(\d+)_res$", path.stem)
        return int(match.group(1)) if match else 0

    paths = sorted(project_dir.glob("*_res.json"), key=page_number)
    if not paths:
        raise FileNotFoundError(f"No *_res.json files found in {project_dir}")
    return paths


def _text_sent_to_translator(label: str, content: str) -> str:
    """Match the source-text preparation in ``translate_page_data``."""
    text = content.strip()
    if label == "abstract" and text.lower().startswith("abstract"):
        return text[8:]
    return text


def build_records(
    project_dirs: Iterable[Path],
    prompt_builder: TranslationPromptBuilder,
    *,
    translate_titles: bool = False,
    max_samples: int | None = None,
) -> list[dict[str, Any]]:
    """Create vLLM custom-dataset records for the blocks the pipeline translates."""
    records: list[dict[str, Any]] = []

    for project_dir in project_dirs:
        for json_path in _page_json_paths(project_dir):
            page = json.loads(json_path.read_text(encoding="utf-8"))
            page_index = page.get("page_index")
            for block in page.get("parsing_res_list", []):
                label = block.get("block_label", "")
                content = block.get("block_content", "")
                if should_translate(
                    label,
                    content,
                    translate_titles=translate_titles,
                ) != "translate":
                    continue

                source_text = _text_sent_to_translator(label, content)
                if not source_text.strip():
                    continue

                prompt = prompt_builder.build_translation_prompt(source_text)
                records.append(
                    {
                        # Fields consumed by vllm bench serve --dataset-name custom.
                        "prompt": f"<<<custom>>>{prompt}",
                        "output_tokens": prompt_builder.get_max_tokens_for_text(
                            source_text
                        ),
                        # Metadata is retained for result review and is ignored by vLLM.
                        "project": project_dir.name,
                        "page_index": page_index,
                        "block_id": block.get("block_id"),
                        "block_label": label,
                    }
                )

                if max_samples is not None and len(records) >= max_samples:
                    return records

    return records


def write_jsonl(records: Iterable[dict[str, Any]], output_path: Path) -> int:
    """Write records in the JSONL format accepted by vLLM CustomDataset."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as output_file:
        for record in records:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a vLLM custom JSONL benchmark dataset from parsed papers."
    )
    parser.add_argument(
        "project_dirs",
        nargs="+",
        type=Path,
        help="One or more directories containing *_res.json parse results.",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--translate-titles",
        action="store_true",
        help="Include paragraph_title blocks, matching CLI --translate-titles.",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        help="Stop after this many translation blocks.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_samples is not None and args.max_samples <= 0:
        raise SystemExit("--max-samples must be greater than zero")

    records = build_records(
        args.project_dirs,
        GemmaTranslator(),
        translate_titles=args.translate_titles,
        max_samples=args.max_samples,
    )
    if not records:
        raise SystemExit("No translatable blocks found in the supplied projects")

    count = write_jsonl(records, args.output)
    print(f"Wrote {count} benchmark samples to {args.output}")
