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


@dataclass
class PackageRef:
    """A reference to a package from config."""
    name: str
    registry: Registry


@dataclass
class Project:
    """A named collection of packages to monitor."""
    name: str
    description: str = ""
    packages: list[PackageRef] = field(default_factory=list)


@dataclass
class Version:
    """A specific version of a package."""
    version: str
    release_date: datetime | None = None
    downloads: int = 0
    is_yanked: bool = False


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
    """GitHub repository stats."""
    stars: int = 0
    forks: int = 0


@dataclass
class Dependency:
    """A dependency of a package."""
    name: str
    requirement: str = ""
    optional: bool = False


@dataclass
class PackageInfo:
    """Full package information fetched from the registry."""
    name: str
    registry: Registry
    description: str = ""
    author: str = ""
    license: str = ""
    homepage: str = ""
    repository_url: str = ""
    documentation_url: str = ""
    latest_version: str = ""
    latest_release_date: datetime | None = None
    total_downloads: int = 0
    download_counts: DownloadCounts = field(default_factory=DownloadCounts)
    github_stats: GitHubStats = field(default_factory=GitHubStats)
    versions: list[Version] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    download_trend: list[DownloadTrendPoint] = field(default_factory=list)
    release_notes: str = ""


@dataclass
class FetchError:
    """Error when fetching package data."""
    package_name: str
    registry: Registry
    message: str
