# Environment variables

Secchi keeps these environment variables optional. They control integrations
that are useful in specific environments without changing the default CLI
experience.

| Variable | Values | Purpose |
| --- | --- | --- |
| `SECCHI_GITHUB_TOKEN` | GitHub token | Authenticates GitHub API requests for stars, repository signals, workflows, README, and issue activity. This is recommended for repeated scans and CI. |
| `SECCHI_DISABLE_UPDATE_CHECK` | `1`, `true`, `yes`, `on` | Disables the once-per-day PyPI release update check. |
| `SECCHI_DISABLE_SPOTLIGHT` | `1`, `true`, `yes`, `on` | Disables the optional Spotlight feed in the dashboard. |
| `XDG_CACHE_HOME` | Directory path | Changes the root directory used for Secchi's local cache. |

## GitHub API access

GitHub enrichment works without a token for occasional use, but unauthenticated
requests have a lower rate limit. If GitHub signals are missing or you run
Secchi repeatedly, authenticate with the GitHub CLI:

```bash
export SECCHI_GITHUB_TOKEN="$(gh auth token)"
secchi show duckdb --no-cache
```

In GitHub Actions, pass the workflow token to the action or Secchi process:

```yaml
env:
  SECCHI_GITHUB_TOKEN: ${{ github.token }}
```

Secchi only uses this token for read-only GitHub API requests. It is never
written to the Secchi cache or included in reports.

## Release update checks

Secchi checks PyPI at most once per day and caches the result locally. If a
newer release exists, the CLI prints an upgrade hint such as:

```text
Notice: A newer Secchi version is available: 0.1.6 (current: 0.1.5).
Upgrade with: pipx upgrade secchi or uv tool upgrade secchi
```

The check is best-effort: network failures never prevent a Secchi command from
running. Disable it when working offline or when a fully network-free command
is required:

```bash
SECCHI_DISABLE_UPDATE_CHECK=1 secchi report duckdb --format md
```

## Browser dashboard

`secchi web` uses the local `textual serve` command provided by Secchi's
installed Textual version. It does not contact a public relay. The server is
intended for local use or a trusted network and does not provide authentication
or production deployment hardening.
