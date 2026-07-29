"""Custom bottom status bar — terminal-editor style with shortcut keys."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from secchi import __version__
from secchi.ui import palette


def _format_key(key: str) -> str:
    return f"[black on {palette.SECCHI}] {key} [/]"


SHORTCUTS = (
    f"{_format_key('r')} Refresh  "
    f"{_format_key('/')} Search  "
    f"{_format_key('?')} Help  "
    f"{_format_key('f')} Filter  "
    f"{_format_key('q')} Quit"
)


def format_path(path: Path | None) -> str:
    if path is None:
        return "—"
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def _age_text(refreshed_at: datetime | None) -> str:
    if refreshed_at is None:
        return "refreshing…"
    now = datetime.now(timezone.utc)
    mins = int((now - refreshed_at).total_seconds() / 60)
    if mins < 1:
        return "just now"
    if mins == 1:
        return "1m ago"
    if mins < 60:
        return f"{mins}m ago"
    return f"{mins // 60}h ago"


class SecchiFooter(Horizontal):
    """Docked bottom bar: info left, shortcuts center, config right."""

    def __init__(self, config_path: Path | None) -> None:
        super().__init__()
        self._config_path = config_path

    def compose(self) -> ComposeResult:
        yield Static("", id="footer-left")
        yield Static(SHORTCUTS, id="footer-center")
        yield Static(
            f"Config: {format_path(self._config_path)}", id="footer-right"
        )

    def on_mount(self) -> None:
        self._tick()
        self.set_interval(30, self._tick)

    def _tick(self) -> None:
        refreshed_at = getattr(self.app, "refreshed_at", None)
        age = _age_text(refreshed_at)
        try:
            self.query_one("#footer-left", Static).update(
                f"[{palette.GREEN}]secchi[/] {__version__}  "
                f"[dim]│[/]  Data: {age}"
            )
        except Exception:
            pass
