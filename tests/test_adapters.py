"""Offline contract tests for registry adapters.

These tests use httpx.MockTransport so parsing and endpoint behavior are tested
without depending on live registry availability or rate limits.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import httpx

from secchi.api.cran import CranAdapter
from secchi.api.crates import CratesAdapter
from secchi.api.golang import GoModuleAdapter
from secchi.api.homebrew import HomebrewAdapter
from secchi.api.npm import NpmAdapter
from secchi.api.pypi import PyPIAdapter
from secchi.models import Registry


def run(operation: Awaitable):
    return asyncio.run(operation)


def client_for(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def json_response(request: httpx.Request, payload: object) -> httpx.Response:
    return httpx.Response(200, json=payload, request=request)


def test_pypi_adapter_parses_metadata_versions_dependencies_and_downloads() -> None:
    package = {
        "info": {
            "name": "demo",
            "version": "2.0.0",
            "summary": "A demo package",
            "author": "Kannan",
            "requires_dist": ["httpx>=0.27", "pytest; extra == 'test'"],
            "project_urls": {"Source": "https://github.com/example/demo"},
            "classifiers": ["Topic :: Utilities"],
        },
        "releases": {
            "1.0.0": [{"upload_time": "2025-01-01T00:00:00Z", "size": 10}],
            "2.0.0": [
                {
                    "upload_time": "2026-01-01T00:00:00Z",
                    "size": 20,
                    "packagetype": "bdist_wheel",
                }
            ],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/demo/json"):
            return json_response(request, package)
        if request.url.path.endswith("/packages/demo/overall"):
            return json_response(
                request,
                {"data": [{"date": "2026-01-01", "downloads": 12}]},
            )
        if request.url.path.endswith("/packages/demo/recent"):
            return json_response(
                request,
                {"data": {"last_day": 2, "last_week": 8, "last_month": 30}},
            )
        return httpx.Response(404, request=request)

    async def exercise() -> None:
        async with client_for(handler) as client:
            adapter = PyPIAdapter(client)
            info = await adapter.fetch_package("demo")
            versions = await adapter.fetch_versions("demo")
            dependencies = await adapter.fetch_dependencies("demo", "2.0.0")
            trend = await adapter.fetch_download_trend("demo")
            counts = await adapter.fetch_download_counts("demo")
            search = await adapter.search("demo")

        assert info.registry is Registry.PYPI
        assert info.package_kind == "CLI"
        assert info.latest_version == "2.0.0"
        assert info.repository_url.endswith("example/demo")
        assert [version.version for version in versions] == ["2.0.0", "1.0.0"]
        assert [(item.name, item.requirement) for item in dependencies] == [
            ("httpx>=0.27", "")
        ]
        assert trend[0].count == 12
        assert counts.month == 30
        assert search[0].exact is True

    run(exercise())


def test_npm_adapter_parses_versions_dependencies_search_and_downloads() -> None:
    package = {
        "name": "demo",
        "description": "A demo npm package",
        "author": {"name": "Kannan"},
        "repository": {"url": "https://github.com/example/demo"},
        "dist-tags": {"latest": "2.0.0"},
        "time": {
            "1.0.0": "2025-01-01T00:00:00Z",
            "2.0.0": "2026-01-01T00:00:00Z",
        },
        "versions": {
            "1.0.0": {"dist": {"unpackedSize": 10}},
            "2.0.0": {
                "license": "MIT",
                "bin": {"demo": "cli.js"},
                "dist": {"unpackedSize": 20},
                "dependencies": {"httpx": "^1.0.0"},
                "peerDependencies": {"typescript": ">=5"},
            },
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/demo":
            return json_response(request, package)
        if path.endswith("/point/last-year/demo"):
            return json_response(request, {"downloads": 1000})
        if path.endswith("/point/last-day/demo"):
            return json_response(request, {"downloads": 10})
        if path.endswith("/point/last-week/demo"):
            return json_response(request, {"downloads": 70})
        if path.endswith("/point/last-month/demo"):
            return json_response(request, {"downloads": 300})
        if path == "/-/v1/search":
            return json_response(
                request,
                {
                    "objects": [
                        {
                            "package": {
                                "name": "demo",
                                "version": "2.0.0",
                                "description": "A demo npm package",
                                "links": {"npm": "https://npmjs.com/demo"},
                            },
                            "score": {"final": 0.9},
                        }
                    ]
                },
            )
        return httpx.Response(404, request=request)

    async def exercise() -> None:
        async with client_for(handler) as client:
            adapter = NpmAdapter(client)
            info = await adapter.fetch_package("demo")
            versions = await adapter.fetch_versions("demo")
            dependencies = await adapter.fetch_dependencies("demo", "2.0.0")
            counts = await adapter.fetch_download_counts("demo")
            search = await adapter.search("demo")

        assert info.package_kind == "CLI"
        assert info.total_downloads == 1000
        assert [version.version for version in versions] == ["2.0.0", "1.0.0"]
        assert {item.name for item in dependencies} == {"httpx", "typescript"}
        assert counts.today == 10 and counts.week == 70 and counts.month == 300
        assert search[0].exact is True

    run(exercise())


def test_crates_adapter_parses_metadata_versions_dependencies_trend_and_search() -> (
    None
):
    payload = {
        "crate": {
            "name": "demo",
            "description": "A demo crate",
            "max_stable_version": "2.0.0",
            "downloads": 500,
            "repository": "https://github.com/example/demo",
            "updated_at": "2026-01-01T00:00:00Z",
        },
        "categories": [{"slug": "command-line-utilities"}],
        "versions": [
            {"id": 1, "num": "1.0.0", "created_at": "2025-01-01T00:00:00Z"},
            {"id": 2, "num": "2.0.0", "created_at": "2026-01-01T00:00:00Z"},
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/crates/demo":
            return json_response(request, payload)
        if path == "/api/v1/crates/demo/2.0.0/dependencies":
            return json_response(
                request,
                {
                    "dependencies": [
                        {"crate_id": "serde", "req": "^1", "optional": False}
                    ]
                },
            )
        if path == "/api/v1/crates/demo/downloads":
            return json_response(
                request,
                {"version_downloads": [{"date": "2026-01-01", "downloads": 4}]},
            )
        if path == "/api/v1/crates":
            return json_response(
                request,
                {
                    "crates": [
                        {"id": "demo", "max_version": "2.0.0", "recent_downloads": 5}
                    ]
                },
            )
        return httpx.Response(404, request=request)

    async def exercise() -> None:
        async with client_for(handler) as client:
            adapter = CratesAdapter(client)
            info = await adapter.fetch_package("demo")
            versions = await adapter.fetch_versions("demo")
            dependencies = await adapter.fetch_dependencies("demo", "2.0.0")
            trend = await adapter.fetch_download_trend("demo")
            counts = await adapter.fetch_download_counts("demo")
            search = await adapter.search("demo")

        assert info.package_kind == "CLI"
        assert info.total_downloads == 500
        assert [version.version for version in versions] == ["2.0.0", "1.0.0"]
        assert dependencies[0].name == "serde"
        assert trend[0].count == 4 and counts.month == 4
        assert search[0].name == "demo"

    run(exercise())


def test_crates_adapter_identifies_secchi_to_crates_io() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert (
            "secchi (https://github.com/kannandreams/secchi)"
            in request.headers["user-agent"]
        )
        return json_response(
            request,
            {
                "crate": {
                    "name": "demo",
                    "max_stable_version": "1.0.0",
                    "versions": [],
                }
            },
        )

    async def exercise() -> None:
        async with client_for(handler) as client:
            info = await CratesAdapter(client).fetch_package("demo")
        assert info.name == "demo"

    run(exercise())


def test_sparse_adapters_parse_metadata_search_and_report_missing_optional_signals() -> (
    None
):
    async def exercise() -> None:
        def homebrew_handler(request: httpx.Request) -> httpx.Response:
            return json_response(
                request,
                {
                    "name": "demo",
                    "desc": "A brew formula",
                    "homepage": "https://example.com/demo",
                    "license": "MIT",
                    "versions": {"stable": "2.0.0"},
                },
            )

        def go_handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/@v/list"):
                return httpx.Response(200, text="v1.0.0\nv2.0.0\n", request=request)
            return json_response(
                request,
                {"Version": "v2.0.0", "Time": "2026-01-01T00:00:00Z"},
            )

        def cran_handler(request: httpx.Request) -> httpx.Response:
            return json_response(
                request,
                {
                    "Package": "demo",
                    "Title": "A CRAN package",
                    "Version": "1.2.0",
                    "Maintainer": "Kannan <kannan@example.com>",
                    "License": "MIT",
                    "URL": "https://example.com/demo, https://github.com/example/demo",
                    "Imports": "R, cli (>= 3.0), jsonlite",
                },
            )

        async with client_for(homebrew_handler) as client:
            homebrew = HomebrewAdapter(client)
            info = await homebrew.fetch_package("demo")
            search = await homebrew.search("demo")
            assert info.latest_version == "2.0.0"
            assert search[0].exact is True
            assert await homebrew.fetch_download_trend("demo") == []
            assert (await homebrew.fetch_download_counts("demo")).month == 0

        async with client_for(go_handler) as client:
            golang = GoModuleAdapter(client)
            info = await golang.fetch_package("github.com/example/demo")
            versions = await golang.fetch_versions("github.com/example/demo")
            search = await golang.search("github.com/example/demo")
            assert info.latest_version == "v2.0.0"
            assert [version.version for version in versions] == ["v1.0.0", "v2.0.0"]
            assert search[0].exact is True
            assert await golang.fetch_dependencies("demo", "v2.0.0") == []

        async with client_for(cran_handler) as client:
            cran = CranAdapter(client)
            info = await cran.fetch_package("demo")
            search = await cran.search("demo")
            assert info.latest_version == "1.2.0"
            assert [item.name for item in info.dependencies] == ["cli", "jsonlite"]
            assert search[0].registry is Registry.CRAN
            assert await cran.fetch_download_trend("demo") == []

    run(exercise())


def test_adapters_return_empty_search_results_for_missing_optional_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    async def exercise() -> None:
        async with client_for(handler) as client:
            assert await HomebrewAdapter(client).search("missing") == []
            assert await GoModuleAdapter(client).search("missing") == []
            assert await CranAdapter(client).search("missing") == []

    run(exercise())
