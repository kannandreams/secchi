"""Package and project intelligence workflow."""

from secchi.models import PackageRef
from secchi.services.intelligence import PackageIntelligenceService, ProjectIntelligence


async def run(refs: list[PackageRef], *, refresh: bool = False) -> ProjectIntelligence:
    return await PackageIntelligenceService().fetch_project(refs, force_refresh=refresh)
