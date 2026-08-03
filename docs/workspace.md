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

## Lazy loading and refresh

Workspace projects load lazily. Opening the dashboard does not fetch every
configured project immediately. Secchi fetches a project when it is selected,
then keeps its results in the local cache for the current day.

Refresh is scoped to the selected package or project:

```bash
secchi dashboard --config secchi.toml --refresh
secchi report --config secchi.toml --project duckdb --refresh --format json
```

Refreshing one project does not force unrelated projects to refresh. This
limits API pressure while preserving explicit control when current data is
needed.

## Multiple registries

When the same package name exists in multiple registries, the dashboard groups
the sources into one logical package. Downloads and ecosystem distribution are
combined, while a primary registry supplies fields that cannot be merged,
such as the preferred latest version profile.

Project identity remains separate: the same package in two projects has two
independent cache and refresh scopes.
