"""Custom top header bar — replaces Textual's default Header."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from pkgwatch import __version__
from pkgwatch.ui import palette


class PkgWatchHeader(Horizontal):
    """Docked top bar: SECCHI wordmark, product line, and shortcut hints."""

    def compose(self) -> ComposeResult:
        brand = f"[{palette.SECCHI}]SECCHI[/]"
        product = (
            "Open Source Package Intelligence   "
            f"[{palette.TEXT_MUTED}]v.{__version__}[/]"
        )
        right = (
            "/ Search   "
            "r Refresh   "
            "? Help   "
            "q Quit"
        )
        yield Static(brand, id="header-brand")
        yield Static(product, id="header-product")
        yield Static(right, id="header-right")
