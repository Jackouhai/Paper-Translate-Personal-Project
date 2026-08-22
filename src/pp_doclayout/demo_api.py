"""HTTP API for the browser-based translation demo."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from threading import Lock, Thread
from typing import Literal
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pypdf import PdfReader, PdfWriter

from pp_doclayout.config import settings
from pp_doclayout.core.parse_api_client import parse_pdf_via_api
from pp_doclayout.core.workflow import ProgressCallback, translate_and_export_project
from pp_doclayout.translators import get_gemma
from pp_doclayout.utils.server_health import check_server_health

JobStatus = Literal["queued", "parsing", "translating", "rendering", "completed", "failed"]
JobMode = Literal["full", "page"]
ParseOperation = Callable[[Path, Path], Path]
TranslateOperation = Callable[
    [Path, Path, ProgressCallback, Callable[[], None], bool],
    Path,
]


@dataclass
class DemoJob:
    job_id: str
    filename: str
    mode: JobMode
    selected_page: int | None
    translate_titles: bool
    total_pages: int
    job_dir: Path
    source_path: Path
    work_path: Path
    project_dir: Path
    translated_pdf_path: Path
    status: JobStatus = "queued"
    completed_pages: int = 0
    error: str | None = None


class DemoJobResponse(BaseModel):
    job_id: str
    filename: str
    mode: JobMode
    selected_page: int | None
    translate_titles: bool
    total_pages: int
    status: JobStatus
    completed_pages: int
    error: str | None
    source_pdf_available: bool
    translated_pdf_available: bool


def _default_parse_operation(pdf_path: Path, project_dir: Path) -> Path:
    return parse_pdf_via_api(
        pdf_path,
        settings.parse_api_base_url,
        output_dir=project_dir,
    )


def _default_translate_operation(
    project_dir: Path,
    translated_pdf_path: Path,
    progress_callback: ProgressCallback,
    on_before_export: Callable[[], None],
    translate_titles: bool,
) -> Path:
    health = check_server_health("TranslateGemma", settings.vllm_base_url)
    if not health.available:
        raise RuntimeError(f"TranslateGemma server is not ready: {health.message}")

    output_paths = translate_and_export_project(
        project_dir,
        get_gemma(),
        export_formats=("html", "pdf"),
        translate_titles=translate_titles,
        on_page_translated=progress_callback,
        on_before_export=on_before_export,
    )
    generated_pdf = next(path for path in output_paths if path.suffix == ".pdf")
    if generated_pdf != translated_pdf_path:
        generated_pdf.replace(translated_pdf_path)
    return translated_pdf_path


async def _save_pdf_upload(upload: UploadFile, destination: Path, max_upload_bytes: int) -> None:
    """Save a PDF with a size cap before its content is inspected."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    first_chunk = b""
    with destination.open("wb") as output_file:
        while chunk := await upload.read(1024 * 1024):
            if not first_chunk:
                first_chunk = chunk
            written += len(chunk)
            if written > max_upload_bytes:
                destination.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="PDF exceeds the upload size limit.",
                )
            output_file.write(chunk)

    if not first_chunk.startswith(b"%PDF"):
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid PDF.")


def _create_selected_page(source_path: Path, destination: Path, page_number: int) -> None:
    reader = PdfReader(str(source_path))
    writer = PdfWriter()
    writer.add_page(reader.pages[page_number - 1])
    with destination.open("wb") as output_file:
        writer.write(output_file)


async def _stream_pdf(path: Path):
    """Yield PDF content in bounded chunks for browser viewers and downloads."""

    with path.open("rb") as input_file:
        while chunk := input_file.read(1024 * 1024):
            yield chunk


def _pdf_response(path: Path, filename: str) -> StreamingResponse:
    ascii_filename = "".join(
        character if 32 <= ord(character) < 127 and character not in {'"', "\\"} else "_"
        for character in filename
    )
    return StreamingResponse(
        _stream_pdf(path),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"inline; filename=\"{ascii_filename or 'document.pdf'}\"; "
                f"filename*=UTF-8''{quote(filename, safe='')}"
            )
        },
    )


def create_app(
    *,
    output_root: Path | None = None,
    parse_operation: ParseOperation = _default_parse_operation,
    translate_operation: TranslateOperation = _default_translate_operation,
    max_upload_bytes: int | None = None,
    max_queued_jobs: int | None = None,
    translation_workers: int | None = None,
) -> FastAPI:
    """Create the staged queue API used by the council demo frontend."""

    root = (output_root or Path(settings.output_dir)) / "web-jobs"
    upload_limit = max_upload_bytes or settings.web_demo_max_upload_bytes
    queue_limit = (
        max_queued_jobs
        if max_queued_jobs is not None
        else settings.web_demo_max_queued_jobs
    )
    translation_worker_count = (
        translation_workers
        if translation_workers is not None
        else settings.web_demo_translation_workers
    )
    if translation_worker_count < 1:
        raise ValueError("translation_workers must be at least 1")
    jobs: dict[str, DemoJob] = {}
    jobs_lock = Lock()
    parse_queue: Queue[str | None] = Queue()
    translation_queue: Queue[str | None] = Queue()
    pending_submissions = 0

    def response_for(job: DemoJob) -> DemoJobResponse:
        return DemoJobResponse(
            job_id=job.job_id,
            filename=job.filename,
            mode=job.mode,
            selected_page=job.selected_page,
            translate_titles=job.translate_titles,
            total_pages=job.total_pages,
            status=job.status,
            completed_pages=job.completed_pages,
            error=job.error,
            source_pdf_available=job.source_path.is_file(),
            translated_pdf_available=(
                job.status == "completed" and job.translated_pdf_path.is_file()
            ),
        )

    def update_job(job_id: str, **changes: object) -> None:
        with jobs_lock:
            job = jobs[job_id]
            for field, value in changes.items():
                setattr(job, field, value)

    def process_parse_queue() -> None:
        while True:
            job_id = parse_queue.get()
            if job_id is None:
                return

            with jobs_lock:
                job = jobs[job_id]

            try:
                update_job(job_id, status="parsing")
                parsed_project_dir = parse_operation(job.work_path, job.project_dir)
                update_job(job_id, project_dir=parsed_project_dir)
            except Exception as error:  # Keep one failed demo job from killing the worker.
                update_job(job_id, status="failed", error=str(error))
            else:
                update_job(job_id, status="queued")
                translation_queue.put(job_id)
            finally:
                parse_queue.task_done()

    def process_translation_queue() -> None:
        while True:
            job_id = translation_queue.get()
            if job_id is None:
                return

            with jobs_lock:
                job = jobs[job_id]

            try:
                update_job(job_id, status="translating")

                def report_progress(completed: int, total: int) -> None:
                    update_job(job_id, completed_pages=min(completed, total))

                translate_operation(
                    job.project_dir,
                    job.translated_pdf_path,
                    report_progress,
                    lambda: update_job(job_id, status="rendering"),
                    job.translate_titles,
                )
            except Exception as error:  # Keep one failed demo job from killing the worker.
                update_job(job_id, status="failed", error=str(error))
            else:
                update_job(job_id, status="completed")
            finally:
                translation_queue.task_done()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        root.mkdir(parents=True, exist_ok=True)
        parse_worker = Thread(
            target=process_parse_queue,
            name="demo-parse-worker",
            daemon=True,
        )
        translation_pool = [
            Thread(
                target=process_translation_queue,
                name=f"demo-translation-worker-{index + 1}",
                daemon=True,
            )
            for index in range(translation_worker_count)
        ]
        parse_worker.start()
        for worker in translation_pool:
            worker.start()
        app.state.demo_parse_worker = parse_worker
        app.state.demo_translation_workers = translation_pool
        try:
            yield
        finally:
            parse_queue.put(None)
            for _ in translation_pool:
                translation_queue.put(None)
            parse_worker.join(timeout=5)
            for worker in translation_pool:
                worker.join(timeout=5)

    app = FastAPI(title="PP-DocLayout Demo API", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/jobs", response_model=DemoJobResponse, status_code=status.HTTP_202_ACCEPTED)
    async def submit_job(
        file: UploadFile = File(...),
        mode: str = Form("full"),
        page_number: int | None = Form(None),
        translate_titles: bool = Form(False),
    ) -> DemoJobResponse:
        filename = Path(file.filename or "document.pdf").name
        if Path(filename).suffix.lower() != ".pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        if mode not in {"full", "page"}:
            raise HTTPException(status_code=400, detail="Mode must be 'full' or 'page'.")

        nonlocal pending_submissions
        with jobs_lock:
            queued_jobs = sum(job.status == "queued" for job in jobs.values())
            if queued_jobs + pending_submissions >= queue_limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="The translation system is busy. Please try again shortly.",
                )
            pending_submissions += 1

        job_id = uuid4().hex
        job_dir = root / job_id
        source_path = job_dir / "source.pdf"
        try:
            try:
                await _save_pdf_upload(file, source_path, upload_limit)
                reader = PdfReader(str(source_path))
                total_pages = len(reader.pages)
            except HTTPException:
                raise
            except Exception as error:
                source_path.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="The uploaded PDF cannot be read.") from error
            finally:
                await file.close()

            selected_page = page_number if mode == "page" else None
            if mode == "page" and (selected_page is None or not 1 <= selected_page <= total_pages):
                source_path.unlink(missing_ok=True)
                raise HTTPException(status_code=400, detail="Selected page is outside the PDF page range.")

            work_path = source_path
            if selected_page is not None:
                work_path = job_dir / "selected-page.pdf"
                _create_selected_page(source_path, work_path, selected_page)

            job = DemoJob(
                job_id=job_id,
                filename=filename,
                mode=mode,
                selected_page=selected_page,
                translate_titles=translate_titles,
                total_pages=total_pages,
                job_dir=job_dir,
                source_path=source_path,
                work_path=work_path,
                project_dir=job_dir / "project",
                translated_pdf_path=job_dir / "translated.pdf",
            )
            with jobs_lock:
                jobs[job_id] = job
            parse_queue.put(job_id)
            return response_for(job)
        finally:
            with jobs_lock:
                pending_submissions -= 1

    @app.get("/jobs/{job_id}", response_model=DemoJobResponse)
    async def get_job(job_id: str) -> DemoJobResponse:
        with jobs_lock:
            job = jobs.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Translation job not found.")
            return response_for(job)

    @app.get("/jobs/{job_id}/source.pdf")
    async def get_source_pdf(job_id: str) -> StreamingResponse:
        with jobs_lock:
            job = jobs.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Translation job not found.")
            source_path = job.source_path
            filename = job.filename
        return _pdf_response(source_path, filename)

    @app.get("/jobs/{job_id}/translated.pdf")
    async def get_translated_pdf(job_id: str) -> StreamingResponse:
        with jobs_lock:
            job = jobs.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Translation job not found.")
            translated_path = job.translated_pdf_path
            filename = f"translated-{Path(job.filename).stem}.pdf"
            completed = job.status == "completed"
        if not completed or not translated_path.is_file():
            raise HTTPException(status_code=409, detail="Translated PDF is not ready yet.")
        return _pdf_response(translated_path, filename)

    return app


app = create_app()
