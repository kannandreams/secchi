"""Shared workflow primitives and application-level errors."""

from __future__ import annotations

from secchi.errors import PackageNotFoundError, RegistryUnavailableError, SecchiError
from secchi.models import PackageRef
from secchi.services.intelligence import IntelligenceResult, PackageIntelligenceService


class WorkflowError(SecchiError):
    """A user-actionable workflow failure suitable for CLI/MCP mapping."""


async def fetch_package(
    ref: PackageRef,
    refresh: bool = False,
    *,
    security_refresh: bool = False,
    service: PackageIntelligenceService | None = None,
) -> IntelligenceResult:
    pipeline = service or PackageIntelligenceService()
    if security_refresh:
        return await pipeline.fetch_package(
            ref, force_refresh=refresh, force_security_refresh=True
        )
    return await pipeline.fetch_package(ref, force_refresh=refresh)


async def require_package(
    ref: PackageRef,
    refresh: bool = False,
    *,
    security_refresh: bool = False,
    service: PackageIntelligenceService | None = None,
) -> IntelligenceResult:
    result = await fetch_package(
        ref, refresh, security_refresh=security_refresh, service=service
    )
    if result.error or result.info is None or result.derived is None:
        message = result.error.message if result.error else "No package data returned."
        error_type = RegistryUnavailableError if result.error else PackageNotFoundError
        raise error_type(
            f"Could not load {ref.name} from {ref.registry.value}: {message}"
        ) from None
    return result
