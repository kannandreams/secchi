from datetime import datetime, timedelta, timezone

from secchi.derived import (
    compute_activity_timeline,
    compute_all,
    compute_downloads_30d,
    compute_health_score,
    compute_install_breakdown,
    compute_release_adoption,
    compute_reverse_dependency_summary,
)
from secchi.models import (
    DownloadCounts,
    DownloadTrendPoint,
    GitHubIssueEvent,
    PackageInfo,
    Registry,
    Version,
)


def _days_ago(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def test_health_score_breaks_down_project_signals() -> None:
    info = PackageInfo(
        name="demo",
        registry=Registry.PYPI,
        homepage="https://example.test",
        documentation_url="https://docs.example.test",
        repository_url="https://github.com/example/demo",
        latest_release_date=_days_ago(10),
        versions=[Version("1.0.0", release_date=_days_ago(20))] * 3,
    )
    info.github_stats.resolved = True
    info.github_stats.has_ci = True
    info.github_stats.has_readme = True
    info.github_stats.stars = 2_000
    info.github_stats.forks = 200

    score = compute_health_score(info)

    assert score.total > 0
    assert score.grade in {"A", "B", "C", "D", "F"}
    assert {item.label for item in score.sub_scores} == {
        "Maintenance",
        "Community",
        "Documentation",
        "Releases",
        "Security",
        "Testing",
    }


def test_release_adoption_slices_downloads_by_version_window() -> None:
    info = PackageInfo(
        name="demo",
        registry=Registry.PYPI,
        versions=[
            Version("2.0.0", release_date=_days_ago(5)),
            Version("1.0.0", release_date=_days_ago(15)),
        ],
        download_trend=[
            DownloadTrendPoint((_days_ago(12)).date().isoformat(), 20),
            DownloadTrendPoint((_days_ago(4)).date().isoformat(), 80),
        ],
    )

    adoption, caption = compute_release_adoption(info)

    assert adoption["2.0.0"] == 80.0
    assert adoption["1.0.0"] == 20.0
    assert "Estimated" in caption


def test_install_breakdown_uses_monthly_activity_then_total() -> None:
    info = PackageInfo(name="demo", registry=Registry.NPM)
    info.download_counts.month = 120

    breakdown = compute_install_breakdown(info)

    assert breakdown.methods[0].label == "npm"
    assert breakdown.methods[0].count == 120
    assert breakdown.methods[0].percent == 100.0


def test_reverse_dependency_summary_explains_missing_data() -> None:
    info = PackageInfo(name="demo", registry=Registry.PYPI)
    unavailable = compute_reverse_dependency_summary(info)
    info.reverse_dependency_count = 12
    available = compute_reverse_dependency_summary(info)

    assert "unavailable" in unavailable.caption
    assert available.count == 12
    assert available.caption == "Projects depending on this package."


def test_activity_timeline_contains_releases_and_issue_lifecycle() -> None:
    info = PackageInfo(
        name="demo",
        registry=Registry.PYPI,
        versions=[Version("1.0.0", release_date=_days_ago(3))],
        github_issue_events=[
            GitHubIssueEvent(
                number=1,
                title="Fix bug",
                is_pull_request=False,
                created_at=_days_ago(2),
                closed_at=_days_ago(1),
                url="https://example.test/issues/1",
            )
        ],
    )

    events = compute_activity_timeline(info)

    assert len(events) == 3
    assert events[0].ref == "#1"
    assert events[-1].ref == "1.0.0"


def test_downloads_30d_returns_change_and_handles_empty_history() -> None:
    info = PackageInfo(
        name="demo",
        registry=Registry.PYPI,
        download_trend=[
            DownloadTrendPoint(str(index), 10 if index < 30 else 20)
            for index in range(60)
        ],
    )

    total, change = compute_downloads_30d(info)
    empty_total, empty_change = compute_downloads_30d(
        PackageInfo(name="empty", registry=Registry.PYPI)
    )

    assert total == 600
    assert change == 100.0
    assert empty_total == 0
    assert empty_change is None


def test_compute_all_combines_dashboard_metrics() -> None:
    info = PackageInfo(
        name="demo",
        registry=Registry.PYPI,
        download_counts=DownloadCounts(month=4),
    )

    derived = compute_all(info)

    assert derived.downloads_30d_total == 4
    assert derived.install_breakdown.methods[0].count == 4
