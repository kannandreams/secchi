"""Detail view — the single main screen: header, stat cards, and tabs."""

from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import DataTable, Markdown, Static, TabbedContent, TabPane

from pkgwatch.models import DerivedPackageData, FetchError, PackageInfo, PackageRef
from pkgwatch.ui.widgets.badge import Badge
from pkgwatch.ui.widgets.bar import render_bar
from pkgwatch.ui.widgets.overview import OverviewTab
from pkgwatch.ui.widgets.stat_card import StatCard
from pkgwatch.utils import (
    format_age,
    format_pct_delta,
    shorten_bytes,
    shorten_number,
)


class DetailView(Container):
    """Rich single-package view — the app's only main-content screen."""

    def __init__(
        self,
        ref: PackageRef,
        info: PackageInfo | None,
        error: FetchError | None,
        derived: DerivedPackageData | None,
        parent_app: object,
    ) -> None:
        super().__init__(id="detail-view")
        self._ref = ref
        self._info = info
        self._error = error
        self._derived = derived
        self._app = parent_app

    # ── layout ──

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="detail-content"):
            yield Static(self._build_header(), id="detail-header")
            yield from self._compose_badges()

            if self._info and self._info.latest_version:
                yield from self._compose_stat_cards()
                yield from self._compose_tabs()
            elif self._error:
                yield Static(
                    f"[b red]Error[/]\n{self._error.message}", id="error-view"
                )
            else:
                yield Static("Loading…", id="loading-view")

    def _compose_badges(self) -> ComposeResult:
        if not self._info:
            return
        info = self._info
        registries = info.source_registries or [info.registry]
        with Horizontal(id="badge-row"):
            for registry in registries:
                yield Badge(registry.language, color="yellow")
            if info.license:
                yield Badge(info.license, color="magenta")
            if info.package_kind:
                yield Badge(info.package_kind, color="cyan")
            if info.homepage:
                yield Badge(
                    _short_url(info.homepage), variant="link", url=info.homepage
                )

    def _compose_stat_cards(self) -> ComposeResult:
        info = self._info
        derived = self._derived
        assert info is not None

        # Latest version + age
        ver_card = StatCard(
            "Latest Version",
            info.latest_version,
            delta=format_age(info.latest_release_date),
        )

        # Downloads 30d + pct change
        total = derived.downloads_30d_total if derived else info.download_counts.month
        pct = derived.downloads_30d_pct_change if derived else None
        pct_text, pct_color = format_pct_delta(pct)
        dl_card = StatCard(
            "Downloads (30d)",
            shorten_number(total),
            delta=pct_text,
            delta_color=pct_color,
        )

        # GitHub stars + weekly delta
        gh = info.github_stats
        stars_card = StatCard(
            "GitHub Stars",
            shorten_number(gh.stars) if gh.resolved else "—",
            delta=_delta_line(gh.stars_delta_7d, good_positive=True),
            delta_color=_delta_color(gh.stars_delta_7d, good_positive=True),
        )

        # Open issues + weekly delta (fewer is better)
        issues_card = StatCard(
            "Open Issues",
            shorten_number(gh.open_issues) if gh.resolved else "—",
            delta=_delta_line(gh.open_issues_delta_7d, good_positive=False),
            delta_color=_delta_color(gh.open_issues_delta_7d, good_positive=False),
        )

        # Health score
        health = derived.health_score if derived else None
        grade = health.grade if health else "—"
        grade_color = _grade_color(grade)
        health_card = StatCard(
            "Health Score",
            grade,
            delta=f"{health.total} / 100" if health else "—",
            value_color=grade_color,
        )

        with Horizontal(id="stat-cards"):
            yield ver_card
            yield dl_card
            yield stars_card
            yield issues_card
            yield health_card

    def _compose_tabs(self) -> ComposeResult:
        info = self._info
        derived = self._derived
        assert info is not None and derived is not None
        with TabbedContent(id="detail-tabs"):
            with TabPane("Overview", id="tab-overview"):
                yield OverviewTab(info, derived)
            with TabPane("Releases", id="tab-releases"):
                yield self._releases_pane()
            with TabPane("Dependencies", id="tab-deps"):
                yield self._deps_pane()
            with TabPane("Versions", id="tab-versions"):
                yield self._versions_pane()
            with TabPane("Activity", id="tab-activity"):
                yield self._activity_pane()

    # ── content builders ──

    def _build_header(self) -> str:
        star = " [yellow]★[/]" if self._ref.favorite else ""
        name = self._ref.name
        header = f"[b]{name}[/]{star}"
        if self._info and self._info.description:
            header += f"\n[dim]{self._info.description[:120]}[/]"
        return header

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
            yanked = " [red](yanked)[/]" if ver.is_yanked else ""
            lines.append(
                f"[green]{ver.version:<12}[/]{yanked} [dim]{age:<14}[/] {bar} "
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
        for dep in (self._info.dependencies if self._info else []):
            table.add_row(
                Text(dep.name),
                dep.requirement or "—",
                "optional" if dep.optional else "required",
            )
        if not (self._info and self._info.dependencies):
            table.add_row(Text("—"), "no dependencies", "")
        return VerticalScroll(table, classes="tab-scroll")

    def _versions_pane(self) -> VerticalScroll:
        table = DataTable(cursor_type=None, zebra_stripes=True)
        table.add_columns("Version", "Released", "Downloads", "Size")
        for ver in (self._info.versions[:100] if self._info else []):
            date_str = ver.release_date.strftime("%Y-%m-%d") if ver.release_date else "—"
            label = f"(yanked) {ver.version}" if ver.is_yanked else ver.version
            table.add_row(
                Text(label, style="red" if ver.is_yanked else ""),
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
            ref = f"[blue]{ev.ref}[/]: " if ev.ref else ""
            title = ev.title if len(ev.title) <= 70 else ev.title[:69] + "…"
            lines.append(
                f"[green]{ev.kind.icon}[/] [b]{ev.kind.label:<12}[/] {ref}{title}"
                f"  [dim]{format_age(ev.timestamp)}[/]"
            )
        body = "\n".join(lines) if lines else "[dim]No recent activity.[/]"
        return VerticalScroll(Static(body, classes="pane-block"), classes="tab-scroll")


# ── helpers ──


def _delta_line(delta: int | None, *, good_positive: bool) -> str:
    if delta is None or delta == 0:
        return "—" if delta is None else "no change this week"
    arrow = "↑" if delta > 0 else "↓"
    return f"{arrow} {abs(delta)} this week"


def _delta_color(delta: int | None, *, good_positive: bool) -> str:
    if delta is None or delta == 0:
        return "dim"
    is_good = (delta > 0) if good_positive else (delta < 0)
    return "green" if is_good else "red"


def _grade_color(grade: str) -> str:
    return {
        "A": "green",
        "B": "green",
        "C": "yellow",
        "D": "red",
        "F": "red",
    }.get(grade, "dim")


def _short_url(url: str) -> str:
    return url.replace("https://", "").replace("http://", "").rstrip("/")
