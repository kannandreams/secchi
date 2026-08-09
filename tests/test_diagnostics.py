from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx

from secchi.cli import build_parser
from secchi.diagnostics import DiagnosticLog, DiagnosticStatus
from secchi.http import SecchiAsyncClient
from secchi.models import Registry, SearchResult
from secchi.services.search import PackageSearchService
from secchi.ui.app import Secchi
from secchi.ui.widgets.modals import LogsScreen


def test_diagnostic_log_formats_and_writes_events(tmp_path) -> None:
    path = tmp_path / "secchi.log"
    log = DiagnosticLog(
        path=path,
        clock=lambda: datetime(2026, 8, 9, 11, 30, tzinfo=UTC),
    )

    log.record(
        DiagnosticStatus.SUCCESS,
        "PyPI",
        "GET response",
        url="https://pypi.org/pypi/tuffcli/json",
        status_code=200,
    )

    line = path.read_text().strip()
    assert "SUCCESS" in line
    assert "[PyPI] GET response" in line
    assert "https://pypi.org/pypi/tuffcli/json" in line
    assert "-> 200" in line


def test_http_client_records_response_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True}, request=request)

    async def exercise() -> None:
        log = DiagnosticLog()
        transport = httpx.MockTransport(handler)
        async with SecchiAsyncClient(transport=transport, diagnostics=log) as client:
            response = await client.get("https://example.test/status")
        assert response.status_code == 200
        event = log.snapshot()[0]
        assert event.status is DiagnosticStatus.SUCCESS
        assert event.status_code == 200
        assert event.url == "https://example.test/status"

    asyncio.run(exercise())


def test_search_records_partial_registry_failure(monkeypatch) -> None:
    class FakeAdapter:
        def __init__(self, registry: Registry) -> None:
            self.registry = registry

        async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
            if self.registry is Registry.NPM:
                raise httpx.HTTPError("npm unavailable")
            return [SearchResult(name=query, registry=self.registry, exact=True)]

    monkeypatch.setattr(
        "secchi.services.search.create_adapter",
        lambda registry, client=None: FakeAdapter(registry),
    )
    log = DiagnosticLog()
    results = asyncio.run(
        PackageSearchService(log).search(
            "demo", registries=[Registry.PYPI, Registry.NPM]
        )
    )

    assert len(results) == 1
    events = log.snapshot()
    assert any(
        event.source == "npm" and event.status is DiagnosticStatus.WARN
        for event in events
    )
    assert any(
        event.source == "PyPI" and event.status is DiagnosticStatus.SUCCESS
        for event in events
    )


def test_cli_accepts_diagnostics_before_or_after_command() -> None:
    parser = build_parser()
    before = parser.parse_args(["--verbose", "search", "demo"])
    after = parser.parse_args(["search", "demo", "--verbose", "--log-file", "run.log"])

    assert before.verbose is True
    assert after.verbose is True
    assert str(after.log_file).endswith("run.log")


def test_dashboard_keeps_filter_and_adds_log_shortcut() -> None:
    bindings = {binding.key: binding.action for binding in Secchi.BINDINGS}
    assert bindings["f"] == "toggle_filter"
    assert bindings["l"] == "logs"
    log_bindings = {binding.key: binding.action for binding in LogsScreen.BINDINGS}
    assert log_bindings["c"] == "copy_logs"
