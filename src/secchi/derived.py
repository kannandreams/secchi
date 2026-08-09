"""Derived metrics — pure functions over an already-fetched PackageInfo.

No network or filesystem I/O lives here: everything is arithmetic over data the
adapters/utils already fetched. This keeps the "real vs. derived" boundary sharp
and makes the scoring logic unit-testable without mocking httpx.
"""

from __future__ import annotations

from datetime import UTC, datetime

from secchi.models import (
    ActivityEvent,
    ActivityEventKind,
    DerivedPackageData,
    HealthScore,
    HealthSubScore,
    InstallBreakdown,
    InstallMethod,
    PackageInfo,
    Registry,
    ReverseDependencySummary,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _days_since(dt: datetime | None) -> float | None:
    dt = _aware(dt)
    if dt is None:
        return None
    return (_now() - dt).total_seconds() / 86400


# ── Health score ─────────────────────────────────────────────────────────────


def _score_maintained(info: PackageInfo) -> int:
    candidates = [
        _days_since(info.latest_release_date),
        _days_since(info.github_stats.pushed_at),
    ]
    ages = [d for d in candidates if d is not None]
    if not ages:
        return 0
    days = min(ages)
    if days <= 30:
        return 20
    if days <= 90:
        return 16
    if days <= 180:
        return 12
    if days <= 365:
        return 6
    return 2


def _score_documentation(info: PackageInfo) -> int:
    score = 0
    if info.homepage:
        score += 5
    if info.documentation_url:
        score += 8
    if info.github_stats.has_readme:
        score += 7
    return min(score, 20)


def _score_testing(info: PackageInfo) -> int:
    # Weak proxy: presence of CI workflows. Not test coverage.
    return 20 if (info.github_stats.resolved and info.github_stats.has_ci) else 0


def _issue_counts_90d(info: PackageInfo) -> tuple[int, int]:
    now = _now()
    opened = closed = 0
    for ev in info.github_issue_events:
        created = _aware(ev.created_at)
        if created and (now - created).days <= 90:
            opened += 1
        closed_at = _aware(ev.closed_at)
        if closed_at and (now - closed_at).days <= 90:
            closed += 1
    return opened, closed


def _score_community(info: PackageInfo) -> int:
    gh = info.github_stats
    if not gh.resolved:
        return 0

    stars = gh.stars
    if stars >= 100_000:
        star_pts = 10
    elif stars >= 10_000:
        star_pts = 8
    elif stars >= 1_000:
        star_pts = 6
    elif stars >= 100:
        star_pts = 4
    elif stars >= 1:
        star_pts = 2
    else:
        star_pts = 0

    forks = gh.forks
    if forks >= 10_000:
        fork_pts = 5
    elif forks >= 1_000:
        fork_pts = 4
    elif forks >= 100:
        fork_pts = 3
    elif forks >= 10:
        fork_pts = 2
    else:
        fork_pts = 0

    opened, closed = _issue_counts_90d(info)
    if opened == 0:
        resp_pts = 3  # neutral — no signal
    elif closed >= opened:
        resp_pts = 5
    elif closed >= 0.5 * opened:
        resp_pts = 3
    elif closed > 0:
        resp_pts = 1
    else:
        resp_pts = 0

    return min(star_pts + fork_pts + resp_pts, 20)


def _score_activity(info: PackageInfo) -> int:
    now = _now()
    releases = 0
    for v in info.versions:
        rd = _aware(v.release_date)
        if rd and (now - rd).days <= 365:
            releases += 1
    if releases == 0:
        return 0
    if releases <= 2:
        return 6
    if releases <= 5:
        return 12
    if releases <= 11:
        return 16
    return 20


def _score_security(info: PackageInfo) -> int:
    """Best-effort registry security signal from locally fetched metadata.

    Secchi does not fetch advisory databases yet, so this category stays honest:
    yanked recent releases and a missing source repository reduce confidence,
    while the absence of those signals is treated as healthy.
    """
    score = 20
    recent = info.versions[:5]
    if any(v.is_yanked for v in recent):
        score -= 8
    if recent and recent[0].is_yanked:
        score -= 6
    if not (info.repository_url or info.github_stats.resolved):
        score -= 4
    return max(score, 0)


def _grade(total: int) -> str:
    if total >= 90:
        return "A"
    if total >= 75:
        return "B"
    if total >= 60:
        return "C"
    if total >= 40:
        return "D"
    return "F"


def compute_health_score(info: PackageInfo) -> HealthScore:
    def scaled(raw_20: int, max_score: int) -> int:
        return round(max(0, min(raw_20, 20)) / 20 * max_score)

    subs = [
        HealthSubScore("Maintenance", _score_maintained(info), 20),
        HealthSubScore("Community", scaled(_score_community(info), 15), 15),
        HealthSubScore("Documentation", scaled(_score_documentation(info), 15), 15),
        HealthSubScore("Releases", scaled(_score_activity(info), 15), 15),
        HealthSubScore("Security", _score_security(info), 20),
        HealthSubScore("Testing", scaled(_score_testing(info), 15), 15),
    ]
    total = sum(s.score for s in subs)
    return HealthScore(sub_scores=subs, total=total, grade=_grade(total))


# ── Release adoption ─────────────────────────────────────────────────────────


def compute_release_adoption(
    info: PackageInfo, limit: int = 5
) -> tuple[dict[str, float], str]:
    """Return (version -> percent, caption)."""
    versions = info.versions[:limit]
    if not versions:
        return {}, ""

    if info.registry is Registry.CRATES and info.version_downloads_recent:
        raw = {
            v.version: info.version_downloads_recent.get(v.external_id, 0)
            for v in versions
        }
        caption = "Source: crates.io real per-version downloads (~90d)"
    else:
        raw = _adoption_from_trend(info, versions)
        caption = "Estimated from 30-day download trend, sliced by release date"

    total = sum(raw.values())
    if total <= 0:
        return {}, caption
    return {ver: (count / total) * 100 for ver, count in raw.items()}, caption


def _adoption_from_trend(info: PackageInfo, versions) -> dict[str, int]:
    """Slice daily download totals into per-version windows by release date."""
    trend = info.download_trend
    if not trend:
        return {v.version: 0 for v in versions}

    def parse(d: str) -> datetime | None:
        try:
            return datetime.fromisoformat(d).replace(tzinfo=UTC)
        except (ValueError, TypeError):
            return None

    points = [(parse(p.date), p.count) for p in trend]
    points = [(d, c) for d, c in points if d is not None]

    raw: dict[str, int] = {}
    # versions are newest-first; window for index i is [release[i], release[i-1])
    for i, v in enumerate(versions):
        start = _aware(v.release_date)
        end = _aware(versions[i - 1].release_date) if i > 0 else None
        total = 0
        for d, c in points:
            if start and d < start:
                continue
            if end and d >= end:
                continue
            total += c
        raw[v.version] = total
    return raw


# ── Ecosystem distribution ───────────────────────────────────────────────────


def compute_install_breakdown(info: PackageInfo) -> InstallBreakdown:
    """Return download share by ecosystem.

    The model name is kept for compatibility with existing views/export, but
    the Overview dashboard renders this as ecosystem distribution rather than
    installation commands.
    """
    count = _registry_activity_count(info)
    label = info.registry.display_name
    caption = "Download share by supported ecosystem."
    return InstallBreakdown(
        methods=[
            InstallMethod(
                label=label,
                count=count,
                percent=100.0 if count > 0 else 0.0,
            )
        ]
        if count > 0
        else [],
        caption=caption,
        is_estimate=False,
    )


def _registry_activity_count(info: PackageInfo) -> int:
    count = info.download_counts.month or sum(
        p.count for p in info.download_trend[-30:]
    )
    return count or info.total_downloads


# ── Reverse dependencies + historical health ────────────────────────────────


def compute_reverse_dependency_summary(info: PackageInfo) -> ReverseDependencySummary:
    if info.reverse_dependency_count is None:
        caption = f"{info.registry.display_name} reverse-dependency count unavailable."
    else:
        caption = "Projects depending on this package."
    return ReverseDependencySummary(
        count=info.reverse_dependency_count,
        monthly_growth=info.reverse_dependency_monthly_growth,
        caption=caption,
    )


# ── Activity timeline ────────────────────────────────────────────────────────


def compute_activity_timeline(
    info: PackageInfo, limit: int = 15
) -> list[ActivityEvent]:
    events: list[ActivityEvent] = []
    for v in info.versions:
        rd = _aware(v.release_date)
        if rd:
            events.append(
                ActivityEvent(
                    kind=ActivityEventKind.RELEASE,
                    timestamp=rd,
                    title=f"v{v.version} published",
                    ref=v.version,
                )
            )
    for ev in info.github_issue_events:
        created = _aware(ev.created_at)
        if created:
            events.append(
                ActivityEvent(
                    kind=ActivityEventKind.PR_OPENED
                    if ev.is_pull_request
                    else ActivityEventKind.ISSUE_OPENED,
                    timestamp=created,
                    title=ev.title,
                    ref=f"#{ev.number}",
                    url=ev.url,
                )
            )
        closed = _aware(ev.closed_at)
        if closed:
            events.append(
                ActivityEvent(
                    kind=ActivityEventKind.PR_CLOSED
                    if ev.is_pull_request
                    else ActivityEventKind.ISSUE_CLOSED,
                    timestamp=closed,
                    title=ev.title,
                    ref=f"#{ev.number}",
                    url=ev.url,
                )
            )
    events.sort(key=lambda e: e.timestamp, reverse=True)
    return events[:limit]


# ── Downloads 30d + % change ─────────────────────────────────────────────────


def compute_downloads_30d(info: PackageInfo) -> tuple[int, float | None]:
    trend = info.download_trend
    if not trend:
        return info.download_counts.month, None
    counts = [p.count for p in trend]
    last30 = sum(counts[-30:])
    prior30 = sum(counts[-60:-30])
    if prior30 <= 0:
        return last30, None
    pct = (last30 - prior30) / prior30 * 100
    return last30, pct


# ── Aggregate ────────────────────────────────────────────────────────────────


def compute_all(info: PackageInfo) -> DerivedPackageData:
    adoption, adoption_caption = compute_release_adoption(info)
    total_30d, pct = compute_downloads_30d(info)
    return DerivedPackageData(
        health_score=compute_health_score(info),
        install_breakdown=compute_install_breakdown(info),
        reverse_dependency_summary=compute_reverse_dependency_summary(info),
        health_timeline=info.health_history,
        activity=compute_activity_timeline(info),
        release_adoption=adoption,
        adoption_caption=adoption_caption,
        downloads_30d_total=total_30d,
        downloads_30d_pct_change=pct,
    )
