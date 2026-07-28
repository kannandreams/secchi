"""Top-row stat cards — label, big value, optional colored delta line."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from secchi.ui import palette


class StatCard(Vertical):
    """A compact stat card: label on top, value below, optional delta subline.

    Delta color convention is metric-specific and set by the caller via
    `delta_good` (True → positive delta is green; False → negative is green,
    e.g. for open-issue counts where fewer is healthier).
    """

    def __init__(
        self,
        label: str,
        value: str = "—",
        *,
        delta: str = "",
        value_color: str = "",
        delta_color: str = "",
    ) -> None:
        self._label = label
        self._value = value
        self._delta = delta
        self._value_color = value_color
        self._delta_color = delta_color
        super().__init__()
        self.add_class("stat-card")

    def compose(self) -> ComposeResult:
        yield Static(self._label, classes="stat-card-label")
        yield Static(self._value_markup(), classes="stat-card-value")
        yield Static(self._delta_markup(), classes="stat-card-delta")

    def set(
        self,
        value: str,
        *,
        delta: str = "",
        value_color: str = "",
        delta_color: str = "",
    ) -> None:
        self._value = value
        self._delta = delta
        self._value_color = value_color
        self._delta_color = delta_color
        if self.is_mounted:
            self.query_one(".stat-card-value", Static).update(self._value_markup())
            self.query_one(".stat-card-delta", Static).update(self._delta_markup())

    def _value_markup(self) -> str:
        if self._value_color:
            return f"[b {self._value_color}]{self._value}[/]"
        else:
            return f"[b {palette.GREEN}]{self._value}[/]"

    def _delta_markup(self) -> str:
        if self._delta:
            color = self._delta_color or "dim"
            return f"[{color}]{self._delta}[/]"
        return ""
