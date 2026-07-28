"""Horizontal bar rendering — reused for adoption %, health scores, install %."""

from __future__ import annotations

_FULL = "█"
_EMPTY = "░"


def render_bar(fraction: float, width: int = 16, color: str = "green") -> str:
    """Return a Rich-markup horizontal bar for `fraction` (0.0–1.0).

    `color` must be a literal Rich color name (not a Textual CSS variable),
    since this string is fed to Static.update()/Text markup, not the stylesheet.
    """
    fraction = max(0.0, min(1.0, fraction))
    filled = round(fraction * width)
    bar = _FULL * filled + _EMPTY * (width - filled)
    return f"[{color}]{_FULL * filled}[/][dim]{_EMPTY * (width - filled)}[/]" if filled < width else f"[{color}]{bar}[/]"
