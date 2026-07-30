"""Resolve direct CLI package names into registry package references."""

from __future__ import annotations

from secchi.models import PackageRef, Registry


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
        raise ValueError(f"Unknown registry '{registry}'. Supported: {supported}") from exc
    return PackageRef(name=spec, registry=selected)
