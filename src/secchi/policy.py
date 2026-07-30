"""Small, explicit policy evaluation primitives for automation workflows."""

from __future__ import annotations

from dataclasses import dataclass

from secchi.models import DerivedPackageData, PackageInfo


@dataclass(frozen=True)
class PolicyResult:
    name: str
    passed: bool
    detail: str


def evaluate_default_policy(
    info: PackageInfo,
    derived: DerivedPackageData,
    *,
    min_health: int = 70,
    require_ci: bool = False,
) -> list[PolicyResult]:
    results = [
        PolicyResult(
            "minimum health score",
            derived.health_score.total >= min_health,
            f"{derived.health_score.total} / 100 (minimum {min_health})",
        )
    ]
    if require_ci:
        results.append(
            PolicyResult(
                "continuous integration",
                info.github_stats.has_ci,
                "GitHub workflow detected" if info.github_stats.has_ci else "No GitHub workflow detected",
            )
        )
    return results
