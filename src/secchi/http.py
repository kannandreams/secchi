"""Shared HTTP client defaults and safe transient retry behavior."""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx


RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
RETRYABLE_METHODS = {"GET", "HEAD", "OPTIONS"}


class SecchiAsyncClient(httpx.AsyncClient):
    """AsyncClient with shared defaults and bounded retries for safe requests."""

    def __init__(self, *, max_retries: int = 2, **kwargs: Any) -> None:
        self.max_retries = max_retries
        super().__init__(
            timeout=kwargs.pop("timeout", httpx.Timeout(10.0)),
            follow_redirects=kwargs.pop("follow_redirects", True),
            **kwargs,
        )

    async def request(self, method: str, url: str, *args: Any, **kwargs: Any) -> httpx.Response:
        method_upper = method.upper()
        retries = self.max_retries if method_upper in RETRYABLE_METHODS else 0
        for attempt in range(retries + 1):
            try:
                response = await super().request(method, url, *args, **kwargs)
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt >= retries:
                    raise
                await asyncio.sleep(_backoff(attempt))
                continue

            if response.status_code not in RETRYABLE_STATUS_CODES or attempt >= retries:
                return response
            await asyncio.sleep(_retry_after(response) or _backoff(attempt))
        raise AssertionError("HTTP retry loop did not return or raise")


class HttpClientFactory:
    """Create consistently configured clients for registry and GitHub calls."""

    def __init__(self, *, max_retries: int = 2) -> None:
        self.max_retries = max_retries

    def create(
        self,
        *,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | float | None = None,
    ) -> SecchiAsyncClient:
        return SecchiAsyncClient(
            headers=headers,
            timeout=timeout or httpx.Timeout(10.0),
            max_retries=self.max_retries,
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
                date = date.replace(tzinfo=timezone.utc)
            return max(0.0, min(10.0, date.timestamp() - datetime.now(timezone.utc).timestamp()))
        except (TypeError, ValueError, OverflowError):
            return None
