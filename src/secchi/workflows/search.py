"""Cross-registry package search workflow."""

from secchi.models import Registry, SearchResult
from secchi.services.search import PackageSearchService


async def run(
    query: str,
    *,
    registry: str | None = None,
    limit: int = 10,
) -> list[SearchResult]:
    registries = [Registry(registry)] if registry else list(Registry)
    return await PackageSearchService().search(
        query, registries=registries, limit=limit
    )
