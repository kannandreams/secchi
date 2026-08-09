"""Cross-registry package discovery and deterministic result ranking."""

from __future__ import annotations

import asyncio
import logging
import math

import httpx

from secchi.api.base import create_adapter
from secchi.diagnostics import (
    DiagnosticLog,
    DiagnosticStatus,
    diagnostic_for_http_error,
)
from secchi.http import HttpClientFactory
from secchi.models import Registry, SearchResult

logger = logging.getLogger(__name__)


class PackageSearchService:
    """Search configured registries concurrently and normalize their results."""

    def __init__(self, diagnostics: DiagnosticLog | None = None) -> None:
        self.diagnostics = diagnostics

    async def search(
        self,
        query: str,
        *,
        registries: list[Registry] | None = None,
        limit: int = 10,
        diagnostics: DiagnosticLog | None = None,
    ) -> list[SearchResult]:
        selected = registries or list(Registry)
        diagnostics = diagnostics or self.diagnostics
        failed_registries: set[Registry] = set()

        async with HttpClientFactory(diagnostics=diagnostics).create() as client:

            async def search_registry(registry: Registry) -> list[SearchResult]:
                try:
                    try:
                        adapter = create_adapter(registry, client=client)
                    except TypeError:
                        adapter = create_adapter(registry)
                    results = await adapter.search(query, limit=limit)
                    if diagnostics is not None:
                        diagnostics.record(
                            DiagnosticStatus.SUCCESS,
                            registry.display_name,
                            f"Search completed ({len(results)} result(s))",
                        )
                    return results
                except (
                    httpx.HTTPError,
                    OSError,
                    ValueError,
                    KeyError,
                    TypeError,
                ) as exc:
                    # One unavailable registry should not hide results from the others.
                    failed_registries.add(registry)
                    if diagnostics is not None:
                        diagnostics.record(
                            DiagnosticStatus.WARN,
                            registry.display_name,
                            f"Search unavailable: {diagnostic_for_http_error(exc)}",
                        )
                    logger.debug(
                        "Registry search failed for %s: %s",
                        registry.value,
                        exc,
                        exc_info=True,
                    )
                    return []

            batches = await asyncio.gather(
                *(search_registry(registry) for registry in selected)
            )
        results = [result for batch in batches for result in batch]
        if (
            diagnostics is not None
            and selected
            and len(failed_registries) == len(selected)
        ):
            diagnostics.record(
                DiagnosticStatus.FAILURE,
                "SEARCH",
                f"All {len(selected)} selected registries failed",
            )
        results.sort(key=lambda result: self._sort_key(result, query))
        return results[: limit * len(selected)]

    @staticmethod
    def _sort_key(result: SearchResult, query: str) -> tuple[int, int, float, str]:
        exact = 0 if result.exact or result.name.casefold() == query.casefold() else 1
        # Registry APIs use incompatible score scales. Compress large download
        # scores while preserving useful ordering within a registry.
        normalized_score = (
            math.log10(result.score + 1) if result.score > 1 else result.score
        )
        return (
            exact,
            0 if result.name.casefold().startswith(query.casefold()) else 1,
            -normalized_score,
            result.name.casefold(),
        )
