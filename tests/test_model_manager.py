from __future__ import annotations

import signal
from pathlib import Path
from typing import Any

import pytest
import requests

from services.model_manager import (
    ManagedModel,
    ModelConfig,
    ModelManagerError,
)


class FakeResponse:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"HTTP error: {self.status_code}"
            )


class FakeProcess:
    def __init__(
        self,
        pid: int = 12345,
        return_code: int | None = None,
    ) -> None:
        self.pid = pid
        self.return_code = return_code

    def poll(self) -> int | None:
        return self.return_code

    def wait(self, timeout: float | None = None) -> int:
        if self.return_code is None:
            self.return_code = 0
        return self.return_code


@pytest.fixture
def model_config() -> ModelConfig:
    return ModelConfig(
        name="test-model",
        port=9999,
        health_url="http://127.0.0.1:9999/v1/models",
        arguments=(
            "-m",
            "fake.module",
            "--port",
            "9999",
        ),
        log_filename="test-model.log",
    )


@pytest.fixture
def managed_model(
    model_config: ModelConfig,
    tmp_path: Path,
) -> ManagedModel:
    return ManagedModel(
        config=model_config,
        log_directory=tmp_path,
    )


def mock_server_unavailable(
    *args: Any,
    **kwargs: Any,
) -> FakeResponse:
    raise requests.ConnectionError(
        "Server is unavailable"
    )


def mock_server_ready(
    *args: Any,
    **kwargs: Any,
) -> FakeResponse:
    return FakeResponse(status_code=200)


def test_initial_status_is_stopped(
    monkeypatch: pytest.MonkeyPatch,
    managed_model: ManagedModel,
) -> None:
    monkeypatch.setattr(
        requests,
        "get",
        mock_server_unavailable,
    )

    status = managed_model.status()

    assert status["process_state"] == "stopped"
    assert status["server_ready"] is False
    assert status["owned_by_app"] is False
    assert status["pid"] is None
    assert status["last_error"] is None


def test_ready_server_without_owned_process_is_external(
    monkeypatch: pytest.MonkeyPatch,
    managed_model: ManagedModel,
) -> None:
    monkeypatch.setattr(
        requests,
        "get",
        mock_server_ready,
    )

    status = managed_model.status()

    assert status["process_state"] == "external"
    assert status["server_ready"] is True
    assert status["owned_by_app"] is False
    assert status["pid"] is None


def test_start_rejects_external_server(
    monkeypatch: pytest.MonkeyPatch,
    managed_model: ManagedModel,
) -> None:
    monkeypatch.setattr(
        requests,
        "get",
        mock_server_ready,
    )

    with pytest.raises(
        ModelManagerError,
        match="externally",
    ):
        managed_model.start()


def test_start_creates_owned_process(
    monkeypatch: pytest.MonkeyPatch,
    managed_model: ManagedModel,
) -> None:
    created: dict[str, Any] = {}

    def fake_popen(
        command: list[str],
        **kwargs: Any,
    ) -> FakeProcess:
        created["command"] = command
        created["kwargs"] = kwargs
        return FakeProcess(pid=23456)

    monkeypatch.setattr(
        requests,
        "get",
        mock_server_unavailable,
    )
    monkeypatch.setattr(
        "services.model_manager.subprocess.Popen",
        fake_popen,
    )

    status = managed_model.start()

    assert status["process_state"] == "starting"
    assert status["server_ready"] is False
    assert status["owned_by_app"] is True
    assert status["pid"] == 23456
    assert status["last_error"] is None

    assert created["command"][0]
    assert created["command"][1:] == [
        "-m",
        "fake.module",
        "--port",
        "9999",
    ]
    assert created["kwargs"]["start_new_session"] is True


def test_owned_process_becomes_ready(
    monkeypatch: pytest.MonkeyPatch,
    managed_model: ManagedModel,
) -> None:
    managed_model.process = FakeProcess(
        pid=34567,
        return_code=None,
    )

    monkeypatch.setattr(
        requests,
        "get",
        mock_server_ready,
    )

    status = managed_model.status()

    assert status["process_state"] == "ready"
    assert status["server_ready"] is True
    assert status["owned_by_app"] is True
    assert status["pid"] == 34567
    assert status["last_error"] is None


def test_exited_owned_process_becomes_failed(
    monkeypatch: pytest.MonkeyPatch,
    managed_model: ManagedModel,
) -> None:
    managed_model.process = FakeProcess(
        pid=45678,
        return_code=1,
    )

    monkeypatch.setattr(
        requests,
        "get",
        mock_server_unavailable,
    )

    status = managed_model.status()

    assert status["process_state"] == "failed"
    assert status["server_ready"] is False
    assert status["owned_by_app"] is False
    assert status["pid"] is None
    assert status["last_error"] == (
        "test-model process exited with code 1"
    )


def test_stop_rejects_external_server(
    monkeypatch: pytest.MonkeyPatch,
    managed_model: ManagedModel,
) -> None:
    monkeypatch.setattr(
        requests,
        "get",
        mock_server_ready,
    )

    with pytest.raises(
        ModelManagerError,
        match="externally",
    ):
        managed_model.stop()


def test_stop_terminates_owned_process_group(
    monkeypatch: pytest.MonkeyPatch,
    managed_model: ManagedModel,
) -> None:
    process = FakeProcess(
        pid=56789,
        return_code=None,
    )
    managed_model.process = process

    signals: list[tuple[int, signal.Signals]] = []

    def fake_killpg(
        process_group_id: int,
        sig: signal.Signals,
    ) -> None:
        signals.append((process_group_id, sig))
        process.return_code = 0

    monkeypatch.setattr(
        requests,
        "get",
        mock_server_unavailable,
    )
    monkeypatch.setattr(
        "services.model_manager.os.killpg",
        fake_killpg,
    )

    status = managed_model.stop()

    assert signals == [
        (56789, signal.SIGTERM),
    ]
    assert status["process_state"] == "stopped"
    assert status["server_ready"] is False
    assert status["owned_by_app"] is False
    assert status["pid"] is None
    assert status["last_error"] is None
