"""Detail view widget — package details with tabs."""

from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import DataTable, Markdown, Static, TabbedContent, TabPane
from textual_plotext import PlotextPlot

from pkgwatch.models import FetchError, PackageInfo, PackageRef
from pkgwatch.utils import shorten_number


class DetailView(Container):
    """Detailed view for a single package — replaces dashboard in main area."""

    DEFAULT_CSS = """
    DetailView {
        width: 1fr;
        height: 1fr;
        layout: horizontal;
    }

    DetailView #detail-sidebar {
        width: 26;
        height: 100%;
        background: $panel-darken-1;
        border-right: tall $primary-darken-2;
        padding: 0 1;
    }

    DetailView #detail-content {
        width: 1fr;
        height: 1fr;
        padding: 1 2;
    }
    """

    def __init__(
        self,
        ref: PackageRef,
        info: PackageInfo | None,
        error: FetchError | None,
        parent_app: object,
    ) -> None:
        super().__init__(id="detail-view")
        self._ref = ref
        self._info = info
        self._error = error
        self._app = parent_app

    def compose(self) -> ComposeResult:
        yield Static(self._build_sidebar(), id="detail-sidebar")

        with VerticalScroll(id="detail-content"):
            yield Static(self._build_header(), id="detail-header")
            yield Static(self._build_meta(), id="detail-meta")

            if self._info:
                with TabbedContent():
                    with TabPane("Stats"):
                        yield PlotextPlot(id="trend-chart")
                    with TabPane("Versions"):
                        yield DataTable(
                            id="versions-table", cursor_type=None, zebra_stripes=True
                        )
                    with TabPane("Dependencies"):
                        yield DataTable(
                            id="deps-table", cursor_type=None, zebra_stripes=True
                        )
                    with TabPane("Release Notes"):
                        yield Container(Markdown(id="notes-content"))
            elif self._error:
                yield Static(
                    f"[bold red]Error[/]\n{self._error.message}",
                    id="error-view",
                )
            else:
                yield Static("Loading…", id="loading-view")

    def on_mount(self) -> None:
        if not self._info:
            return
        self._render_versions()
        self._render_dependencies()
        self._render_notes()
        self._render_chart()

    def _build_sidebar(self) -> str:
        lines = [
            f"[b]{self._ref.registry.icon} {self._ref.name}[/]",
            "",
            f"Registry: {self._ref.registry.display_name}",
        ]
        if self._info:
            if self._info.author:
                lines.append(f"Author: {self._info.author}")
            if self._info.license:
                lines.append(f"License: {self._info.license}")

            # Download breakdown
            dc = self._info.download_counts
            if dc.today or dc.week or dc.month:
                lines.append("")
                lines.append("[b]Downloads[/]")
                if dc.today:
                    lines.append(f"  Today: {shorten_number(dc.today)}")
                if dc.week:
                    lines.append(f"  Week:  {shorten_number(dc.week)}")
                if dc.month:
                    lines.append(f"  Month: {shorten_number(dc.month)}")

            # GitHub stats
            gh = self._info.github_stats
            if gh.stars or gh.forks:
                lines.append("")
                lines.append("[b]GitHub[/]")
                lines.append(f"  Stars: {shorten_number(gh.stars)}")
                lines.append(f"  Forks: {shorten_number(gh.forks)}")

            if self._info.homepage:
                lines.append(f"\n{self._info.homepage}")
            if self._info.repository_url:
                lines.append(f"{self._info.repository_url}")
        return "\n".join(lines)

    def _build_header(self) -> str:
        icon = self._ref.registry.icon
        name = self._ref.name
        if self._info and self._info.latest_version:
            version = self._info.latest_version
            header = f"[b]{icon} {name}  {version}[/]"
        else:
            header = f"[b]{icon} {name}[/]"

        if self._info and self._info.description:
            desc = self._info.description[:200]
            header += f"\n\n{desc}"
        return header

    def _build_meta(self) -> str:
        if not self._info:
            return ""
        parts = []
        if self._info.total_downloads:
            parts.append(
                f"[dim]Downloads[/] [b]{shorten_number(self._info.total_downloads)}[/]"
            )
        if self._info.latest_release_date:
            d = (datetime.now(timezone.utc) - self._info.latest_release_date).days
            age = "today" if d == 0 else f"{d}d ago"
            parts.append(f"[dim]Released[/] [b]{age}[/]")
        if self._info.versions:
            parts.append(f"[dim]Versions[/] [b]{len(self._info.versions)}[/]")
        if self._info.dependencies:
            deps_count = sum(1 for d in self._info.dependencies if not d.optional)
            parts.append(f"[dim]Deps[/] [b]{deps_count}[/]")
        return "  ·  ".join(parts)

    def _render_chart(self) -> None:
        if not self._info or not self._info.download_trend:
            return
        try:
            chart = self.query_one("#trend-chart", PlotextPlot)
            plt = chart.plt
            trend = self._info.download_trend
            dates = [p.date for p in trend]
            downloads = [p.count for p in trend]
            plt.clear_data()
            plt.plot_date(dates, downloads)
            plt.title(f"Downloads — Last {len(trend)} Days")
            plt.theme("textual-design-dark")
            plt.grid(True)
            chart.refresh()
        except Exception:
            pass

    def _render_versions(self) -> None:
        if not self._info:
            return
        table = self.query_one("#versions-table", DataTable)
        table.add_columns("Version", "Released", "Downloads")
        for ver in self._info.versions[:50]:
            date_str = ver.release_date.strftime("%Y-%m-%d") if ver.release_date else ""
            label = f"[red](yanked) [/]{ver.version}" if ver.is_yanked else ver.version
            style = "red" if ver.is_yanked else ""
            table.add_row(
                Text(label, style=style),
                date_str,
                shorten_number(ver.downloads),
            )

    def _render_dependencies(self) -> None:
        if not self._info:
            return
        table = self.query_one("#deps-table", DataTable)
        table.add_columns("Package", "Requirement", "Type")
        for dep in self._info.dependencies:
            dep_type = "optional" if dep.optional else "required"
            table.add_row(
                Text(dep.name),
                dep.requirement,
                dep_type,
            )

    def _render_notes(self) -> None:
        if not self._info or not self._info.release_notes:
            try:
                notes = self.query_one("#notes-content", Markdown)
                notes.update(
                    "No release notes available.\n\nCheck the package's homepage or repository."
                )
            except Exception:
                pass
            return
        try:
            notes = self.query_one("#notes-content", Markdown)
            notes.update(self._info.release_notes)
        except Exception:
            pass
