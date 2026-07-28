"""Main Textual App — single-screen package-intelligence dashboard."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal

from pkgwatch import derived as derive
from pkgwatch.api.base import create_adapter
from pkgwatch.history import (
    HistorySnapshot,
    append_snapshot,
    compute_delta,
    find_baseline,
    load_snapshots,
)
from pkgwatch.models import (
    DerivedPackageData,
    FetchError,
    PackageInfo,
    PackageRef,
    Project,
)
from pkgwatch.ui.widgets.detail import DetailView
from pkgwatch.ui.widgets.header_bar import PkgWatchHeader
from pkgwatch.ui.widgets.modals import HelpScreen, SearchScreen
from pkgwatch.ui.widgets.sidebar import Sidebar
from pkgwatch.ui.widgets.status_bar import PkgWatchFooter
from pkgwatch.utils import (
    fetch_github_extended_stats_for_package,
    fetch_release_notes_for_package,
)


class PkgWatch(App[None]):
    """Single-screen dashboard — sidebar + rich per-package detail view."""

    CSS_PATH = "styles/dashboard.tcss"
    TITLE = "pkgwatch"

    BINDINGS = [
        Binding("r", "refresh", "Refresh", priority=True),
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

    @property
    def project(self) -> Project:
        return self._project

    @property
    def refreshed_at(self) -> datetime | None:
        return self._refreshed_at

    @property
    def package_data(self) -> dict[str, PackageInfo]:
        return self._package_data

    def get_package_info(self, ref: PackageRef) -> PackageInfo | None:
        return self._package_data.get(_package_key(ref))

    def get_package_error(self, ref: PackageRef) -> FetchError | None:
        return self._package_errors.get(_package_key(ref))

    def get_derived(self, ref: PackageRef) -> DerivedPackageData | None:
        return self._derived_data.get(_package_key(ref))

    def compose(self) -> ComposeResult:
        yield PkgWatchHeader()
        yield Horizontal(
            Sidebar(),
            Container(id="main-content"),
        )
        yield PkgWatchFooter(self._config_path)

    def on_mount(self) -> None:
        self.theme = "tokyo-night"
        self._select_default_package()
        self._start_data_fetch()

    # ── actions ──

    def action_refresh(self) -> None:
        self._start_data_fetch()

    def action_toggle_filter(self) -> None:
        self.query_one(Sidebar).toggle_favorites_filter()

    def action_search(self) -> None:
        def _on_result(ref: PackageRef | None) -> None:
            if ref is not None:
                self.navigate_to_package(ref)

        self.push_screen(SearchScreen(self._project), _on_result)

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    # ── navigation ──

    def _select_default_package(self) -> None:
        if not self._project.packages:
            return
        favorite = next((r for r in self._project.packages if r.favorite), None)
        self.navigate_to_package(favorite or self._project.packages[0])

    def navigate_to_package(self, ref: PackageRef) -> None:
        self._selected_ref = ref
        self._render_selected()
        try:
            self.query_one(Sidebar).select_package(ref)
        except Exception:
            pass

    def _render_selected(self) -> None:
        if self._selected_ref is None:
            return
        self.run_worker(
            self._render_selected_async(), exclusive=True, group="render"
        )

    async def _render_selected_async(self) -> None:
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
        await main.mount(DetailView(ref, info, error, derived, parent_app=self))

    # ── data fetching ──

    def _start_data_fetch(self) -> None:
        self._refreshed_at = None
        for ref in self._project.packages:
            key = _package_key(ref)
            if key not in self._package_data:
                self._package_data[key] = PackageInfo(
                    name=ref.name, registry=ref.registry
                )
        self.run_worker(self._fetch_all_packages(), exclusive=False)

    async def _fetch_all_packages(self) -> None:
        for ref in self._project.packages:
            await self._fetch_single_package(ref)

        self._refreshed_at = datetime.now(timezone.utc)
        self._notify_ui_update()

    async def _fetch_single_package(self, ref: PackageRef) -> None:
        adapter = create_adapter(ref.registry)
        key = _package_key(ref)
        try:
            info = await adapter.fetch_package(ref.name)

            (
                versions,
                trend,
                counts,
                gh_result,
                version_dl,
                reverse_deps,
            ) = await asyncio.gather(
                adapter.fetch_versions(ref.name),
                adapter.fetch_download_trend(ref.name, days=60),
                adapter.fetch_download_counts(ref.name),
                fetch_github_extended_stats_for_package(
                    info.homepage, info.repository_url
                ),
                adapter.fetch_version_download_breakdown(ref.name),
                adapter.fetch_reverse_dependencies(ref.name),
            )

            gh_stats, issue_events = gh_result
            info.versions = versions
            info.download_trend = trend
            info.download_counts = counts
            info.github_stats = gh_stats
            info.github_issue_events = issue_events
            info.version_downloads_recent = version_dl
            info.reverse_dependencies = reverse_deps

            self._apply_history_deltas(key, info)

            if info.latest_version:
                info.dependencies = await adapter.fetch_dependencies(
                    ref.name, info.latest_version
                )
                notes = await adapter.fetch_release_notes(ref.name, info.latest_version)
                if not notes and (info.homepage or info.repository_url):
                    notes = await fetch_release_notes_for_package(
                        info.homepage, info.repository_url, info.latest_version
                    )
                info.release_notes = notes

            self._package_data[key] = info
            self._package_errors.pop(key, None)
            self._derived_data[key] = derive.compute_all(info)

        except Exception as e:
            self._package_errors[key] = FetchError(
                package_name=ref.name,
                registry=ref.registry,
                message=str(e),
            )

        self._notify_ui_update(changed_ref=ref)

    def _apply_history_deltas(self, key: str, info: PackageInfo) -> None:
        gh = info.github_stats
        if not gh.resolved:
            return
        baseline = find_baseline(load_snapshots(key))
        gh.stars_delta_7d = compute_delta(
            gh.stars, baseline.stars if baseline else None
        )
        gh.open_issues_delta_7d = compute_delta(
            gh.open_issues, baseline.open_issues if baseline else None
        )
        append_snapshot(
            key,
            HistorySnapshot(
                timestamp=datetime.now(timezone.utc),
                stars=gh.stars,
                open_issues=gh.open_issues,
            ),
        )

    def _notify_ui_update(self, changed_ref: PackageRef | None = None) -> None:
        try:
            sidebar = self.query_one(Sidebar)
            sidebar.refresh_versions()
        except Exception:
            pass

        # Re-render the detail view when its package's data lands.
        if self._selected_ref is not None and (
            changed_ref is None or _package_key(changed_ref) == _package_key(self._selected_ref)
        ):
            self._render_selected()


def _package_key(ref: PackageRef) -> str:
    return f"{ref.registry.value}:{ref.name}"
