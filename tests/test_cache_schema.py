import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from secchi import cache
from secchi.export import export_package_json
from secchi.models import PackageInfo, Registry, SecurityAdvisory
from secchi.schema import CACHE_SCHEMA_VERSION, PACKAGE_EXPORT_SCHEMA_VERSION
from secchi.schemas import CacheEnvelope, PackageExport


def test_cache_writes_and_reads_versioned_envelope(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cache, "cache_root", lambda: tmp_path)
    info = PackageInfo(name="demo", registry=Registry.PYPI, latest_version="1.0.0")
    fetched_at = datetime.now(UTC)

    cache.save_package_cache("pypi:demo", info, fetched_at)
    raw = json.loads(cache.package_cache_path("pypi:demo").read_text())
    loaded = cache.load_package_cache("pypi:demo")

    assert raw["schema_version"] == CACHE_SCHEMA_VERSION
    assert loaded is not None
    assert loaded[0].latest_version == "1.0.0"


def test_security_cache_is_scoped_to_package_version_and_day(tmp_path) -> None:
    fetched_at = datetime.now(UTC)
    advisory = SecurityAdvisory(id="GHSA-demo-1234-abcd", severity="HIGH")

    cache.save_security_cache(
        "pypi:demo", "1.0.0", [advisory], fetched_at, root=tmp_path
    )

    loaded = cache.load_security_cache(
        "pypi:demo", "1.0.0", root=tmp_path, now=lambda: fetched_at
    )
    assert loaded is not None
    assert loaded[0][0].id == advisory.id
    assert (
        cache.load_security_cache(
            "pypi:demo", "2.0.0", root=tmp_path, now=lambda: fetched_at
        )
        is None
    )


def test_legacy_unversioned_cache_is_readable_and_future_cache_is_ignored(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(cache, "cache_root", lambda: tmp_path)
    info = PackageInfo(name="demo", registry=Registry.PYPI, latest_version="1.0.0")
    fetched_at = datetime.now(UTC).astimezone().isoformat()
    path = cache.package_cache_path("pypi:demo")
    path.parent.mkdir(parents=True)

    payload = {
        "fetched_at": fetched_at,
        "package": cache._encode(
            {"name": "demo", "registry": "pypi", "latest_version": "1.0.0"}
        ),
    }
    path.write_text(json.dumps(payload))
    assert cache.load_package_cache("pypi:demo")[0].name == info.name

    payload["schema_version"] = CACHE_SCHEMA_VERSION + 1
    path.write_text(json.dumps(payload))
    assert cache.load_package_cache("pypi:demo") is None


def test_package_export_declares_stable_schema() -> None:
    from secchi.models import DerivedPackageData, PackageRef

    document = json.loads(
        export_package_json(
            PackageInfo(name="demo", registry=Registry.PYPI),
            DerivedPackageData(),
            PackageRef("demo", Registry.PYPI),
            "demo",
        )
    )

    assert document["schema_version"] == PACKAGE_EXPORT_SCHEMA_VERSION
    assert document["schema"] == "secchi.package-intelligence"


def test_cache_envelope_rejects_unsupported_schema_version() -> None:
    with pytest.raises(ValidationError):
        CacheEnvelope(
            schema_version=CACHE_SCHEMA_VERSION + 1,
            fetched_at=datetime.now(UTC),
            package={},
        )


def test_package_export_contract_rejects_wrong_schema() -> None:
    with pytest.raises(ValidationError):
        PackageExport(
            schema_version=PACKAGE_EXPORT_SCHEMA_VERSION + 1,
            project="demo",
            package="demo",
            registry="pypi",
            exported_at=datetime.now(UTC),
        )


def test_cache_supports_injected_root_and_clock(tmp_path) -> None:
    fetched_at = datetime(2026, 8, 2, 12, tzinfo=UTC)
    info = PackageInfo(name="demo", registry=Registry.PYPI, latest_version="1.0.0")

    cache.save_package_cache("pypi:demo", info, fetched_at, root=tmp_path)

    loaded = cache.load_package_cache(
        "pypi:demo", root=tmp_path, now=lambda: fetched_at
    )
    expired = cache.load_package_cache(
        "pypi:demo",
        root=tmp_path,
        now=lambda: fetched_at.replace(day=fetched_at.day + 1),
    )

    assert loaded is not None
    assert loaded[0].latest_version == "1.0.0"
    assert expired is None
