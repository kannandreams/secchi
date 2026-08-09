"""Resolve direct CLI package names into registry package references."""

from __future__ import annotations

from secchi.diagnostics import DiagnosticLog
from secchi.errors import ConfigError
from secchi.models import PackageRef, Registry
from secchi.services.search import PackageSearchService


def parse_package_spec(spec: str, registry: str | None = None) -> PackageRef:
    """Resolve ``name`` or ``registry:name`` with PyPI as the safe default."""
    if ":" in spec and registry is None:
        candidate_registry, name = spec.split(":", 1)
        try:
            return PackageRef(name=name, registry=Registry(candidate_registry))
        except ValueError:
            pass
    try:
        selected = Registry(registry) if registry else Registry.PYPI
    except ValueError as exc:
        supported = ", ".join(item.value for item in Registry)
        raise ConfigError(
            f"Unknown registry '{registry}'. Supported: {supported}"
        ) from exc
    return PackageRef(name=spec, registry=selected)


async def resolve_package(
    spec: str,
    *,
    configured_refs: list[PackageRef] | None = None,
    registry: str | None = None,
    diagnostics: DiagnosticLog | None = None,
) -> list[PackageRef]:
    """Resolve a package spec from config first, then exact registry matches."""
    explicit = parse_package_spec(spec, registry)
    if registry is not None or ":" in spec:
        return [explicit]

    configured = [
        ref for ref in configured_refs or [] if ref.name.casefold() == spec.casefold()
    ]
    if configured:
        return configured

    matches = await PackageSearchService(diagnostics=diagnostics).search(spec)
    exact = [result for result in matches if result.exact]
    return [PackageRef(result.name, result.registry) for result in exact]
