import asyncio
from datetime import date, timedelta

from textual.app import App, ComposeResult

from secchi.models import DownloadTrendPoint, MetricTimelinePoint, PackageInfo, Registry
from secchi.ui.widgets.overview import (
    AdoptionTrendBody,
    AdoptionTrendPanel,
    EcosystemDistributionPanel,
    HealthScorePanel,
    HealthTimelinePanel,
    OverviewTab,
    ReverseDependenciesPanel,
    VersionAdoptionPanel,
    _adoption_points,
    _point_limit,
    _render_line_chart,
    _trend_label,
)


def _daily_points(count: int = 30) -> list[DownloadTrendPoint]:
    start = date(2026, 1, 1)
    return [
        DownloadTrendPoint(
            date=(start + timedelta(days=index)).isoformat(), count=100 + index * 10
        )
        for index in range(count)
    ]


def test_overview_mounts_the_six_dashboard_panels_in_order() -> None:
    info = PackageInfo(name="demo", registry=Registry.PYPI)
    tab = OverviewTab(info, derived=_derived())

    class Harness(App[None]):
        def compose(self) -> ComposeResult:
            yield tab

    async def run_check() -> None:
        harness = Harness()
        async with harness.run_test(size=(120, 40)):
            assert harness.query_one("#overview-grid")
            assert [type(panel) for panel in harness.query("Panel")] == [
                AdoptionTrendPanel,
                HealthScorePanel,
                EcosystemDistributionPanel,
                ReverseDependenciesPanel,
                HealthTimelinePanel,
                VersionAdoptionPanel,
            ]

    asyncio.run(run_check())


def test_adoption_trend_aggregates_and_keeps_latest_period() -> None:
    points = _daily_points(365)

    daily = _adoption_points(points, 30, 12)
    weekly = _adoption_points(points, 90, 8)
    monthly = _adoption_points(points, 365, 12)

    assert len(daily) == 12
    assert len(weekly) <= 8
    assert len(monthly) <= 12
    assert daily[-1].value == points[-1].count
    assert weekly[-1].value > 0
    assert monthly[-1].label == "Dec"


def test_adoption_trend_responsive_limits_and_interpretation() -> None:
    assert _point_limit(40) == 5
    assert _point_limit(60) == 8
    assert _point_limit(90) == 12
    assert (
        _trend_label(
            18.3, [MetricTimelinePoint("Jan", 1), MetricTimelinePoint("Feb", 2)]
        )
        == "Growing"
    )
    assert (
        _trend_label(
            -18.3, [MetricTimelinePoint("Jan", 2), MetricTimelinePoint("Feb", 1)]
        )
        == "Declining"
    )
    assert (
        _trend_label(
            2.0, [MetricTimelinePoint("Jan", 1), MetricTimelinePoint("Feb", 1)]
        )
        == "Stable"
    )


def test_line_chart_contains_connected_observations_and_labels() -> None:
    chart = _render_line_chart(
        [
            MetricTimelinePoint("Jan", 10),
            MetricTimelinePoint("Feb", 20),
            MetricTimelinePoint("Mar", 15),
        ],
        width=40,
        height=4,
        line_color="#00ff00",
    )

    assert "Jan" in chart
    assert "Mar" in chart
    assert "●" in chart
    assert any(char in chart for char in (chr(0x2571), chr(0x2572)))


def test_overview_widgets_have_explicit_empty_states() -> None:
    info = PackageInfo(name="demo", registry=Registry.PYPI)
    trend_body = AdoptionTrendBody(info, 30)
    trend_body._update_content()
    assert "No historical adoption data available" in str(trend_body.render())

    assert "No ecosystem download data available" in str(
        EcosystemDistributionPanel(info, _derived()).compose_body()[0].render()
    )
    assert "No reverse-dependency data available" in str(
        ReverseDependenciesPanel(info, _derived()).compose_body()[0].render()
    )


def _derived():
    from secchi.models import DerivedPackageData

    return DerivedPackageData()
