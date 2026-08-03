# Reports

Secchi can export package and project intelligence as JSON, Markdown, or HTML.

## Package reports

```bash
secchi report duckdb --format json
secchi report duckdb --format md --output duckdb-report.md
secchi report duckdb --format html --output duckdb-report.html
```

## Project reports

Use a configuration file and project name to combine all configured registry
sources:

```bash
secchi report \
  --config secchi.toml \
  --project duckdb \
  --format html \
  --output duckdb-project.html
```

If no output path is given, the report is written to the current directory.
Use `--output -` to write to standard output.

## Choosing a format

| Format | Best for |
| --- | --- |
| JSON | Automation, APIs, and agent workflows |
| Markdown | Pull requests, documentation, and readable sharing |
| HTML | Standalone reports for teams and stakeholders |

JSON output includes a schema name and schema version. Cache and report
boundaries are validated so consumers can reject incompatible data deliberately.

Generated reports identify Secchi as the reporting tool and link back to the
Secchi repository.

Example exports are available in
[`examples/reports`](https://github.com/kannandreams/secchi/tree/main/examples/reports).
