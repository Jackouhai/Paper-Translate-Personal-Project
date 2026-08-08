"""Tests for the long-lived queued parse API."""

import asyncio
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from pp_doclayout.api import create_app


async def _wait_for_job(client: AsyncClient, job_id: str) -> dict:
    """Poll a fast fake job without introducing a production retry policy."""

    for _ in range(100):
        response = await client.get(f"/jobs/{job_id}")
        response.raise_for_status()
        job = response.json()
        if job["status"] in {"completed", "failed"}:
            return job
        await asyncio.sleep(0.01)

    raise AssertionError(f"Job {job_id} did not finish")


def test_parse_api_reuses_one_pipeline_and_queues_pdf_jobs(tmp_path: Path):
    """Two uploads share one long-lived pipeline and run in FIFO order."""

    events = []

    class FakePipeline:
        def close(self):
            events.append("close")

    def factory():
        events.append("factory")
        return FakePipeline()

    def parse_operation(pipeline, pdf_path: Path, project_dir: Path) -> Path:
        events.append(pdf_path.name.split("-", 1)[1])
        project_dir.mkdir(parents=True)
        return project_dir

    app = create_app(
        pipeline_factory=factory,
        parse_operation=parse_operation,
        output_root=tmp_path,
    )
    custom_output = tmp_path / "custom-output"

    async def submit_jobs() -> tuple[dict, dict]:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                first_response = await client.post(
                    "/parse",
                    files={"file": ("first.pdf", b"first", "application/pdf")},
                    data={"output_dir": str(custom_output)},
                )
                second_response = await client.post(
                    "/parse",
                    files={"file": ("second.pdf", b"second", "application/pdf")},
                )

                assert first_response.status_code == 202
                assert second_response.status_code == 202

                first = await _wait_for_job(client, first_response.json()["job_id"])
                second = await _wait_for_job(client, second_response.json()["job_id"])
                return first, second

    first, second = asyncio.run(submit_jobs())

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert Path(first["project_dir"]).is_dir()
    assert Path(second["project_dir"]).is_dir()
    assert Path(first["project_dir"]).parent == custom_output

    assert events == ["factory", "first.pdf", "second.pdf", "close"]


def test_parse_api_rejects_non_pdf_uploads(tmp_path: Path):
    """The parse endpoint rejects files that do not have a PDF extension."""

    app = create_app(
        pipeline_factory=lambda: object(),
        output_root=tmp_path,
    )

    async def submit_non_pdf():
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.post(
                    "/parse",
                    files={"file": ("notes.txt", b"not a PDF", "text/plain")},
                )

    response = asyncio.run(submit_non_pdf())

    assert response.status_code == 400
    assert response.json() == {"detail": "Only PDF files are supported."}
