"""Small chip widgets — language / license / package-type / homepage-link."""

from __future__ import annotations

from textual.widgets import Static

from pkgwatch.ui import palette


class Badge(Static):
    """A compact bordered chip. `variant='link'` renders a clickable URL."""

    def __init__(
        self,
        text: str,
        *,
        variant: str = "default",
        url: str = "",
        color: str = "",
    ) -> None:
        if variant == "link" and url:
            content = f"[{palette.CYAN}]{text}[/]"
        elif color:
            content = f"[{color}]{text}[/{color}]"
        else:
            content = text
        super().__init__(content)
        self.add_class("badge")
        if variant == "link":
            self.add_class("badge--link")
