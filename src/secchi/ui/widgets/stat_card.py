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
        signal: str = "",
        value_color: str = "",
        delta_color: str = "",
        signal_color: str = "",
    ) -> None:
        self._label = label
        self._value = value
        self._delta = delta
        self._signal = signal
        self._value_color = value_color
        self._delta_color = delta_color
        self._signal_color = signal_color
        super().__init__()
        self.add_class("stat-card")

    def compose(self) -> ComposeResult:
        yield Static(self._label, classes="stat-card-label")
        yield Static(self._value_markup(), classes="stat-card-value")
        yield Static(self._delta_markup(), classes="stat-card-delta")
        yield Static(self._signal_markup(), classes="stat-card-signal")

    def set(
        self,
        value: str,
        *,
        delta: str = "",
        signal: str = "",
        value_color: str = "",
        delta_color: str = "",
        signal_color: str = "",
    ) -> None:
        self._value = value
        self._delta = delta
        self._signal = signal
        self._value_color = value_color
        self._delta_color = delta_color
        self._signal_color = signal_color
        if self.is_mounted:
            self.query_one(".stat-card-value", Static).update(self._value_markup())
            self.query_one(".stat-card-delta", Static).update(self._delta_markup())
            self.query_one(".stat-card-signal", Static).update(self._signal_markup())

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

    def _signal_markup(self) -> str:
        if self._signal:
            color = self._signal_color or "dim"
            return f"[{color}]{self._signal}[/]"
        return ""
