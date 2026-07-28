from __future__ import annotations

import sys
from pathlib import Path

from pp_doclayout.cli import parse as run_parse
from pp_doclayout.cli import translate as run_translate


if getattr(sys, "frozen", False):
    APP_DATA_DIR = (
        Path.home()
        / ".local"
        / "share"
        / "papertranslate"
    )
    PIPELINE_OUTPUT_DIR = APP_DATA_DIR / "output"
else:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    PIPELINE_OUTPUT_DIR = PROJECT_ROOT / "output"

PIPELINE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class PipelineError(RuntimeError):
    """Raised when the pp_doclayout pipeline fails."""


def parse_pdf(pdf_path: Path) -> Path:
    pdf_path = pdf_path.resolve()

    try:
        run_parse(
            pdf_path=str(pdf_path),
            output_dir=str(PIPELINE_OUTPUT_DIR),
        )
    except BaseException as exc:
        message = str(exc).strip()

        if not message:
            message = f"{type(exc).__name__}: {exc!r}"

        raise PipelineError(
            f"Parse pipeline failed: {message}"
        ) from exc

    project_name = pdf_path.stem
    project_dir = PIPELINE_OUTPUT_DIR / project_name

    if not project_dir.exists():
        raise PipelineError(
            f"Parse completed but output directory was not found: {project_dir}"
        )

    json_files = sorted(project_dir.glob("*_res.json"))

    if not json_files:
        raise PipelineError(
            "Parse completed but no OCR JSON file was created."
        )

    return project_dir


def validate_project_name(project_name: str) -> str:
    clean_name = Path(project_name).name

    if clean_name != project_name:
        raise PipelineError("Invalid project name.")

    if not clean_name:
        raise PipelineError("Project name cannot be empty.")

    return clean_name


def translate_project(project_name: str) -> Path:
    clean_name = validate_project_name(project_name)
    project_dir = PIPELINE_OUTPUT_DIR / clean_name

    if not project_dir.exists():
        raise PipelineError(
            f"Parsed project directory was not found: {project_dir}"
        )

    json_files = sorted(project_dir.glob("*_res.json"))

    if not json_files:
        raise PipelineError(
            f"No parsed OCR JSON files were found in: {project_dir}"
        )

    try:
        run_translate(
            project_dir=str(project_dir),
            output_suffix="translated",
            export_format="html",
        )
    except Exception as exc:
        raise PipelineError(
            f"Translation pipeline failed: {exc}"
        ) from exc

    expected_html = project_dir / f"translated_{clean_name}.html"

    if expected_html.exists():
        return expected_html

    html_files = sorted(project_dir.glob("translated_*.html"))

    if not html_files:
        raise PipelineError(
            "Translation completed but no translated HTML file was created."
        )

    return html_files[0]
