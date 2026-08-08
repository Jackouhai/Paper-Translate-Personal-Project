"""Tests for the single-worker parse queue."""

import pytest

from pp_doclayout.core.parse_worker import ParseWorker


def test_parse_worker_reuses_one_pipeline_and_runs_jobs_in_order():
    """The shared pipeline is created once and released after queued jobs."""

    events = []

    class FakePipeline:
        def close(self):
            events.append("close")

    def factory():
        events.append("factory")
        return FakePipeline()

    worker = ParseWorker(factory)
    worker.start()

    first = worker.submit(lambda pipeline: events.append("first") or "first-result")
    second = worker.submit(lambda pipeline: events.append("second") or "second-result")

    assert first.result() == "first-result"
    assert second.result() == "second-result"

    worker.close()

    assert events == ["factory", "first", "second", "close"]


def test_parse_worker_keeps_running_after_one_job_fails():
    """A failed PDF job must not prevent the next queued job from running."""

    worker = ParseWorker(lambda: object())
    worker.start()

    failed = worker.submit(lambda pipeline: (_ for _ in ()).throw(ValueError("bad PDF")))
    successful = worker.submit(lambda pipeline: "next job completed")

    with pytest.raises(ValueError, match="bad PDF"):
        failed.result()

    assert successful.result() == "next job completed"
    worker.close()


def test_parse_worker_reports_pipeline_startup_error():
    """A model-loading error is reported synchronously by start()."""

    def factory():
        raise OSError("model unavailable")

    worker = ParseWorker(factory)

    with pytest.raises(RuntimeError, match="Cannot start parse worker"):
        worker.start()

    worker.close()
