"""Utilities for selecting PaddleOCR local inference devices."""


def resolve_paddle_device(configured_device: str | None) -> str:
    """Resolve the PaddleOCR document layout analysis model device.

    auto:
    - use gpu:0 when Paddle can see a CUDA GPU;
    - otherwise fall back to cpu.

    Explicit values such as cpu or gpu:0 are returned unchanged.
    """

    request_device = (configured_device or "auto").strip()
    if not request_device:
        request_device = "auto"

    if request_device.lower() != "auto":
        return request_device

    try:
        import paddle
    except ImportError:
        return "cpu"

    try:
        if not paddle.device.is_compiled_with_cuda():
            return "cpu"
        if paddle.device.cuda.device_count() <= 0:
            return "cpu"
    except Exception:
        return "cpu"

    return "gpu:0"
