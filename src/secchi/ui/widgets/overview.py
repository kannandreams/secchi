"""Overview tab: a compact 3 x 2 package-intelligence dashboard."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from itertools import pairwise

from rich.markup import escape
from textual import on
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.events import Resize
from textual.widget import Widget
from textual.widgets import Button, Static

from secchi.models import (
    DerivedPackageData,
    DownloadTrendPoint,
    MetricTimelinePoint,
    PackageInfo,
    Registry,
)
from secchi.ui import palette
from secchi.ui.widgets.bar import render_bar
from secchi.ui.widgets.panel import Panel
from secchi.utils import format_pct_delta, shorten_number

_RANGES: tuple[tuple[str, int], ...] = (("30d", 30), ("90d", 90), ("1y", 365))


def _downloads_source(registry: Registry) -> str:
    return {
        Registry.CRATES: "Source: crates.io",
        Registry.PYPI: "Source: PyPI (via pypistats)",
        Registry.NPM: "Source: npm registry",
    }[registry]


def _source_registries(info: PackageInfo) -> list[Registry]:
    return info.source_registries or [info.registry]


class OverviewTab(Vertical):
    """Composes the Overview dashboard into a two-row, three-column grid."""

    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        super().__init__(id="overview-tab")
        self._info = info
        self._derived = derived
        self._range_days = 30

    def compose(self) -> ComposeResult:
        with Horizontal(id="overview-range"):
            yield Static("Range", classes="overview-range-label")
            for label, days in _RANGES:
                classes = "overview-range-button"
                if days == self._range_days:
                    classes += " overview-range-button--active"
                yield Button(label, id=f"overview-range-{days}", classes=classes)

        with Grid(id="overview-grid"):
            yield AdoptionTrendPanel(self._info, self._derived, self._range_days)
            yield HealthScorePanel(self._info, self._derived)
            yield EcosystemDistributionPanel(self._info, self._derived)
            yield ReverseDependenciesPanel(self._info, self._derived)
            yield HealthTimelinePanel(self._info, self._derived)
            yield VersionAdoptionPanel(self._info, self._derived)

    @on(Button.Pressed, ".overview-range-button")
    def _on_range_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        prefix = "overview-range-"
        if not button_id.startswith(prefix):
            return
        try:
            self._range_days = int(button_id.removeprefix(prefix))
        except ValueError:
            return
        event.stop()
        self.refresh(recompose=True)


class AdoptionTrendPanel(Panel):
    def __init__(
        self,
        info: PackageInfo,
        derived: DerivedPackageData,
        range_days: int,
    ) -> None:
        self._info = info
        self._range_days = range_days
        registries = _source_registries(info)
        caption = (
            "Source: combined registry downloads"
            if len(registries) > 1
            else _downloads_source(info.registry)
        )
        super().__init__("ADOPTION TREND", caption=caption)

    def compose_body(self) -> list[Widget]:
        return [AdoptionTrendBody(self._info, self._range_days)]


class AdoptionTrendBody(Static):
    def __init__(self, info: PackageInfo, range_days: int) -> None:
        super().__init__("", classes="ov-chart-block")
        self._info = info
        self._range_days = range_days

    def on_mount(self) -> None:
        self._update_content()

    def on_resize(self, event: Resize) -> None:
        self._update_content()

    def _update_content(self) -> None:
        width = self.size.width or 36
        max_points = _point_limit(width)
        points = _adoption_points(
            self._info.download_trend, self._range_days, max_points
        )
        if len(points) < 2:
            self.update("[dim]No historical adoption data available.[/]")
            return

        total, pct = _period_download_summary(
            self._info.download_trend, self._range_days
        )
        trend = _trend_label(pct, points)
        trend_color = palette.RED if trend == "Declining" else palette.GREEN
        pct_text, pct_color = format_pct_delta(pct)
        period_label = _range_label(self._range_days)
        chart = _render_line_chart(
            points,
            width=width,
            height=max(3, min(6, self.size.height - 4)),
            line_color=trend_color,
        )
        self.update(
            "\n".join(
                [
                    chart,
                    f"[dim]{period_label} Downloads[/]",
                    f"[b]{shorten_number(total)}[/] [{pct_color}]{pct_text} vs previous period[/]",
                    f"Trend: [{trend_color}]{trend}[/]",
                ]
            )
        )


class HealthScorePanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._health = derived.health_score
        super().__init__(
            f"HEALTH SCORE ({self._health.total} / 100)",
            caption="Derived from package signals",
        )

    def compose_body(self) -> list[Widget]:
        rows: list[Widget] = []
        for sub in self._health.sub_scores:
            frac = sub.score / sub.max_score if sub.max_score else 0
            bar = render_bar(frac, width=10)
            rows.append(
                Static(
                    f"[dim]{sub.label:<13}[/] {bar} "
                    f"[b]{sub.score:>2}/{sub.max_score:<2}[/]"
                )
            )
        rows.append(Static(f"\n[dim]Signal:[/] {_health_signal(self._health.total)}"))
        return rows


class EcosystemDistributionPanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._breakdown = derived.install_breakdown
        super().__init__("ECOSYSTEM DISTRIBUTION", caption=self._breakdown.caption)

    def compose_body(self) -> list[Widget]:
        methods = self._breakdown.methods
        if not methods:
            return [Static("[dim]No ecosystem download data available.[/]")]

        rows: list[Widget] = []
        for method in methods[:5]:
            label = _clip(method.label, 12)
            bar = render_bar(method.percent / 100, width=12)
            rows.append(Static(f"{label:<12} {bar} [b]{method.percent:>4.0f}%[/]"))

        primary = methods[0]
        sources = ", ".join(method.label for method in methods)
        rows.append(
            Static(
                f"\n[dim]Sources:[/] {escape(sources)}\n"
                f"[dim]Signal:[/] Highest observed activity: {escape(primary.label)}."
            )
        )
        return rows


class ReverseDependenciesPanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._summary = derived.reverse_dependency_summary
        super().__init__("REVERSE DEPENDENCIES", caption=self._summary.caption)

    def compose_body(self) -> list[Widget]:
        if self._summary.count is None:
            return [Static("[dim]No reverse-dependency data available.[/]")]

        growth = self._summary.monthly_growth
        if growth is None:
            growth_line = "[dim]Monthly growth: —[/]"
            signal = "Growth baseline will appear after future snapshots."
        else:
            color = palette.GREEN if growth >= 0 else palette.RED
            sign = "+" if growth >= 0 else ""
            growth_line = f"[{color}]▲ {sign}{shorten_number(growth)} this month[/]"
            signal = (
                "Library adoption is accelerating."
                if growth > 0
                else "Library adoption is stable."
                if growth == 0
                else "Library adoption is contracting."
            )

        return [
            Static("[dim]Projects depending on this package[/]"),
            Static(
                f"[b {palette.GREEN}]{shorten_number(self._summary.count)}[/]",
                classes="ov-big-number",
            ),
            Static(growth_line),
            Static(f"\n[dim]Signal:[/] {signal}"),
        ]


class HealthTimelinePanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._points = derived.health_timeline
        super().__init__("HEALTH TIMELINE", caption="Monthly health score")

    def compose_body(self) -> list[Widget]:
        return [HealthTimelineBody(self._points)]


class HealthTimelineBody(Static):
    def __init__(self, points: list[MetricTimelinePoint]) -> None:
        super().__init__("", classes="ov-chart-block")
        self._points = points

    def on_mount(self) -> None:
        self._update_content()

    def on_resize(self, event: Resize) -> None:
        self._update_content()

    def _update_content(self) -> None:
        width = self.size.width or 36
        points = self._points[-_point_limit(width) :]
        if len(points) < 2:
            self.update("[dim]Health history will appear after future snapshots.[/]")
            return

        delta = points[-1].value - points[0].value
        trend = (
            "Stable" if abs(delta) <= 3 else "Improving" if delta > 0 else "Declining"
        )
        color = palette.RED if trend == "Declining" else palette.GREEN
        chart = _render_line_chart(
            points,
            width=width,
            height=max(3, min(6, self.size.height - 3)),
            line_color=color,
            value_floor=0,
            value_ceiling=100,
        )
        sign = "+" if delta > 0 else ""
        self.update(
            "\n".join(
                [
                    chart,
                    f"Trend: [{color}]{trend}[/]",
                    f"[dim]{sign}{delta} points since {escape(points[0].label)}[/]",
                ]
            )
        )


class VersionAdoptionPanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._info = info
        self._derived = derived
        caption = derived.adoption_caption or "% = adoption download share"
        super().__init__("VERSION ADOPTION", caption=caption)

    def compose_body(self) -> list[Widget]:
        adoption = self._derived.release_adoption
        if not self._info.versions or not adoption:
            return [Static("[dim]No version adoption data available.[/]")]

        rows: list[Widget] = []
        shown_total = 0.0
        for ver in self._info.versions[:4]:
            pct = adoption.get(ver.version, 0.0)
            shown_total += pct
            label = f"v{_clip(ver.version, 8)}"
            rows.append(_version_bar(label, pct))

        older = max(0.0, 100.0 - shown_total)
        if older >= 0.5:
            rows.append(_version_bar("Older", older))

        latest = adoption.get(self._info.versions[0].version, 0.0)
        summary = (
            "Healthy" if latest >= 50 else "Fragmented" if latest >= 25 else "Lagging"
        )
        rows.append(Static(f"\n[dim]Latest version adoption:[/] {summary}"))
        return rows


def _version_bar(label: str, pct: float) -> Static:
    bar = render_bar(pct / 100, width=14)
    return Static(f"{escape(label):<9} {bar} [b]{pct:>4.0f}%[/]")


def _adoption_points(
    trend: list[DownloadTrendPoint],
    days: int,
    max_points: int,
) -> list[MetricTimelinePoint]:
    recent = trend[-days:] if len(trend) > days else trend[:]
    if days <= 30:
        points = [
            MetricTimelinePoint(label=_short_date_label(p.date), value=p.count)
            for p in recent
        ]
    elif days <= 90:
        points = _bucket_by_week(recent)
    else:
        points = _bucket_by_month(recent)
    return _thin_points(points, max_points)


def _bucket_by_week(points: list[DownloadTrendPoint]) -> list[MetricTimelinePoint]:
    buckets: dict[tuple[int, int], int] = defaultdict(int)
    labels: dict[tuple[int, int], str] = {}
    for point in points:
        parsed = _parse_day(point.date)
        if parsed is None:
            continue
        year, week, _ = parsed.isocalendar()
        key = (year, week)
        buckets[key] += point.count
        labels[key] = f"W{week:02d}"
    return [
        MetricTimelinePoint(label=labels[key], value=buckets[key])
        for key in sorted(buckets)
    ]


def _bucket_by_month(points: list[DownloadTrendPoint]) -> list[MetricTimelinePoint]:
    buckets: dict[str, int] = defaultdict(int)
    for point in points:
        parsed = _parse_day(point.date)
        if parsed is None:
            continue
        buckets[parsed.strftime("%Y-%m")] += point.count
    return [
        MetricTimelinePoint(label=_short_month(key), value=buckets[key])
        for key in sorted(buckets)
    ]


def _thin_points(
    points: list[MetricTimelinePoint],
    max_points: int,
) -> list[MetricTimelinePoint]:
    if len(points) <= max_points:
        return points
    if max_points <= 1:
        return points[-1:]
    step = (len(points) - 1) / (max_points - 1)
    indexes = {round(i * step) for i in range(max_points)}
    indexes.add(len(points) - 1)
    return [points[i] for i in sorted(indexes)][-max_points:]


def _period_download_summary(
    trend: list[DownloadTrendPoint],
    days: int,
) -> tuple[int, float | None]:
    if not trend:
        return 0, None
    current_len = min(days, len(trend))
    current = sum(point.count for point in trend[-current_len:])
    previous_slice = trend[-(current_len * 2) : -current_len]
    previous = sum(point.count for point in previous_slice)
    if previous <= 0:
        return current, None
    return current, (current - previous) / previous * 100


def _trend_label(
    pct: float | None,
    points: list[MetricTimelinePoint],
) -> str:
    if pct is None:
        first = points[0].value
        last = points[-1].value
        pct = None if first <= 0 else (last - first) / first * 100
    if pct is None or abs(pct) < 5:
        return "Stable"
    return "Growing" if pct > 0 else "Declining"


def _render_line_chart(
    points: list[MetricTimelinePoint],
    *,
    width: int,
    height: int,
    line_color: str,
    value_floor: int | None = None,
    value_ceiling: int | None = None,
) -> str:
    values = [p.value for p in points]
    lo = min(values) if value_floor is None else value_floor
    hi = max(values) if value_ceiling is None else value_ceiling
    if lo == hi:
        hi = lo + 1

    left_width = max(4, min(6, max(len(shorten_number(hi)), len(shorten_number(lo)))))
    plot_width = max(4, width - left_width - 3)
    chart_height = max(3, height)
    grid = [[" " for _ in range(plot_width)] for _ in range(chart_height)]
    coords: list[tuple[int, int]] = []

    for index, point in enumerate(points):
        x = round(index * (plot_width - 1) / max(len(points) - 1, 1))
        ratio = (point.value - lo) / (hi - lo)
        y = chart_height - 1 - round(ratio * (chart_height - 1))
        coords.append((x, y))

    for start, end in pairwise(coords):
        _draw_segment(grid, start, end)
    for x, y in coords:
        grid[y][x] = "●"

    lines: list[str] = []
    for row, cells in enumerate(grid):
        value = round(hi - (hi - lo) * row / max(chart_height - 1, 1))
        axis = "┤" if row < chart_height - 1 else "└"
        label = f"{shorten_number(value):>{left_width}}"
        lines.append(
            f"[{palette.SEPARATOR}]{label} {axis}[/][{line_color}]{''.join(cells)}[/]"
        )

    label_row = [" " for _ in range(plot_width)]
    occupied: set[int] = set()
    for index, (x, _) in enumerate(coords):
        label = points[index].label
        if index not in (0, len(coords) - 1) and plot_width < len(coords) * 5:
            continue
        start = min(max(0, x - len(label) // 2), max(0, plot_width - len(label)))
        slots = set(range(start, start + len(label)))
        if slots & occupied:
            continue
        occupied.update(slots)
        for offset, char in enumerate(label):
            label_row[start + offset] = char
    lines.append(
        " " * (left_width + 2)
        + f"[{palette.TEXT_MUTED}]{''.join(label_row).rstrip()}[/]"
    )
    return "\n".join(lines)


def _draw_segment(
    grid: list[list[str]],
    start: tuple[int, int],
    end: tuple[int, int],
) -> None:
    x0, y0 = start
    x1, y1 = end
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    prev = start
    for step in range(steps + 1):
        x = round(x0 + (x1 - x0) * step / steps)
        y = round(y0 + (y1 - y0) * step / steps)
        if (x, y) == start or (x, y) == end:
            continue
        dy = y - prev[1]
        grid[y][x] = "─" if dy == 0 else chr(0x2571) if dy < 0 else chr(0x2572)
        prev = (x, y)


def _point_limit(width: int) -> int:
    if width < 48:
        return 5
    if width < 72:
        return 8
    return 12


def _parse_day(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw).replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _short_date_label(raw: str) -> str:
    parts = raw.split("-")
    if len(parts) == 3:
        return f"{parts[1]}/{parts[2]}"
    return raw[-5:] if len(raw) > 5 else raw


def _short_month(raw: str) -> str:
    parts = raw.split("-")
    if len(parts) == 2:
        month = int(parts[1])
        return datetime(2000, month, 1).strftime("%b")
    return raw


def _range_label(days: int) -> str:
    if days <= 30:
        return "30d"
    if days <= 90:
        return "90d"
    return "1y"


def _clip(value: str, max_len: int) -> str:
    return value if len(value) <= max_len else value[: max_len - 1] + "…"


def _health_signal(total: int) -> str:
    if total >= 85:
        return "Well maintained."
    if total >= 65:
        return "Generally healthy."
    if total >= 45:
        return "Mixed maintenance signals."
    return "Needs attention."
