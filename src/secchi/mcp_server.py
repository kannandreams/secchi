"""Model Context Protocol server for Secchi package intelligence."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

from secchi import __version__
from secchi.config import find_config
from secchi.errors import SecchiError
from secchi.export import export_package_json
from secchi.models import PackageRef
from secchi.services.intelligence import IntelligenceResult, PackageIntelligenceService
from secchi.services.resolver import parse_package_spec, resolve_package
from secchi.workflows import check as check_workflow
from secchi.workflows import compare as compare_workflow
from secchi.workflows import inspect as inspect_workflow
from secchi.workflows import report as report_workflow
from secchi.workflows import search as search_workflow

server = MCPServer(
    name="secchi",
    title="Secchi Package Intelligence",
    description=(
        "Explore package health, security advisories, adoption, dependencies, releases, and "
        "ecosystem signals across supported registries."
    ),
    version=__version__,
)
_intelligence_service = PackageIntelligenceService()
logger = logging.getLogger(__name__)


async def _resolve_refs(package: str, registry: str | None) -> list[PackageRef]:
    if registry is not None:
        return [parse_package_spec(package, registry)]
    return await resolve_package(package)


def _package_result(result: IntelligenceResult) -> dict[str, Any]:
    if result.error or result.info is None or result.derived is None:
        return {
            "package": result.ref.name,
            "registry": result.ref.registry.value,
            "error": result.error.message
            if result.error
            else "No package data returned.",
        }
    return json.loads(
        export_package_json(
            result.info,
            result.derived,
            result.ref,
            result.ref.project_name,
            result.warnings,
        )
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
    """Return health, security advisory, adoption, release, dependency, and repository signals."""
    refs = await _resolve_refs(package, registry)
    if not refs:
        return {
            "query": package,
            "matches": [],
            "message": "No exact package matches found.",
        }
    intelligence = await inspect_workflow.run(
        refs, refresh=refresh, service=_intelligence_service
    )
    return {
        "query": package,
        "matches": [
            _package_result(result) for result in intelligence.results.values()
        ],
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
    results = await search_workflow.run(query, registry=registry, limit=limit)
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
        raise ValueError(
            "No Secchi config found. Provide config or create secchi.toml."
        )
    output = await report_workflow.run(
        project_name=project,
        config=str(config_path),
        format_name="json",
        output="-",
        refresh=refresh,
        service=_intelligence_service,
    )
    return json.loads(output.content)


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
        return {
            "query": package,
            "matches": [],
            "message": "No exact package matches found.",
        }

    matches: list[dict[str, Any]] = []
    for ref in refs:
        item: dict[str, Any] = {
            "package": ref.name,
            "registry": ref.registry.value,
        }
        try:
            check_result = await check_workflow.run(
                ref,
                min_health=min_health,
                require_ci=require_ci,
                refresh=refresh,
                service=_intelligence_service,
            )
            item["passed"] = check_result.passed
            item["checks"] = [
                {"name": check.name, "passed": check.passed, "detail": check.detail}
                for check in check_result.checks
            ]
            item["warnings"] = [
                {"source": warning.source, "message": warning.message}
                for warning in check_result.warnings
            ]
        except (
            SecchiError,
            httpx.HTTPError,
            OSError,
            ValueError,
            KeyError,
            TypeError,
        ) as exc:
            item["passed"] = False
            item["error"] = str(exc)
            logger.debug(
                "MCP policy check failed for %s (%s): %s",
                ref.name,
                ref.registry.value,
                exc,
                exc_info=True,
            )
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
    comparison = await compare_workflow.run(
        packages,
        registry=registry,
        refresh=refresh,
        service=_intelligence_service,
    )
    return {"query": packages, **comparison.as_dict()}


def main() -> None:
    """Run the MCP server over stdio for local agent integrations."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
