import asyncio

import pytest

from secchi.config import find_config, load_project
from secchi.errors import (
    ConfigError,
    PackageNotFoundError,
    RegistryUnavailableError,
    ReportError,
    SecchiError,
)
from secchi.models import (
    DerivedPackageData,
    FetchError,
    PackageInfo,
    PackageRef,
    Registry,
)
from secchi.renderers.reports import render_report
from secchi.services.intelligence import IntelligenceResult
from secchi.services.resolver import parse_package_spec
from secchi.workflows.common import require_package


def test_expected_errors_share_the_secchi_base_type() -> None:
    assert all(
        issubclass(error_type, SecchiError)
        for error_type in (
            PackageNotFoundError,
            RegistryUnavailableError,
            ConfigError,
            ReportError,
        )
    )


def test_missing_explicit_config_is_a_config_error(tmp_path) -> None:
    with pytest.raises(ConfigError, match="Config file not found"):
        find_config(str(tmp_path / "missing.toml"))


def test_malformed_config_is_a_config_error(tmp_path) -> None:
    path = tmp_path / "secchi.toml"
    path.write_text("[projects.demo\ninvalid")

    with pytest.raises(ConfigError, match="Could not read config file"):
        load_project(path, "demo")


def test_invalid_registry_is_a_config_error() -> None:
    with pytest.raises(ConfigError, match="Unknown registry"):
        parse_package_spec("demo", registry="unknown")


def test_require_package_classifies_missing_data() -> None:
    ref = PackageRef("missing", Registry.PYPI)

    class MissingService:
        async def fetch_package(self, requested_ref, *, force_refresh=False):
            return IntelligenceResult(ref=requested_ref)

    with pytest.raises(PackageNotFoundError):
        asyncio.run(require_package(ref, service=MissingService()))


def test_require_package_classifies_registry_failure() -> None:
    ref = PackageRef("demo", Registry.PYPI)

    class FailedService:
        async def fetch_package(self, requested_ref, *, force_refresh=False):
            return IntelligenceResult(
                ref=requested_ref,
                error=FetchError(
                    package_name=requested_ref.name,
                    registry=requested_ref.registry,
                    message="registry unavailable",
                ),
            )

    with pytest.raises(RegistryUnavailableError, match="registry unavailable"):
        asyncio.run(require_package(ref, service=FailedService()))


def test_unsupported_report_format_is_a_report_error() -> None:
    with pytest.raises(ReportError, match="Unsupported report format"):
        render_report(
            "xml",
            PackageInfo(name="demo", registry=Registry.PYPI),
            DerivedPackageData(),
            PackageRef("demo", Registry.PYPI),
            "demo",
        )
