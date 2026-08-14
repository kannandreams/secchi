# Secchi

Secchi is an open source package intelligence CLI. It combines registry
metadata, download activity, release history, GitHub signals, dependency
information, and security advisories into a single view of a package,
across PyPI, npm, crates.io, Homebrew, Go Modules, and CRAN. It ships an
interactive terminal dashboard, cross-registry search and comparison,
exportable reports, workspace monitoring, and a read-only MCP server for
coding agents.

For the product overview, see [secchi.dev](https://secchi.dev).

## Install

```bash
uv tool install secchi
```

Then inspect a package directly — no configuration file required:

```bash
secchi dashboard duckdb
```

See [Getting started](getting-started.md) for pipx and pip installation
and first-run guidance.

## Documentation

| Page | Covers |
| --- | --- |
| [Getting started](getting-started.md) | Installation and first commands. |
| [Commands](commands.md) | The full CLI command reference. |
| [Dashboard metrics](metrics.md) | Every dashboard signal and how the health score is calculated. |
| [Workspace](workspace.md) | Monitoring a named list of projects. |
| [Reports](reports.md) | JSON, Markdown, and HTML export. |
| [Environment variables](environment.md) | Optional integrations and behavior switches. |
| [GitHub Actions](github-actions.md) | Using the Secchi Marketplace Action in CI. |
| [MCP and agents](mcp.md) | The read-only MCP server for coding agents. |
| [Development](development.md) | Working on Secchi itself. |
| [Contributing](contributing.md) | How to file issues and submit changes. |

## Related projects

- [Secchi CLI Analytics](https://github.com/kannandreams/secchi-cli-analytics)
  — a separate binary that gives CLI authors local-first usage analytics:
  command and flag usage, failures, and human-versus-agent attribution,
  with command paths and flag names only, never argument values.
- Test coverage for this repository is published at
  [docs.secchi.dev/coverage](https://docs.secchi.dev/coverage/).
