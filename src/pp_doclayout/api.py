"""Long-lived HTTP API for queued PDF parsing."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Literal
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from pp_doclayout.config import settings
from pp_doclayout.core.parse_worker import ParseWorker
from pp_doclayout.utils.server_health import check_server_health

ParseOperation = Callable[[Any, Path, Path], Path]
PipelineFactory = Callable[[], Any]


@dataclass
class ParseJob:
    """The in-memory state of one queued PDF parse request."""

    job_id: str
    filename: str
    project_dir: Path
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    error: str | None = None


class ParseJobResponse(BaseModel):
    """Public representation of a parse job."""

    job_id: str
    filename: str
    project_dir: str
    status: Literal["queued", "running", "completed", "failed"]
    error: str | None = None


def _create_default_pipeline() -> Any:
    """Verify the remote OCR server before loading local layout models."""

    # Keep the PaddleOCRVL construction in one place with the CLI configuration.
    from pp_doclayout.cli import _create_paddle_ocr_pipeline

    backend = settings.paddle_ocr_backend
    if backend == "vllm-server":
        health = check_server_health(
            name="PaddleOCR-VL",
            base_url=settings.paddle_ocr_server_url,
        )
        if not health.available:
            if settings.parsing_backend.lower() != "auto":
                raise RuntimeError(
                    f"PaddleOCR-VL server is not ready: {health.url}. "
                    f"Reason: {health.message}"
                )
            backend = "native"

    return _create_paddle_ocr_pipeline(backend=backend)


def _parse_pdf(pipeline: Any, pdf_path: Path, project_dir: Path) -> Path:
    """Run PaddleOCRVL and save the parsed artifacts for one PDF."""

    project_dir.mkdir(parents=True, exist_ok=True)
    output = pipeline.predict(str(pdf_path))

    for result in output:
        result.save_to_json(save_path=str(project_dir))
        result.save_to_markdown(save_path=str(project_dir))

    return project_dir


async def _save_upload(upload: UploadFile, destination: Path) -> None:
    """Persist an upload in chunks so a large PDF is not held fully in memory."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output_file:
        while chunk := await upload.read(1024 * 1024):
            output_file.write(chunk)


def create_app(
    *,
    pipeline_factory: PipelineFactory = _create_default_pipeline,
    parse_operation: ParseOperation = _parse_pdf,
    output_root: Path | None = None,
) -> FastAPI:
    """Create an API whose single worker owns one PaddleOCRVL pipeline."""

    root = output_root or Path(settings.output_dir)
    jobs: dict[str, ParseJob] = {}
    jobs_lock = Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        worker = ParseWorker(pipeline_factory)
        try:
            worker.start()
        except Exception:
            worker.close()
            raise

        app.state.parse_worker = worker
        try:
            yield
        finally:
            worker.close()

    app = FastAPI(
        title="PP-DocLayout Parse API",
        version="0.1.0",
        lifespan=lifespan,
    )

    def response_for(job: ParseJob) -> ParseJobResponse:
        return ParseJobResponse(
            job_id=job.job_id,
            filename=job.filename,
            project_dir=str(job.project_dir),
            status=job.status,
            error=job.error,
        )

    def update_job(job_id: str, **changes: Any) -> None:
        with jobs_lock:
            job = jobs[job_id]
            for attribute, value in changes.items():
                setattr(job, attribute, value)

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Report that the API and its long-lived parse worker are ready."""

        return {"status": "ready"}

    @app.post(
        "/parse",
        response_model=ParseJobResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def submit_parse(
        file: UploadFile = File(...),
        output_dir: str | None = Form(None),
    ) -> ParseJobResponse:
        """Queue one PDF; requests are processed in first-in, first-out order."""

        filename = Path(file.filename or "document.pdf").name
        if Path(filename).suffix.lower() != ".pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are supported.")

        job_id = uuid4().hex
        base_output = Path(output_dir).expanduser() if output_dir else root
        pdf_path = base_output / "_uploads" / f"{job_id}-{filename}"
        project_dir = base_output / f"{Path(filename).stem}-{job_id[:8]}"

        try:
            await _save_upload(file, pdf_path)
        finally:
            await file.close()

        job = ParseJob(
            job_id=job_id,
            filename=filename,
            project_dir=project_dir,
        )
        with jobs_lock:
            jobs[job_id] = job

        def run_parse(pipeline: Any) -> Path:
            update_job(job_id, status="running")
            return parse_operation(pipeline, pdf_path, project_dir)

        future = app.state.parse_worker.submit(run_parse)

        def finish_parse(completed_future) -> None:
            try:
                completed_future.result()
            except Exception as error:
                update_job(job_id, status="failed", error=str(error))
            else:
                update_job(job_id, status="completed")

        future.add_done_callback(finish_parse)
        return response_for(job)

    @app.get("/jobs/{job_id}", response_model=ParseJobResponse)
    async def get_job(job_id: str) -> ParseJobResponse:
        """Read the current state of a queued, running, or completed parse job."""

        with jobs_lock:
            job = jobs.get(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail="Parse job not found.")
            return response_for(job)

    return app


app = create_app()
