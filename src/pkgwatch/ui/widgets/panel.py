"""Reusable titled-box-with-caption panel — the mock's recurring container look."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static


class Panel(Vertical):
    """A bordered box with an embedded title and an optional dim caption footer.

    Children passed positionally are mounted into the body. Subclasses that need
    to build content lazily can override `compose_body()` instead.
    """

    def __init__(
        self,
        title: str,
        *children: Widget,
        caption: str = "",
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._title = title
        self._body_children = list(children)
        self._caption = caption
        self.add_class("panel")

    def on_mount(self) -> None:
        self.border_title = self._title

    def compose(self) -> ComposeResult:
        body_children = self.compose_body()
        yield PanelBody(*body_children)
        if self._caption:
            yield Static(self._caption, classes="panel-caption")

    def compose_body(self) -> list[Widget]:
        """Override to build body widgets lazily; default returns ctor children."""
        return self._body_children

    def set_caption(self, caption: str) -> None:
        self._caption = caption
        try:
            self.query_one(".panel-caption", Static).update(caption)
        except Exception:
            pass


class PanelBody(Vertical):
    """The flexible-height body region of a Panel (above the caption)."""

    def __init__(self, *children: Widget) -> None:
        super().__init__(*children)
        self.add_class("panel-body")
