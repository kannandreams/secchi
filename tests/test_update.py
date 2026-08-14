from datetime import UTC, datetime, timedelta
from pathlib import Path

from secchi.export import report_filename, report_mime_type
from secchi.update import check_for_update


def test_update_notice_is_returned_for_newer_release(tmp_path: Path) -> None:
    now = datetime(2026, 8, 14, tzinfo=UTC)
    notice = check_for_update(
        current_version="0.1.5",
        cache_path=tmp_path / "update.json",
        now=lambda: now,
        fetch=lambda: {"latest_version": "0.1.6"},
    )

    assert notice is not None
    assert "0.1.6" in notice.message
    assert "pipx upgrade secchi" in notice.message


def test_update_check_uses_fresh_cache_without_network(tmp_path: Path) -> None:
    cache = tmp_path / "update.json"
    now = datetime(2026, 8, 14, tzinfo=UTC)
    check_for_update(
        current_version="0.1.5",
        cache_path=cache,
        now=lambda: now,
        fetch=lambda: {"latest_version": "0.1.6"},
    )

    def fail_fetch():
        raise AssertionError("fresh cache should avoid the network")

    notice = check_for_update(
        current_version="0.1.5",
        cache_path=cache,
        now=lambda: now + timedelta(hours=1),
        fetch=fail_fetch,
    )
    assert notice is not None


def test_update_check_refreshes_expired_cache(tmp_path: Path) -> None:
    cache = tmp_path / "update.json"
    old = datetime(2026, 8, 12, tzinfo=UTC)
    check_for_update(
        current_version="0.1.5",
        cache_path=cache,
        now=lambda: old,
        fetch=lambda: {"latest_version": "0.1.5"},
    )

    notice = check_for_update(
        current_version="0.1.5",
        cache_path=cache,
        now=lambda: datetime(2026, 8, 14, tzinfo=UTC),
        fetch=lambda: {"latest_version": "0.1.6"},
    )
    assert notice is not None


def test_update_check_never_fails_on_fetch_errors(tmp_path: Path) -> None:
    def fail_fetch():
        raise OSError("offline")

    assert (
        check_for_update(
            current_version="0.1.5",
            cache_path=tmp_path / "update.json",
            fetch=fail_fetch,
        )
        is None
    )


def test_report_download_metadata_is_stable() -> None:
    assert (
        report_filename("demo project", "my/package", "markdown", date="2026-08-14")
        == "secchi-demo_project-my_package-2026-08-14.md"
    )
    assert report_mime_type("markdown") == "text/markdown"
    assert report_mime_type("json") == "application/json"
    assert report_mime_type("html") == "text/html"
