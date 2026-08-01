import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import secchi.mcp_server as mcp_server
from secchi.aggregate import package_key
from secchi.models import (
    DerivedPackageData,
    HealthScore,
    PackageInfo,
    PackageRef,
    Registry,
    SearchResult,
)
from secchi.services.intelligence import IntelligenceResult, ProjectIntelligence


def _result(ref: PackageRef, health: int = 88, *, has_ci: bool = True) -> IntelligenceResult:
    info = PackageInfo(name=ref.name, registry=ref.registry, latest_version="1.2.3")
    info.github_stats.has_ci = has_ci
    derived = DerivedPackageData(health_score=HealthScore(total=health))
    return IntelligenceResult(ref=ref, info=info, derived=derived)


def service_project(ref: PackageRef, result: IntelligenceResult) -> ProjectIntelligence:
    return ProjectIntelligence(results={package_key(ref): result})


class FakeIntelligenceService:
    result: IntelligenceResult | None = None

    async def fetch_project(
        self, refs: list[PackageRef], *, force_refresh: bool = False
    ) -> ProjectIntelligence:
        assert force_refresh is True
        result = self.result or _result(refs[0])
        return ProjectIntelligence(
            results={package_key(result.ref): result},
        )


def test_inspect_package_returns_structured_package_data(monkeypatch: pytest.MonkeyPatch) -> None:
    ref = PackageRef("duckdb", Registry.PYPI)
    service = FakeIntelligenceService()
    service.result = _result(ref)
    async def fake_inspect(refs, *, refresh=False):
        return service_project(ref, service.result)

    monkeypatch.setattr(mcp_server.inspect_workflow, "run", fake_inspect)
    monkeypatch.setattr(
        mcp_server,
        "_resolve_refs",
        lambda package, registry: _async_refs([ref]),
    )

    result = asyncio.run(mcp_server.inspect_package("duckdb", refresh=True))

    assert result["query"] == "duckdb"
    assert result["matches"][0]["package_info"]["latest_version"] == "1.2.3"
    assert result["matches"][0]["derived"]["health_score"]["total"] == 88


def test_inspect_package_reports_no_exact_match(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_refs(package: str, registry: str | None) -> list[PackageRef]:
        return []

    monkeypatch.setattr(mcp_server, "_resolve_refs", no_refs)

    result = asyncio.run(mcp_server.inspect_package("unknown"))

    assert result == {
        "query": "unknown",
        "matches": [],
        "message": "No exact package matches found.",
    }


def test_search_packages_normalizes_ranked_results(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSearch:
        async def search(self, query: str, *, registries, limit: int) -> list[SearchResult]:
            assert query == "duckdb"
            assert registries == [Registry.PYPI]
            assert limit == 5
            return [
                SearchResult(
                    name="duckdb",
                    registry=Registry.PYPI,
                    version="1.2.3",
                    description="Analytical database",
                    score=100,
                    exact=True,
                )
            ]

    async def fake_search(query, *, registry=None, limit=10):
        assert query == "duckdb"
        assert registry == "pypi"
        assert limit == 5
        return await FakeSearch().search(
            query, registries=[Registry.PYPI], limit=limit
        )

    monkeypatch.setattr(mcp_server.search_workflow, "run", fake_search)

    result = asyncio.run(mcp_server.search_packages("duckdb", registry="pypi", limit=5))

    assert result["results"] == [
        {
            "name": "duckdb",
            "registry": "pypi",
            "version": "1.2.3",
            "description": "Analytical database",
            "score": 100,
            "exact": True,
        }
    ]


def test_search_packages_rejects_invalid_limit() -> None:
    with pytest.raises(ValueError, match="between 1 and 50"):
        asyncio.run(mcp_server.search_packages("duckdb", limit=51))


def test_inspect_project_uses_config_and_json_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = tmp_path / "secchi.toml"
    config.write_text(
        """[projects.demo]
title = "Demo Project"
packages = [{ name = "demo", registry = "pypi" }]
"""
    )
    ref = PackageRef("demo", Registry.PYPI, project_name="demo")
    service = FakeIntelligenceService()
    service.result = _result(ref)
    async def fake_report(**kwargs):
        return SimpleNamespace(
            content=json.dumps(
                {
                    "generated_by": "Secchi",
                    "project": {"title": "Demo Project"},
                    "summary": {"source_count": 1},
                }
            )
        )

    monkeypatch.setattr(mcp_server.report_workflow, "run", fake_report)

    result = asyncio.run(mcp_server.inspect_project("demo", config=str(config), refresh=True))

    assert result["generated_by"] == "Secchi"
    assert result["project"]["title"] == "Demo Project"
    assert result["summary"]["source_count"] == 1


def test_check_package_returns_policy_results(monkeypatch: pytest.MonkeyPatch) -> None:
    ref = PackageRef("demo", Registry.PYPI)
    service = FakeIntelligenceService()
    service.result = _result(ref, health=65, has_ci=False)
    async def fake_check(ref, **kwargs):
        checks = [
            SimpleNamespace(name="minimum health score", passed=False, detail="65 / 100"),
            SimpleNamespace(name="continuous integration", passed=False, detail="No workflow"),
        ]
        return SimpleNamespace(passed=False, checks=checks, warnings=[])

    monkeypatch.setattr(mcp_server.check_workflow, "run", fake_check)
    monkeypatch.setattr(
        mcp_server,
        "_resolve_refs",
        lambda package, registry: _async_refs([ref]),
    )

    result = asyncio.run(
        mcp_server.check_package(
            "demo", min_health=70, require_ci=True, refresh=True
        )
    )

    assert result["matches"][0]["passed"] is False
    assert {check["name"] for check in result["matches"][0]["checks"]} == {
        "minimum health score",
        "continuous integration",
    }


def test_compare_packages_returns_ranked_recommendation(monkeypatch: pytest.MonkeyPatch) -> None:
    refs = [PackageRef("one", Registry.PYPI), PackageRef("two", Registry.PYPI)]

    async def fake_compare(packages, *, registry=None, refresh=False):
        assert packages == ["one", "two"]
        assert refresh is True
        from secchi.services.comparison import compare_intelligence

        return compare_intelligence([
            _result(refs[0], health=70),
            _result(refs[1], health=92),
        ])

    monkeypatch.setattr(mcp_server.compare_workflow, "run", fake_compare)
    result = asyncio.run(mcp_server.compare_packages(["one", "two"], refresh=True))

    assert result["winner"]["package"] == "two"
    assert result["candidates"][0]["recommendation"] in {
        "Recommended",
        "Acceptable",
        "Use with caution",
    }


async def _async_refs(refs: list[PackageRef]) -> list[PackageRef]:
    return refs
