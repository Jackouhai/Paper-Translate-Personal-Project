"""Tests for exporters module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from pp_doclayout.exporters import BaseExporter, HTMLExporter, PDFExporter


def test_base_exporter_is_abstract():
    """Test BaseExporter cannot be instantiated directly."""
    try:
        BaseExporter()
        assert False, "Should have raised TypeError"
    except TypeError:
        pass  # Expected


def test_html_exporter_initialization():
    """Test HTMLExporter initialization."""
    exporter = HTMLExporter()
    assert exporter.templates_dir.exists()
    assert exporter.env is not None


def test_html_exporter_export_method_exists():
    """Test HTMLExporter has export method."""
    exporter = HTMLExporter()
    assert hasattr(exporter, "export")


def test_html_exporter_export_creates_file(tmp_path):
    """Test HTMLExporter.export creates output file."""
    exporter = HTMLExporter()

    project_data = {
        "project_name": "test_project",
        "pages": [
            {
                "page_index": 0,
                "html_content": "<p>Test content</p>",
            }
        ],
    }

    output_path = tmp_path / "test_output.html"
    result = exporter.export(project_data, output_path)

    assert result.exists()
    assert result == output_path

    content = result.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "test_project" in content
    assert "Test content" in content


def test_pdf_exporter_uses_playwright_chromium_and_encoded_file_url(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    output_path = Path("folder with spaces/result #1.pdf")

    project_data = {
        "project_name": "test_project",
        "pages": [
            {
                "page_index": 0,
                "width": 800,
                "height": 1200,
                "html_content": "<p>Test content</p>",
            }
        ],
    }

    with patch(
        "pp_doclayout.exporters.pdf.sync_playwright"
    ) as mock_sync_playwright:
        playwright = MagicMock()
        mock_sync_playwright.return_value.__enter__.return_value = (
            playwright
        )

        browser = playwright.chromium.launch.return_value
        page = browser.new_page.return_value

        exporter = PDFExporter()
        exporter.export(project_data, output_path)

        playwright.chromium.launch.assert_called_once_with(
            headless=True
        )

        expected_html = output_path.with_suffix(".html")
        page.goto.assert_called_once_with(
            expected_html.resolve().as_uri(),
            wait_until="networkidle",
        )


def test_pdf_export_continues_when_auto_fit_times_out(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    output_path = Path("result.pdf")

    project_data = {
        "project_name": "test",
        "pages": [{
            "page_index": 0,
            "width": 800,
            "height": 1200,
            "html_content": "<p>Test</p>",
        }],
    }

    with patch(
        "pp_doclayout.exporters.pdf.sync_playwright"
    ) as mock_sync_playwright:
        playwright = MagicMock()
        mock_sync_playwright.return_value.__enter__.return_value = (
            playwright
        )

        browser = playwright.chromium.launch.return_value
        page = browser.new_page.return_value
        page.wait_for_function.side_effect = [
            PlaywrightTimeoutError("auto-fit timeout"),
            None,
        ]

        PDFExporter().export(project_data, output_path)

        page.pdf.assert_called_once()
        browser.close.assert_called_once()
        assert not output_path.with_suffix(".html").exists()


def test_pdf_exporter_creates_pdf_file(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    output_path = Path("result.pdf")

    project_data = {
        "project_name": "test",
        "pages": [{
            "page_index": 0,
            "width": 800,
            "height": 1200,
            "html_content": "<p>Test</p>",
        }],
    }

    with patch(
        "pp_doclayout.exporters.pdf.sync_playwright"
    ) as mock_sync_playwright:
        playwright = MagicMock()
        mock_sync_playwright.return_value.__enter__.return_value = (
            playwright
        )

        browser = playwright.chromium.launch.return_value
        page = browser.new_page.return_value

        def write_fake_pdf(**kwargs):
            Path(kwargs["path"]).write_bytes(b"%PDF-1.4 test")

        page.pdf.side_effect = write_fake_pdf

        result = PDFExporter().export(project_data, output_path)

        assert result == output_path
        assert output_path.exists()
        assert output_path.read_bytes().startswith(b"%PDF")
        assert not output_path.with_suffix(".html").exists()


def test_html_exporter_preserves_ocr_whitespace(tmp_path):
    exporter = HTMLExporter()

    project_data = {
        "project_name": "test",
        "pages": [{
            "page_index": 0,
            "html_content": (
                '<div class="block text">'
                "First line\n  Second line"
                "</div>"
            ),
        }],
    }

    output_path = tmp_path / "result.html"
    exporter.export(project_data, output_path)

    content = output_path.read_text(encoding="utf-8")

    assert "white-space: pre-wrap;" in content
    assert "First line\n  Second line" in content


def test_html_exporter_uses_bounded_font_size_search(tmp_path):
    exporter = HTMLExporter()

    project_data = {
        "project_name": "test",
        "pages": [{
            "page_index": 0,
            "html_content": '<div class="block text auto-fit">Test</div>',
        }],
    }

    output_path = tmp_path / "result.html"
    exporter.export(project_data, output_path)

    content = output_path.read_text(encoding="utf-8")

    assert "while (lowStep <= highStep)" in content
    assert "const middleStep = Math.floor" in content
    assert "startSize -= 1" not in content
    assert "startSize -= 0.5" not in content
