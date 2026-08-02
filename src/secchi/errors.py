"""Stable exception types exposed by Secchi application boundaries."""

from __future__ import annotations


class SecchiError(Exception):
    """Base class for expected, user-actionable Secchi failures."""


class PackageNotFoundError(SecchiError):
    """No package or exact registry match could be resolved."""


class RegistryUnavailableError(SecchiError):
    """A registry or enrichment service could not be reached or used."""


class ConfigError(SecchiError):
    """The requested Secchi configuration is missing or invalid."""


class ReportError(SecchiError):
    """A report could not be rendered or its format is unsupported."""
