"""Local snapshot cache — produces real week-over-week deltas.

GitHub stars and open-issue counts have no cheap point-in-time historical API,
so we persist a small rolling cache of snapshots per package. Deltas degrade to
None (rendered "—") until a baseline of the right age exists — never fabricated.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

from secchi.models import HistorySnapshot

_LOCK_STALE_SECONDS = 30
_LOCK_TIMEOUT_SECONDS = 5
_LOCK_POLL_SECONDS = 0.05


def history_file_path(root: Path | None = None) -> Path:
    """XDG_CACHE_HOME/secchi/history.json, else ~/.cache/secchi/history.json."""
    if root is not None:
        return root / "history.json"
    if base := os.environ.get("XDG_CACHE_HOME", ""):
        root = Path(base)
    else:
        root = Path.home() / ".cache"
    return root / "secchi" / "history.json"


@contextlib.contextmanager
def _locked(path: Path) -> Iterator[None]:
    """Best-effort advisory lock so two secchi processes don't lose each
    other's snapshots in a read-modify-write race on history.json.

    Uses atomic lock-file creation (``O_CREAT | O_EXCL``), which behaves
    identically on POSIX and Windows — no ``fcntl``/``msvcrt`` split needed.
    A lock older than ``_LOCK_STALE_SECONDS`` is assumed abandoned by a
    crashed holder and reclaimed. If the lock can't be acquired within
    ``_LOCK_TIMEOUT_SECONDS``, the operation proceeds unlocked rather than
    hanging or failing — history is a best-effort local cache, never a
    reason to block a run.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f"{path.name}.lock")
    deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
    fd: int | None = None
    try:
        while fd is None:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except OSError:
                try:
                    age = time.time() - lock_path.stat().st_mtime
                except OSError:
                    age = 0.0
                if age > _LOCK_STALE_SECONDS:
                    with contextlib.suppress(OSError):
                        lock_path.unlink()
                    continue
                if time.monotonic() >= deadline:
                    break
                time.sleep(_LOCK_POLL_SECONDS)
        yield
    finally:
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)
            with contextlib.suppress(OSError):
                lock_path.unlink()


def _load_all(path: Path | None = None) -> dict[str, list[dict]]:
    path = path or history_file_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all(data: dict[str, list[dict]], path: Path | None = None) -> None:
    path = path or history_file_path()
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(data, indent=2))
        os.replace(tmp_path, path)
    except OSError:
        with contextlib.suppress(OSError):
            tmp_path.unlink()


def load_snapshots(key: str, *, path: Path | None = None) -> list[HistorySnapshot]:
    snapshots: list[HistorySnapshot] = []
    for raw in _load_all(path).get(key, []):
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


def append_snapshot(
    key: str,
    snapshot: HistorySnapshot,
    max_keep: int = 420,
    *,
    path: Path | None = None,
) -> None:
    path = path or history_file_path()
    with _locked(path):
        data = _load_all(path)
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
        _save_all(data, path)


def find_baseline(
    snapshots: list[HistorySnapshot],
    min_age_days: int = 6,
    max_age_days: int = 10,
    *,
    now: Callable[[], datetime] | None = None,
) -> HistorySnapshot | None:
    """Closest snapshot whose age falls in [min_age_days, max_age_days]."""
    current_time = (now or (lambda: datetime.now(UTC)))()
    candidates: list[tuple[float, HistorySnapshot]] = []
    for snap in snapshots:
        ts = snap.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        age_days = (current_time - ts).total_seconds() / 86400
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
