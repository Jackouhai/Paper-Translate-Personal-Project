"""Tests for CLI commands that submit parse jobs to the Parse API."""

from pathlib import Path

from pp_doclayout import cli
from pp_doclayout.core.parse_api_client import ParseAPIError


def test_parse_submits_pdf_to_long_lived_parse_api(tmp_path, monkeypatch):
    """The parse CLI command must not construct a local PaddleOCRVL pipeline."""

    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"fake PDF")
    project_dir = tmp_path / "custom-output" / "paper-12345678"
    calls = []
    messages = []

    def fake_parse_via_api(pdf_path, base_url, output_dir):
        calls.append((pdf_path, base_url, output_dir))
        return project_dir

    monkeypatch.setattr(cli, "parse_pdf_via_api", fake_parse_via_api)
    monkeypatch.setattr(cli.typer, "echo", lambda message, **kwargs: messages.append(message))

    cli.parse(str(pdf_path), output_dir=str(tmp_path / "custom-output"))

    assert calls == [
        (
            pdf_path,
            cli.settings.parse_api_base_url,
            tmp_path / "custom-output",
        )
    ]
    assert messages[-1] == f"✓ Parse hoàn tất: {project_dir}"


def test_auto_parsing_falls_back_to_native_pipeline(tmp_path, monkeypatch):
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"fake PDF")
    output_dir = tmp_path / "output"

    class FakeResult:
        def save_to_json(self, save_path):
            Path(save_path, "paper_0_res.json").write_text("{}")

        def save_to_markdown(self, save_path):
            Path(save_path, "paper_0_res.md").write_text("")

    class FakePipeline:
        def predict(self, path):
            assert path == str(pdf_path)
            return [FakeResult()]

    monkeypatch.setattr(
        cli,
        "settings",
        type(
            "Settings",
            (),
            {
                "parsing_backend": "auto",
                "parse_api_base_url": "http://127.0.0.1:8082",
                "output_dir": str(output_dir),
            },
        )(),
    )
    monkeypatch.setattr(
        cli,
        "parse_pdf_via_api",
        lambda **kwargs: (_ for _ in ()).throw(ParseAPIError("offline")),
    )
    monkeypatch.setattr(
        cli,
        "_create_paddle_ocr_pipeline",
        lambda *, backend: FakePipeline(),
    )
    monkeypatch.setattr(cli, "_local_paddle_pipeline", None)

    project_dir = cli._parse_via_service(pdf_path)

    assert project_dir == output_dir / "paper"
    assert (project_dir / "paper_0_res.json").is_file()
