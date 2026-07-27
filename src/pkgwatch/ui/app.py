"""Main Textual App — btop-style single-screen dashboard."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Footer, Header

from pkgwatch.api.base import create_adapter
from pkgwatch.models import (
    FetchError,
    PackageInfo,
    PackageRef,
    Project,
)
from pkgwatch.ui.widgets.sidebar import Sidebar
from pkgwatch.ui.widgets.dashboard import DashboardView
from pkgwatch.ui.widgets.detail import DetailView
from pkgwatch.utils import (
    fetch_github_stats_for_package,
    fetch_release_notes_for_package,
)


class PkgWatch(App[None]):
    """Main application — single-screen btop-style dashboard."""

    CSS_PATH = "styles/dashboard.tcss"
    TITLE = "pkgwatch"

    BINDINGS = [
        Binding("r", "refresh", "Refresh", priority=True),
        Binding("escape", "show_dashboard", "Dashboard", show=False),
        Binding("ctrl+c", "quit", "Quit"),
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
        self._refreshed_at: datetime | None = None
        self._showing_detail = False

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

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Horizontal(
            Sidebar(),
            Container(id="main-content"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.theme = "tokyo-night"
        self._show_dashboard_view()
        self._start_data_fetch()

    def action_refresh(self) -> None:
        self._start_data_fetch()

    def navigate_to_package(self, ref: PackageRef) -> None:
        info = self.get_package_info(ref)
        error = self.get_package_error(ref)
        if info is None and error is None:
            self.notify("Still loading...", severity="warning")
            return

        self._showing_detail = True
        main = self.query_one("#main-content", Container)
        main.remove_children()
        main.mount(DetailView(ref, info, error, parent_app=self))

        sidebar = self.query_one(Sidebar)
        sidebar.select_package(ref)

    def show_dashboard(self) -> None:
        self._show_dashboard_view()

    def action_show_dashboard(self) -> None:
        if self._showing_detail:
            self._show_dashboard_view()
        else:
            self.exit()

    def _show_dashboard_view(self) -> None:
        self._showing_detail = False
        main = self.query_one("#main-content", Container)
        main.remove_children()
        main.mount(DashboardView(parent_app=self))

        sidebar = self.query_one(Sidebar)
        sidebar.deselect_all()

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

            versions_task = adapter.fetch_versions(ref.name)
            trend_task = adapter.fetch_download_trend(ref.name)
            counts_task = adapter.fetch_download_counts(ref.name)
            github_task = fetch_github_stats_for_package(
                info.homepage, info.repository_url
            )

            versions, trend, counts, gh_stats = await asyncio.gather(
                versions_task, trend_task, counts_task, github_task
            )

            info.versions = versions
            info.download_trend = trend
            info.download_counts = counts
            info.github_stats = gh_stats

            if info.latest_version:
                deps = await adapter.fetch_dependencies(ref.name, info.latest_version)
                info.dependencies = deps

                notes = await adapter.fetch_release_notes(ref.name, info.latest_version)
                if not notes and (info.homepage or info.repository_url):
                    notes = await fetch_release_notes_for_package(
                        info.homepage, info.repository_url, info.latest_version
                    )
                info.release_notes = notes

            self._package_data[key] = info
            self._package_errors.pop(key, None)

        except Exception as e:
            self._package_errors[key] = FetchError(
                package_name=ref.name,
                registry=ref.registry,
                message=str(e),
            )

        self._notify_ui_update()

    def _notify_ui_update(self) -> None:
        if self._showing_detail:
            return
        try:
            main = self.query_one("#main-content", Container)
            view = main.query(DashboardView).first()
            if view is not None:
                view.refresh_data()
        except Exception:
            pass

        sidebar = self.query_one(Sidebar)
        sidebar.refresh(layout=True)


def _package_key(ref: PackageRef) -> str:
    return f"{ref.registry.value}:{ref.name}"
