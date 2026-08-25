import json
from pathlib import Path

from pp_doclayout.benchmarks.translation_dataset import build_records, write_jsonl


class FakePromptBuilder:
    def build_translation_prompt(self, text, source_lang="en", target_lang="vi"):
        return f"prompt:{source_lang}:{target_lang}:{text}"

    def get_max_tokens_for_text(self, text):
        return len(text)


def test_build_records_matches_translation_policy_and_abstract_handling(tmp_path):
    project_dir = tmp_path / "paper"
    project_dir.mkdir()
    page = {
        "page_index": 2,
        "parsing_res_list": [
            {"block_label": "text", "block_content": "Main body", "block_id": 1},
            {"block_label": "abstract", "block_content": "Abstract Summary", "block_id": 2},
            {"block_label": "table", "block_content": "Do not translate", "block_id": 3},
            {"block_label": "paragraph_title", "block_content": "Methods", "block_id": 4},
        ],
    }
    (project_dir / "paper_2_res.json").write_text(json.dumps(page), encoding="utf-8")

    records = build_records([project_dir], FakePromptBuilder())

    assert [record["block_label"] for record in records] == ["text", "abstract"]
    assert records[0]["prompt"] == "<<<custom>>>prompt:en:vi:Main body"
    assert records[1]["prompt"] == "<<<custom>>>prompt:en:vi: Summary"
    assert records[1]["output_tokens"] == len(" Summary")
    assert records[1]["project"] == "paper"
    assert records[1]["page_index"] == 2


def test_build_records_can_include_titles_and_write_jsonl(tmp_path):
    project_dir = tmp_path / "paper"
    project_dir.mkdir()
    (project_dir / "paper_0_res.json").write_text(
        json.dumps(
            {
                "page_index": 0,
                "parsing_res_list": [
                    {
                        "block_label": "paragraph_title",
                        "block_content": "Methods",
                        "block_id": 8,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    records = build_records(
        [project_dir], FakePromptBuilder(), translate_titles=True
    )
    output_path = tmp_path / "bench" / "samples.jsonl"

    assert write_jsonl(records, output_path) == 1
    assert json.loads(output_path.read_text(encoding="utf-8")) == records[0]


def test_build_records_orders_pages_numerically(tmp_path):
    project_dir = tmp_path / "paper"
    project_dir.mkdir()
    for page_index in (10, 2):
        (project_dir / f"paper_{page_index}_res.json").write_text(
            json.dumps(
                {
                    "page_index": page_index,
                    "parsing_res_list": [
                        {"block_label": "text", "block_content": str(page_index)}
                    ],
                }
            ),
            encoding="utf-8",
        )

    records = build_records([project_dir], FakePromptBuilder())

    assert [record["page_index"] for record in records] == [2, 10]
