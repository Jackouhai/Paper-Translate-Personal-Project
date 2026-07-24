from pathlib import Path
import shutil
import requests
import sys

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from services.pipeline_service import (
    PipelineError,
    parse_pdf,
    translate_project,
)


app = FastAPI(title="PaperTranslate Backend")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# Project paths
# =========================

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

if getattr(sys, "frozen", False):
    APP_DATA_DIR = (
        Path.home()
        / ".local"
        / "share"
        / "papertranslate"
    )

    UPLOAD_DIR = APP_DATA_DIR / "uploads"
    OUTPUT_DIR = APP_DATA_DIR / "outputs"
    PIPELINE_OUTPUT_DIR = APP_DATA_DIR / "output"
else:
    UPLOAD_DIR = BACKEND_DIR / "uploads"
    OUTPUT_DIR = BACKEND_DIR / "outputs"
    PIPELINE_OUTPUT_DIR = PROJECT_ROOT / "output"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PIPELINE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# Static file routes
# =========================

app.mount(
    "/uploads",
    StaticFiles(directory=str(UPLOAD_DIR)),
    name="uploads",
)

app.mount(
    "/outputs",
    StaticFiles(directory=str(OUTPUT_DIR)),
    name="outputs",
)

app.mount(
    "/pipeline-output",
    StaticFiles(directory=str(PIPELINE_OUTPUT_DIR)),
    name="pipeline-output",
)


# =========================
# Basic endpoint
# =========================

@app.get("/")
def root():
    return {
        "message": "Backend running",
        "status": "success",
    }


# =========================
# Helpers
# =========================

def safe_filename(filename: str | None) -> str:
    """
    Validate and normalize an uploaded PDF filename.
    """

    if not filename:
        raise HTTPException(
            status_code=400,
            detail="Missing filename.",
        )

    clean_name = Path(filename).name

    if not clean_name:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename.",
        )

    if Path(clean_name).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted.",
        )

    return clean_name


def build_pipeline_output_url(path: Path) -> str:
    """
    Convert a local pipeline output path into a URL served by FastAPI.
    """

    try:
        relative_path = path.resolve().relative_to(
            PIPELINE_OUTPUT_DIR.resolve()
        )
    except ValueError as exc:
        raise PipelineError(
            f"Output file is outside the pipeline output directory: {path}"
        ) from exc

    return (
        "http://127.0.0.1:8002/"
        f"pipeline-output/{relative_path.as_posix()}"
    )


# =========================
# Stage 1: Parse PDF
# =========================

@app.post("/pipeline/parse")
async def parse_uploaded_pdf(
    file: UploadFile = File(...),
):
    """
    Upload a PDF and run the repository's real parse pipeline.

    Pipeline:
    PDF -> pp_doclayout parse -> PaddleOCR-VL -> JSON/Markdown
    """

    filename = safe_filename(file.filename)
    save_path = UPLOAD_DIR / filename

    try:
        with save_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        project_dir = parse_pdf(save_path)

        json_files = [
            path.name
            for path in sorted(project_dir.glob("*_res.json"))
        ]

        markdown_files = [
            path.name
            for path in sorted(project_dir.glob("*.md"))
        ]

        return {
            "status": "parsed",
            "filename": filename,
            "project_name": save_path.stem,
            "project_dir": str(project_dir),
            "json_files": json_files,
            "markdown_files": markdown_files,
            "pdf_url": (
                f"http://127.0.0.1:8002/uploads/{filename}"
            ),
        }

    except PipelineError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not save uploaded PDF: {exc}",
        ) from exc

    finally:
        await file.close()


# =========================
# Stage 2: Translate project
# =========================

def merge_markdown_files(
    project_dir: Path,
    project_name: str,
) -> Path | None:
    markdown_files = sorted(
        project_dir.glob("*.md"),
        key=lambda path: path.name,
    )

    if not markdown_files:
        return None

    merged_path = project_dir / f"{project_name}.md"
    merged_sections = []

    for page_number, markdown_path in enumerate(
        markdown_files,
        start=1,
    ):
        content = markdown_path.read_text(
            encoding="utf-8",
        ).strip()

        merged_sections.append(
            f"<!-- Page {page_number} -->\n\n{content}"
        )

    merged_path.write_text(
        "\n\n---\n\n".join(merged_sections) + "\n",
        encoding="utf-8",
    )

    return merged_path

@app.post("/pipeline/translate/{project_name}")
def translate_parsed_project(project_name: str):
    try:
        html_path = translate_project(project_name)
        project_dir = PIPELINE_OUTPUT_DIR / project_name

        json_files = sorted(
            project_dir.glob("*_res.json"),
        )

        merged_markdown_path = merge_markdown_files(
            project_dir,
            project_name,
        )

        json_urls = [
            build_pipeline_output_url(path)
            for path in json_files
        ]

        return {
            "status": "completed",
            "project_name": project_name,
            "page_count": len(json_files),
            "html_file": html_path.name,
            "html_url": build_pipeline_output_url(html_path),
            "markdown_url": (
                build_pipeline_output_url(
                    merged_markdown_path,
                )
                if merged_markdown_path
                else None
            ),
            "json_urls": json_urls,
            "pdf_url": None,
        }

    except PipelineError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc




@app.get("/pipeline/model-status")
def get_model_status():
    ocr_ready = False
    translator_ready = False

    try:
        response = requests.get(
            "http://127.0.0.1:8000/v1/models",
            timeout=2,
        )
        ocr_ready = response.ok
    except requests.RequestException:
        pass

    try:
        response = requests.get(
            "http://127.0.0.1:8001/v1/models",
            timeout=2,
        )
        translator_ready = response.ok
    except requests.RequestException:
        pass

    return {
        "ocr_ready": ocr_ready,
        "translator_ready": translator_ready,
    }