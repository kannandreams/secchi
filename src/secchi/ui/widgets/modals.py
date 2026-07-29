"""Modal screens — fuzzy package search and the help overlay."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option

from secchi.models import PackageRef, Project


_SHORTCUTS = [
    ("↑ / ↓", "Move the selection in the sidebar"),
    ("Enter", "Open the selected package"),
    ("/", "Search packages by name"),
    ("r", "Refresh all package data"),
    ("f", "Toggle favorites-only filter"),
    ("?", "Show this help"),
    ("q / Ctrl+C", "Quit secchi"),
    ("Esc", "Close overlay / dismiss"),
]


class SearchScreen(ModalScreen[PackageRef | None]):
    """Substring search over the project's packages."""

    BINDINGS = [Binding("escape", "dismiss_screen", "Close", show=False)]

    def __init__(self, project: Project) -> None:
        super().__init__()
        self._project = project

    def compose(self) -> ComposeResult:
        with Vertical(id="search-box"):
            yield Static("Search packages", classes="modal-title")
            yield Input(placeholder="Type to filter…", id="search-input")
            yield OptionList(id="search-results")

    def on_mount(self) -> None:
        self._populate("")
        self.query_one("#search-input", Input).focus()

    def _populate(self, query: str) -> None:
        results = self.query_one("#search-results", OptionList)
        results.clear_options()
        q = query.lower().strip()
        for ref in self._visible_packages():
            if q and q not in ref.name.lower():
                continue
            star = "★ " if ref.favorite else "  "
            label = f"{star}{ref.name}  [dim]{ref.registry.display_name}[/]"
            results.add_option(Option(label, id=self._key(ref)))

    def _key(self, ref: PackageRef) -> str:
        return f"{ref.registry.value}:{ref.name}"

    @on(Input.Changed, "#search-input")
    def _on_change(self, event: Input.Changed) -> None:
        self._populate(event.value)

    @on(Input.Submitted, "#search-input")
    def _on_submit(self) -> None:
        results = self.query_one("#search-results", OptionList)
        if results.option_count > 0:
            highlighted = results.highlighted or 0
            option = results.get_option_at_index(highlighted)
            self._select(option.id)

    @on(OptionList.OptionSelected, "#search-results")
    def _on_option(self, event: OptionList.OptionSelected) -> None:
        self._select(event.option.id)

    def _select(self, key: str | None) -> None:
        if not key:
            self.dismiss(None)
            return
        for ref in self._visible_packages():
            if self._key(ref) == key:
                self.dismiss(ref)
                return
        self.dismiss(None)

    def _visible_packages(self) -> list[PackageRef]:
        seen: dict[str, PackageRef] = {}
        for ref in self._project.packages:
            key = ref.name.lower()
            current = seen.get(key)
            if current is None:
                seen[key] = PackageRef(ref.name, ref.registry, ref.favorite)
            elif ref.favorite and not current.favorite:
                current.favorite = True
        return list(seen.values())

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)


class HelpScreen(ModalScreen[None]):
    """Keyboard shortcut reference overlay."""

    BINDINGS = [Binding("escape,q,question_mark", "dismiss_screen", "Close", show=False)]

    def compose(self) -> ComposeResult:
        rows = "\n".join(f"[b white]{k:<12}[/] [white]{v}[/]" for k, v in _SHORTCUTS)
        with Vertical(id="help-box"):
            yield Static("Keyboard Shortcuts", classes="modal-title")
            yield Static(rows, id="help-body")
            yield Static("Press Esc to close", classes="modal-hint")

    def on_key(self) -> None:
        self.dismiss(None)

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)


class ExportScreen(ModalScreen[str | None]):
    """Export modal — JSON, PNG screenshot, or HTML."""

    BINDINGS = [
        Binding("escape", "dismiss_none", "Cancel", show=False),
        Binding("left", "focus_left", "Left", show=False),
        Binding("right", "focus_right", "Right", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="export-box"):
            yield Static("Export Package Data", classes="modal-title")
            yield OptionList(
                Option("JSON Output", id="json"),
                Option(
                    "Terminal Screenshot as Image in PNG Format [dim](coming soon)[/]",
                    id="png",
                ),
                Option(
                    "Single HTML file [dim](coming soon)[/]",
                    id="html",
                ),
                id="export-options",
            )
            with Horizontal(id="export-buttons"):
                yield Button("OK", variant="primary", id="export-ok")
                yield Button("Cancel", variant="default", id="export-cancel")

    def on_mount(self) -> None:
        options = self.query_one("#export-options", OptionList)
        options.highlighted = 0
        options.focus()

    @on(OptionList.OptionSelected, "#export-options")
    def _on_option_select(self) -> None:
        self._do_export()

    @on(Button.Pressed, "#export-ok")
    def _on_ok(self) -> None:
        self._do_export()

    @on(Button.Pressed, "#export-cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    def _do_export(self) -> None:
        options = self.query_one("#export-options", OptionList)
        if options.highlighted is not None:
            option = options.get_option_at_index(options.highlighted)
            if option.id == "json":
                self.dismiss(option.id)
                return
            self.notify("Coming soon", severity="warning")
            self.query_one("#export-options", OptionList).focus()
            return
        self.dismiss(None)

    def action_focus_left(self) -> None:
        self.query_one("#export-ok", Button).focus()

    def action_focus_right(self) -> None:
        self.query_one("#export-cancel", Button).focus()

    def action_dismiss_none(self) -> None:
        self.dismiss(None)
