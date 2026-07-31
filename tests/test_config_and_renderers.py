import asyncio
from pathlib import Path

from secchi.config import load_project
from secchi.aggregate import package_key
from secchi.models import DerivedPackageData, HealthScore, PackageInfo, PackageRef, Registry
from secchi.policy import evaluate_default_policy
from secchi.renderers.summary import render_summary
from secchi.services.search import PackageSearchService
from secchi.services.resolver import parse_package_spec, resolve_package
from secchi.models import SearchResult


def test_project_favorite_is_applied_to_package_refs(tmp_path: Path) -> None:
    config = tmp_path / "secchi.toml"
    config.write_text(
        """[projects.demo]
favorite = true
title = "Demo Project"
repository = "https://example.test/repo"
packages = [{ name = "demo", registry = "pypi" }]
"""
    )
    project = load_project(config, "demo")
    assert project.favorite is True
    assert project.title == "Demo Project"
    assert project.repository_url == "https://example.test/repo"
    assert project.packages[0].favorite is True
    assert project.packages[0].project_name == "demo"


def test_workspace_package_keys_keep_same_name_projects_separate() -> None:
    first = PackageRef("shared", Registry.PYPI, project_name="first")
    second = PackageRef("shared", Registry.PYPI, project_name="second")
    assert package_key(first) != package_key(second)


def test_registry_prefixed_package_spec() -> None:
    ref = parse_package_spec("npm:duckdb")
    assert ref == PackageRef(name="duckdb", registry=Registry.NPM)


def test_resolver_prefers_configured_registry_sources() -> None:
    refs = asyncio.run(
        resolve_package(
            "duckdb",
            configured_refs=[
                PackageRef("duckdb", Registry.PYPI),
                PackageRef("duckdb", Registry.NPM),
            ],
        )
    )
    assert [ref.registry for ref in refs] == [Registry.PYPI, Registry.NPM]


def test_summary_includes_primary_signals() -> None:
    info = PackageInfo(name="duckdb", registry=Registry.PYPI, latest_version="1.5.5")
    info.github_stats.resolved = True
    info.github_stats.stars = 34_000
    derived = DerivedPackageData(health_score=HealthScore(total=92))
    output = render_summary(info, derived)
    assert "Health Score      92 / 100" in output
    assert "Latest Version    1.5.5" in output
    assert "GitHub Stars      34.0k" in output


def test_default_policy_reports_a_failed_health_threshold() -> None:
    info = PackageInfo(name="demo", registry=Registry.PYPI)
    results = evaluate_default_policy(
        info, DerivedPackageData(health_score=HealthScore(total=69)), min_health=70
    )
    assert results[0].passed is False


def test_search_service_prioritizes_exact_matches_and_survives_registry_errors(monkeypatch) -> None:
    class FakeAdapter:
        def __init__(self, registry: Registry) -> None:
            self.registry = registry

        async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
            if self.registry is Registry.NPM:
                raise RuntimeError("registry unavailable")
            return [
                SearchResult(
                    name="duckdb-tools", registry=self.registry, score=100_000
                ),
                SearchResult(name=query, registry=self.registry, exact=True, score=1),
            ]

    monkeypatch.setattr(
        "secchi.services.search.create_adapter",
        lambda registry: FakeAdapter(registry),
    )
    results = asyncio.run(
        PackageSearchService().search("duckdb", registries=[Registry.PYPI, Registry.NPM])
    )
    assert results[0].name == "duckdb"
    assert all(result.registry is Registry.PYPI for result in results)
