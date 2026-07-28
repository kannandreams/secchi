"""Modal screens — fuzzy package search and the help overlay."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from pkgwatch.models import PackageRef, Project


_SHORTCUTS = [
    ("↑ / ↓", "Move the selection in the sidebar"),
    ("Enter", "Open the selected package"),
    ("/", "Search packages by name"),
    ("r", "Refresh all package data"),
    ("f", "Toggle favorites-only filter"),
    ("?", "Show this help"),
    ("q / Ctrl+C", "Quit pkgwatch"),
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
        rows = "\n".join(f"[b blue]{k:<12}[/] {v}" for k, v in _SHORTCUTS)
        with Vertical(id="help-box"):
            yield Static("Keyboard Shortcuts", classes="modal-title")
            yield Static(rows, id="help-body")
            yield Static("[dim]Press Esc to close[/]", classes="modal-hint")

    def on_key(self) -> None:
        self.dismiss(None)

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)
