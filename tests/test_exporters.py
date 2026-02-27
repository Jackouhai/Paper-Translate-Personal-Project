"""Tests for exporters module."""

from pathlib import Path

from pp_doclayout.exporters import BaseExporter, HTMLExporter


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
