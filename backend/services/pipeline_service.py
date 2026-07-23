from __future__ import annotations

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
PIPELINE_OUTPUT_DIR = PROJECT_ROOT / "output"


class PipelineError(RuntimeError):
    """Raised when the pp_doclayout pipeline command fails."""


def run_pipeline_command(
    command: list[str],
    timeout_seconds: int = 1800,
) -> subprocess.CompletedProcess[str]:
    full_command = [
        str(PROJECT_PYTHON),
        "-m",
        "pp_doclayout.cli",
        *command,
    ]

    try:
        result = subprocess.run(
            full_command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise PipelineError(
            f"Pipeline timed out after {timeout_seconds} seconds."
        ) from exc

    if result.returncode != 0:
        error_message = result.stderr.strip() or result.stdout.strip()
        raise PipelineError(error_message or "Pipeline command failed.")

    return result


def parse_pdf(pdf_path: Path) -> Path:
    result = run_pipeline_command(
        ["parse", str(pdf_path.resolve())],
        timeout_seconds=1800,
    )

    print(result.stdout)

    project_name = pdf_path.stem
    project_dir = PIPELINE_OUTPUT_DIR / project_name

    if not project_dir.exists():
        raise PipelineError(
            f"Parse completed but output directory was not found: {project_dir}"
        )

    json_files = list(project_dir.glob("*_res.json"))

    if not json_files:
        raise PipelineError("Parse completed but no OCR JSON file was created.")

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

    result = run_pipeline_command(
        ["translate", str(project_dir)],
        timeout_seconds=3600,
    )

    if result.stdout:
        print(result.stdout)

    if result.stderr:
        print(result.stderr)

    expected_html = project_dir / f"translated_{clean_name}.html"

    if expected_html.exists():
        return expected_html

    html_files = sorted(project_dir.glob("translated_*.html"))

    if not html_files:
        raise PipelineError(
            "Translation completed but no translated HTML file was created."
        )

    return html_files[0]