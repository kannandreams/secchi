"""Pydantic schemas for Secchi's persisted and external data boundaries.

The application domain remains dataclass-based.  These models deliberately sit
at the edges of the application so cache files, reports, and MCP responses have
an explicit, validated contract without coupling the UI and services to a
serialization library.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from secchi.schema import (
    CACHE_SCHEMA_VERSION,
    COMPARISON_SCHEMA_VERSION,
    PACKAGE_EXPORT_SCHEMA_VERSION,
    PROJECT_EXPORT_SCHEMA_VERSION,
)


class SignalWarningSchema(BaseModel):
    """A non-fatal signal-fetch warning exposed to users and agents."""

    model_config = ConfigDict(extra="forbid")

    source: str
    message: str


class CacheEnvelope(BaseModel):
    """Versioned package cache envelope.

    Version ``0`` represents the legacy unversioned cache format.  It remains
    readable so upgrading Secchi does not discard a user's same-day cache.
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: int = CACHE_SCHEMA_VERSION
    fetched_at: datetime
    package: dict[str, Any]

    @field_validator("schema_version")
    @classmethod
    def validate_supported_version(cls, value: int) -> int:
        if value not in (0, CACHE_SCHEMA_VERSION):
            raise ValueError(f"unsupported cache schema version: {value}")
        return value


class PackageExport(BaseModel):
    """Stable JSON contract returned by package reports and MCP."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = PACKAGE_EXPORT_SCHEMA_VERSION
    schema_name: str = Field("secchi.package-intelligence", alias="schema")
    generated_by: str = "Secchi"
    project: str
    package: str
    registry: str
    exported_at: datetime
    package_info: dict[str, Any] | None = None
    derived: dict[str, Any] | None = None
    warnings: list[SignalWarningSchema] = Field(default_factory=list)

    @field_validator("schema_version")
    @classmethod
    def validate_version(cls, value: int) -> int:
        if value != PACKAGE_EXPORT_SCHEMA_VERSION:
            raise ValueError(f"unsupported package export schema version: {value}")
        return value


class ProjectExport(BaseModel):
    """Stable JSON contract for project-wide reports."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = PROJECT_EXPORT_SCHEMA_VERSION
    schema_name: str = Field("secchi.project-intelligence", alias="schema")
    generated_by: str = "Secchi"
    project: dict[str, Any]
    generated_at: datetime
    summary: dict[str, Any]
    sources: list[dict[str, Any]]

    @field_validator("schema_version")
    @classmethod
    def validate_version(cls, value: int) -> int:
        if value != PROJECT_EXPORT_SCHEMA_VERSION:
            raise ValueError(f"unsupported project export schema version: {value}")
        return value


class ComparisonExport(BaseModel):
    """Stable JSON contract for agent-readable package comparisons."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: int = COMPARISON_SCHEMA_VERSION
    schema_name: str = Field("secchi.package-comparison", alias="schema")
    generated_by: str = "Secchi"
    recommendation_basis: str
    winner: dict[str, Any] | None = None
    candidates: list[dict[str, Any]]

    @field_validator("schema_version")
    @classmethod
    def validate_version(cls, value: int) -> int:
        if value != COMPARISON_SCHEMA_VERSION:
            raise ValueError(f"unsupported comparison schema version: {value}")
        return value
