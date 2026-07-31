from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class Registry(str, Enum):
    PYPI = "pypi"
    CRATES = "crates.io"
    NPM = "npm"

    @property
    def display_name(self) -> str:
        return {self.PYPI: "PyPI", self.CRATES: "crates.io", self.NPM: "npm"}[self]

    @property
    def icon(self) -> str:
        return {self.PYPI: "📦", self.CRATES: "🦀", self.NPM: "📜"}[self]

    @property
    def language(self) -> str:
        return {self.PYPI: "Python", self.CRATES: "Rust", self.NPM: "JavaScript"}[self]

    @property
    def install_command(self) -> str:
        return {self.PYPI: "pip install", self.CRATES: "cargo install", self.NPM: "npm install"}[self]


@dataclass
class PackageRef:
    """A reference to a package from config."""
    name: str
    registry: Registry
    favorite: bool = False
    project_name: str = ""


@dataclass
class Project:
    """A named collection of packages to monitor."""
    name: str
    description: str = ""
    favorite: bool = False
    repository_url: str = ""
    packages: list[PackageRef] = field(default_factory=list)
    title: str = ""


@dataclass
class Version:
    """A specific version of a package."""
    version: str
    release_date: datetime | None = None
    downloads: int = 0
    is_yanked: bool = False
    # crates.io numeric version id — joins to /downloads' `version` field. None for pypi/npm.
    external_id: int | str | None = None
    # pypi: sum of release-file sizes; npm: dist.unpackedSize; crates: crate_size.
    size_bytes: int | None = None


@dataclass
class DownloadTrendPoint:
    """A single data point for download trend charts."""
    date: str
    count: int


@dataclass
class DownloadCounts:
    """Breakdown of downloads by period."""
    today: int = 0
    week: int = 0
    month: int = 0


@dataclass
class GitHubStats:
    """GitHub repository stats (raw, from the repo + signals APIs)."""
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    created_at: datetime | None = None
    pushed_at: datetime | None = None  # proxy for "last commit"
    has_ci: bool = False               # proxy for "Testing": .github/workflows non-empty
    has_readme: bool = False
    resolved: bool = False             # True iff an owner/repo was derivable + fetched
    # week-over-week deltas from local history cache. None = no baseline yet ("—").
    stars_delta_7d: int | None = None
    open_issues_delta_7d: int | None = None


@dataclass
class Dependency:
    """A dependency of a package."""
    name: str
    requirement: str = ""
    optional: bool = False


@dataclass
class ReleaseFile:
    """One published artifact for a version.

    PyPI has several per version; npm/crates get one synthetic entry.
    """
    packagetype: str  # "bdist_wheel" | "sdist" | "npm-package" | "crate"
    size: int = 0
    filename: str = ""


@dataclass
class ReverseDependency:
    """A package that depends on this one, ranked by its own real total downloads."""
    name: str
    downloads: int = 0


@dataclass
class GitHubIssueEvent:
    """Raw GitHub issue OR pull request record.

    Feeds both health-score issue counts and the Activity timeline.
    """
    number: int
    title: str
    is_pull_request: bool
    created_at: datetime
    closed_at: datetime | None
    url: str = ""


@dataclass
class HistorySnapshot:
    """A point-in-time snapshot cached locally to derive week-over-week deltas."""
    timestamp: datetime
    stars: int
    open_issues: int
    health_score: int | None = None
    reverse_dependency_count: int | None = None


@dataclass
class MetricTimelinePoint:
    """A compact labeled metric point for dashboard sparklines."""
    label: str
    value: int


# ── Derived-display dataclasses (produced by derived.py, consumed by widgets) ──


@dataclass
class InstallMethod:
    label: str
    count: int
    percent: float


@dataclass
class InstallBreakdown:
    methods: list[InstallMethod] = field(default_factory=list)
    caption: str = ""
    is_estimate: bool = False


@dataclass
class ReverseDependencySummary:
    count: int | None = None
    monthly_growth: int | None = None
    caption: str = ""


class ActivityEventKind(str, Enum):
    RELEASE = "release"
    ISSUE_OPENED = "issue_opened"
    ISSUE_CLOSED = "issue_closed"
    PR_OPENED = "pr_opened"
    PR_CLOSED = "pr_closed"

    @property
    def icon(self) -> str:
        return {
            self.RELEASE: "◉",
            self.ISSUE_OPENED: "◈",
            self.ISSUE_CLOSED: "✓",
            self.PR_OPENED: "⇄",
            self.PR_CLOSED: "⇥",
        }[self]

    @property
    def label(self) -> str:
        return {
            self.RELEASE: "New Release",
            self.ISSUE_OPENED: "New Issue",
            self.ISSUE_CLOSED: "Issue Closed",
            self.PR_OPENED: "New PR",
            self.PR_CLOSED: "PR Closed",
        }[self]


@dataclass
class ActivityEvent:
    kind: ActivityEventKind
    timestamp: datetime
    title: str
    ref: str = ""
    url: str = ""


@dataclass
class HealthSubScore:
    label: str
    score: int
    max_score: int = 20


@dataclass
class HealthScore:
    sub_scores: list[HealthSubScore] = field(default_factory=list)
    total: int = 0   # 0-100
    grade: str = "—"  # "A".."F"


@dataclass
class DerivedPackageData:
    """All display-ready metrics derived (via arithmetic, no I/O) from a PackageInfo."""
    health_score: HealthScore = field(default_factory=HealthScore)
    install_breakdown: InstallBreakdown = field(default_factory=InstallBreakdown)
    reverse_dependency_summary: ReverseDependencySummary = field(default_factory=ReverseDependencySummary)
    health_timeline: list[MetricTimelinePoint] = field(default_factory=list)
    activity: list[ActivityEvent] = field(default_factory=list)
    release_adoption: dict[str, float] = field(default_factory=dict)
    adoption_caption: str = ""
    downloads_30d_total: int = 0
    downloads_30d_pct_change: float | None = None


@dataclass
class PackageInfo:
    """Full package information fetched from the registry."""
    name: str
    registry: Registry
    source_registries: list[Registry] = field(default_factory=list)
    description: str = ""
    author: str = ""
    license: str = ""
    homepage: str = ""
    repository_url: str = ""
    documentation_url: str = ""
    latest_version: str = ""
    latest_release_date: datetime | None = None
    total_downloads: int = 0
    package_kind: str = ""  # best-effort "CLI" / "Library" / etc.
    download_counts: DownloadCounts = field(default_factory=DownloadCounts)
    github_stats: GitHubStats = field(default_factory=GitHubStats)
    versions: list[Version] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    download_trend: list[DownloadTrendPoint] = field(default_factory=list)
    release_notes: str = ""
    # raw extras feeding derivation
    latest_release_files: list[ReleaseFile] = field(default_factory=list)
    version_downloads_recent: dict[int | str, int] = field(default_factory=dict)  # crates.io only
    reverse_dependencies: list[ReverseDependency] = field(default_factory=list)    # crates.io only
    reverse_dependency_count: int | None = None
    reverse_dependency_monthly_growth: int | None = None
    health_history: list[MetricTimelinePoint] = field(default_factory=list)
    github_issue_events: list[GitHubIssueEvent] = field(default_factory=list)


@dataclass
class FetchError:
    """Error when fetching package data."""
    package_name: str
    registry: Registry
    message: str


@dataclass
class SearchResult:
    """A normalized package discovery result from a registry search."""

    name: str
    registry: Registry
    version: str = ""
    description: str = ""
    url: str = ""
    score: float = 0.0
    exact: bool = False
