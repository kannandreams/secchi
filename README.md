<table>
  <tr>
    <td><img src="https://raw.githubusercontent.com/kannandreams/secchi/main/assets/secchi-logo.png" alt="Secchi logo" width="110"></td>
    <td>
      <h1>secchi</h1>
      <p><strong>Open Source Package Intelligence</strong></p>
    </td>
  </tr>
</table>

[![PyPI version](https://img.shields.io/pypi/v/secchi.svg)](https://pypi.org/project/secchi/)
[![PyPI license](https://img.shields.io/pypi/l/secchi.svg)](https://pypi.org/project/secchi/)
[![Latest release](https://img.shields.io/github/v/release/kannandreams/secchi?display_name=tag)](https://github.com/kannandreams/secchi/releases)
[![CI](https://github.com/kannandreams/secchi/actions/workflows/ci.yml/badge.svg)](https://github.com/kannandreams/secchi/actions/workflows/ci.yml)

Secchi lets you explore, compare, monitor, and report on package health,
adoption, dependencies, releases, and ecosystem signals from your terminal.

> **How to pronounce it:** Secchi is pronounced **“SEK-ee.”** The name is
> inspired by the [Secchi disk](https://www.merriam-webster.com/dictionary/Secchi%20disc),
> an instrument used to measure water clarity—an apt metaphor for making
> package intelligence easier to see.

![secchi TUI dashboard](https://raw.githubusercontent.com/kannandreams/secchi/main/assets/duck-db-demo.png)

## Try Secchi first

You can try the CLI and open the dashboard without installing Secchi as a
permanent command. This uses [`uvx`](https://docs.astral.sh/uv/guides/tools/),
which creates a temporary environment and removes it when you are done.

You only need [uv](https://docs.astral.sh/uv/getting-started/installation/)
installed:

```bash
# Print package intelligence in your terminal
uvx --from secchi secchi show duckdb

# Open the interactive dashboard
uvx --from secchi secchi dashboard duckdb
```

See the available commands before trying a package:

```bash
uvx --from secchi secchi --help
```

Secchi checks PyPI at most once per day and prints an upgrade notice when a
newer release is available. Disable this optional check with
`SECCHI_DISABLE_UPDATE_CHECK=1`.

If you like what you see, install Secchi permanently with one of the options
below. You do not need to run `secchi init` for direct package exploration;
`init` is only needed when you want to create a workspace configuration for
your own projects.

## Supported Ecosystems

<table>
  <tr>
    <td align="center"><img src="https://cdn.simpleicons.org/python" alt="Python" width="28"><br><strong>PyPI</strong><br><small>Python</small></td>
    <td align="center"><img src="https://cdn.simpleicons.org/javascript" alt="JavaScript" width="28"><br><strong>npm</strong><br><small>JavaScript</small></td>
    <td align="center"><img src="https://cdn.simpleicons.org/rust" alt="Rust" width="28"><br><strong>crates.io</strong><br><small>Rust</small></td>
    <td align="center"><img src="https://cdn.simpleicons.org/homebrew" alt="Homebrew" width="28"><br><strong>Homebrew</strong><br><small>Formulae</small></td>
    <td align="center"><img src="https://cdn.simpleicons.org/go" alt="Go" width="28"><br><strong>Go Modules</strong><br><small>Go</small></td>
    <td align="center"><img src="https://cdn.simpleicons.org/r" alt="R" width="28"><br><strong>CRAN</strong><br><small>R</small></td>
  </tr>
</table>

## Capabilities

| Type | Capability | What it helps with | Status |
| --- | --- | --- | :---: |
| Explore | Direct package lookup | Quickly inspect any package from the terminal | ✅ |
| Explore | Interactive dashboard | Explore health, adoption, releases, dependencies, and optional [Web dashboard](docs/getting-started.md#open-the-dashboard-in-a-browser) access | ✅ |
| Explore | Workspace monitoring | Monitor configured projects and registry sources | ✅ |
| Explore | Cross-registry search | Find packages across supported ecosystems | ✅ |
| Explore | Health and adoption signals | Understand project momentum and maintenance quality | ✅ |
| Explore | Security advisories | See OSV advisories affecting the latest package version | ✅ |
| Explore | Package comparison | Rank package choices with health, adoption, and confidence evidence | ✅ |
| Report | JSON reports | Use package intelligence in scripts and automation | ✅ |
| Report | Markdown reports | Share readable reports in GitHub, Notion, or documentation | ✅ |
| Report | HTML reports | Generate standalone reports for teams and stakeholders | ✅ |
| Report | Project-wide reports | Combine registry sources for one monitored project | ✅ |
| Automate | Package health checks | Fail workflows when package standards are not met | 🚧 |
| Automate | Workspace policy checks | Evaluate every configured project against policies | ⏳ |
| Automate | GitHub Actions integration | Run Secchi automatically in CI | ✅ |
| Integrate | Python SDK | Use Secchi from Python applications and scripts | ⏳ |
| Integrate | MCP Server | Let AI assistants query package intelligence | ✅ |
| Explore | Ecosystem adapters | Support PyPI, npm, crates.io, Homebrew, Go Modules, and CRAN | ✅ |

## Install

For regular use, install Secchi as a command-line tool:

```bash
uv tool install secchi
```

```bash
pipx install secchi
```

```bash
pip install secchi
```

## Quick Start

After installation, scaffold a config file interactively:

```bash
secchi init
```

Launch the dashboard for a project:

```bash
secchi -p duckdb
secchi --project opencode
```

Explore a package directly, without a configuration file:

```bash
secchi show duckdb
secchi dashboard duckdb
secchi search duckdb
secchi compare pypi:duckdb pypi:polars
secchi compare pypi:duckdb pypi:polars --format json
secchi report duckdb --format html --output duckdb-report.html
secchi report --config secchi.toml --project duckdb --format html
secchi check duckdb --min-health 80 --require-ci
```

Run the MCP server for local AI-agent integrations:

```bash
secchi mcp
# or
secchi-mcp
```

The server communicates over standard input/output and exposes tools for
package inspection, cross-registry search, configured project reports, and
health policy checks. It reuses the same cached intelligence pipeline as the
CLI, dashboard, and report commands.

## GitHub Actions

Secchi is available on the GitHub Marketplace as
[Secchi Package Intelligence](https://github.com/marketplace/actions/secchi-package-intelligence).
Use it to run package intelligence in CI and publish Markdown reports to the
Actions job summary or a pull request comment.

```yaml
- uses: kannandreams/secchi-action@v1
  with:
    package: pypi:duckdb
```

## Use Secchi with MCP

Secchi can be added to an MCP-compatible coding agent or desktop client as a
local stdio server. If `secchi` is installed as a tool, use:

```json
{
  "mcpServers": {
    "secchi": {
      "command": "secchi-mcp"
    }
  }
}
```

When running from a source checkout with uv, point the client at the project:

```json
{
  "mcpServers": {
    "secchi": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/secchi",
        "secchi-mcp"
      ]
    }
  }
}
```

The exact configuration file location depends on the MCP client. After the
server is added, the agent can use these tools:

| MCP tool | Use it for |
| --- | --- |
| `inspect_package` | Inspect health, adoption, releases, dependencies, and repository signals |
| `search_packages` | Find matching packages across PyPI, npm, crates.io, Homebrew, Go Modules, and CRAN |
| `inspect_project` | Read a configured project from `secchi.toml` and summarize all its package sources |
| `check_package` | Evaluate minimum health and repository CI policies |
| `compare_packages` | Rank two or more package choices with recommendations, confidence, and evidence |

Package inspection uses Secchi's local cache by default. Ask the agent to
refresh the data when current registry information is required. The MCP server
is read-only: it does not modify packages, repositories, or configuration.
Successful package results may include signal warnings when an optional source
is unavailable; those warnings are preserved instead of turning the package
into a failed result.

Reports are written to the current directory by default. Use `--output` to
choose a file path, or `--output -` to print the report to stdout.

Package inspection includes a Security tab in the dashboard and advisory data
in `show`, JSON, Markdown, HTML, and MCP results. Advisories are queried from
OSV.dev for the latest published version. A failed advisory lookup is reported
as a non-fatal signal warning; it does not change the health score or policy
check result. Homebrew does not currently have a stable OSV ecosystem mapping
in Secchi and is reported without advisory coverage.

Use `--no-cache` for a complete fresh fetch. It bypasses the local cache and
re-fetches package metadata, registry signals, GitHub signals, and OSV security
advisories.

Use `--security-no-cache` when only the OSV advisory data should be refreshed;
the package, registry, and GitHub caches are reused.

See [DuckDB report examples](examples/reports/README.md) for package and
project exports in JSON, Markdown, and HTML.

JSON reports declare a `schema` and `schema_version` so automation can reject
or migrate incompatible output deliberately. Secchi's local package cache uses
the same versioned-envelope approach and continues to read legacy unversioned
cache entries while writing the current schema for new data.

The serialized boundaries are validated with Pydantic models while the internal
application remains dataclass-based. This keeps the service and TUI lightweight
while giving cache files, reports, and MCP responses explicit contracts. Future
schema changes can be introduced as migrations instead of relying on every
renderer and consumer to handle new fields independently.

`search`, `show`, `dashboard`, and `report` use the same data collection and scoring
pipeline. Add `--registry` with `pypi`, `crates.io`, `npm`, `homebrew`, `go`, or
`cran` when a package name needs an explicit ecosystem.

For registry troubleshooting, add `--verbose` to show readable `SUCCESS`,
`WARN`, and `FAILURE` events, including HTTP response statuses. Use
`--log-file PATH` to save the current run's diagnostics. In the dashboard,
press `l` for the process log; `f` remains the favorites-only filter.

`compare` is an advisory decision aid for agents and engineers choosing between
dependencies. It reports `Recommended`, `Acceptable`, `Use with caution`, or
`Avoid`, along with the evidence and unknown signals behind the result. Use
explicit `registry:name` references when comparing packages across ecosystems.
Secchi does not install, upgrade, remove, or approve a dependency automatically.

See the [Dashboard metrics and health score guide](docs/metrics.md) for the
meaning of the dashboard cards, overview panels, health categories, grades, and
practical ways to improve a package's signals.

List available projects:

```bash
secchi --list
```

## Config

Secchi looks for config in this order:

1. `--config` / `-c` path
2. `./secchi.toml`
3. `./.secchi.toml`
4. `~/.config/secchi/config.toml`

Example `secchi.toml`:

```toml
[projects.duckdb]
title = "DuckDB"
description = "DuckDB — embeddable analytical database"
favorite = true
repository = "https://github.com/duckdb/duckdb"
packages = [
    { name = "duckdb", registry = "pypi" },
    { name = "duckdb", registry = "npm" },
]
```

`favorite` belongs to the project, which makes workspace navigation clear when
one project contains several registry variants of the same package. Existing
package-level `favorite` entries remain supported for compatibility.

## Optional Spotlight Feed

The dashboard can show a small, curated Spotlight card from Secchi's public
feed. Spotlight is cached locally and can be disabled completely when you do
not want Secchi to request the feed.

```bash
SECCHI_DISABLE_SPOTLIGHT=1 secchi dashboard duckdb
```

When this variable is set to `1`, `true`, `yes`, or `on`, Secchi does not read
or fetch Spotlight data and removes the card from the dashboard.

See the [environment variables guide](docs/environment.md) for release update
checks, GitHub API authentication, cache location, and optional integrations.

## CLI Options

```
secchi dashboard [package]              Launch the TUI (workspace when omitted)
secchi web [package]                    Serve the TUI dashboard in a browser
secchi show <package>                   Print a concise intelligence summary
secchi search <package>                 Search packages across supported registries
secchi report <package> --format <type> Generate json, html, or md output
secchi compare <package> <package>      Rank package choices; add --format json for agents
secchi check <package>                 Evaluate health and CI policies for automation
secchi --project <name>                 Backwards-compatible project dashboard
secchi --list                           List projects in config
secchi init                             Interactively create secchi.toml
```

Run `uv sync` and `uv run secchi web duckdb` from a source checkout; Secchi
uses Textual's built-in local web server. No separate browser server package
or relay account is required. The
`web` command is available in recent Secchi releases; if it does not appear in
`secchi --help`, upgrade Secchi. There is currently no `secchi[web]` extra
because browser serving is provided by Secchi's existing Textual dependency.

The local server uses port `8000` by default. Choose another port when needed:

```bash
uv run secchi web duckdb --port 8001
```

Browser support is currently beta and intended for local demos or trusted
networks. The Python process runs on the host machine and the browser connects
to the local server. See the [environment variables guide](docs/environment.md)
for related runtime controls.
Browser mode serves the existing Textual dashboard through the local server;
generated URLs should be treated as access to the live dashboard session.

## Development

Live reload during development:

```bash
uv run textual run --dev src/secchi/dev.py -- -p duckdb
```

Press `ctrl+r` to manually reload the dashboard without exiting.

### Coverage Reports

The latest `main` coverage report is published at
[`kannandreams.github.io/secchi/coverage/`](https://kannandreams.github.io/secchi/coverage/)
after GitHub Pages is enabled for the repository.

## Project Information

- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## License

Apache 2.0
