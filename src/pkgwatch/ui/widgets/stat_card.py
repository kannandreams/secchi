"""Top-row stat cards — label, big value, optional colored delta line."""

from __future__ import annotations

from textual.widgets import Static


class StatCard(Static):
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
        super().__init__(self._content())
        self.add_class("stat-card")

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
            self.update(self._content())

    def _content(self) -> str:
        label = f"[dim]{self._label}[/dim]"
        if self._value_color:
            value = f"[b {self._value_color}]{self._value}[/]"
        else:
            value = f"[b]{self._value}[/b]"
        delta = ""
        if self._delta:
            color = self._delta_color or "dim"
            delta = f"\n[{color}]{self._delta}[/]"
        return f"{label}\n{value}{delta}"
