"""Tests for the browser demo job API without model dependencies."""

import asyncio
from pathlib import Path
from threading import Event, Lock

from httpx import ASGITransport, AsyncClient
from pypdf import PdfReader, PdfWriter

from pp_doclayout.demo_api import create_app


def _write_pdf(path: Path, pages: int = 1) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as output_file:
        writer.write(output_file)


async def _wait_for_completion(client: AsyncClient, job_id: str) -> dict:
    for _ in range(100):
        response = await client.get(f"/jobs/{job_id}")
        response.raise_for_status()
        job = response.json()
        if job["status"] in {"completed", "failed"}:
            return job
        await asyncio.sleep(0.01)
    raise AssertionError("Demo job did not finish")


async def _wait_for_status(client: AsyncClient, job_id: str, expected: str) -> None:
    for _ in range(100):
        response = await client.get(f"/jobs/{job_id}")
        response.raise_for_status()
        if response.json()["status"] == expected:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"Demo job did not enter {expected!r}")


def test_demo_api_translates_a_selected_page_and_serves_artifacts(tmp_path: Path):
    source_pdf = tmp_path / "source.pdf"
    _write_pdf(source_pdf, pages=2)
    parsed_page_counts: list[int] = []
    translated_project_dirs: list[Path] = []

    def parse_operation(pdf_path: Path, project_dir: Path) -> Path:
        parsed_page_counts.append(len(PdfReader(str(pdf_path)).pages))
        parsed_project_dir = project_dir / "parser-output"
        parsed_project_dir.mkdir(parents=True)
        return parsed_project_dir

    def translate_operation(project_dir, translated_pdf_path, progress, before_export):
        translated_project_dirs.append(project_dir)
        progress(1, 1)
        before_export()
        _write_pdf(translated_pdf_path)
        return translated_pdf_path

    app = create_app(
        output_root=tmp_path / "output",
        parse_operation=parse_operation,
        translate_operation=translate_operation,
    )

    async def submit_and_check() -> None:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                with source_pdf.open("rb") as upload:
                    response = await client.post(
                        "/jobs",
                        files={"file": ("bài báo.pdf", upload, "application/pdf")},
                        data={"mode": "page", "page_number": "2"},
                    )
                assert response.status_code == 202
                job_id = response.json()["job_id"]
                job = await _wait_for_completion(client, job_id)
                assert job["status"] == "completed"
                assert job["completed_pages"] == 1
                assert job["translated_pdf_available"] is True

                source_response = await client.get(f"/jobs/{job_id}/source.pdf")
                translated_response = await client.get(f"/jobs/{job_id}/translated.pdf")
                assert source_response.status_code == 200
                assert translated_response.status_code == 200
                assert "filename*=UTF-8''" in source_response.headers["content-disposition"]
                assert "filename*=UTF-8''" in translated_response.headers["content-disposition"]

    asyncio.run(submit_and_check())
    assert parsed_page_counts == [1]
    assert translated_project_dirs[0].name == "parser-output"


def test_demo_api_rejects_invalid_page_and_busy_queue(tmp_path: Path):
    source_pdf = tmp_path / "source.pdf"
    _write_pdf(source_pdf)
    release_parse = Event()

    def parse_operation(pdf_path: Path, project_dir: Path) -> Path:
        release_parse.wait(timeout=2)
        project_dir.mkdir(parents=True)
        return project_dir

    def translate_operation(project_dir, translated_pdf_path, progress, before_export):
        before_export()
        _write_pdf(translated_pdf_path)
        return translated_pdf_path

    app = create_app(
        output_root=tmp_path / "output",
        parse_operation=parse_operation,
        translate_operation=translate_operation,
    )

    async def submit_cases() -> None:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                with source_pdf.open("rb") as upload:
                    invalid_page = await client.post(
                        "/jobs",
                        files={"file": ("paper.pdf", upload, "application/pdf")},
                        data={"mode": "page", "page_number": "2"},
                    )
                assert invalid_page.status_code == 400

                with source_pdf.open("rb") as first:
                    first_job = await client.post(
                        "/jobs",
                        files={"file": ("paper.pdf", first, "application/pdf")},
                    )
                assert first_job.status_code == 202
                await _wait_for_status(client, first_job.json()["job_id"], "parsing")

                # The worker is busy with the first job, so one waiting job is allowed.
                with source_pdf.open("rb") as second:
                    second_job = await client.post(
                        "/jobs",
                        files={"file": ("paper.pdf", second, "application/pdf")},
                    )
                assert second_job.status_code == 202

                with source_pdf.open("rb") as third:
                    busy = await client.post(
                        "/jobs",
                        files={"file": ("paper.pdf", third, "application/pdf")},
                    )
                assert busy.status_code == 429
                release_parse.set()

    asyncio.run(submit_cases())


def test_demo_api_serializes_parse_and_runs_two_translations(tmp_path: Path):
    source_pdf = tmp_path / "source.pdf"
    _write_pdf(source_pdf)
    counters_lock = Lock()
    parse_active = 0
    max_parse_active = 0
    translation_active = 0
    max_translation_active = 0
    two_translations_started = Event()
    release_translations = Event()

    def parse_operation(pdf_path: Path, project_dir: Path) -> Path:
        nonlocal parse_active, max_parse_active
        with counters_lock:
            parse_active += 1
            max_parse_active = max(max_parse_active, parse_active)
        project_dir.mkdir(parents=True)
        with counters_lock:
            parse_active -= 1
        return project_dir

    def translate_operation(project_dir, translated_pdf_path, progress, before_export):
        nonlocal translation_active, max_translation_active
        with counters_lock:
            translation_active += 1
            max_translation_active = max(max_translation_active, translation_active)
            if translation_active == 2:
                two_translations_started.set()
        release_translations.wait(timeout=2)
        progress(1, 1)
        before_export()
        _write_pdf(translated_pdf_path)
        with counters_lock:
            translation_active -= 1
        return translated_pdf_path

    app = create_app(
        output_root=tmp_path / "output",
        parse_operation=parse_operation,
        translate_operation=translate_operation,
        max_queued_jobs=2,
        translation_workers=2,
    )

    async def submit_and_check() -> None:
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                job_ids = []
                for _ in range(2):
                    with source_pdf.open("rb") as upload:
                        response = await client.post(
                            "/jobs",
                            files={"file": ("paper.pdf", upload, "application/pdf")},
                        )
                    assert response.status_code == 202
                    job_ids.append(response.json()["job_id"])

                for _ in range(100):
                    if two_translations_started.is_set():
                        break
                    await asyncio.sleep(0.01)
                else:
                    raise AssertionError("Two translation workers did not start")

                release_translations.set()
                completed = [await _wait_for_completion(client, job_id) for job_id in job_ids]
                assert all(job["status"] == "completed" for job in completed)

    asyncio.run(submit_and_check())
    assert max_parse_active == 1
    assert max_translation_active == 2
