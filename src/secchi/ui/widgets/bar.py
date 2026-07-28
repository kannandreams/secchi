"""Horizontal bar rendering — reused for adoption %, health scores, install %."""

from __future__ import annotations

_FULL = "█"
_EMPTY = "░"


from secchi.ui import palette


def render_bar(
    fraction: float,
    width: int = 16,
    color: str = palette.PROGRESS_FG,
    *,
    filled_char: str = _FULL,
    empty_char: str = _EMPTY,
) -> str:
    """Return a Rich-markup horizontal bar for `fraction` (0.0–1.0).

    `color` must be a literal Rich color name (not a Textual CSS variable),
    since this string is fed to Static.update()/Text markup, not the stylesheet.
    """
    fraction = max(0.0, min(1.0, fraction))
    filled = round(fraction * width)
    bar = filled_char * filled + empty_char * (width - filled)
    if filled < width:
        return (
            f"[{color}]{filled_char * filled}[/]"
            f"[{palette.PROGRESS_BG}]{empty_char * (width - filled)}[/]"
        )
    return f"[{color}]{bar}[/]"
