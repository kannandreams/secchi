"""Cross-registry package discovery and deterministic result ranking."""

from __future__ import annotations

import asyncio
import logging
import math

import httpx

from secchi.api.base import create_adapter
from secchi.http import HttpClientFactory
from secchi.models import Registry, SearchResult

logger = logging.getLogger(__name__)


class PackageSearchService:
    """Search configured registries concurrently and normalize their results."""

    async def search(
        self,
        query: str,
        *,
        registries: list[Registry] | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        selected = registries or list(Registry)

        async with HttpClientFactory().create() as client:

            async def search_registry(registry: Registry) -> list[SearchResult]:
                try:
                    try:
                        adapter = create_adapter(registry, client=client)
                    except TypeError:
                        adapter = create_adapter(registry)
                    return await adapter.search(query, limit=limit)
                except (
                    httpx.HTTPError,
                    OSError,
                    ValueError,
                    KeyError,
                    TypeError,
                ) as exc:
                    # One unavailable registry should not hide results from the others.
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
