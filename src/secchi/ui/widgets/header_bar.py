"""Custom top header bar — replaces Textual's default Header."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from secchi import __version__
from secchi.ui import palette


class SecchiHeader(Horizontal):
    """Docked top bar: SECCHI wordmark and product line."""

    def compose(self) -> ComposeResult:
        brand = "SECCHI"
        product = (
            "Open Source Package Intelligence   "
            f"[{palette.TEXT_MUTED}]v.{__version__}[/]"
        )
        yield Static(brand, id="header-brand")
        yield Static(product, id="header-product")
