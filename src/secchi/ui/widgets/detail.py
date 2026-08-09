"""Detail view — the single main screen: header, stat cards, and tabs."""

from __future__ import annotations

from rich.markup import escape
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Grid, Horizontal, VerticalScroll
from textual.widgets import DataTable, Markdown, Static, TabbedContent, TabPane

from secchi.models import DerivedPackageData, FetchError, PackageInfo, PackageRef
from secchi.services.intelligence import SignalWarning
from secchi.ui import palette
from secchi.ui.widgets.bar import render_bar
from secchi.ui.widgets.overview import OverviewTab
from secchi.ui.widgets.stat_card import StatCard
from secchi.utils import (
    derive_github_repo,
    format_age,
    format_pct_delta,
    shorten_bytes,
    shorten_number,
)

# Kept in one place so additional package sources can be surfaced without
# changing the project-card layout. Only ecosystems present in source_registries
# are rendered today.
ECOSYSTEM_ICONS: dict[str, str] = {
    "crates.io": "🦀",
    "pypi": "🐍",
    "npm": "⬢",
    "homebrew": "🍺",
    "go": "🐹",
    "cran": "📈",
    "docker": "🐳",
    "nix": "❄️",
    "winget": "🪟",
    "scoop": "📦",
}


class DetailView(Container):
    """Rich single-package view — the app's only main-content screen."""

    def __init__(
        self,
        ref: PackageRef,
        info: PackageInfo | None,
        error: FetchError | None,
        derived: DerivedPackageData | None,
        warnings: list[SignalWarning],
        parent_app: object,
    ) -> None:
        super().__init__(id="detail-view")
        self._ref = ref
        self._info = info
        self._error = error
        self._derived = derived
        self._warnings = warnings
        self._app = parent_app

    # ── layout ──

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="detail-content"):
            yield from self._compose_summary_row()

            if self._info and self._info.latest_version:
                yield from self._compose_tabs()
            elif self._error:
                yield Static(f"[b red]Error[/]\n{self._error.message}", id="error-view")
            else:
                yield Static("Loading…", id="loading-view")

    def _compose_summary_row(self) -> ComposeResult:
        with Horizontal(id="summary-row"):
            yield Static(self._build_project_card(), id="project-card")
            if self._info and self._info.latest_version:
                yield from self._compose_stat_cards()

    def _build_project_card(self) -> str:
        title = self._build_title()
        if not self._info:
            return title

        info = self._info
        registries = info.source_registries or [info.registry]
        icons = " ".join(_registry_icon_label(registry) for registry in registries)

        lines = [title]
        if info.description:
            lines.append(f"[#E5E7EB]{info.description[:96]}[/]")

        repo = derive_github_repo([info.repository_url, info.homepage])
        repo_str = (
            f"github.com/{repo[0]}/{repo[1]}" if repo else (info.repository_url or "—")
        )
        docs_str = (
            _short_url(info.documentation_url or info.homepage)
            if (info.documentation_url or info.homepage)
            else "—"
        )
        stars = (
            shorten_number(info.github_stats.stars)
            if info.github_stats.resolved
            else "—"
        )
        latest = f"v{info.latest_version}" if info.latest_version else "—"

        lines.append(
            f"[dim]Latest[/] [{palette.GREEN}]{latest}[/]   "
            f"[dim]Stars[/] [{palette.YELLOW}]{stars}[/]"
        )
        lines.append(
            f"[dim]Repo[/] [{palette.CYAN}]{repo_str}[/]   "
            f"[dim]Docs[/] [{palette.CYAN}]{docs_str}[/]"
        )

        size = _resolve_size(info)
        meta: list[str] = []
        if icons:
            meta.append(f"[dim]Ecosystem[/] {icons}")
        if info.license:
            meta.append(f"[dim]License[/] [{palette.PURPLE}]{info.license}[/]")
        if size:
            meta.append(f"[dim]Size[/] {shorten_bytes(size)}")
        if meta:
            lines.append("   ".join(meta))
        return "\n".join(lines)

    def _compose_stat_cards(self) -> ComposeResult:
        info = self._info
        derived = self._derived
        assert info is not None

        total = derived.downloads_30d_total if derived else info.download_counts.month
        pct = derived.downloads_30d_pct_change if derived else None
        pct_text, pct_color = format_pct_delta(pct)
        adoption_card = StatCard(
            "ADOPTION",
            shorten_number(total),
            delta=pct_text,
            signal=_trend_label(pct),
            delta_color=pct_color,
            signal_color=_trend_color(pct),
        )

        health = derived.health_score if derived else None
        grade = health.grade if health else "—"
        grade_color = _grade_color(grade)
        health_delta, health_delta_color = _health_mom(derived)
        health_card = StatCard(
            "HEALTH",
            f"{health.total} / 100" if health else "—",
            delta=health_delta,
            signal=_health_label(health.total) if health else "",
            delta_color=health_delta_color,
            signal_color=grade_color,
        )

        deps = derived.reverse_dependency_summary if derived else None
        dep_growth = deps.monthly_growth if deps else None
        dep_card = StatCard(
            "DEPENDENTS",
            shorten_number(deps.count) if deps and deps.count is not None else "—",
            delta=_dependent_delta(dep_growth),
            signal=_dependent_signal(dep_growth, deps.count if deps else None),
            delta_color=_growth_color(dep_growth),
            signal_color=_growth_color(dep_growth),
        )

        latest_pct = _latest_version_adoption(info, derived)
        latest_card = StatCard(
            "LATEST VERSION",
            f"v{info.latest_version}" if info.latest_version else "—",
            delta=f"{latest_pct:.0f}% adoption"
            if latest_pct is not None
            else "— adoption",
            signal=_rollout_signal(latest_pct),
            delta_color=_rollout_color(latest_pct),
            signal_color=_rollout_color(latest_pct),
        )

        with Grid(id="stat-cards"):
            yield adoption_card
            yield health_card
            yield dep_card
            yield latest_card

    def _compose_tabs(self) -> ComposeResult:
        info = self._info
        derived = self._derived
        assert info is not None and derived is not None
        with TabbedContent(id="detail-tabs"):
            with TabPane("Overview", id="tab-overview"):
                yield OverviewTab(info, derived)
            with TabPane("Security", id="tab-security"):
                yield self._security_pane()
            with TabPane("Releases", id="tab-releases"):
                yield self._releases_pane()
            with TabPane("Dependencies", id="tab-deps"):
                yield self._deps_pane()
            with TabPane("Versions", id="tab-versions"):
                yield self._versions_pane()
            with TabPane("Activity", id="tab-activity"):
                yield self._activity_pane()

    # ── content builders ──

    def _build_title(self) -> str:
        star = f" [{palette.YELLOW}]★[/]" if self._ref.favorite else ""
        name = self._ref.name
        return f"[b {palette.GREEN}]{name}[/]{star}"

    def _releases_pane(self) -> VerticalScroll:
        info = self._info
        derived = self._derived
        assert info is not None and derived is not None
        adoption = derived.release_adoption
        lines: list[str] = []
        for ver in info.versions[:30]:
            pct = adoption.get(ver.version, 0.0)
            bar = render_bar(pct / 100, width=12) if pct else ""
            age = format_age(ver.release_date)
            yanked = f" [{palette.RED}](yanked)[/]" if ver.is_yanked else ""
            lines.append(
                f"[{palette.GREEN}]{ver.version:<12}[/]{yanked} [dim]{age:<14}[/] {bar} "
                f"[b]{pct:4.1f}%[/]"
            )
        body = "\n".join(lines) if lines else "[dim]No releases.[/]"
        children: list = [Static(body, classes="pane-block")]
        if info.release_notes:
            children.append(Static("\n[b]Release Notes[/]\n", classes="pane-heading"))
            children.append(Markdown(info.release_notes))
        return VerticalScroll(*children, classes="tab-scroll")

    def _deps_pane(self) -> VerticalScroll:
        table = DataTable(cursor_type=None, zebra_stripes=True)
        table.add_columns("Package", "Requirement", "Type")
        for dep in self._info.dependencies if self._info else []:
            table.add_row(
                Text(dep.name),
                dep.requirement or "—",
                "optional" if dep.optional else "required",
            )
        if not (self._info and self._info.dependencies):
            table.add_row(Text("—"), "no dependencies", "")
        return VerticalScroll(table, classes="tab-scroll")

    def _security_pane(self) -> VerticalScroll:
        advisories = self._info.security_advisories if self._info else []
        if not advisories:
            return VerticalScroll(
                Static(
                    "[b green]No known advisories[/]\n"
                    "No OSV advisories affect the latest published version.",
                    classes="pane-block",
                ),
                classes="tab-scroll",
            )

        children: list[Static] = [
            Static(
                f"[b red]{len(advisories)} advisory(ies)[/] affect the latest version.",
                classes="pane-heading",
            )
        ]
        for advisory in advisories:
            fixed = ", ".join(advisory.fixed_versions) or "No fixed version listed"
            lines = [
                f"[b red]{escape(advisory.id)}[/]  {escape(advisory.severity or 'Severity unavailable')}",
                escape(advisory.summary or "No summary available."),
                f"Fixed versions: {escape(fixed)}",
                f"[dim]{escape(advisory.url)}[/]",
            ]
            children.append(Static("\n".join(lines), classes="pane-block"))
        return VerticalScroll(*children, classes="tab-scroll")

    def _versions_pane(self) -> VerticalScroll:
        table = DataTable(cursor_type=None, zebra_stripes=True)
        table.add_columns("Version", "Released", "Downloads", "Size")
        for ver in self._info.versions[:100] if self._info else []:
            date_str = (
                ver.release_date.strftime("%Y-%m-%d") if ver.release_date else "—"
            )
            label = f"(yanked) {ver.version}" if ver.is_yanked else ver.version
            table.add_row(
                Text(label, style=palette.RED if ver.is_yanked else ""),
                date_str,
                shorten_number(ver.downloads) if ver.downloads else "—",
                shorten_bytes(ver.size_bytes),
            )
        return VerticalScroll(table, classes="tab-scroll")

    def _activity_pane(self) -> VerticalScroll:
        derived = self._derived
        events = derived.activity if derived else []
        lines: list[str] = []
        for ev in events:
            ref = f"[{palette.BLUE}]{ev.ref}[/]: " if ev.ref else ""
            title = ev.title if len(ev.title) <= 70 else ev.title[:69] + "…"
            lines.append(
                f"[{palette.GREEN}]{ev.kind.icon}[/] [b]{ev.kind.label:<12}[/] {ref}{title}"
                f"  [dim]{format_age(ev.timestamp)}[/]"
            )
        body = "\n".join(lines) if lines else "[dim]No recent activity.[/]"
        return VerticalScroll(Static(body, classes="pane-block"), classes="tab-scroll")


# ── helpers ──


def _grade_color(grade: str) -> str:
    if grade in {"A", "B"}:
        return palette.GREEN
    if grade == "C":
        return palette.HEALTH_FAIR
    return palette.RED


def _health_label(score: int) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 75:
        return "Good"
    if score >= 50:
        return "Fair"
    return "Needs Attention"


def _trend_label(pct: float | None) -> str:
    if pct is None or abs(pct) < 5:
        return "Stable"
    return "Growing" if pct > 0 else "Declining"


def _trend_color(pct: float | None) -> str:
    if pct is None or abs(pct) < 5:
        return "dim"
    return palette.GREEN if pct > 0 else palette.RED


def _health_mom(derived: DerivedPackageData | None) -> tuple[str, str]:
    points = derived.health_timeline if derived else []
    if len(points) < 2:
        return "— MoM", "dim"
    delta = points[-1].value - points[-2].value
    sign = "+" if delta > 0 else ""
    color = palette.GREEN if delta >= 0 else palette.RED
    return f"{sign}{delta} MoM", color


def _dependent_delta(growth: int | None) -> str:
    if growth is None:
        return "— this month"
    sign = "+" if growth >= 0 else ""
    return f"{sign}{shorten_number(growth)} this month"


def _dependent_signal(growth: int | None, count: int | None) -> str:
    if count is None:
        return "Unavailable"
    if growth is None:
        return "Tracking"
    if growth > 0:
        return "Accelerating"
    if growth == 0:
        return "Stable"
    return "Contracting"


def _growth_color(growth: int | None) -> str:
    if growth is None or growth == 0:
        return "dim"
    return palette.GREEN if growth > 0 else palette.RED


def _latest_version_adoption(
    info: PackageInfo,
    derived: DerivedPackageData | None,
) -> float | None:
    if not info.latest_version or not derived:
        return None
    return derived.release_adoption.get(info.latest_version)


def _rollout_signal(pct: float | None) -> str:
    if pct is None:
        return "Unknown rollout"
    if pct >= 50:
        return "Healthy rollout"
    if pct >= 25:
        return "Mixed rollout"
    return "Lagging rollout"


def _rollout_color(pct: float | None) -> str:
    if pct is None:
        return "dim"
    if pct >= 50:
        return palette.GREEN
    if pct >= 25:
        return palette.HEALTH_FAIR
    return palette.RED


def _short_url(url: str) -> str:
    return url.replace("https://", "").replace("http://", "").rstrip("/")


def _resolve_size(info) -> int | None:
    for v in info.versions:
        if v.version == info.latest_version and v.size_bytes:
            return v.size_bytes
    if info.latest_release_files:
        total = sum(f.size for f in info.latest_release_files)
        if total:
            return total
    return None


def _registry_icon_label(registry) -> str:
    return ECOSYSTEM_ICONS.get(registry.value, registry.icon)
