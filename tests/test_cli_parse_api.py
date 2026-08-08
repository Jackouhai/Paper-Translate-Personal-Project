"""Tests for CLI commands that submit parse jobs to the Parse API."""

from pathlib import Path

from pp_doclayout import cli


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
