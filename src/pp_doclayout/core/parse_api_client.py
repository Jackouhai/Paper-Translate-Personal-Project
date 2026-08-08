"""Client for submitting CLI PDF parses to the long-lived Parse API."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import aiohttp


class ParseAPIError(RuntimeError):
    """The Parse API could not accept or finish a PDF job."""


async def _read_json(response: aiohttp.ClientResponse) -> dict[str, Any]:
    try:
        payload = await response.json(content_type=None)
    except aiohttp.ContentTypeError as error:
        raise ParseAPIError("Parse API returned invalid JSON.") from error

    if not isinstance(payload, dict):
        raise ParseAPIError("Parse API returned an unexpected response.")
    return payload


async def _submit_and_wait(
    pdf_path: Path,
    base_url: str,
    output_dir: Path | None,
    poll_interval: float,
) -> Path:
    base_url = base_url.rstrip("/")
    timeout = aiohttp.ClientTimeout(total=30)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"{base_url}/health") as response:
                health = await _read_json(response)
                if response.status != 200 or health.get("status") != "ready":
                    raise ParseAPIError("Parse API is not ready.")

            form = aiohttp.FormData()
            if output_dir is not None:
                form.add_field("output_dir", str(output_dir))

            with pdf_path.open("rb") as pdf_file:
                form.add_field(
                    "file",
                    pdf_file,
                    filename=pdf_path.name,
                    content_type="application/pdf",
                )
                async with session.post(f"{base_url}/parse", data=form) as response:
                    submission = await _read_json(response)

            if response.status != 202:
                detail = submission.get("detail", "Unknown error")
                raise ParseAPIError(f"Parse API rejected the PDF: {detail}")

            job_id = submission.get("job_id")
            if not isinstance(job_id, str):
                raise ParseAPIError("Parse API response did not include a job ID.")

            while True:
                await asyncio.sleep(poll_interval)
                async with session.get(f"{base_url}/jobs/{job_id}") as response:
                    job = await _read_json(response)

                if response.status != 200:
                    detail = job.get("detail", "Unknown error")
                    raise ParseAPIError(f"Cannot read parse job status: {detail}")

                job_status = job.get("status")
                if job_status == "completed":
                    project_dir = job.get("project_dir")
                    if isinstance(project_dir, str):
                        return Path(project_dir)
                    raise ParseAPIError("Completed parse job did not include its output path.")

                if job_status == "failed":
                    raise ParseAPIError(job.get("error") or "Parse job failed.")

                if job_status not in {"queued", "running"}:
                    raise ParseAPIError(f"Unknown parse job status: {job_status!r}")
    except (aiohttp.ClientError, TimeoutError, OSError) as error:
        raise ParseAPIError(
            f"Cannot reach Parse API at {base_url}. Start scripts/start_parse_api.sh."
        ) from error


def parse_pdf_via_api(
    pdf_path: Path,
    base_url: str,
    output_dir: Path | None = None,
    poll_interval: float = 1.0,
) -> Path:
    """Submit one PDF and wait until the long-lived worker finishes it."""

    return asyncio.run(
        _submit_and_wait(
            pdf_path=pdf_path,
            base_url=base_url,
            output_dir=output_dir,
            poll_interval=poll_interval,
        )
    )
