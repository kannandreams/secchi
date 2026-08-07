# Getting started

## Installation

Recommended installation methods:

=== "uv"

    ```bash
    uv tool install secchi
    ```

=== "pipx"

    ```bash
    pipx install secchi
    ```

=== "pip"

    ```bash
    pip install secchi
    ```

## Inspect a package directly

No configuration file is required for direct package commands:

```bash
secchi show duckdb
secchi dashboard duckdb
secchi search duckdb
secchi compare pypi:duckdb pypi:polars
```

Use `--registry` when a package name is ambiguous or when you want one
specific ecosystem:

```bash
secchi show duckdb --registry pypi
secchi dashboard serde --registry crates.io
```

## Create a workspace

Create a starter configuration interactively:

```bash
secchi init
```

Then launch the configured dashboard:

```bash
secchi dashboard
```

Secchi searches for configuration in this order:

1. The path passed with `--config` or `-c`
2. `./secchi.toml`
3. `./.secchi.toml`
4. `~/.config/secchi/config.toml`

See [Workspace](workspace.md) for the full configuration model.

## Refresh data

Package data is cached locally for the current day. Use `--no-cache` when you
need a complete fresh fetch. It bypasses the cache and re-fetches package
metadata, registry signals, GitHub signals, and security advisories from
OSV.dev:

```bash
secchi dashboard duckdb --no-cache
secchi report duckdb --no-cache --format json
```

To refresh only OSV security advisories while reusing the other package
signals, use:

```bash
secchi dashboard duckdb --security-no-cache
secchi show duckdb --security-no-cache
```

Optional signals such as download history or reverse dependencies may be
unavailable because of registry rate limits or missing endpoints. Secchi keeps
the package result available and reports warnings for missing signals.
