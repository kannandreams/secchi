"""Main Textual App — single-screen package-intelligence dashboard."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal

from secchi import derived as derive
from secchi.diagnostics import DiagnosticLog
from secchi.export import save_report
from secchi.models import (
    DerivedPackageData,
    FetchError,
    PackageInfo,
    PackageRef,
    Project,
)
from secchi.renderers.reports import (
    build_project_report,
    render_project_report,
    render_report,
)
from secchi.services.intelligence import (
    IntelligenceResult,
    PackageIntelligenceService,
    SignalWarning,
)
from secchi.spotlight import fetch_spotlight, spotlight_disabled
from secchi.trending import fetch_trending, load_cached_trending, save_cached_trending
from secchi.ui.widgets.detail import DetailView
from secchi.ui.widgets.header_bar import SecchiHeader
from secchi.ui.widgets.modals import ExportScreen, HelpScreen, LogsScreen, SearchScreen
from secchi.ui.widgets.sidebar import Sidebar
from secchi.ui.widgets.status_bar import SecchiFooter
from secchi.workspace import (
    WorkspaceState,
    combine_install_breakdown,
    combine_package_infos,
    logical_package_refs,
    package_key,
)

logger = logging.getLogger(__name__)


class Secchi(App[None]):
    """Single-screen dashboard — sidebar + rich per-package detail view."""

    CSS_PATH = "styles/dashboard.tcss"
    TITLE = "secchi"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("r", "refresh", "Refresh", priority=True),
        Binding("e", "export", "Export"),
        Binding("slash", "search", "Search"),
        Binding("question_mark", "help", "Help"),
        Binding("l", "logs", "Logs"),
        Binding("f", "toggle_filter", "Filter"),
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    def __init__(
        self,
        project: Project,
        config_path: Path,
        force_refresh: bool = False,
        force_security_refresh: bool = False,
        workspace: list[Project] | None = None,
        intelligence: PackageIntelligenceService | None = None,
        diagnostics: DiagnosticLog | None = None,
    ) -> None:
        super().__init__()
        self._project = project
        self._workspace = workspace or []
        self._config_path = config_path
        self._force_refresh = force_refresh
        self._force_security_refresh = force_security_refresh
        self._package_data: dict[str, PackageInfo] = {}
        self._package_errors: dict[str, FetchError] = {}
        self._package_warnings: dict[str, list[SignalWarning]] = {}
        self._derived_data: dict[str, DerivedPackageData] = {}
        self._refreshed_at: datetime | None = None
        self._workspace_state = WorkspaceState()
        self._render_in_progress = False
        self._render_again = False
        self._intelligence = intelligence or PackageIntelligenceService()
        self._diagnostics = diagnostics or DiagnosticLog()

    @property
    def project(self) -> Project:
        return self._project

    @property
    def visible_packages(self) -> list[PackageRef]:
        if self._workspace:
            return list(self._project.packages)
        return logical_package_refs(self._project.packages)

    @property
    def workspace_projects(self) -> list[Project]:
        return self._workspace

    @property
    def refreshed_at(self) -> datetime | None:
        return self._refreshed_at

    @property
    def package_data(self) -> dict[str, PackageInfo]:
        return self._package_data

    def get_package_info(self, ref: PackageRef) -> PackageInfo | None:
        refs = self._matching_refs(ref)
        infos = [
            self._package_data[package_key(r)]
            for r in refs
            if package_key(r) in self._package_data
        ]
        if len(infos) <= 1:
            return infos[0] if infos else None
        return combine_package_infos(ref, infos)

    def get_package_error(self, ref: PackageRef) -> FetchError | None:
        for r in self._matching_refs(ref):
            error = self._package_errors.get(package_key(r))
            if error:
                return error
        return None

    def get_package_warnings(self, ref: PackageRef) -> list[SignalWarning]:
        warnings: list[SignalWarning] = []
        for item in self._matching_refs(ref):
            warnings.extend(self._package_warnings.get(package_key(item), []))
        return warnings

    def get_derived(self, ref: PackageRef) -> DerivedPackageData | None:
        refs = self._matching_refs(ref)
        derived_items = [
            self._derived_data[package_key(r)]
            for r in refs
            if package_key(r) in self._derived_data
        ]
        if not derived_items:
            return None
        if len(derived_items) == 1:
            return derived_items[0]

        info = self.get_package_info(ref)
        if info is None:
            return None
        combined = derive.compute_all(info)
        combined.install_breakdown = combine_install_breakdown(
            [
                self._package_data[package_key(r)]
                for r in refs
                if package_key(r) in self._package_data
            ]
        )
        return combined

    def _matching_refs(self, ref: PackageRef) -> list[PackageRef]:
        target = ref.name.lower()
        refs = [
            r
            for r in self._project.packages
            if r.name.lower() == target
            and (not ref.project_name or r.project_name == ref.project_name)
        ]
        return refs or [ref]

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
        selected_ref = self._workspace_state.selected_ref
        project_name = selected_ref.project_name if selected_ref else None
        self._start_data_fetch(force=True, project_name=project_name)

    def action_toggle_filter(self) -> None:
        self.query_one(Sidebar).toggle_favorites_filter()

    def action_search(self) -> None:
        def _on_result(ref: PackageRef | None) -> None:
            if ref is not None:
                self.navigate_to_package(ref)

        self.push_screen(SearchScreen(self._project), _on_result)

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_logs(self) -> None:
        self.push_screen(LogsScreen(self._diagnostics))

    def action_export(self) -> None:
        if self._workspace_state.selected_ref is None:
            self.notify("No package selected.", severity="warning")
            return

        project_scope = bool(self._workspace or len(self._project.packages) > 1)

        def _on_export(format_id: str | None) -> None:
            if format_id is None:
                return
            ref = self._workspace_state.selected_ref
            if ref is None:
                return
            format_name = format_id
            if project_scope:
                project = next(
                    (item for item in self._workspace if item.name == ref.project_name),
                    self._project,
                )
                results = {
                    package_key(source_ref): IntelligenceResult(
                        ref=source_ref,
                        info=self._package_data.get(package_key(source_ref)),
                        derived=self._derived_data.get(package_key(source_ref)),
                        warnings=self._package_warnings.get(
                            package_key(source_ref), []
                        ),
                        error=self._package_errors.get(package_key(source_ref)),
                    )
                    for source_ref in project.packages
                }
                report = build_project_report(project, results)
                content = render_project_report(format_name, report)
                subject = project.title or project.name
                project_name = project.name
            else:
                info = self.get_package_info(ref)
                derived = self.get_derived(ref)
                if info is None or derived is None:
                    self.notify("No data loaded yet.", severity="warning")
                    return
                content = render_report(
                    format_name, info, derived, ref, self._project.name
                )
                subject = ref.name
                project_name = self._project.name
            path = save_report(content, project_name, subject, format_name)
            self.notify(f"Exported to {path.name}", title="Export")

        self.push_screen(ExportScreen(project_scope=project_scope), _on_export)

    def _start_spotlight_fetch(self) -> None:
        if spotlight_disabled():
            try:
                self.query_one(Sidebar).set_spotlight(None)
            except Exception:
                # The sidebar may not be mounted during app startup/shutdown.
                logger.debug("Unable to clear the spotlight card", exc_info=True)
            return
        self.run_worker(self._fetch_spotlight(), exclusive=False, group="spotlight")

    async def _fetch_spotlight(self) -> None:
        spotlight = await fetch_spotlight()
        try:
            self.query_one(Sidebar).set_spotlight(spotlight)
        except Exception:
            # A best-effort remote card must not interrupt dashboard rendering.
            logger.debug("Unable to update the spotlight card", exc_info=True)

    def _start_trending_fetch(self) -> None:
        try:
            sidebar = self.query_one(Sidebar)
            cached = load_cached_trending()
            if cached is not None:
                sidebar.set_trending(cached)
        except Exception:
            # Cached sidebar content is optional while the app is mounting.
            logger.debug("Unable to load cached trending content", exc_info=True)
        self.run_worker(self._fetch_trending(), exclusive=False, group="trending")

    async def _fetch_trending(self) -> None:
        trending = await fetch_trending()
        if trending is not None:
            save_cached_trending(trending)
        try:
            self.query_one(Sidebar).set_trending(trending)
        except Exception:
            # Trending is an optional sidebar enhancement.
            logger.debug("Unable to update the trending card", exc_info=True)

    # ── navigation ──

    def _select_default_package(self, *, render: bool = True) -> None:
        packages = self.visible_packages
        if not packages:
            return
        if self._workspace:
            favorite_project = next((p for p in self._workspace if p.favorite), None)
            project = favorite_project or self._workspace[0]
            selected = project.packages[0] if project.packages else None
        else:
            selected = next((r for r in packages if r.favorite), None) or packages[0]
        if selected is not None:
            self.navigate_to_package(selected, render=render, load=False)

    def navigate_to_package(
        self, ref: PackageRef, *, render: bool = True, load: bool = True
    ) -> None:
        self._workspace_state.select(ref)
        if load and self._workspace and ref.project_name:
            self._start_data_fetch(project_name=ref.project_name)
        if render:
            self._render_selected()
        try:
            self.query_one(Sidebar).select_package(ref)
        except Exception:
            # Navigation can race with sidebar mount/unmount transitions.
            logger.debug("Unable to select package in the sidebar", exc_info=True)

    @on(Sidebar.PackageSelected)
    def _on_package_selected(self, event: Sidebar.PackageSelected) -> None:
        self.navigate_to_package(event.ref)

    @on(Sidebar.ProjectSelected)
    def _on_project_selected(self, event: Sidebar.ProjectSelected) -> None:
        if not event.project.packages:
            self.notify("This project has no package sources.", severity="warning")
            return
        self.navigate_to_package(event.project.packages[0])

    def _render_selected(self) -> None:
        if self._workspace_state.selected_ref is None:
            return
        if self._render_in_progress:
            self._render_again = True
            return
        self._render_in_progress = True
        self.run_worker(self._render_selected_loop, exclusive=False, group="render")

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
            ref = self._workspace_state.selected_ref
            if ref is None:
                return
            try:
                main = self.query_one("#main-content", Container)
            except Exception:
                # A worker can finish while the screen is being replaced.
                logger.debug("Main content container is not mounted", exc_info=True)
                return
            info = self.get_package_info(ref)
            error = self.get_package_error(ref)
            derived = self.get_derived(ref)
            warnings = self.get_package_warnings(ref)
            await main.remove_children()
            if ref != self._workspace_state.selected_ref:
                return
            await main.mount(
                DetailView(ref, info, error, derived, warnings, parent_app=self)
            )
        except asyncio.CancelledError:
            return

    # ── data fetching ──

    def _start_data_fetch(
        self, *, force: bool = False, project_name: str | None = None
    ) -> None:
        self._refreshed_at = None
        refs = self._project.packages
        effective_project = project_name
        if self._workspace:
            target = project_name or (
                self._workspace_state.selected_ref.project_name
                if self._workspace_state.selected_ref
                else ""
            )
            if not target:
                return
            if not self._workspace_state.begin_load(target, force=force):
                return
            refs = [ref for ref in self._project.packages if ref.project_name == target]
            effective_project = target

        for ref in refs:
            key = package_key(ref)
            if key not in self._package_data:
                self._package_data[key] = PackageInfo(
                    name=ref.name, registry=ref.registry
                )
        group = f"fetch:{effective_project}" if effective_project else "fetch"
        self.run_worker(
            self._fetch_all_packages(
                refs,
                force=force,
                force_security_refresh=self._force_security_refresh or force,
                project_name=effective_project,
            ),
            exclusive=False,
            group=group,
        )

    async def _fetch_all_packages(
        self,
        refs: list[PackageRef],
        *,
        force: bool = False,
        force_security_refresh: bool = False,
        project_name: str | None = None,
    ) -> None:
        result = await self._intelligence.fetch_project(
            refs,
            force_refresh=force,
            force_security_refresh=force_security_refresh,
        )
        for key, package_result in result.results.items():
            if package_result.info is not None:
                self._package_data[key] = package_result.info
                self._package_errors.pop(key, None)
            if package_result.derived is not None:
                self._derived_data[key] = package_result.derived
            self._package_warnings[key] = package_result.warnings
            if package_result.error is not None:
                self._package_errors[key] = package_result.error
        self._refreshed_at = result.refreshed_at or datetime.now(UTC)
        if project_name:
            self._workspace_state.finish_load(project_name)
        self._notify_ui_update()

    async def _fetch_single_package(
        self, ref: PackageRef, *, force: bool = False
    ) -> None:
        key = package_key(ref)
        result = await self._intelligence.fetch_package(
            ref,
            force_refresh=force,
            force_security_refresh=force,
        )
        if result.info is not None:
            self._package_data[key] = result.info
        if result.derived is not None:
            self._derived_data[key] = result.derived
        self._package_warnings[key] = result.warnings
        if result.error is not None:
            self._package_errors[key] = result.error
        self._notify_ui_update(changed_ref=ref)

    def _notify_ui_update(self, changed_ref: PackageRef | None = None) -> None:
        try:
            sidebar = self.query_one(Sidebar)
            sidebar.refresh_versions()
        except Exception:
            # Data workers may finish during app teardown; the refresh is optional.
            logger.debug("Unable to refresh sidebar versions", exc_info=True)

        # Re-render the detail view when its package's data lands.
        if self._workspace_state.selected_ref is not None and (
            changed_ref is None
            or changed_ref.name.lower()
            == self._workspace_state.selected_ref.name.lower()
        ):
            self._render_selected()
