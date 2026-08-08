"""Single-worker queue for GPU-backed PDF parsing."""

from __future__ import annotations

from concurrent.futures import Future
from queue import Queue
from threading import Event, Thread
from typing import Any, Callable, TypeVar

T = TypeVar("T")
_STOP = object()


class ParseWorker:
    """Own one PaddleOCRVL pipeline and execute parse jobs sequentially."""

    def __init__(self, pipeline_factory: Callable[[], Any]) -> None:
        self._pipeline_factory = pipeline_factory
        self._jobs: Queue[object] = Queue()
        self._thread: Thread | None = None
        self._ready = Event()
        self._startup_error: BaseException | None = None
        self._closed = False

    def start(self) -> None:
        """Load the pipeline once in the worker thread."""

        if self._thread is not None:
            return

        self._thread = Thread(
            target=self._run,
            name="pp-doclayout-parse-worker",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait()

        if self._startup_error is not None:
            raise RuntimeError("Cannot start parse worker") from self._startup_error

    def submit(self, operation: Callable[[Any], T]) -> Future[T]:
        """Queue one operation that receives the shared pipeline."""

        if self._thread is None:
            raise RuntimeError("Parse worker has not been started.")

        if self._closed:
            raise RuntimeError("Parse worker is closed")

        future: Future[T] = Future()
        self._jobs.put((operation, future))
        return future

    def close(self) -> None:
        """Finish queued jobs, release the pipeline, then stop the thread."""
        if self._thread is None or self._closed:
            return

        self._closed = True
        self._jobs.put(_STOP)
        self._thread.join()
        self._thread = None

    def _run(self) -> None:
        pipeline = None

        try:
            pipeline = self._pipeline_factory()
        except BaseException as error:
            self._startup_error = error
            self._ready.set()
            return

        self._ready.set()

        try:
            while True:
                job = self._jobs.get()

                try:
                    if job is _STOP:
                        return

                    operation, future = job

                    if future.set_running_or_notify_cancel():
                        try:
                            future.set_result(operation(pipeline))
                        except BaseException as error:
                            future.set_exception(error)
                finally:
                    self._jobs.task_done()
        finally:
            close_pipeline = getattr(pipeline, "close", None)
            if callable(close_pipeline):
                close_pipeline()
