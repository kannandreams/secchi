<table>
  <tr>
    <td><img src="assets/secchi-logo.png" alt="Secchi logo" width="110"></td>
    <td>
      <h1>secchi</h1>
      <p><strong>Open Source Package Intelligence</strong></p>
    </td>
  </tr>
</table>

Secchi lets you explore, compare, monitor, and report on package health,
adoption, dependencies, releases, and ecosystem signals from your terminal.

![secchi TUI dashboard](assets/secchi-v0.1.0-demo-1.gif)

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
| Explore | Interactive dashboard | Explore health, adoption, releases, and dependencies | ✅ |
| Explore | Workspace monitoring | Monitor configured projects and registry sources | ✅ |
| Explore | Cross-registry search | Find packages across supported ecosystems | ✅ |
| Explore | Health and adoption signals | Understand project momentum and maintenance quality | ✅ |
| Explore | Package comparison | Compare multiple packages side by side | ⏳ |
| Report | JSON reports | Use package intelligence in scripts and automation | ✅ |
| Report | Markdown reports | Share readable reports in GitHub, Notion, or documentation | ✅ |
| Report | HTML reports | Generate standalone reports for teams and stakeholders | ✅ |
| Report | Project-wide reports | Combine registry sources for one monitored project | ✅ |
| Automate | Package health checks | Fail workflows when package standards are not met | 🚧 |
| Automate | Workspace policy checks | Evaluate every configured project against policies | ⏳ |
| Automate | GitHub Actions integration | Run Secchi automatically in CI | ⏳ |
| Integrate | Python SDK | Use Secchi from Python applications and scripts | ⏳ |
| Integrate | MCP Server | Let AI assistants query package intelligence | ⏳ |
| Explore | Ecosystem adapters | Support PyPI, npm, crates.io, Homebrew, Go Modules, and CRAN | ✅ |

## Install

Recommended installation methods:

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

Scaffold a config file interactively:

```bash
secchi init
```

Launch the dashboard for a project:

```bash
secchi -p tuffcli
secchi --project opencode
```

Explore a package directly, without a configuration file:

```bash
secchi show duckdb
secchi dashboard duckdb
secchi search duckdb
secchi report duckdb --format html --output duckdb-report.html
secchi report --config secchi.toml --project duckdb --format html
secchi check duckdb --min-health 80 --require-ci
```

Reports are written to the current directory by default. Use `--output` to
choose a file path, or `--output -` to print the report to stdout.

`search`, `show`, `dashboard`, and `report` use the same data collection and scoring
pipeline. Add `--registry` with `pypi`, `crates.io`, `npm`, `homebrew`, `go`, or
`cran` when a package name needs an explicit ecosystem.

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
[projects.tuffcli]
title = "TuffCLI"
description = "tuffcli — capability lifecycle manager for coding agents"
favorite = true
repository = "https://github.com/example/tuffcli"
packages = [
    { name = "tuffcli", registry = "crates.io" },
    { name = "tuffcli", registry = "pypi" },
]
```

`favorite` belongs to the project, which makes workspace navigation clear when
one project contains several registry variants of the same package. Existing
package-level `favorite` entries remain supported for compatibility.

## Supported Registries

| Registry   | Key           |
|------------|---------------|
| PyPI       | `pypi`        |
| crates.io  | `crates.io`   |
| npm        | `npm`         |
| Homebrew   | `homebrew`    |
| Go Modules | `go`          |
| CRAN (R)   | `cran`        |

## CLI Options

```
secchi dashboard [package]              Launch the TUI (workspace when omitted)
secchi show <package>                   Print a concise intelligence summary
secchi search <package>                 Search packages across supported registries
secchi report <package> --format <type> Generate json, html, or md output
secchi check <package>                 Evaluate health and CI policies for automation
secchi --project <name>                 Backwards-compatible project dashboard
secchi --list                           List projects in config
secchi init                             Interactively create secchi.toml
```

## Development

Live reload during development:

```bash
uv run textual run --dev src/secchi/dev.py -- -p tuffcli
```

Press `ctrl+r` to manually reload the dashboard without exiting.

## License

Apache 2.0
