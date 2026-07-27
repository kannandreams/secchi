"""Sidebar widget — lists project packages grouped by registry."""

from __future__ import annotations

from collections import defaultdict

from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static

from pkgwatch.models import PackageRef, Project, Registry


class SidebarItem(Static):
    """A clickable package entry in the sidebar."""

    can_focus = True

    class Clicked(Message):
        """Emitted when a sidebar item is clicked."""

        def __init__(self, ref: PackageRef) -> None:
            super().__init__()
            self.ref = ref

    def __init__(self, ref: PackageRef) -> None:
        super().__init__(f"  {ref.name}")
        self.ref = ref

    def on_click(self) -> None:
        self.post_message(self.Clicked(self.ref))


class Sidebar(VerticalScroll):
    """Left sidebar showing project packages, grouped by registry."""

    class PackageSelected(Message):
        """Emitted when a package is clicked. Bubbles up to the app."""

        def __init__(self, ref: PackageRef) -> None:
            super().__init__()
            self.ref = ref

    def on_mount(self) -> None:
        self._items: dict[str, SidebarItem] = {}
        self._build()

    def _build(self) -> None:
        self.remove_children()
        self._items.clear()

        app = self.app
        if not hasattr(app, "project"):
            return

        project: Project = app.project

        self.mount(Static(project.name, classes="sidebar-title"))
        if project.description:
            self.mount(Static(project.description, classes="sidebar-subtitle"))
        self.mount(Static("─" * 22, classes="sidebar-divider"))

        groups: dict[Registry, list[PackageRef]] = defaultdict(list)
        for ref in project.packages:
            groups[ref.registry].append(ref)

        for registry in Registry:
            refs = groups.get(registry, [])
            if not refs:
                continue
            self.mount(
                Static(
                    f"{registry.icon} {registry.display_name}",
                    classes="sidebar-group-header",
                )
            )
            for ref in refs:
                item = SidebarItem(ref)
                key = f"{ref.registry.value}:{ref.name}"
                self._items[key] = item
                self.mount(item)

    def select_package(self, ref: PackageRef) -> None:
        key = f"{ref.registry.value}:{ref.name}"
        for k, item in self._items.items():
            if k == key:
                item.add_class("sidebar-item--selected")
            else:
                item.remove_class("sidebar-item--selected")

    def deselect_all(self) -> None:
        for item in self._items.values():
            item.remove_class("sidebar-item--selected")

    def on_side_bar_item_clicked(self, event: SidebarItem.Clicked) -> None:
        event.stop()
        self.select_package(event.ref)
        self.post_message(self.PackageSelected(event.ref))
