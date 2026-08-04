# Secchi

**Open Source Package Intelligence** for the terminal.

Secchi helps engineers and coding agents explore, compare, monitor, and report
on package health, adoption, dependencies, releases, and ecosystem signals.

![Secchi dashboard](https://raw.githubusercontent.com/kannandreams/secchi/main/assets/duck-db-demo.png)

## Why Secchi?

Package choice is increasingly part of automated development. Secchi provides
one normalized view across registries so people and agents can understand the
signals behind a dependency decision.

It can be used in two ways:

- Inspect a package directly, such as `secchi dashboard duckdb`.
- Monitor named projects from a `secchi.toml` workspace configuration.

## Supported ecosystems

| Ecosystem | Registry | Typical package reference |
| --- | --- | --- |
| Python | PyPI | `pypi:duckdb` |
| JavaScript | npm | `npm:duckdb` |
| Rust | crates.io | `crates.io:serde` |
| Homebrew | Homebrew | `homebrew:jq` |
| Go | Go Modules | `go:github.com/example/project` |
| R | CRAN | `cran:jsonlite` |

## Capabilities

- Interactive terminal dashboard
- Cross-registry package search
- Health, adoption, dependency, release, and repository signals
- Workspace monitoring with lazy project loading
- JSON, Markdown, and HTML reports
- Package comparison with evidence and confidence
- MCP tools for coding agents

## Next steps

- [Install and run Secchi](getting-started.md)
- [Learn the CLI commands](commands.md)
- [Configure workspace monitoring](workspace.md)
- [Use Secchi with MCP](mcp.md)
