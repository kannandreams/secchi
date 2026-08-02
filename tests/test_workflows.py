import asyncio

from secchi.models import (
    DerivedPackageData,
    HealthScore,
    PackageInfo,
    PackageRef,
    Registry,
)
from secchi.services.intelligence import IntelligenceResult
from secchi.workflows import check, dashboard


def test_dashboard_workflow_resolves_workspace_config(tmp_path) -> None:
    config = tmp_path / "secchi.toml"
    config.write_text(
        """[projects.demo]
title = "Demo"
packages = [{ name = "duckdb", registry = "pypi" }]
"""
    )

    request = asyncio.run(dashboard.run(config=str(config)))

    assert request.project.name == "Workspace"
    assert request.workspace is not None
    assert request.workspace[0].name == "demo"
    assert request.project.packages[0].name == "duckdb"


def test_check_workflow_returns_structured_policy_result(monkeypatch) -> None:
    ref = PackageRef("demo", Registry.PYPI)
    info = PackageInfo(name="demo", registry=Registry.PYPI, latest_version="1.0.0")
    intelligence = IntelligenceResult(
        ref=ref,
        info=info,
        derived=DerivedPackageData(health_score=HealthScore(total=85)),
    )

    async def fake_require_package(ref, refresh=False):
        return intelligence

    monkeypatch.setattr(check, "require_package", fake_require_package)
    result = asyncio.run(check.run(ref, min_health=80))

    assert result.passed is True
    assert result.checks[0].name == "minimum health score"
