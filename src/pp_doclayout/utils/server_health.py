"""Utilities for checking OpenAI-compatible model servers."""

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ServerHealth:
    """Result of a server health check."""

    name: str
    url: str
    available: bool
    message: str


def check_server_health(
    name: str,
    base_url: str,
    timeout: float = 2.0,
) -> ServerHealth:
    """Check an OpenAI-compatible server through its models endpoint."""

    models_url = f"{base_url.rstrip('/')}/models"
    request = Request(
        models_url,
        headers={"Accept": "application/json"},
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)

    except HTTPError as exc:
        return ServerHealth(
            name=name,
            url=models_url,
            available=False,
            message=f"HTTP {exc.code}",
        )

    except (URLError, TimeoutError, OSError) as exc:
        return ServerHealth(
            name=name,
            url=models_url,
            available=False,
            message=str(exc),
        )

    except json.JSONDecodeError:
        return ServerHealth(
            name=name,
            url=models_url,
            available=False,
            message="Server returned invalid JSON",
        )

    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return ServerHealth(
            name=name,
            url=models_url,
            available=False,
            message="Unexpected /v1/models response",
        )
    return ServerHealth(
        name=name,
        url=models_url,
        available=True,
        message="Server is ready",
    )
