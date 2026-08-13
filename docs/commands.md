# Commands

Secchi's CLI commands share the same package resolution, caching, enrichment,
and scoring services. The output surface changes by command; the intelligence
pipeline does not.

Use [Workspace](workspace.md) to understand when `secchi.toml` is read, how
configuration paths are selected, and where dashboard favorites come from.

## `show`

Print a compact terminal summary:

```bash
secchi show duckdb
secchi show duckdb --registry pypi
```

## `dashboard`

Launch the full-screen Textual dashboard:

```bash
secchi dashboard duckdb
secchi dashboard --config secchi.toml
secchi dashboard --project duckdb
```

The dashboard includes adoption trend, health, ecosystem distribution, reverse
dependencies, health timeline, version adoption, and a dedicated Security tab.
See [Dashboard metrics](metrics.md) for the meaning of each card and panel and
the detailed health-score calculation.

## `web`

Serve the same Textual dashboard in a browser with
[`textual-web`](https://github.com/Textualize/textual-web):

```bash
secchi web duckdb
secchi web --config secchi.toml
secchi web --project duckdb
```

Install the external `textual-web` CLI before using the command:

```bash
pipx install textual-web
```

Browser mode generates a temporary `textual-web` configuration that launches
`secchi dashboard` with the same package, project, config, cache, diagnostics,
and security-refresh options. It does not serve an arbitrary terminal.

Treat generated URLs as access to the live dashboard session. The Textual app
still runs on the host machine or server; the browser connects to that running
process.

`textual-web` is intentionally treated as an external command rather than a
Secchi package dependency because the latest PyPI release currently pins an
older Textual runtime than Secchi itself uses.

## `search`

Search supported registries and return ranked matches:

```bash
secchi search duckdb
secchi search serde --registry crates.io
secchi search tuffcli --verbose
secchi search tuffcli --log-file secchi-run.log
```

Search queries each selected registry independently. A registry that cannot be
reached is reported as `WARN` while successful registry results remain visible.
Use `--verbose` to show every `SUCCESS`, `WARN`, and `FAILURE` event, including
the URL and HTTP status returned by a registry. Use `--log-file PATH` to save
the same readable diagnostics for troubleshooting.

In the dashboard, press `l` to open the current session's process log. The
existing `f` shortcut remains the favorites-only filter. Non-fatal signal
warnings stay in the process log rather than being repeated in the package
detail view; critical package-fetch failures still appear in the detail view.

## `report`

Generate package or project reports in JSON, Markdown, or HTML:

```bash
secchi report duckdb --format json
secchi report duckdb --format md --output duckdb.md
secchi report duckdb --format html --output duckdb.html
secchi report --config secchi.toml --project duckdb --format html
```

Reports use the current directory by default. Pass `--output -` to print the
report to stdout.

## `compare`

Compare two or more package choices:

```bash
secchi compare pypi:duckdb pypi:polars
secchi compare pypi:duckdb pypi:polars --format json
```

Comparison is advisory. It reports evidence, confidence, data completeness,
and a recommendation such as `Recommended`, `Acceptable`, `Use with caution`,
or `Avoid`. Secchi never installs or changes packages.

## `check`

Evaluate a package against policy thresholds:

```bash
secchi check duckdb --min-health 80 --require-ci
```

## Other options

```bash
secchi --list
secchi init
secchi --version
secchi --help
```
