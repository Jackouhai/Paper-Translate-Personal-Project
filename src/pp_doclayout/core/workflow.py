"""Reusable translation and export workflow for CLI and web jobs."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from pp_doclayout.core.renderer import (
    build_project_data,
    render_page_blocks,
    translate_page_data,
)
from pp_doclayout.exporters.html import HTMLExporter
from pp_doclayout.exporters.pdf import PDFExporter
from pp_doclayout.types import ProjectData

ProgressCallback = Callable[[int, int], None]
ExportCallback = Callable[[], None]


def export_project(
    project_data: ProjectData,
    project_dir: Path,
    output_suffix: str,
    export_formats: Iterable[str],
) -> list[Path]:
    """Export translated project data in the requested formats."""

    output_paths: list[Path] = []
    for export_format in export_formats:
        if export_format == "html":
            exporter = HTMLExporter()
        elif export_format == "pdf":
            exporter = PDFExporter()
        else:
            raise ValueError(f"Unsupported export format: {export_format}")

        output_path = (
            project_dir / f"{output_suffix}_{project_data['project_name']}.{export_format}"
        )
        exporter.export(project_data, output_path)
        output_paths.append(output_path)

    return output_paths


def translate_and_export_project(
    project_dir: Path,
    translator,
    *,
    output_suffix: str = "translated",
    export_formats: Iterable[str] = ("html", "pdf"),
    on_page_translated: ProgressCallback | None = None,
    on_before_export: ExportCallback | None = None,
) -> list[Path]:
    """Translate parsed pages, render them, and export final artifacts."""

    project_data = build_project_data(project_dir)
    translated_pages = []
    total_pages = len(project_data["pages"])
    imgs_dir = project_dir / "imgs"

    for completed_pages, page in enumerate(project_data["pages"], start=1):
        translated_page = translate_page_data(page, translator)
        translated_page["html_content"] = render_page_blocks(
            translated_page,
            imgs_dir,
            project_dir,
        )
        translated_pages.append(translated_page)

        if on_page_translated is not None:
            on_page_translated(completed_pages, total_pages)

    project_data["pages"] = translated_pages
    if on_before_export is not None:
        on_before_export()
    return export_project(
        project_data,
        project_dir,
        output_suffix,
        export_formats,
    )
