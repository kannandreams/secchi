"""Shared HTTP client defaults and safe transient retry behavior."""

from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from secchi.diagnostics import (
    DiagnosticLog,
    DiagnosticStatus,
    diagnostic_for_http_error,
)

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
RETRYABLE_METHODS = {"GET", "HEAD", "OPTIONS"}


class SecchiAsyncClient(httpx.AsyncClient):
    """AsyncClient with shared defaults and bounded retries for safe requests."""

    def __init__(
        self,
        *,
        max_retries: int = 2,
        diagnostics: DiagnosticLog | None = None,
        **kwargs: Any,
    ) -> None:
        self.max_retries = max_retries
        self.diagnostics = diagnostics
        super().__init__(
            timeout=kwargs.pop("timeout", httpx.Timeout(10.0)),
            follow_redirects=kwargs.pop("follow_redirects", True),
            **kwargs,
        )

    async def request(
        self, method: str, url: str, *args: Any, **kwargs: Any
    ) -> httpx.Response:
        method_upper = method.upper()
        retries = self.max_retries if method_upper in RETRYABLE_METHODS else 0
        for attempt in range(retries + 1):
            try:
                response = await super().request(method, url, *args, **kwargs)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if self.diagnostics is not None:
                    self.diagnostics.record(
                        DiagnosticStatus.FAILURE
                        if attempt >= retries
                        else DiagnosticStatus.WARN,
                        "HTTP",
                        f"{method_upper} request failed ({diagnostic_for_http_error(exc)})"
                        + (
                            f"; retry {attempt + 1}/{retries}"
                            if attempt < retries
                            else ""
                        ),
                        url=url,
                    )
                if attempt >= retries:
                    raise
                await asyncio.sleep(_backoff(attempt))
                continue

            if self.diagnostics is not None:
                status = (
                    DiagnosticStatus.SUCCESS
                    if response.status_code < 400
                    else DiagnosticStatus.WARN
                )
                self.diagnostics.record(
                    status,
                    "HTTP",
                    f"{method_upper} response",
                    url=url,
                    status_code=response.status_code,
                )
            if response.status_code not in RETRYABLE_STATUS_CODES or attempt >= retries:
                return response
            if self.diagnostics is not None:
                self.diagnostics.record(
                    DiagnosticStatus.WARN,
                    "HTTP",
                    f"Retrying {method_upper} response ({attempt + 1}/{retries})",
                    url=url,
                    status_code=response.status_code,
                )
            await asyncio.sleep(_retry_after(response) or _backoff(attempt))
        raise AssertionError("HTTP retry loop did not return or raise")


class HttpClientFactory:
    """Create consistently configured clients for registry and GitHub calls."""

    def __init__(
        self, *, max_retries: int = 2, diagnostics: DiagnosticLog | None = None
    ) -> None:
        self.max_retries = max_retries
        self.diagnostics = diagnostics

    def create(
        self,
        *,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | float | None = None,
        diagnostics: DiagnosticLog | None = None,
    ) -> SecchiAsyncClient:
        return SecchiAsyncClient(
            headers=headers,
            timeout=timeout or httpx.Timeout(10.0),
            max_retries=self.max_retries,
            diagnostics=diagnostics or self.diagnostics,
        )


def _backoff(attempt: int) -> float:
    return min(2.0, 0.25 * (2**attempt)) + random.uniform(0, 0.05)


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return max(0.0, min(10.0, float(raw)))
    except ValueError:
        try:
            date = parsedate_to_datetime(raw)
            if date.tzinfo is None:
                date = date.replace(tzinfo=UTC)
            return max(
                0.0,
                min(10.0, date.timestamp() - datetime.now(UTC).timestamp()),
            )
        except (TypeError, ValueError, OverflowError):
            return None
