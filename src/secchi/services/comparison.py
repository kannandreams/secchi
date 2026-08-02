"""Evidence-based package comparison and agent recommendation logic.

This module is deliberately read-only and deterministic.  It consumes the same
``IntelligenceResult`` objects as the CLI, dashboard, reports, and MCP server;
it does not fetch data or make installation decisions on a user's behalf.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from secchi.models import PackageInfo, PackageRef
from secchi.schema import COMPARISON_SCHEMA_VERSION
from secchi.schemas import ComparisonExport
from secchi.services.intelligence import IntelligenceResult


class Recommendation(str, Enum):
    RECOMMENDED = "Recommended"
    ACCEPTABLE = "Acceptable"
    CAUTION = "Use with caution"
    AVOID = "Avoid"


@dataclass(frozen=True)
class ComparisonCandidate:
    ref: PackageRef
    recommendation: Recommendation
    score: float | None
    confidence: float
    health_score: int | None
    latest_version: str | None
    adoption_change_pct: float | None
    github_stars: int | None
    strengths: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class ComparisonResult:
    candidates: list[ComparisonCandidate]
    recommendation_basis: str = (
        "Health, momentum, community, release recency, and data completeness; "
        "unknown signals reduce confidence."
    )

    @property
    def winner(self) -> ComparisonCandidate | None:
        usable = [
            candidate for candidate in self.candidates if candidate.score is not None
        ]
        return usable[0] if usable else None

    def as_dict(self) -> dict:
        payload = {
            "schema_version": COMPARISON_SCHEMA_VERSION,
            "schema": "secchi.package-comparison",
            "generated_by": "Secchi",
            "recommendation_basis": self.recommendation_basis,
            "winner": _candidate_dict(self.winner) if self.winner else None,
            "candidates": [_candidate_dict(candidate) for candidate in self.candidates],
        }
        return ComparisonExport.model_validate(payload).model_dump(
            mode="json", by_alias=True
        )


def compare_intelligence(results: list[IntelligenceResult]) -> ComparisonResult:
    """Rank fetched package intelligence for an agent-readable decision."""
    candidates = [evaluate_candidate(result) for result in results]
    candidates.sort(
        key=lambda candidate: (
            candidate.score is not None,
            candidate.score if candidate.score is not None else -1,
        ),
        reverse=True,
    )
    return ComparisonResult(candidates=candidates)


def evaluate_candidate(result: IntelligenceResult) -> ComparisonCandidate:
    """Turn one intelligence result into a recommendation with evidence."""
    ref = result.ref
    if result.error or result.info is None or result.derived is None:
        return ComparisonCandidate(
            ref=ref,
            recommendation=Recommendation.AVOID,
            score=None,
            confidence=0.0,
            health_score=None,
            latest_version=None,
            adoption_change_pct=None,
            github_stars=None,
            concerns=["Package intelligence could not be fetched."],
            error=(getattr(result.error, "message", None) or str(result.error))
            if result.error
            else "No package data returned.",
        )

    info = result.info
    derived = result.derived
    health = derived.health_score.total
    momentum = _momentum_score(derived.downloads_30d_pct_change)
    community = _community_score(info.github_stats.stars, info.github_stats.resolved)
    recency = _recency_score(info)
    completeness = _completeness_score(info)
    score = round(
        health * 0.55
        + momentum * 0.15
        + community * 0.10
        + recency * 0.10
        + completeness * 0.10,
        1,
    )
    confidence = round(completeness / 100, 2)

    strengths: list[str] = []
    concerns: list[str] = []
    evidence: list[str] = [f"Health score: {health}/100"]
    if health >= 80:
        strengths.append("Strong overall health")
    elif health < 60:
        concerns.append("Health score is below the preferred range")
    if derived.downloads_30d_pct_change is not None:
        change = derived.downloads_30d_pct_change
        evidence.append(f"30-day adoption change: {change:+.1f}%")
        if change >= 10:
            strengths.append("Adoption is growing")
        elif change < -10:
            concerns.append("Adoption is declining")
    else:
        concerns.append("Adoption trend has no comparison baseline")
    if info.github_stats.resolved and info.github_stats.stars > 0:
        evidence.append(f"GitHub stars: {info.github_stats.stars:,}")
        if info.github_stats.stars >= 1000:
            strengths.append("Established community signal")
    else:
        concerns.append("Repository or community data is unavailable")
    if info.github_stats.has_ci:
        strengths.append("Repository CI detected")
    else:
        concerns.append("Repository CI was not detected")
    if info.latest_version:
        evidence.append(f"Latest version: {info.latest_version}")
    else:
        concerns.append("Latest version is unavailable")
    if info.versions and info.versions[0].is_yanked:
        concerns.append("Latest release is yanked")

    warnings = [
        {"source": warning.source, "message": warning.message}
        for warning in result.warnings
    ]
    if warnings:
        concerns.append(f"{len(warnings)} enrichment signal(s) unavailable")

    recommendation = _recommendation(score, confidence, info)
    return ComparisonCandidate(
        ref=ref,
        recommendation=recommendation,
        score=score,
        confidence=confidence,
        health_score=health,
        latest_version=info.latest_version or None,
        adoption_change_pct=derived.downloads_30d_pct_change,
        github_stars=info.github_stats.stars if info.github_stats.resolved else None,
        strengths=strengths,
        concerns=concerns,
        evidence=evidence,
        warnings=warnings,
    )


def _recommendation(
    score: float, confidence: float, info: PackageInfo
) -> Recommendation:
    if (
        not info.latest_version
        or (info.versions and info.versions[0].is_yanked)
        or score < 40
    ):
        return Recommendation.AVOID
    if score >= 80 and confidence >= 0.65:
        return Recommendation.RECOMMENDED
    if score >= 65 and confidence >= 0.45:
        return Recommendation.ACCEPTABLE
    return Recommendation.CAUTION


def _momentum_score(change: float | None) -> float:
    if change is None:
        return 50
    return max(0, min(100, 50 + change * 2))


def _community_score(stars: int, resolved: bool) -> float:
    if not resolved:
        return 0
    if stars <= 0:
        return 20
    return min(100, 20 + math.log10(stars) * 25)


def _recency_score(info: PackageInfo) -> float:
    date = info.latest_release_date
    if date is None:
        return 0
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    age_days = max(0, (datetime.now(timezone.utc) - date).days)
    if age_days <= 90:
        return 100
    if age_days <= 180:
        return 80
    if age_days <= 365:
        return 55
    if age_days <= 730:
        return 25
    return 0


def _completeness_score(info: PackageInfo) -> float:
    signals = [
        bool(info.latest_version),
        bool(info.latest_release_date),
        bool(info.download_trend or info.download_counts.month),
        info.github_stats.resolved,
        bool(info.repository_url or info.homepage),
        bool(info.versions),
        info.reverse_dependency_count is not None,
        bool(info.dependencies),
    ]
    return round(sum(signals) / len(signals) * 100, 1)


def _candidate_dict(candidate: ComparisonCandidate | None) -> dict | None:
    if candidate is None:
        return None
    return {
        "package": candidate.ref.name,
        "registry": candidate.ref.registry.value,
        "recommendation": candidate.recommendation.value,
        "score": candidate.score,
        "confidence": candidate.confidence,
        "health_score": candidate.health_score,
        "latest_version": candidate.latest_version,
        "adoption_change_pct": candidate.adoption_change_pct,
        "github_stars": candidate.github_stars,
        "strengths": candidate.strengths,
        "concerns": candidate.concerns,
        "evidence": candidate.evidence,
        "warnings": candidate.warnings,
        "error": candidate.error,
    }


def render_comparison(result: ComparisonResult) -> str:
    """Render a compact terminal comparison while retaining agent JSON support."""
    lines = ["Package comparison", "=" * 72]
    for index, candidate in enumerate(result.candidates, start=1):
        ref = f"{candidate.ref.name} ({candidate.ref.registry.value})"
        if candidate.score is None:
            lines.append(f"{index}. {ref} — {candidate.recommendation.value}")
            lines.append(f"   Error: {candidate.error}")
            continue
        change = (
            "—"
            if candidate.adoption_change_pct is None
            else f"{candidate.adoption_change_pct:+.1f}%"
        )
        stars = "—" if candidate.github_stars is None else f"{candidate.github_stars:,}"
        lines.extend(
            [
                f"{index}. {ref} — {candidate.recommendation.value}",
                f"   Score {candidate.score:.1f}  Confidence {candidate.confidence:.0%}  Health {candidate.health_score}/100",
                f"   Latest {candidate.latest_version or '—'}  Adoption {change}  GitHub stars {stars}",
            ]
        )
        if candidate.strengths:
            lines.append(f"   Strengths: {', '.join(candidate.strengths)}")
        if candidate.concerns:
            lines.append(f"   Concerns: {', '.join(candidate.concerns)}")
    if result.winner:
        lines.append("")
        lines.append(
            f"Recommendation: {result.winner.ref.name} ({result.winner.ref.registry.value}) "
            f"— {result.winner.recommendation.value}."
        )
    lines.append(
        "Note: Secchi provides advisory evidence; review compatibility, license, and security requirements before adopting."
    )
    return "\n".join(lines)
