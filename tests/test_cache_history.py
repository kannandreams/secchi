"""Deterministic tests for cache freshness and historical signal calculations."""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta

from secchi import cache, history
from secchi.history import compute_delta, find_baseline
from secchi.models import HistorySnapshot, PackageInfo, Registry
from secchi.schema import CACHE_SCHEMA_VERSION
from secchi.services.intelligence import health_history_points

NOW = datetime(2026, 8, 2, 12, tzinfo=UTC)


def test_same_day_cache_is_a_hit_and_previous_day_cache_is_a_miss(tmp_path) -> None:
    info = PackageInfo(name="demo", registry=Registry.PYPI, latest_version="1.0.0")
    cache.save_package_cache("pypi:demo", info, NOW, root=tmp_path)

    same_day = cache.load_package_cache("pypi:demo", root=tmp_path, now=lambda: NOW)
    previous_day = cache.load_package_cache(
        "pypi:demo",
        root=tmp_path,
        now=lambda: NOW + timedelta(days=1),
    )

    assert same_day is not None
    assert same_day[0].latest_version == "1.0.0"
    assert previous_day is None


def test_corrupt_cache_is_ignored_safely(tmp_path) -> None:
    path = cache.package_cache_path("pypi:demo", root=tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{not valid json")

    assert cache.load_package_cache("pypi:demo", root=tmp_path, now=lambda: NOW) is None


def test_cache_schema_version_mismatch_is_ignored(tmp_path) -> None:
    info = PackageInfo(name="demo", registry=Registry.PYPI)
    cache.save_package_cache("pypi:demo", info, NOW, root=tmp_path)
    path = cache.package_cache_path("pypi:demo", root=tmp_path)
    payload = json.loads(path.read_text())
    payload["schema_version"] = CACHE_SCHEMA_VERSION + 1
    path.write_text(json.dumps(payload))

    assert cache.load_package_cache("pypi:demo", root=tmp_path, now=lambda: NOW) is None


def test_append_snapshot_persists_and_round_trips_via_load_snapshots(tmp_path) -> None:
    path = tmp_path / "history.json"

    history.append_snapshot(
        "pypi:demo",
        HistorySnapshot(NOW - timedelta(days=7), 10, 1, health_score=80),
        path=path,
    )
    history.append_snapshot(
        "pypi:demo",
        HistorySnapshot(NOW, 12, 2, health_score=82),
        path=path,
    )
    history.append_snapshot(
        "pypi:other",
        HistorySnapshot(NOW, 5, 0, health_score=70),
        path=path,
    )

    demo_snapshots = history.load_snapshots("pypi:demo", path=path)
    other_snapshots = history.load_snapshots("pypi:other", path=path)

    assert [s.stars for s in demo_snapshots] == [10, 12]
    assert [s.stars for s in other_snapshots] == [5]


def test_append_snapshot_leaves_no_temp_or_lock_file_behind(tmp_path) -> None:
    path = tmp_path / "history.json"

    history.append_snapshot("pypi:demo", HistorySnapshot(NOW, 10, 1), path=path)

    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "history.json"]
    assert leftovers == []


def test_append_snapshot_survives_a_failed_write_without_corrupting_history(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "history.json"
    history.append_snapshot(
        "pypi:demo", HistorySnapshot(NOW - timedelta(days=7), 10, 1), path=path
    )
    original = path.read_text()

    def _boom(*args, **kwargs) -> None:
        raise OSError("simulated crash mid-write")

    monkeypatch.setattr(history.os, "replace", _boom)

    history.append_snapshot("pypi:demo", HistorySnapshot(NOW, 99, 9), path=path)

    assert path.read_text() == original
    assert [s.stars for s in history.load_snapshots("pypi:demo", path=path)] == [10]


def test_append_snapshot_reclaims_a_stale_lock_instead_of_hanging(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(history, "_LOCK_STALE_SECONDS", 1)
    monkeypatch.setattr(history, "_LOCK_TIMEOUT_SECONDS", 5)
    path = tmp_path / "history.json"
    stale_lock = tmp_path / "history.json.lock"
    stale_lock.parent.mkdir(parents=True, exist_ok=True)
    stale_lock.write_text("")
    long_ago = time.time() - 60
    os.utime(stale_lock, (long_ago, long_ago))

    history.append_snapshot("pypi:demo", HistorySnapshot(NOW, 10, 1), path=path)

    assert not stale_lock.exists()
    assert [s.stars for s in history.load_snapshots("pypi:demo", path=path)] == [10]


def test_append_snapshot_proceeds_unlocked_after_timeout_when_lock_is_held(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(history, "_LOCK_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(history, "_LOCK_POLL_SECONDS", 0.01)
    path = tmp_path / "history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    held_lock = tmp_path / "history.json.lock"
    fd = os.open(held_lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        history.append_snapshot("pypi:demo", HistorySnapshot(NOW, 10, 1), path=path)
        assert [s.stars for s in history.load_snapshots("pypi:demo", path=path)] == [10]
    finally:
        os.close(fd)
        held_lock.unlink()


def test_history_baseline_chooses_closest_snapshot_in_age_window() -> None:
    snapshots = [
        HistorySnapshot(NOW - timedelta(days=8), 10, 1),
        HistorySnapshot(NOW - timedelta(days=7), 20, 2),
        HistorySnapshot(NOW - timedelta(days=15), 30, 3),
    ]

    baseline = find_baseline(snapshots, now=lambda: NOW)

    assert baseline is snapshots[1]


def test_monthly_growth_uses_28_to_35_day_baseline() -> None:
    baseline = HistorySnapshot(
        timestamp=NOW - timedelta(days=31),
        stars=10,
        open_issues=1,
        reverse_dependency_count=100,
    )
    monthly_baseline = find_baseline(
        [baseline], min_age_days=28, max_age_days=35, now=lambda: NOW
    )

    assert monthly_baseline is baseline
    assert compute_delta(125, monthly_baseline.reverse_dependency_count) == 25
    assert compute_delta(125, None) is None


def test_health_timeline_keeps_latest_monthly_snapshot_and_current_score() -> None:
    snapshots = [
        HistorySnapshot(datetime(2026, 6, 10, tzinfo=UTC), 1, 1, 80),
        HistorySnapshot(datetime(2026, 7, 1, tzinfo=UTC), 1, 1, 82),
        HistorySnapshot(datetime(2026, 7, 20, tzinfo=UTC), 1, 1, 88),
    ]

    timeline = health_history_points(snapshots, 92, now=lambda: NOW)

    assert [(point.label, point.value) for point in timeline] == [
        ("Jun", 80),
        ("Jul", 88),
        ("Aug", 92),
    ]
