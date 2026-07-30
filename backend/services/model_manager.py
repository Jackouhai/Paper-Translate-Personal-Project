from __future__ import annotations

import atexit
import os
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


REQUEST_TIMEOUT_SECONDS = 2
STOP_TIMEOUT_SECONDS = 20


class ModelManagerError(RuntimeError):
    """Raised when a model process cannot be managed safely."""


@dataclass(frozen=True)
class ModelConfig:
    name: str
    port: int
    health_url: str
    arguments: tuple[str, ...]
    log_filename: str


OCR_CONFIG = ModelConfig(
    name="ocr",
    port=8000,
    health_url="http://127.0.0.1:8000/v1/models",
    arguments=(
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        "PaddlePaddle/PaddleOCR-VL-1.5",
        "--served-model-name",
        "PaddleOCR-VL-1.5-0.9B",
        "--trust-remote-code",
        "--dtype",
        "bfloat16",
        "--max-model-len",
        "16384",
        "--max-num-seqs",
        "10",
        "--max-num-batched-tokens",
        "8192",
        "--gpu-memory-utilization",
        "0.5",
        "--enforce-eager",
        "--no-enable-prefix-caching",
        "--mm-processor-cache-gb",
        "0",
        "--port",
        "8000",
    ),
    log_filename="ocr.log",
)


TRANSLATOR_CONFIG = ModelConfig(
    name="translator",
    port=8001,
    health_url="http://127.0.0.1:8001/v1/models",
    arguments=(
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        "Infomaniak-AI/vllm-translategemma-4b-it",
        "--dtype",
        "bfloat16",
        "--quantization",
        "bitsandbytes",
        "--load-format",
        "bitsandbytes",
        "--max-model-len",
        "8192",
        "--max-num-seqs",
        "10",
        "--max-num-batched-tokens",
        "8192",
        "--gpu-memory-utilization",
        "0.7",
        "--port",
        "8001",
    ),
    log_filename="translator.log",
)


class ManagedModel:
    def __init__(
        self,
        config: ModelConfig,
        log_directory: Path,
    ) -> None:
        self.config = config
        self.log_directory = log_directory
        self.process: subprocess.Popen[bytes] | None = None
        self.log_handle: Any | None = None
        self.last_error: str | None = None
        self._lock = threading.RLock()

    def _server_ready(self) -> bool:
        try:
            response = requests.get(
                self.config.health_url,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            return response.ok
        except requests.RequestException:
            return False

    def _owned_process_alive(self) -> bool:
        return (
            self.process is not None
            and self.process.poll() is None
        )

    def _close_log(self) -> None:
        if self.log_handle is not None:
            try:
                self.log_handle.close()
            finally:
                self.log_handle = None

    def _clear_finished_process(self) -> None:
        if self.process is None:
            return

        exit_code = self.process.poll()

        if exit_code is None:
            return

        if exit_code != 0 and self.last_error is None:
            self.last_error = (
                f"{self.config.name} process exited "
                f"with code {exit_code}"
            )

        self.process = None
        self._close_log()

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._clear_finished_process()

            ready = self._server_ready()
            owned_alive = self._owned_process_alive()

            if ready and owned_alive:
                process_state = "ready"
            elif ready and not owned_alive:
                process_state = "external"
            elif owned_alive:
                process_state = "starting"
            elif self.last_error:
                process_state = "failed"
            else:
                process_state = "stopped"

            return {
                "name": self.config.name,
                "process_state": process_state,
                "server_ready": ready,
                "owned_by_app": owned_alive,
                "pid": (
                    self.process.pid
                    if owned_alive and self.process is not None
                    else None
                ),
                "port": self.config.port,
                "health_url": self.config.health_url,
                "log_file": str(
                    self.log_directory / self.config.log_filename
                ),
                "last_error": self.last_error,
            }

    def start(self) -> dict[str, Any]:
        with self._lock:
            self._clear_finished_process()

            current_status = self.status()

            if current_status["server_ready"]:
                if current_status["owned_by_app"]:
                    return current_status

                raise ModelManagerError(
                    f"{self.config.name} server is already running "
                    "externally and is not owned by PaperTranslate."
                )

            if self._owned_process_alive():
                return self.status()

            self.log_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            log_path = (
                self.log_directory / self.config.log_filename
            )

            self.log_handle = log_path.open(
                "ab",
                buffering=0,
            )

            command = [
                sys.executable,
                *self.config.arguments,
            ]

            environment = os.environ.copy()
            environment["PYTHONUNBUFFERED"] = "1"

            try:
                self.process = subprocess.Popen(
                    command,
                    stdout=self.log_handle,
                    stderr=subprocess.STDOUT,
                    env=environment,
                    start_new_session=True,
                )
            except OSError as exc:
                self._close_log()
                self.last_error = str(exc)

                raise ModelManagerError(
                    f"Could not start {self.config.name}: {exc}"
                ) from exc

            self.last_error = None
            return self.status()

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._clear_finished_process()

            if self.process is None:
                if self._server_ready():
                    raise ModelManagerError(
                        f"{self.config.name} server is running "
                        "externally and cannot be stopped by "
                        "PaperTranslate."
                    )

                self.last_error = None
                return self.status()

            process = self.process

            if process.poll() is not None:
                self.process = None
                self._close_log()
                self.last_error = None
                return self.status()

            try:
                os.killpg(
                    process.pid,
                    signal.SIGTERM,
                )

                process.wait(
                    timeout=STOP_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                os.killpg(
                    process.pid,
                    signal.SIGKILL,
                )

                process.wait(
                    timeout=5,
                )
            except ProcessLookupError:
                pass
            except OSError as exc:
                raise ModelManagerError(
                    f"Could not stop {self.config.name}: {exc}"
                ) from exc
            finally:
                self.process = None
                self._close_log()

            self.last_error = None
            return self.status()


class ModelManager:
    def __init__(self) -> None:
        data_directory = Path(
            os.environ.get(
                "PAPERTRANSLATE_DATA_DIR",
                Path.home()
                / ".local"
                / "share"
                / "com.jackouhai.papertranslate",
            )
        ).expanduser()

        self.log_directory = (
            data_directory / "logs" / "models"
        )

        self.ocr = ManagedModel(
            OCR_CONFIG,
            self.log_directory,
        )

        self.translator = ManagedModel(
            TRANSLATOR_CONFIG,
            self.log_directory,
        )

    def status(self) -> dict[str, Any]:
        return {
            "ocr": self.ocr.status(),
            "translator": self.translator.status(),
        }

    def stop_all(self) -> dict[str, Any]:
        results: dict[str, Any] = {}

        # Stop the translator first so GPU memory begins to be
        # released before the OCR service is stopped.
        for model in (
            self.translator,
            self.ocr,
        ):
            model_name = model.config.name

            try:
                current_status = model.status()

                if current_status["process_state"] == "external":
                    results[model_name] = {
                        "action": "skipped_external",
                        "model": current_status,
                    }
                    continue

                if not current_status["owned_by_app"]:
                    results[model_name] = {
                        "action": "already_stopped",
                        "model": current_status,
                    }
                    continue

                results[model_name] = {
                    "action": "stopped",
                    "model": model.stop(),
                }

            except Exception as exc:
                # A failure stopping one model must not prevent the
                # application from attempting to stop the other model.
                results[model_name] = {
                    "action": "failed",
                    "error": str(exc),
                }

        return results


model_manager = ModelManager()

atexit.register(model_manager.stop_all)

