"""Package summary workflow."""

from secchi.models import PackageRef
from secchi.services.intelligence import IntelligenceResult
from secchi.services.resolver import parse_package_spec
from secchi.workflows.common import require_package


async def run(
    package: str | PackageRef,
    *,
    registry: str | None = None,
    refresh: bool = False,
) -> IntelligenceResult:
    ref = parse_package_spec(package, registry) if isinstance(package, str) else package
    return await require_package(ref, refresh)
