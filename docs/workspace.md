# Workspace monitoring

Workspace mode lets a team keep a named list of projects and the package
sources that belong to each project. A project can contain the same logical
package in multiple registries.

## Configuration

Create `secchi.toml` in the current directory:

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

[projects.polars]
title = "Polars"
description = "Fast DataFrame library"
packages = [
    { name = "polars", registry = "pypi" },
    { name = "polars", registry = "crates.io" },
]
```

Supported registry values are `pypi`, `npm`, `crates.io`, `homebrew`, `go`,
and `cran`.

### When Secchi reads the configuration

Workspace commands read `secchi.toml` to load projects and package sources:

```bash
secchi dashboard
secchi dashboard --project tools
secchi monitor tools
secchi report --project tools
secchi --list
```

Secchi looks for configuration in this order:

1. The path passed with `--config` or `-c`.
2. `./secchi.toml`.
3. `./.secchi.toml`.
4. `~/.config/secchi/config.toml`, or `$XDG_CONFIG_HOME/secchi/config.toml`.

Direct package commands do not require a configuration file and inspect the
package named on the command line instead:

```bash
secchi show tuffcli
secchi dashboard tuffcli
secchi search tuffcli
```

If a direct dashboard package matches a configured project or package, Secchi
uses that configured workspace entry; otherwise it resolves the package across
the supported registries.

## Project titles and favorites

Use `title` for the human-readable project name shown in the dashboard. Use
project-level `favorite = true` to control the default workspace selection.

Package-level favorites remain supported for compatibility with older config
files:

```toml
[projects.duckdb]
packages = [
    { name = "duckdb", registry = "pypi", favorite = true },
]
```

New configurations should prefer project-level favorites because the project,
not an individual registry variant, controls workspace navigation.

Favorites are stored in `secchi.toml`; they are not maintained in a separate
database. The `f` dashboard shortcut only toggles the favorites-only view for
the current session and does not change the configuration file.

## Lazy loading and refresh

Workspace projects load lazily. Opening the dashboard does not fetch every
configured project immediately. Secchi fetches a project when it is selected,
then keeps its results in the local cache for the current day.

Refresh is scoped to the selected package or project. It bypasses the local
cache and re-fetches package metadata, registry signals, GitHub signals, and
OSV security advisories:

```bash
secchi dashboard --config secchi.toml --no-cache
secchi report --config secchi.toml --project duckdb --no-cache --format json
```

Refreshing one project does not force unrelated projects to refresh. This
limits API pressure while preserving explicit control when current data is
needed.

Use `--security-no-cache` when only OSV advisories need to be re-fetched; the
general package cache remains in use.

## Multiple registries

When the same package name exists in multiple registries, the dashboard groups
the sources into one logical package. Downloads and ecosystem distribution are
combined, while a primary registry supplies fields that cannot be merged,
such as the preferred latest version profile.

Project identity remains separate: the same package in two projects has two
independent cache and refresh scopes.
