# Report examples

These files are sanitized, checked-in examples of Secchi's supported report
formats. They are useful for understanding the output shape, building demos,
and testing integrations that consume Secchi reports.

The DuckDB examples cover both report scopes:

- `duckdb/package.*` shows one package source (`duckdb` on PyPI).
- `duckdb/project.*` shows the configured DuckDB project, including its PyPI
  and npm package sources.

The supported formats are:

| Extension | Format | Intended use |
| --- | --- | --- |
| `.json` | JSON | Automation, MCP, and programmatic integrations |
| `.md` | Markdown | Documentation, pull requests, and terminal-friendly sharing |
| `.html` | HTML | Standalone browser reports |

## Regenerate the examples

Run these commands from the repository root. The commands use the same report
workflow as the CLI and dashboard export menu.

```bash
# Package reports
uv run secchi report duckdb \
  --format json \
  --output examples/reports/duckdb/package.json

uv run secchi report duckdb \
  --format md \
  --output examples/reports/duckdb/package.md

uv run secchi report duckdb \
  --format html \
  --output examples/reports/duckdb/package.html

# Project reports from the repository's DuckDB configuration
uv run secchi report --project duckdb --config secchi.toml \
  --format json \
  --output examples/reports/duckdb/project.json

uv run secchi report --project duckdb --config secchi.toml \
  --format md \
  --output examples/reports/duckdb/project.md

uv run secchi report --project duckdb --config secchi.toml \
  --format html \
  --output examples/reports/duckdb/project.html
```

The reports contain live registry data and therefore change over time. Treat
them as representative examples rather than immutable fixtures. Stable schema
and renderer behavior is covered by the automated tests under `tests/`.
