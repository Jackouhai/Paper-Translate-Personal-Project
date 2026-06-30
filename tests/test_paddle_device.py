"""Tests for PaddleOCR helper model device selection."""

import builtins
import sys
from types import SimpleNamespace

from pp_doclayout.utils.paddle_device import resolve_paddle_device


def _fake_paddle(*, compiled_with_cuda: bool, device_count: int):
    return SimpleNamespace(
        device=SimpleNamespace(
            is_compiled_with_cuda=lambda: compiled_with_cuda,
            cuda=SimpleNamespace(device_count=lambda: device_count),
        ),
    )


def test_resolve_paddle_device_returns_explicit_device():
    """Explicit values are user intent and should not be changed."""

    assert resolve_paddle_device("cpu") == "cpu"
    assert resolve_paddle_device("gpu:0") == "gpu:0"
    assert resolve_paddle_device(" gpu:1 ") == "gpu:1"


def test_resolve_paddle_device_auto_uses_gpu_when_paddle_sees_cuda(monkeypatch):
    """auto should use gpu:0 when Paddle reports usable CUDA devices."""

    monkeypatch.setitem(
        sys.modules,
        "paddle",
        _fake_paddle(compiled_with_cuda=True, device_count=1),
    )

    assert resolve_paddle_device("auto") == "gpu:0"


def test_resolve_paddle_device_auto_uses_cpu_when_paddle_has_no_cuda(monkeypatch):
    """auto falls back to cpu when Paddle is not compiled with CUDA."""

    monkeypatch.setitem(
        sys.modules,
        "paddle",
        _fake_paddle(compiled_with_cuda=False, device_count=1),
    )

    assert resolve_paddle_device("auto") == "cpu"


def test_resolve_paddle_device_auto_uses_cpu_when_no_gpu_is_visible(monkeypatch):
    """auto falls back to cpu when CUDA exists but no GPU is visible."""

    monkeypatch.setitem(
        sys.modules,
        "paddle",
        _fake_paddle(compiled_with_cuda=True, device_count=0),
    )

    assert resolve_paddle_device("auto") == "cpu"


def test_resolve_paddle_device_auto_uses_cpu_when_paddle_import_fails(
    monkeypatch,
):
    """auto falls back to cpu when Paddle is not importable."""

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "paddle":
            raise ImportError("No module named paddle")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    assert resolve_paddle_device("auto") == "cpu"


def test_resolve_paddle_device_auto_uses_cpu_when_paddle_check_raises(
    monkeypatch,
):
    """auto falls back to cpu instead of failing the CLI."""

    broken_paddle = SimpleNamespace(
        device=SimpleNamespace(
            is_compiled_with_cuda=lambda: True,
            cuda=SimpleNamespace(device_count=lambda: (_ for _ in ()).throw(
                RuntimeError("CUDA probe failed")
            )),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "paddle",
        broken_paddle,
    )

    assert resolve_paddle_device("auto") == "cpu"
