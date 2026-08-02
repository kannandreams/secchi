"""Package comparison workflow."""

from secchi.models import PackageRef, Registry
from secchi.services.comparison import ComparisonResult, compare_intelligence
from secchi.services.intelligence import PackageIntelligenceService
from secchi.services.resolver import parse_package_spec, resolve_package


async def _resolve_refs(specs: list[str], registry: str | None) -> list[PackageRef]:
    refs: list[PackageRef] = []
    preference = {item: index for index, item in enumerate(Registry)}
    for spec in specs:
        if registry or ":" in spec:
            refs.append(parse_package_spec(spec, None if ":" in spec else registry))
            continue
        matches = await resolve_package(spec)
        if not matches:
            raise ValueError(
                f"No exact package named '{spec}' was found across registries."
            )
        refs.append(sorted(matches, key=lambda ref: preference[ref.registry])[0])
    return refs


async def run(
    specs: list[str],
    *,
    registry: str | None = None,
    refresh: bool = False,
    service: PackageIntelligenceService | None = None,
) -> ComparisonResult:
    if len(specs) < 2:
        raise ValueError("Compare requires at least two packages.")
    refs = await _resolve_refs(specs, registry)
    pipeline = service or PackageIntelligenceService()
    intelligence = await pipeline.fetch_project(refs, force_refresh=refresh)
    return compare_intelligence(list(intelligence.results.values()))
