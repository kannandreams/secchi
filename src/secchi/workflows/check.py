"""Package policy-check workflow."""

from dataclasses import dataclass

from secchi.models import PackageRef
from secchi.policy import PolicyResult, evaluate_default_policy
from secchi.services.resolver import parse_package_spec
from secchi.workflows.common import require_package


@dataclass(frozen=True)
class CheckResult:
    package: PackageRef
    checks: list[PolicyResult]
    warnings: list[object]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


async def run(
    package: str | PackageRef,
    *,
    registry: str | None = None,
    min_health: int = 70,
    require_ci: bool = False,
    refresh: bool = False,
) -> CheckResult:
    if min_health < 0 or min_health > 100:
        raise ValueError("min_health must be between 0 and 100")
    ref = (
        parse_package_spec(package, registry)
        if isinstance(package, str)
        else package
    )
    result = await require_package(ref, refresh)
    checks = evaluate_default_policy(
        result.info,
        result.derived,
        min_health=min_health,
        require_ci=require_ci,
    )
    return CheckResult(ref, checks, result.warnings)
