"""Main Textual App — single-screen package-intelligence dashboard."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual import on

from secchi import derived as derive
from secchi.export import export_package_json, save_export
from secchi.models import (
    DerivedPackageData,
    FetchError,
    InstallBreakdown,
    InstallMethod,
    PackageInfo,
    PackageRef,
    Project,
    Registry,
)
from secchi.spotlight import fetch_spotlight, spotlight_disabled
from secchi.services.intelligence import PackageIntelligenceService
from secchi.trending import load_cached_trending, fetch_trending, save_cached_trending
from secchi.ui.widgets.detail import DetailView
from secchi.ui.widgets.header_bar import SecchiHeader
from secchi.ui.widgets.modals import ExportScreen, HelpScreen, SearchScreen
from secchi.ui.widgets.sidebar import Sidebar
from secchi.ui.widgets.status_bar import SecchiFooter


class Secchi(App[None]):
    """Single-screen dashboard — sidebar + rich per-package detail view."""

    CSS_PATH = "styles/dashboard.tcss"
    TITLE = "secchi"

    BINDINGS = [
        Binding("r", "refresh", "Refresh", priority=True),
        Binding("e", "export", "Export"),
        Binding("slash", "search", "Search"),
        Binding("question_mark", "help", "Help"),
        Binding("f", "toggle_filter", "Filter"),
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    def __init__(
        self,
        project: Project,
        config_path: Path,
        force_refresh: bool = False,
    ) -> None:
        super().__init__()
        self._project = project
        self._config_path = config_path
        self._force_refresh = force_refresh
        self._package_data: dict[str, PackageInfo] = {}
        self._package_errors: dict[str, FetchError] = {}
        self._derived_data: dict[str, DerivedPackageData] = {}
        self._refreshed_at: datetime | None = None
        self._selected_ref: PackageRef | None = None
        self._render_in_progress = False
        self._render_again = False
        self._intelligence = PackageIntelligenceService()

    @property
    def project(self) -> Project:
        return self._project

    @property
    def visible_packages(self) -> list[PackageRef]:
        return _logical_package_refs(self._project.packages)

    @property
    def refreshed_at(self) -> datetime | None:
        return self._refreshed_at

    @property
    def package_data(self) -> dict[str, PackageInfo]:
        return self._package_data

    def get_package_info(self, ref: PackageRef) -> PackageInfo | None:
        refs = self._matching_refs(ref)
        infos = [
            self._package_data[_package_key(r)]
            for r in refs
            if _package_key(r) in self._package_data
        ]
        if len(infos) <= 1:
            return infos[0] if infos else None
        return _combine_package_infos(ref, infos)

    def get_package_error(self, ref: PackageRef) -> FetchError | None:
        for r in self._matching_refs(ref):
            error = self._package_errors.get(_package_key(r))
            if error:
                return error
        return None

    def get_derived(self, ref: PackageRef) -> DerivedPackageData | None:
        refs = self._matching_refs(ref)
        derived_items = [
            self._derived_data[_package_key(r)]
            for r in refs
            if _package_key(r) in self._derived_data
        ]
        if not derived_items:
            return None
        if len(derived_items) == 1:
            return derived_items[0]

        info = self.get_package_info(ref)
        if info is None:
            return None
        combined = derive.compute_all(info)
        combined.install_breakdown = _combine_install_breakdown(
            [
                self._package_data[_package_key(r)]
                for r in refs
                if _package_key(r) in self._package_data
            ]
        )
        return combined

    def _matching_refs(self, ref: PackageRef) -> list[PackageRef]:
        target = ref.name.lower()
        return [r for r in self._project.packages if r.name.lower() == target] or [ref]

    def compose(self) -> ComposeResult:
        yield SecchiHeader()
        yield Horizontal(
            Sidebar(),
            Container(id="main-content"),
        )
        yield SecchiFooter(self._config_path)

    def on_mount(self) -> None:
        self.theme = "textual-dark"
        self._select_default_package(render=False)
        self._start_spotlight_fetch()
        self._start_trending_fetch()
        self._start_data_fetch(force=self._force_refresh)

    # ── actions ──

    def action_refresh(self) -> None:
        self._start_data_fetch(force=True)

    def action_toggle_filter(self) -> None:
        self.query_one(Sidebar).toggle_favorites_filter()

    def action_search(self) -> None:
        def _on_result(ref: PackageRef | None) -> None:
            if ref is not None:
                self.navigate_to_package(ref)

        self.push_screen(SearchScreen(self._project), _on_result)

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_export(self) -> None:
        if self._selected_ref is None:
            self.notify("No package selected.", severity="warning")
            return

        def _on_export(format_id: str | None) -> None:
            if format_id is None:
                return
            ref = self._selected_ref
            if ref is None:
                return
            info = self.get_package_info(ref)
            derived = self.get_derived(ref)
            if info is None:
                self.notify("No data loaded yet.", severity="warning")
                return
            json_str = export_package_json(
                info, derived, ref, self._project.name
            )
            path = save_export(json_str, self._project.name, ref.name)
            self.notify(f"Exported to {path.name}", title="Export")

        self.push_screen(ExportScreen(), _on_export)

    def _start_spotlight_fetch(self) -> None:
        if spotlight_disabled():
            try:
                self.query_one(Sidebar).set_spotlight(None)
            except Exception:
                pass
            return
        self.run_worker(self._fetch_spotlight(), exclusive=False, group="spotlight")

    async def _fetch_spotlight(self) -> None:
        spotlight = await fetch_spotlight()
        try:
            self.query_one(Sidebar).set_spotlight(spotlight)
        except Exception:
            pass

    def _start_trending_fetch(self) -> None:
        try:
            sidebar = self.query_one(Sidebar)
            cached = load_cached_trending()
            if cached is not None:
                sidebar.set_trending(cached)
        except Exception:
            pass
        self.run_worker(self._fetch_trending(), exclusive=False, group="trending")

    async def _fetch_trending(self) -> None:
        trending = await fetch_trending()
        if trending is not None:
            save_cached_trending(trending)
        try:
            self.query_one(Sidebar).set_trending(trending)
        except Exception:
            pass

    # ── navigation ──

    def _select_default_package(self, *, render: bool = True) -> None:
        packages = self.visible_packages
        if not packages:
            return
        favorite = next((r for r in packages if r.favorite), None)
        self.navigate_to_package(favorite or packages[0], render=render)

    def navigate_to_package(self, ref: PackageRef, *, render: bool = True) -> None:
        self._selected_ref = ref
        if render:
            self._render_selected()
        try:
            self.query_one(Sidebar).select_package(ref)
        except Exception:
            pass

    @on(Sidebar.PackageSelected)
    def _on_package_selected(self, event: Sidebar.PackageSelected) -> None:
        self.navigate_to_package(event.ref)

    def _render_selected(self) -> None:
        if self._selected_ref is None:
            return
        if self._render_in_progress:
            self._render_again = True
            return
        self._render_in_progress = True
        self.run_worker(
            self._render_selected_loop, exclusive=False, group="render"
        )

    async def _render_selected_loop(self) -> None:
        try:
            while True:
                self._render_again = False
                await self._render_selected_once()
                if not self._render_again:
                    break
        except asyncio.CancelledError:
            return
        finally:
            self._render_in_progress = False
            if self._render_again:
                self._render_selected()

    async def _render_selected_once(self) -> None:
        try:
            ref = self._selected_ref
            if ref is None:
                return
            try:
                main = self.query_one("#main-content", Container)
            except Exception:
                return
            info = self.get_package_info(ref)
            error = self.get_package_error(ref)
            derived = self.get_derived(ref)
            await main.remove_children()
            if ref != self._selected_ref:
                return
            await main.mount(DetailView(ref, info, error, derived, parent_app=self))
        except asyncio.CancelledError:
            return

    # ── data fetching ──

    def _start_data_fetch(self, *, force: bool = False) -> None:
        self._refreshed_at = None
        for ref in self._project.packages:
            key = _package_key(ref)
            if key not in self._package_data:
                self._package_data[key] = PackageInfo(
                    name=ref.name, registry=ref.registry
                )
        self.run_worker(self._fetch_all_packages(force=force), exclusive=False)

    async def _fetch_all_packages(self, *, force: bool = False) -> None:
        result = await self._intelligence.fetch_project(
            self._project.packages, force_refresh=force
        )
        for key, package_result in result.results.items():
            if package_result.info is not None:
                self._package_data[key] = package_result.info
                self._package_errors.pop(key, None)
            if package_result.derived is not None:
                self._derived_data[key] = package_result.derived
            if package_result.error is not None:
                self._package_errors[key] = package_result.error
        self._refreshed_at = result.refreshed_at or datetime.now(timezone.utc)
        self._notify_ui_update()

    async def _fetch_single_package(
        self, ref: PackageRef, *, force: bool = False
    ) -> None:
        key = _package_key(ref)
        result = await self._intelligence.fetch_package(ref, force_refresh=force)
        if result.info is not None:
            self._package_data[key] = result.info
        if result.derived is not None:
            self._derived_data[key] = result.derived
        if result.error is not None:
            self._package_errors[key] = result.error
        self._notify_ui_update(changed_ref=ref)

    def _notify_ui_update(self, changed_ref: PackageRef | None = None) -> None:
        try:
            sidebar = self.query_one(Sidebar)
            sidebar.refresh_versions()
        except Exception:
            pass

        # Re-render the detail view when its package's data lands.
        if self._selected_ref is not None and (
            changed_ref is None
            or changed_ref.name.lower() == self._selected_ref.name.lower()
        ):
            self._render_selected()


def _package_key(ref: PackageRef) -> str:
    return f"{ref.registry.value}:{ref.name}"


def _oldest_time(current: datetime | None, candidate: datetime) -> datetime:
    if current is None:
        return candidate
    return current if current <= candidate else candidate


def _logical_package_refs(refs: list[PackageRef]) -> list[PackageRef]:
    grouped: dict[str, PackageRef] = {}
    for ref in refs:
        key = ref.name.lower()
        current = grouped.get(key)
        if current is None:
            grouped[key] = replace(ref)
        elif ref.favorite and not current.favorite:
            current.favorite = True
    return list(grouped.values())


def _combine_package_infos(ref: PackageRef, infos: list[PackageInfo]) -> PackageInfo:
    primary = _pick_primary_info(infos)
    combined = replace(primary)
    combined.name = ref.name
    combined.source_registries = _unique_registries(info.registry for info in infos)
    combined.total_downloads = sum(info.total_downloads for info in infos)
    combined.download_counts = replace(primary.download_counts)
    combined.download_counts.today = sum(info.download_counts.today for info in infos)
    combined.download_counts.week = sum(info.download_counts.week for info in infos)
    combined.download_counts.month = sum(info.download_counts.month for info in infos)
    combined.download_trend = _combine_download_trends(infos)

    best_github = next((info.github_stats for info in infos if info.github_stats.resolved), None)
    if best_github is not None:
        combined.github_stats = best_github

    crates_info = next((info for info in infos if info.registry is Registry.CRATES), None)
    if crates_info is not None:
        combined.reverse_dependencies = crates_info.reverse_dependencies
        combined.reverse_dependency_count = crates_info.reverse_dependency_count
        combined.reverse_dependency_monthly_growth = (
            crates_info.reverse_dependency_monthly_growth
        )

    combined.health_history = primary.health_history

    return combined


def _pick_primary_info(infos: list[PackageInfo]) -> PackageInfo:
    for registry in (Registry.CRATES, Registry.PYPI, Registry.NPM):
        for info in infos:
            if info.registry is registry and info.latest_version:
                return info
    return infos[0]


def _unique_registries(registries) -> list[Registry]:
    seen: set[Registry] = set()
    out: list[Registry] = []
    for registry in registries:
        if registry not in seen:
            seen.add(registry)
            out.append(registry)
    return out


def _combine_download_trends(infos: list[PackageInfo]):
    from secchi.models import DownloadTrendPoint

    counts: dict[str, int] = {}
    for info in infos:
        for point in info.download_trend:
            counts[point.date] = counts.get(point.date, 0) + point.count
    return [DownloadTrendPoint(date=date, count=counts[date]) for date in sorted(counts)]


def _combine_install_breakdown(infos: list[PackageInfo]) -> InstallBreakdown:
    totals: dict[str, int] = {}
    for info in infos:
        label = info.registry.display_name
        count = info.download_counts.month or sum(p.count for p in info.download_trend[-30:])
        if count == 0:
            count = info.total_downloads
        totals[label] = totals.get(label, 0) + count

    total = sum(totals.values())
    if total <= 0:
        return InstallBreakdown(
            methods=[],
            caption="No 30-day download data available across ecosystems.",
        )

    methods = [
        InstallMethod(label=label, count=count, percent=count / total * 100)
        for label, count in sorted(totals.items(), key=lambda item: item[1], reverse=True)
    ]
    return InstallBreakdown(
        methods=methods,
        caption="Combined from registry 30-day download totals.",
    )
