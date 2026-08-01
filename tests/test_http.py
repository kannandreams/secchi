import asyncio

import httpx

from secchi.http import HttpClientFactory, SecchiAsyncClient


def test_shared_client_retries_safe_transient_get(monkeypatch) -> None:
    calls = 0

    async def no_sleep(delay: float) -> None:
        return None

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(200, request=request, json={"ok": True})

    monkeypatch.setattr("secchi.http.asyncio.sleep", no_sleep)

    async def run() -> httpx.Response:
        client = SecchiAsyncClient(
            transport=httpx.MockTransport(handler), max_retries=1
        )
        async with client:
            return await client.get("https://example.test/health")

    response = asyncio.run(run())

    assert response.status_code == 200
    assert calls == 2


def test_factory_applies_shared_defaults() -> None:
    client = HttpClientFactory().create(headers={"X-Secchi-Test": "yes"})
    assert client.follow_redirects is True
    assert client.timeout is not None
    assert client.headers["X-Secchi-Test"] == "yes"
    asyncio.run(client.aclose())
