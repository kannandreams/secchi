"""Overview tab — the 3-row grid of intelligence panels from the reference mock."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static
from textual_plotext import PlotextPlot

from secchi.derived import compute_downloads_30d
from secchi.models import DerivedPackageData, PackageInfo, Registry
from secchi.ui import palette
from secchi.ui.widgets.bar import render_bar
from secchi.ui.widgets.panel import Panel
from secchi.utils import (
    derive_github_repo,
    format_age,
    format_age_short,
    format_pct_delta,
    shorten_bytes,
    shorten_number,
)


def _downloads_source(registry: Registry) -> str:
    return {
        Registry.CRATES: "Source: crates.io",
        Registry.PYPI: "Source: PyPI (via pypistats)",
        Registry.NPM: "Source: npm registry",
    }[registry]


def _source_registries(info: PackageInfo) -> list[Registry]:
    return info.source_registries or [info.registry]


def _download_date_ticks(trend: list) -> tuple[list[int], list[str]]:
    if not trend:
        return [], []
    positions = sorted({0, len(trend) // 2, len(trend) - 1})
    return positions, [_short_date_label(trend[pos].date) for pos in positions]


def _download_count_ticks(counts: list[int]) -> tuple[list[int], list[str]]:
    if not counts:
        return [], []
    lo = min(counts)
    hi = max(counts)
    if lo == hi:
        return [lo], [shorten_number(lo)]
    mid = (lo + hi) // 2
    ticks = [lo, mid, hi]
    return ticks, [shorten_number(tick) for tick in ticks]


def _short_date_label(raw: str) -> str:
    parts = raw.split("-")
    if len(parts) == 3:
        return f"{parts[1]}/{parts[2]}"
    return raw[-5:] if len(raw) > 5 else raw


class OverviewTab(Vertical):
    """Composes all overview panels into three horizontal rows."""

    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        super().__init__(id="overview-tab")
        self._info = info
        self._derived = derived

    def compose(self) -> ComposeResult:
        info, derived = self._info, self._derived
        with Horizontal(classes="overview-row"):
            yield DownloadsPanel(info, derived)
            yield HealthScorePanel(info, derived)
            yield MaintenancePanel(info, derived)
        with Horizontal(classes="overview-row"):
            yield InstallMethodsPanel(info, derived)
            yield ReleasesPanel(info, derived)
            with Horizontal(classes="overview-split"):
                yield EcosystemReachPanel(info, derived)
                yield RiskSignalsPanel(info, derived)
        with Horizontal(classes="overview-row overview-row--bottom"):
            yield ActivityPanel(info, derived, classes="panel--wide")
            yield DetailsPanel(info, derived)


class DownloadsPanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._info = info
        self._derived = derived
        registries = _source_registries(info)
        caption = (
            "Source: combined registry downloads"
            if len(registries) > 1
            else _downloads_source(info.registry)
        )
        super().__init__(
            "DOWNLOADS (last 30 days)",
            caption=caption,
        )

    def compose_body(self) -> list[Widget]:
        total, pct = self._derived.downloads_30d_total, self._derived.downloads_30d_pct_change
        text, color = format_pct_delta(pct)
        summary = (
            f"[dim]Total (30d):[/] [b]{shorten_number(total)}[/]   [{color}]{text}[/]"
        )
        return [PlotextPlot(id="ov-trend-chart"), Static(summary, classes="ov-summary")]

    def on_mount(self) -> None:
        super().on_mount()
        trend = self._info.download_trend[-30:]
        if not trend:
            return
        try:
            chart = self.query_one("#ov-trend-chart", PlotextPlot)
            plt = chart.plt
            plt.clear_data()
            plt.theme("clear")
            plt.frame(False)
            plt.axes_color(palette.SEPARATOR)
            plt.ticks_color(palette.BORDER_SECONDARY)
            plt.grid(False)
            xs = list(range(len(trend)))
            ys = [p.count for p in trend]
            plt.plot(
                xs,
                ys,
                marker="braille",
                color=palette.GREEN,
            )
            plt.xticks(*_download_date_ticks(trend))
            plt.yticks(*_download_count_ticks(ys))
            chart.refresh()
        except Exception:
            pass


class ReleasesPanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._info = info
        self._derived = derived
        caption = derived.adoption_caption or "% = adoption (downloads share)"
        super().__init__("LATEST RELEASES", caption=caption)

    def compose_body(self) -> list[Widget]:
        rows: list[Widget] = []
        adoption = self._derived.release_adoption
        for ver in self._info.versions[:5]:
            pct = adoption.get(ver.version, 0.0)
            bar = render_bar(pct / 100, width=8)
            age = format_age_short(ver.release_date)
            version = ver.version if len(ver.version) <= 8 else ver.version[:7] + "…"
            line = (
                f"[{palette.GREEN}]{version:<8}[/] [dim]{age:>4}[/] "
                f"{bar} [b]{pct:4.1f}%[/]"
            )
            rows.append(Static(line))
        if not rows:
            rows.append(Static("[dim]No release data.[/]"))
        return rows


class InstallMethodsPanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._breakdown = derived.install_breakdown
        super().__init__(
            "INSTALL METHODS (last 30 days)",
            caption=self._breakdown.caption,
        )

    def compose_body(self) -> list[Widget]:
        methods = self._breakdown.methods
        if not methods:
            return [Static("[dim]No install data available.[/]")]
        rows: list[Widget] = []
        max_count_width = max(len(shorten_number(m.count)) for m in methods)
        for m in methods:
            bar = render_bar(m.percent / 100, width=20)
            label = m.label if len(m.label) <= 15 else m.label[:14] + "…"
            count = shorten_number(m.count)
            rows.append(
                Static(
                    f"{label:<15}  {bar:<20}  "
                    f"[b]{count:>{max_count_width}}[/] [dim]({m.percent:>4.1f}%)[/]"
                )
            )
        return rows


class DetailsPanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._info = info
        super().__init__(
            "DETAILS",
            caption=f"Source: GitHub, {', '.join(r.display_name for r in _source_registries(info))}",
        )

    def compose_body(self) -> list[Widget]:
        info = self._info
        repo = derive_github_repo([info.repository_url, info.homepage])
        repo_str = f"github.com/{repo[0]}/{repo[1]}" if repo else (info.repository_url or "—")
        size = None
        for v in info.versions:
            if v.version == info.latest_version and v.size_bytes:
                size = v.size_bytes
                break
        if size is None and info.latest_release_files:
            size = sum(f.size for f in info.latest_release_files) or None

        gh = info.github_stats
        rows = [
            ("Repository", repo_str),
            ("Created", format_age(gh.created_at)),
            ("Size", shorten_bytes(size)),
            ("Docs", info.documentation_url or "—"),
        ]
        for registry in _source_registries(info):
            rows.append((registry.display_name, _short_url(_registry_url(info, registry))))
        if info.homepage and info.homepage not in (info.repository_url, info.documentation_url):
            rows.append(("Homepage", _short_url(info.homepage)))
        lines = "\n".join(f"[dim]{k:<12}[/] {v}" for k, v in rows)
        return [Static(lines)]


class MaintenancePanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._info = info
        super().__init__("MAINTENANCE", caption="Source: registry + GitHub")

    def compose_body(self) -> list[Widget]:
        info = self._info
        gh = info.github_stats
        rows = [
            ("Last Release", format_age(info.latest_release_date)),
            ("Last Commit", format_age(gh.pushed_at)),
            ("CI", "yes" if gh.has_ci else "—"),
            ("README", "yes" if gh.has_readme else "—"),
        ]
        return [Static("\n".join(f"[dim]{k:<12}[/] {v}" for k, v in rows))]


class EcosystemReachPanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._info = info
        self._breakdown = derived.install_breakdown
        super().__init__("REACH", caption="Availability + 30-day downloads")

    def compose_body(self) -> list[Widget]:
        registries = _source_registries(self._info)
        icons = " ".join(registry.icon for registry in registries)
        rows = [Static(f"[dim]Available[/] {icons}")]
        for method in self._breakdown.methods[:4]:
            label = method.label.replace(" install", "")
            rows.append(
                Static(
                    f"{label:<8} [{palette.GREEN}]{shorten_number(method.count):>6}[/] "
                    f"[dim]{method.percent:>4.1f}%[/]"
                )
            )
        return rows


class RiskSignalsPanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._info = info
        self._health = derived.health_score
        super().__init__("RISKS", caption="Derived from package signals")

    def compose_body(self) -> list[Widget]:
        info = self._info
        gh = info.github_stats
        risks: list[tuple[str, bool]] = [
            ("Stale release", _age_bucket_days(info.latest_release_date) > 365),
            ("No repository", not gh.resolved),
            ("No docs", not (info.documentation_url or info.homepage or gh.has_readme)),
            ("No CI signal", not gh.has_ci),
            ("Low health", self._health.total < 50),
        ]
        rows = []
        for label, active in risks:
            marker = f"[{palette.RED}]●[/]" if active else f"[{palette.GREEN}]●[/]"
            state = "watch" if active else "ok"
            rows.append(Static(f"{marker} {label:<13} [dim]{state}[/]"))
        return rows


class HealthScorePanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._health = derived.health_score
        super().__init__(
            f"HEALTH SCORE ({self._health.total} / 100)",
            caption="Derived from multiple signals",
        )

    def compose_body(self) -> list[Widget]:
        rows: list[Widget] = []
        for sub in self._health.sub_scores:
            frac = sub.score / sub.max_score if sub.max_score else 0
            bar = _muted_block_chain(frac, segments=20)
            rows.append(
                Static(
                    f"[dim]{sub.label:<13}[/] "
                    f"[dim]{sub.score:>2}/{sub.max_score}[/] {bar}"
                )
            )
        return rows


class ActivityPanel(Panel):
    def __init__(
        self, info: PackageInfo, derived: DerivedPackageData, classes: str | None = None
    ) -> None:
        self._events = derived.activity
        super().__init__("RECENT ACTIVITY", classes=classes)

    def compose_body(self) -> list[Widget]:
        if not self._events:
            return [Static("[dim]No recent activity.[/]")]
        rows: list[Widget] = []
        for ev in self._events[:8]:
            icon = ev.kind.icon
            label = ev.kind.label
            ref = f"[{palette.BLUE}]{ev.ref}[/]: " if ev.ref else ""
            title = ev.title if len(ev.title) <= 46 else ev.title[:45] + "…"
            age = format_age(ev.timestamp)
            rows.append(
                Static(
                    f"[{palette.GREEN}]{icon}[/] [b]{label:<12}[/] {ref}{title}"
                    f"  [dim]{age}[/]"
                )
            )
        return rows


def _registry_url(info: PackageInfo, registry: Registry) -> str:
    name = info.name
    return {
        Registry.PYPI: f"https://pypi.org/project/{name}/",
        Registry.CRATES: f"https://crates.io/crates/{name}",
        Registry.NPM: f"https://www.npmjs.com/package/{name}",
    }[registry]


def _age_bucket_days(dt) -> int:
    if dt is None:
        return 10_000
    from datetime import datetime, timezone

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - dt).days, 0)


def _short_url(url: str) -> str:
    return url.replace("https://", "").replace("http://", "").rstrip("/")


def _muted_block_chain(fraction: float, segments: int = 20) -> str:
    fraction = max(0.0, min(1.0, fraction))
    filled = round(fraction * segments)
    blocks = []
    for i in range(segments):
        style = palette.GREEN if i < filled else palette.BORDER_SECONDARY
        blocks.append(f"[{style}]▮[/]")
    return "".join(blocks)
