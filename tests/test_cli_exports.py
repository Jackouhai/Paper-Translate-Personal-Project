from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from pp_doclayout import cli


def test_parse_export_formats_normalizes_and_deduplicates():
    assert cli._parse_export_formats(" PDF, html, pdf ") == ["pdf", "html"]


def test_parse_export_formats_rejects_unknown_format():
    with pytest.raises(typer.BadParameter, match="Unsupported export format"):
        cli._parse_export_formats("html,docx")


def test_export_project_creates_html_then_pdf(tmp_path):
    project_data = {
        "project_name": "paper",
        "pages": [],
    }
    html_exporter = MagicMock()
    pdf_exporter = MagicMock()

    with patch(
        "pp_doclayout.exporters.html.HTMLExporter",
        return_value=html_exporter,
    ), patch(
        "pp_doclayout.exporters.pdf.PDFExporter",
        return_value=pdf_exporter,
    ):
        output_paths = cli._export_project(
            project_data,
            tmp_path,
            "translated",
            "html,pdf",
        )

    html_path = tmp_path / "translated_paper.html"
    pdf_path = tmp_path / "translated_paper.pdf"
    assert output_paths == [html_path, pdf_path]
    html_exporter.export.assert_called_once_with(project_data, html_path)
    pdf_exporter.export.assert_called_once_with(project_data, pdf_path)
