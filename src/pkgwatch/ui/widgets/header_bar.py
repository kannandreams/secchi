"""Custom top header bar — replaces Textual's default Header."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from pkgwatch import __version__


class PkgWatchHeader(Horizontal):
    """Docked top bar: brand + tagline on the left, shortcut hints on the right."""

    def compose(self) -> ComposeResult:
        left = (
            f"[b green]pkgwatch[/]  [dim]│[/]  Package Intelligence"
            f"   [dim]v{__version__}[/]"
        )
        right = (
            "[dim]│[/]  [b]/[/] Search   "
            "[b]r[/] Refresh   "
            "[b]?[/] Help   "
            "[b]q[/] Quit  "
        )
        yield Static(left, id="header-left")
        yield Static(right, id="header-right")
