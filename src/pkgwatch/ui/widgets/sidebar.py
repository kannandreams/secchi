"""Sidebar — favorites + all packages, keyboard-navigable, with a shortcuts box."""

from __future__ import annotations

from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Static

from pkgwatch.models import PackageRef, Project


_SHORTCUTS = [
    ("↑/↓", "Navigate"),
    ("Enter", "Select"),
    ("/", "Search"),
    ("r", "Refresh"),
    ("f", "Filter"),
    ("?", "Help"),
    ("q", "Quit"),
]


class SidebarItem(Static):
    """A clickable/selectable package entry showing name + version."""

    def __init__(self, ref: PackageRef) -> None:
        self.ref = ref
        self._version = ""
        super().__init__(self._content())
        self.can_focus = False

    def set_version(self, version: str) -> None:
        self._version = version
        self.update(self._content())

    def _content(self) -> str:
        name = self.ref.name
        display = name if len(name) <= 14 else name[:13] + "…"
        version = self._version or "…"
        return f"{display:<14}[dim]{version:>6}[/]"

    def on_click(self) -> None:
        self.post_message(Sidebar.PackageSelected(self.ref))


class Sidebar(VerticalScroll):
    """Left sidebar: PACKAGES (favorites + all) and a docked SHORTCUTS box."""

    can_focus = True

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("enter", "select_cursor", "Select", show=False),
    ]

    class PackageSelected(Message):
        """Emitted when a package is chosen (click or Enter). Bubbles to the app."""

        def __init__(self, ref: PackageRef) -> None:
            super().__init__()
            self.ref = ref

    def __init__(self) -> None:
        super().__init__()
        self._items: dict[str, SidebarItem] = {}
        self._order: list[str] = []
        self._cursor: int = -1
        self._favorites_only: bool = False

    def on_mount(self) -> None:
        self._build()

    # ── construction ──

    def _build(self) -> None:
        self.remove_children()
        self._items.clear()
        self._order.clear()

        app = self.app
        if not hasattr(app, "project"):
            return
        project: Project = app.project

        self.mount(Static("PACKAGES", classes="sidebar-title"))

        favorites = [r for r in project.packages if r.favorite]
        all_pkgs = project.packages

        if favorites:
            self.mount(
                Static(
                    f"[yellow]★ Favorites[/] [dim]({len(favorites)})[/]",
                    classes="sidebar-section",
                )
            )
            for ref in favorites:
                self._add_item(ref, key_suffix="fav")

        self.mount(
            Static(
                f"All Packages [dim]({len(all_pkgs)})[/]",
                classes="sidebar-section sidebar-section--all",
            )
        )
        shown = favorites if self._favorites_only else all_pkgs
        for ref in shown:
            self._add_item(ref, key_suffix="all")

        # docked shortcuts box
        rows = "\n".join(f"[b]{k:<6}[/] {v}" for k, v in _SHORTCUTS)
        self.mount(
            Vertical(
                Static("SHORTCUTS", classes="shortcuts-title"),
                Static(rows, classes="shortcuts-body"),
                id="shortcuts-box",
            )
        )

        self._refresh_versions()
        self._highlight()

    def _add_item(self, ref: PackageRef, key_suffix: str) -> None:
        item = SidebarItem(ref)
        order_key = f"{key_suffix}:{ref.registry.value}:{ref.name}"
        self._items[order_key] = item
        self._order.append(order_key)
        self.mount(item)

    # ── version population ──

    def _refresh_versions(self) -> None:
        app = self.app
        data = getattr(app, "package_data", {})
        for order_key, item in self._items.items():
            info = data.get(f"{item.ref.registry.value}:{item.ref.name}")
            if info and info.latest_version:
                item.set_version(info.latest_version)

    def refresh_versions(self) -> None:
        self._refresh_versions()

    # ── selection / highlight ──

    def _pkg_key(self, ref: PackageRef) -> str:
        return f"{ref.registry.value}:{ref.name}"

    def select_package(self, ref: PackageRef) -> None:
        target = self._pkg_key(ref)
        for i, order_key in enumerate(self._order):
            if self._pkg_key(self._items[order_key].ref) == target:
                self._cursor = i
                break
        self._highlight()

    def deselect_all(self) -> None:
        self._cursor = -1
        self._highlight()

    def _highlight(self) -> None:
        for i, order_key in enumerate(self._order):
            item = self._items[order_key]
            item.set_class(i == self._cursor, "sidebar-item--selected")

    # ── actions ──

    def action_cursor_down(self) -> None:
        if not self._order:
            return
        self._cursor = min(self._cursor + 1, len(self._order) - 1)
        self._highlight()
        self._scroll_to_cursor()

    def action_cursor_up(self) -> None:
        if not self._order:
            return
        self._cursor = max(self._cursor - 1, 0)
        self._highlight()
        self._scroll_to_cursor()

    def action_select_cursor(self) -> None:
        if 0 <= self._cursor < len(self._order):
            ref = self._items[self._order[self._cursor]].ref
            self.post_message(self.PackageSelected(ref))

    def _scroll_to_cursor(self) -> None:
        if 0 <= self._cursor < len(self._order):
            item = self._items[self._order[self._cursor]]
            self.scroll_to_widget(item, animate=False)

    def toggle_favorites_filter(self) -> None:
        self._favorites_only = not self._favorites_only
        self._build()
