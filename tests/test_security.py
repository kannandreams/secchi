"""Offline tests for OSV advisory lookup and normalization."""

from __future__ import annotations

import asyncio
import json

import httpx

from secchi import security
from secchi.models import PackageInfo, Registry
from secchi.security import fetch_osv_advisories


def test_osv_lookup_queries_latest_version_and_normalizes_advisory() -> None:
    request_payload: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.osv.dev/v1/query"
        request_payload.update(json.loads(request.read()))
        return httpx.Response(
            200,
            json={
                "vulns": [
                    {
                        "id": "GHSA-demo-1234-abcd",
                        "aliases": ["CVE-2026-1234"],
                        "summary": "A demo vulnerability",
                        "details": "Details",
                        "published": "2026-01-01T00:00:00Z",
                        "modified": "2026-02-01T00:00:00Z",
                        "affected": [
                            {
                                "ecosystem_specific": {"severity": "HIGH"},
                                "ranges": [
                                    {
                                        "events": [
                                            {"introduced": "0"},
                                            {"fixed": "2.0.1"},
                                        ]
                                    }
                                ],
                            }
                        ],
                        "references": [
                            {"type": "ADVISORY", "url": "https://example.test/advisory"}
                        ],
                    },
                    {"id": "WITHDRAWN", "withdrawn": "2026-02-02T00:00:00Z"},
                ]
            },
            request=request,
        )

    async def exercise() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            advisories = await fetch_osv_advisories(
                PackageInfo(
                    name="demo", registry=Registry.PYPI, latest_version="2.0.0"
                ),
                client=client,
            )

        assert request_payload["package"] == {"name": "demo", "ecosystem": "PyPI"}
        assert request_payload["version"] == "2.0.0"
        assert len(advisories) == 1
        advisory = advisories[0]
        assert advisory.id == "GHSA-demo-1234-abcd"
        assert advisory.aliases == ["CVE-2026-1234"]
        assert advisory.severity == "HIGH"
        assert advisory.fixed_versions == ["2.0.1"]
        assert advisory.url.endswith(advisory.id)

    asyncio.run(exercise())


def test_osv_lookup_follows_pagination_across_multiple_pages() -> None:
    request_bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        request_bodies.append(body)
        if "page_token" not in body:
            return httpx.Response(
                200,
                json={"vulns": [{"id": "GHSA-page1"}], "next_page_token": "tok-2"},
                request=request,
            )
        return httpx.Response(
            200, json={"vulns": [{"id": "GHSA-page2"}]}, request=request
        )

    async def exercise() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            advisories = await fetch_osv_advisories(
                PackageInfo(
                    name="demo", registry=Registry.PYPI, latest_version="2.0.0"
                ),
                client=client,
            )

        assert [a.id for a in advisories] == ["GHSA-page1", "GHSA-page2"]
        assert len(request_bodies) == 2
        assert "page_token" not in request_bodies[0]
        assert request_bodies[1]["page_token"] == "tok-2"

    asyncio.run(exercise())


def test_osv_lookup_stops_paginating_at_the_safety_cap() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            200,
            json={
                "vulns": [{"id": f"GHSA-{request_count}"}],
                "next_page_token": "always-more",
            },
            request=request,
        )

    async def exercise() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            advisories = await fetch_osv_advisories(
                PackageInfo(
                    name="demo", registry=Registry.PYPI, latest_version="2.0.0"
                ),
                client=client,
            )
        assert len(advisories) == security._OSV_MAX_PAGES
        assert request_count == security._OSV_MAX_PAGES

    asyncio.run(exercise())


def test_osv_lookup_skips_unsupported_registry() -> None:
    async def exercise() -> None:
        async with httpx.AsyncClient() as client:
            advisories = await fetch_osv_advisories(
                PackageInfo(
                    name="demo", registry=Registry.HOMEBREW, latest_version="1.0"
                ),
                client=client,
            )
        assert advisories == []

    asyncio.run(exercise())
