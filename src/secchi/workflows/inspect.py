"""Package and project intelligence workflow."""

from secchi.models import PackageRef
from secchi.services.intelligence import PackageIntelligenceService, ProjectIntelligence


async def run(
    refs: list[PackageRef],
    *,
    refresh: bool = False,
    service: PackageIntelligenceService | None = None,
) -> ProjectIntelligence:
    pipeline = service or PackageIntelligenceService()
    return await pipeline.fetch_project(refs, force_refresh=refresh)
