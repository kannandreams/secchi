from datetime import datetime, timezone

from secchi.models import (
    DerivedPackageData,
    DownloadCounts,
    GitHubStats,
    HealthScore,
    PackageInfo,
    PackageRef,
    Registry,
    Version,
)
from secchi.services.comparison import Recommendation, compare_intelligence
from secchi.services.intelligence import IntelligenceResult


def _result(name: str, health: int, change: float, stars: int) -> IntelligenceResult:
    ref = PackageRef(name, Registry.PYPI)
    info = PackageInfo(
        name=name,
        registry=Registry.PYPI,
        latest_version="1.0.0",
        latest_release_date=datetime.now(timezone.utc),
        download_counts=DownloadCounts(month=100),
        versions=[Version("1.0.0", datetime.now(timezone.utc))],
        dependencies=[ ],
        repository_url=f"https://github.com/example/{name}",
    )
    info.github_stats = GitHubStats(stars=stars, resolved=True, has_ci=True)
    derived = DerivedPackageData(
        health_score=HealthScore(total=health),
        downloads_30d_pct_change=change,
    )
    return IntelligenceResult(ref=ref, info=info, derived=derived)


def test_comparison_ranks_candidates_and_explains_decision() -> None:
    result = compare_intelligence([
        _result("steady", health=72, change=2, stars=100),
        _result("popular", health=92, change=18, stars=20_000),
    ])

    assert result.winner is not None
    assert result.winner.ref.name == "popular"
    assert result.winner.recommendation is Recommendation.RECOMMENDED
    assert result.winner.confidence == 0.75
    assert any("Health score" in evidence for evidence in result.winner.evidence)
    assert result.as_dict()["candidates"][0]["package"] == "popular"
    assert result.as_dict()["schema"] == "secchi.package-comparison"
    assert result.as_dict()["schema_version"] == 1


def test_comparison_marks_failed_fetch_as_avoid() -> None:
    ref = PackageRef("missing", Registry.PYPI)
    result = compare_intelligence([
        IntelligenceResult(ref=ref, error=Exception("not used")),
    ])

    assert result.candidates[0].recommendation is Recommendation.AVOID
    assert result.candidates[0].score is None
