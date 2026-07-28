"""Overview tab — the 3-row grid of intelligence panels from the reference mock."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static
from textual_plotext import PlotextPlot

from pkgwatch.derived import compute_downloads_30d
from pkgwatch.models import DerivedPackageData, PackageInfo, Registry
from pkgwatch.ui.widgets.bar import render_bar
from pkgwatch.ui.widgets.panel import Panel
from pkgwatch.utils import (
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
            yield ReleasesPanel(info, derived)
            yield DependenciesPanel(info, derived)
        with Horizontal(classes="overview-row"):
            yield InstallMethodsPanel(info, derived)
            yield MetadataPanel(info, derived)
            yield HealthScorePanel(info, derived)
        with Horizontal(classes="overview-row overview-row--bottom"):
            yield ActivityPanel(info, derived, classes="panel--wide")
            yield LinksPanel(info, derived)


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
            plt.plot([p.count for p in trend], marker="braille")
            plt.theme("clear")
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
                f"[green]{version:<8}[/] [dim]{age:>4}[/] "
                f"{bar} [b]{pct:4.1f}%[/]"
            )
            rows.append(Static(line))
        if not rows:
            rows.append(Static("[dim]No release data.[/]"))
        return rows


class DependenciesPanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._info = info
        caption = (
            "Source: crates.io reverse deps"
            if info.registry is Registry.CRATES
            else ""
        )
        super().__init__("TOP DEPENDENCIES", caption=caption)

    def compose_body(self) -> list[Widget]:
        if self._info.registry is not Registry.CRATES:
            return [
                Static(
                    f"[dim]Reverse-dependency data is not available for "
                    f"{self._info.registry.display_name}.\n"
                    f"No public reverse-dependency API exists for this registry.[/]"
                )
            ]
        rev = self._info.reverse_dependencies
        if not rev:
            return [Static("[dim]No reverse dependencies found.[/]")]
        rows: list[Widget] = []
        for dep in rev:
            rows.append(
                Static(f"{dep.name:<20} [dim]{shorten_number(dep.downloads):>8}[/]")
            )
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
        for m in methods:
            bar = render_bar(m.percent / 100, width=8)
            label = m.label if len(m.label) <= 18 else m.label[:17] + "…"
            rows.append(
                Static(
                    f"{label:<18}\n  {bar} "
                    f"[b]{shorten_number(m.count)}[/] [dim]({m.percent:.0f}%)[/]"
                )
            )
        return rows


class MetadataPanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._info = info
        super().__init__(
            "METADATA",
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
            ("License", info.license or "—"),
            ("Created", format_age(gh.created_at)),
            ("Size", shorten_bytes(size)),
            ("Docs", info.documentation_url or "—"),
            ("Last Commit", format_age(gh.pushed_at)),
        ]
        lines = "\n".join(f"[dim]{k:<12}[/] {v}" for k, v in rows)
        return [Static(lines)]


class HealthScorePanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._health = derived.health_score
        super().__init__(
            f"HEALTH SCORE ({self._health.total}/100)",
            caption="Derived from multiple signals",
        )

    def compose_body(self) -> list[Widget]:
        rows: list[Widget] = []
        for sub in self._health.sub_scores:
            frac = sub.score / sub.max_score if sub.max_score else 0
            color = "green" if frac >= 0.75 else "yellow" if frac >= 0.5 else "red"
            bar = render_bar(frac, width=10, color=color)
            rows.append(
                Static(f"[dim]{sub.label:<13}[/] [b]{sub.score:>2}/{sub.max_score}[/] {bar}")
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
            ref = f"[blue]{ev.ref}[/]: " if ev.ref else ""
            title = ev.title if len(ev.title) <= 46 else ev.title[:45] + "…"
            age = format_age(ev.timestamp)
            rows.append(
                Static(
                    f"[green]{icon}[/] [b]{label:<12}[/] {ref}{title}"
                    f"  [dim]{age}[/]"
                )
            )
        return rows


class LinksPanel(Panel):
    def __init__(self, info: PackageInfo, derived: DerivedPackageData) -> None:
        self._info = info
        super().__init__("LINKS")

    def compose_body(self) -> list[Widget]:
        info = self._info
        rows: list[tuple[str, str]] = []
        if info.repository_url:
            rows.append(("Repository", info.repository_url))
        for registry in _source_registries(info):
            rows.append((registry.display_name, self._registry_url(registry)))
        if info.documentation_url:
            rows.append(("Docs", info.documentation_url))
        if info.homepage and info.homepage not in (info.repository_url, info.documentation_url):
            rows.append(("Homepage", info.homepage))
        if not rows:
            return [Static("[dim]No links available.[/]")]
        widgets: list[Widget] = []
        for label, url in rows:
            widgets.append(
                Static(f"[dim]{label:<12}[/] [blue]{_short_url(url)}[/]")
            )
        return widgets

    def _registry_url(self, registry: Registry) -> str:
        name = self._info.name
        return {
            Registry.PYPI: f"https://pypi.org/project/{name}/",
            Registry.CRATES: f"https://crates.io/crates/{name}",
            Registry.NPM: f"https://www.npmjs.com/package/{name}",
        }[registry]


def _short_url(url: str) -> str:
    return url.replace("https://", "").replace("http://", "").rstrip("/")
