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

## Capabilities

| Type | Capability | Status |
| --- | --- | :---: |
| Explore | CLI | ✅ |
| Explore | Interactive TUI | ✅ |
| Explore | Package discovery across registries | ✅ |
| Explore | Compare packages | ✅ |
| Report | HTML | ✅ |
| Report | JSON | ✅ |
| Report | Markdown | ✅ |
| Report | CSV | ⏳ |
| Automate | Repository configuration | ⏳ |
| Automate | Policy checks | ⏳ |
| Automate | GitHub Actions | ⏳ |
| Automate | CI integration | ⏳ |
| Integrate | MCP Server | ⏳ |
| Integrate | REST API | ⏳ |
| Integrate | Python SDK | ⏳ |

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
pipeline. Add `--registry pypi`, `--registry crates.io`, or `--registry npm`
when a package name needs an explicit ecosystem.

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

MIT
