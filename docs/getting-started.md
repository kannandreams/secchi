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

## Open the dashboard in a browser

Secchi can serve the same Textual dashboard in a local browser with Textual's
built-in server:

```bash
uv sync
uv run secchi web duckdb
```

The server runs locally and normally prints a URL such as
`http://localhost:8000`. Contributors only need `uv sync`; no separate browser
server package or relay account is required.

The default port is `8000`. If that port is already in use, choose another:

```bash
uv run secchi web duckdb --port 8001
```

The `web` command must be available in the installed Secchi version. If
`secchi --help` does not list `web`, upgrade Secchi or run the current checkout
with uv:

```bash
uv tool upgrade secchi
# or, from a Secchi checkout:
uv run secchi web duckdb
```

Browser mode launches the existing `secchi dashboard` experience through
Textual's local server. Treat generated URLs as access to the live dashboard
session. Browser support is currently beta and is intended for local demos or
trusted networks.

## Create a workspace

Secchi checks PyPI at most once per day and prints an upgrade hint when a newer
release is available. Disable the check with
`SECCHI_DISABLE_UPDATE_CHECK=1` when working offline.

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
