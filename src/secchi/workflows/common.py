"""Shared workflow primitives and application-level errors."""

from __future__ import annotations

from secchi.models import PackageRef
from secchi.services.intelligence import IntelligenceResult, PackageIntelligenceService


class WorkflowError(RuntimeError):
    """A user-actionable workflow failure suitable for CLI/MCP mapping."""


async def fetch_package(
    ref: PackageRef,
    refresh: bool = False,
    *,
    service: PackageIntelligenceService | None = None,
) -> IntelligenceResult:
    pipeline = service or PackageIntelligenceService()
    return await pipeline.fetch_package(ref, force_refresh=refresh)


async def require_package(
    ref: PackageRef,
    refresh: bool = False,
    *,
    service: PackageIntelligenceService | None = None,
) -> IntelligenceResult:
    result = await fetch_package(ref, refresh, service=service)
    if result.error or result.info is None or result.derived is None:
        message = result.error.message if result.error else "No package data returned."
        raise WorkflowError(
            f"Could not load {ref.name} from {ref.registry.value}: {message}"
        )
    return result
