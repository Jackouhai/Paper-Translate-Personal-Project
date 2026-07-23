from pathlib import Path
import shutil

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

@app.post("/pipeline/translate/{project_name}")
def translate_parsed_project(project_name: str):
    try:
        html_path = translate_project(project_name)
        project_dir = PIPELINE_OUTPUT_DIR / project_name

        markdown_files = sorted(project_dir.glob("*.md"))
        json_files = sorted(project_dir.glob("*_res.json"))

        return {
            "status": "completed",
            "project_name": project_name,
            "html_file": html_path.name,
            "html_url": build_pipeline_output_url(html_path),
            "markdown_url": (
                build_pipeline_output_url(markdown_files[0])
                if markdown_files
                else None
            ),
            "json_url": (
                build_pipeline_output_url(json_files[0])
                if json_files
                else None
            ),
            "pdf_url": None,
        }

    except PipelineError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc