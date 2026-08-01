"""Model Context Protocol server for Secchi package intelligence."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.mcpserver import MCPServer

from secchi import __version__
from secchi.config import find_config, load_project
from secchi.export import export_package_json
from secchi.models import PackageRef, Registry
from secchi.policy import evaluate_default_policy
from secchi.renderers.reports import build_project_report, render_project_report
from secchi.services.intelligence import IntelligenceResult, PackageIntelligenceService
from secchi.services.comparison import compare_intelligence
from secchi.services.resolver import parse_package_spec, resolve_package
from secchi.services.search import PackageSearchService


server = MCPServer(
    name="secchi",
    title="Secchi Package Intelligence",
    description=(
        "Explore package health, adoption, dependencies, releases, and "
        "ecosystem signals across supported registries."
    ),
    version=__version__,
)


async def _resolve_refs(package: str, registry: str | None) -> list[PackageRef]:
    if registry is not None:
        return [parse_package_spec(package, registry)]
    return await resolve_package(package)


async def _resolve_compare_refs(packages: list[str], registry: str | None) -> list[PackageRef]:
    refs: list[PackageRef] = []
    preference = {item: index for index, item in enumerate(Registry)}
    for package in packages:
        if registry or ":" in package:
            refs.append(parse_package_spec(package, None if ":" in package else registry))
            continue
        matches = await resolve_package(package)
        if not matches:
            continue
        refs.append(sorted(matches, key=lambda ref: preference[ref.registry])[0])
    return refs


def _package_result(result: IntelligenceResult) -> dict[str, Any]:
    if result.error or result.info is None or result.derived is None:
        return {
            "package": result.ref.name,
            "registry": result.ref.registry.value,
            "error": result.error.message if result.error else "No package data returned.",
        }
    return json.loads(
        export_package_json(result.info, result.derived, result.ref, result.ref.project_name)
    )


@server.tool(
    name="inspect_package",
    title="Inspect package intelligence",
    description=(
        "Fetch normalized package intelligence. Without a registry, resolve "
        "exact matches across supported ecosystems; with a registry, inspect "
        "that specific package source."
    ),
    structured_output=True,
)
async def inspect_package(
    package: str,
    registry: str | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Return health, adoption, release, dependency, and repository signals."""
    refs = await _resolve_refs(package, registry)
    if not refs:
        return {"query": package, "matches": [], "message": "No exact package matches found."}
    intelligence = await PackageIntelligenceService().fetch_project(
        refs, force_refresh=refresh
    )
    return {
        "query": package,
        "matches": [_package_result(result) for result in intelligence.results.values()],
    }


@server.tool(
    name="search_packages",
    title="Search package ecosystems",
    description="Search supported package registries and return ranked normalized matches.",
    structured_output=True,
)
async def search_packages(
    query: str,
    registry: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search one registry or all supported registries."""
    if limit < 1 or limit > 50:
        raise ValueError("limit must be between 1 and 50")
    registries = [Registry(registry)] if registry else list(Registry)
    results = await PackageSearchService().search(query, registries=registries, limit=limit)
    return {
        "query": query,
        "results": [
            {
                "name": result.name,
                "registry": result.registry.value,
                "version": result.version,
                "description": result.description,
                "score": result.score,
                "exact": result.exact,
            }
            for result in results
        ],
    }


@server.tool(
    name="inspect_project",
    title="Inspect configured project",
    description="Load one project from secchi.toml and return its combined registry report.",
    structured_output=True,
)
async def inspect_project(
    project: str,
    config: str | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Return project-wide intelligence using the same report pipeline as the CLI."""
    config_path = find_config(config)
    if config_path is None:
        raise ValueError("No Secchi config found. Provide config or create secchi.toml.")
    selected = load_project(config_path, project)
    intelligence = await PackageIntelligenceService().fetch_project(
        selected.packages, force_refresh=refresh
    )
    report = build_project_report(selected, intelligence.results)
    return json.loads(render_project_report("json", report))


@server.tool(
    name="check_package",
    title="Evaluate package policy",
    description="Evaluate a package against minimum health and repository CI policies.",
    structured_output=True,
)
async def check_package(
    package: str,
    registry: str | None = None,
    min_health: int = 70,
    require_ci: bool = False,
    refresh: bool = False,
) -> dict[str, Any]:
    """Return policy results without terminating the MCP server on failure."""
    if min_health < 0 or min_health > 100:
        raise ValueError("min_health must be between 0 and 100")
    refs = await _resolve_refs(package, registry)
    if not refs:
        return {"query": package, "matches": [], "message": "No exact package matches found."}

    intelligence = await PackageIntelligenceService().fetch_project(
        refs, force_refresh=refresh
    )
    matches: list[dict[str, Any]] = []
    for result in intelligence.results.values():
        item: dict[str, Any] = {
            "package": result.ref.name,
            "registry": result.ref.registry.value,
        }
        if result.error or result.info is None or result.derived is None:
            item["passed"] = False
            item["error"] = result.error.message if result.error else "No package data returned."
        else:
            checks = evaluate_default_policy(
                result.info,
                result.derived,
                min_health=min_health,
                require_ci=require_ci,
            )
            item["passed"] = all(check.passed for check in checks)
            item["checks"] = [
                {"name": check.name, "passed": check.passed, "detail": check.detail}
                for check in checks
            ]
        matches.append(item)
    return {"query": package, "matches": matches}


@server.tool(
    name="compare_packages",
    title="Compare package choices",
    description=(
        "Compare two or more package choices using health, adoption momentum, "
        "community, release recency, and data completeness. Returns advisory "
        "recommendations with evidence and confidence; it never installs packages."
    ),
    structured_output=True,
)
async def compare_packages(
    packages: list[str],
    registry: str | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Return a ranked, evidence-backed package selection recommendation."""
    if len(packages) < 2:
        raise ValueError("packages must contain at least two package references")
    if len(packages) > 20:
        raise ValueError("packages must contain no more than 20 package references")
    refs = await _resolve_compare_refs(packages, registry)
    if len(refs) < 2:
        return {
            "query": packages,
            "candidates": [],
            "message": "Fewer than two exact package matches were found.",
        }
    intelligence = await PackageIntelligenceService().fetch_project(
        refs, force_refresh=refresh
    )
    comparison = compare_intelligence(list(intelligence.results.values()))
    return {"query": packages, **comparison.as_dict()}


def main() -> None:
    """Run the MCP server over stdio for local agent integrations."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
