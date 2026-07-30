"""Local snapshot cache — produces real week-over-week deltas.

GitHub stars and open-issue counts have no cheap point-in-time historical API,
so we persist a small rolling cache of snapshots per package. Deltas degrade to
None (rendered "—") until a baseline of the right age exists — never fabricated.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from secchi.models import HistorySnapshot


def history_file_path() -> Path:
    """XDG_CACHE_HOME/secchi/history.json, else ~/.cache/secchi/history.json."""
    if base := os.environ.get("XDG_CACHE_HOME", ""):
        root = Path(base)
    else:
        root = Path.home() / ".cache"
    return root / "secchi" / "history.json"


def _load_all() -> dict[str, list[dict]]:
    path = history_file_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all(data: dict[str, list[dict]]) -> None:
    path = history_file_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
    except OSError:
        pass


def load_snapshots(key: str) -> list[HistorySnapshot]:
    snapshots: list[HistorySnapshot] = []
    for raw in _load_all().get(key, []):
        ts = raw.get("timestamp")
        try:
            timestamp = datetime.fromisoformat(ts) if ts else None
        except (ValueError, TypeError):
            timestamp = None
        if timestamp is None:
            continue
        snapshots.append(
            HistorySnapshot(
                timestamp=timestamp,
                stars=raw.get("stars", 0),
                open_issues=raw.get("open_issues", 0),
                health_score=raw.get("health_score"),
                reverse_dependency_count=raw.get("reverse_dependency_count"),
            )
        )
    return snapshots


def append_snapshot(key: str, snapshot: HistorySnapshot, max_keep: int = 420) -> None:
    data = _load_all()
    entries = data.get(key, [])
    entries.append(
        {
            "timestamp": snapshot.timestamp.isoformat(),
            "stars": snapshot.stars,
            "open_issues": snapshot.open_issues,
            "health_score": snapshot.health_score,
            "reverse_dependency_count": snapshot.reverse_dependency_count,
        }
    )
    data[key] = entries[-max_keep:]
    _save_all(data)


def find_baseline(
    snapshots: list[HistorySnapshot],
    min_age_days: int = 6,
    max_age_days: int = 10,
) -> HistorySnapshot | None:
    """Closest snapshot whose age falls in [min_age_days, max_age_days]."""
    now = datetime.now(timezone.utc)
    candidates: list[tuple[float, HistorySnapshot]] = []
    for snap in snapshots:
        ts = snap.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age_days = (now - ts).total_seconds() / 86400
        if min_age_days <= age_days <= max_age_days:
            candidates.append((abs(age_days - 7), snap))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0])
    return candidates[0][1]


def compute_delta(current: int, baseline: int | None) -> int | None:
    """current - baseline, or None if no baseline — never fabricate."""
    if baseline is None:
        return None
    return current - baseline
