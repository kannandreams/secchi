"""Dashboard view — stat cards + package table."""

from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import DataTable, Static

from pkgwatch.models import PackageInfo, PackageRef, Project
from pkgwatch.utils import shorten_number


class DashboardView(VerticalScroll):
    """Main dashboard: stat cards on top, package table below."""

    DEFAULT_CSS = """
    DashboardView {
        width: 1fr;
        height: 1fr;
        padding: 1 2;
    }
    """

    def __init__(self, parent_app: object) -> None:
        super().__init__(id="dashboard-view")
        self._app = parent_app

    def compose(self) -> ComposeResult:
        with Horizontal(id="stat-cards"):
            yield StatCard("Packages", "0")
            yield StatCard("Registries", "0")
            yield StatCard("Outdated", "0")
            yield StatCard("Last Refresh", "—")

        yield DataTable(id="package-table", cursor_type="row", zebra_stripes=True)

        with Horizontal(id="status-bar"):
            yield Static("Ready", classes="status-left")
            yield Static("", classes="status-right", id="status-refresh-time")

    def on_mount(self) -> None:
        table = self.query_one("#package-table", DataTable)
        table.add_columns("Package", "Registry", "Version", "Downloads", "Updated")

    def refresh_data(self) -> None:
        app = self._app
        if not hasattr(app, "project"):
            return
        self._update_stats()
        self._update_table()
        self._update_status()

    def _update_stats(self) -> None:
        app = self._app
        project: Project = app.project
        packages = project.packages
        data = app.package_data

        total = len(packages)
        registries = len({ref.registry for ref in packages})

        outdated = 0
        for ref in packages:
            info = data.get(f"{ref.registry.value}:{ref.name}")
            if info and info.latest_release_date:
                age = (datetime.now(timezone.utc) - info.latest_release_date).days
                if age > 90:
                    outdated += 1

        refreshed_at = getattr(app, "refreshed_at", None)
        refresh_text = "—"
        if refreshed_at:
            diff = datetime.now(timezone.utc) - refreshed_at
            mins = int(diff.total_seconds() / 60)
            if mins < 1:
                refresh_text = "just now"
            elif mins == 1:
                refresh_text = "1m ago"
            else:
                refresh_text = f"{mins}m ago"

        cards = list(self.query("StatCard"))
        values = [str(total), str(registries), str(outdated), refresh_text]
        for card, value in zip(cards, values):
            if hasattr(card, "set_value"):
                card.set_value(value)

    def _update_table(self) -> None:
        app = self._app
        project: Project = app.project
        data = app.package_data
        table = self.query_one("#package-table", DataTable)
        table.clear()

        for ref in project.packages:
            key = f"{ref.registry.value}:{ref.name}"
            info = data.get(key)
            error = (
                app.get_package_error(ref)
                if hasattr(app, "get_package_error")
                else None
            )

            if error and (not info or not info.latest_version):
                name_cell = Text(f"{ref.registry.icon} {ref.name}", style="red")
                table.add_row(
                    name_cell,
                    ref.registry.display_name,
                    "error",
                    "—",
                    str(error.message)[:40],
                    key=key,
                )
                continue

            if not info or not info.latest_version:
                name_cell = Text(f"{ref.registry.icon} {ref.name}", style="dim")
                table.add_row(
                    name_cell,
                    ref.registry.display_name,
                    "loading…",
                    "—",
                    "—",
                    key=key,
                )
                continue

            downloads = shorten_number(info.total_downloads)
            updated = ""
            if info.latest_release_date:
                diff = datetime.now(timezone.utc) - info.latest_release_date
                d = diff.days
                if d == 0:
                    updated = "today"
                elif d == 1:
                    updated = "1d ago"
                elif d < 30:
                    updated = f"{d}d ago"
                elif d < 365:
                    updated = f"{d // 30}mo ago"
                else:
                    updated = f"{d // 365}y ago"

            name_cell = Text(f"{ref.registry.icon} {ref.name}", style="bold")
            table.add_row(
                name_cell,
                ref.registry.display_name,
                info.latest_version,
                downloads,
                updated,
                key=key,
            )

    def _update_status(self) -> None:
        app = self._app
        project: Project = app.project
        total = len(project.packages)
        loaded = sum(
            1
            for ref in project.packages
            if app.package_data.get(
                f"{ref.registry.value}:{ref.name}",
                PackageInfo(name="", registry=ref.registry),
            ).latest_version
        )

        status = self.query_one("#status-refresh-time", Static)
        status.update(f"{loaded}/{total} loaded")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key is None or not hasattr(event.row_key, "value"):
            return
        key = str(event.row_key.value)
        try:
            registry_str, name = key.split(":", 1)
            from pkgwatch.models import Registry

            registry = Registry(registry_str.strip())
            ref = PackageRef(name=name.strip(), registry=registry)
            if hasattr(self._app, "navigate_to_package"):
                self._app.navigate_to_package(ref)
        except (ValueError, KeyError):
            pass


class StatCard(Static):
    """A compact stat card — label on top, value below."""

    DEFAULT_CSS = """
    StatCard {
        width: 1fr;
        height: 4;
        padding: 0 2;
        margin: 0 1 0 0;
        border: solid $primary-darken-2;
        background: $surface;
    }
    """

    def __init__(self, label: str, value: str = "—") -> None:
        super().__init__()
        self._label = label
        self._value = value

    def on_mount(self) -> None:
        self.update(self._card_content())

    def set_value(self, value: str) -> None:
        self._value = value
        if self.is_mounted:
            self.update(self._card_content())

    def _card_content(self) -> str:
        return f"{self._label}\n{self._value}"
