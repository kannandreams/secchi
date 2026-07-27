"""Utility helpers — formatting, release notes via GitHub, etc."""

from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from pkgwatch.config import get_env_token
from pkgwatch.models import GitHubStats


def shorten_number(n: int) -> str:
    """Format a large number with K, M, B suffixes."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def derive_github_repo(urls: list[str]) -> tuple[str, str] | None:
    """Try to extract (owner, repo) from a list of URLs.

    Returns None if no GitHub URL is found.
    """
    for url in urls:
        if not url:
            continue
        parsed = urlparse(url)
        if "github.com" not in parsed.hostname or not parsed.hostname:
            continue
        path = parsed.path.strip("/").rstrip(".git")
        parts = path.split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]
    return None


async def fetch_github_release_notes(owner: str, repo: str, tag: str | None = None) -> str:
    """Fetch the latest release notes from GitHub.

    Uses PKGWATCH_GITHUB_TOKEN env var for higher rate limits.
    """
    token = get_env_token("PKGWATCH_GITHUB_TOKEN")
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    params: dict[str, str] = {"per_page": "3"}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            releases = resp.json()
        except httpx.HTTPError:
            return ""

        if not releases:
            return ""

        release = releases[0]
        if tag and tag in [r.get("tag_name", "") for r in releases]:
            release = next(r for r in releases if r.get("tag_name") == tag)

        body = release.get("body", "")
        max_chars = 3000
        return body[:max_chars] + ("..." if len(body) > max_chars else "")


async def fetch_github_stats(owner: str, repo: str) -> GitHubStats:
    """Fetch GitHub stars and forks for a repo."""
    token = get_env_token("PKGWATCH_GITHUB_TOKEN")
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{owner}/{repo}"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return GitHubStats(
                stars=data.get("stargazers_count", 0),
                forks=data.get("forks_count", 0),
            )
        except httpx.HTTPError:
            return GitHubStats()


async def fetch_github_stats_for_package(
    homepage: str, repository_url: str
) -> GitHubStats:
    """Fetch GitHub stats by deriving repo from package URLs."""
    urls = [repository_url, homepage]
    repo = derive_github_repo(urls)
    if repo:
        return await fetch_github_stats(repo[0], repo[1])
    return GitHubStats()


async def fetch_release_notes_for_package(
    homepage: str, repository_url: str, version: str
) -> str:
    """Fetch release notes by deriving GitHub repo from package URLs."""
    urls = [repository_url, homepage]
    repo = derive_github_repo(urls)
    if repo:
        owner, name = repo
        tag = f"v{version}" if not version.startswith("v") else version
        notes = await fetch_github_release_notes(owner, name, tag)
        if notes:
            return notes
        return await fetch_github_release_notes(owner, name)
    return ""
