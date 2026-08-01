import json
from datetime import datetime, timezone

from secchi import cache
from secchi.models import PackageInfo, Registry
from secchi.schema import CACHE_SCHEMA_VERSION, PACKAGE_EXPORT_SCHEMA_VERSION
from secchi.export import export_package_json


def test_cache_writes_and_reads_versioned_envelope(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cache, "cache_root", lambda: tmp_path)
    info = PackageInfo(name="demo", registry=Registry.PYPI, latest_version="1.0.0")
    fetched_at = datetime.now(timezone.utc)

    cache.save_package_cache("pypi:demo", info, fetched_at)
    raw = json.loads(cache.package_cache_path("pypi:demo").read_text())
    loaded = cache.load_package_cache("pypi:demo")

    assert raw["schema_version"] == CACHE_SCHEMA_VERSION
    assert loaded is not None
    assert loaded[0].latest_version == "1.0.0"


def test_legacy_unversioned_cache_is_readable_and_future_cache_is_ignored(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(cache, "cache_root", lambda: tmp_path)
    info = PackageInfo(name="demo", registry=Registry.PYPI, latest_version="1.0.0")
    fetched_at = datetime.now(timezone.utc).astimezone().isoformat()
    path = cache.package_cache_path("pypi:demo")
    path.parent.mkdir(parents=True)

    payload = {"fetched_at": fetched_at, "package": cache._encode({"name": "demo", "registry": "pypi", "latest_version": "1.0.0"})}
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
