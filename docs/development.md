# Development

## Set up the project

```bash
git clone https://github.com/kannandreams/secchi.git
cd secchi
uv sync
```

## Run the dashboard from source

```bash
uv run textual run --dev src/secchi/dev.py -- -p duckdb
```

## Run checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check src tests
uv build
```

The test suite uses mocked HTTP transports for registry adapters and local
temporary paths for cache/history behavior. Tests do not need live registry
access.

## Build the documentation site

Install the documentation dependency through the development group:

```bash
uv sync
```

Preview the site locally:

```bash
uv run mkdocs serve
```

Build a static site into `site/`:

```bash
uv run mkdocs build --strict
```

The documentation configuration lives in `mkdocs.yml`, and source pages live
under `docs/`.

The site shares the [secchi.dev](https://secchi.dev) design system: its
tokens, fonts, and rules are ported into `docs/stylesheets/extra.css` (design
tokens at the top), and the header and mobile drawer come from the Material
template overrides in `overrides/partials/`. There are dark (carbon-blue
page, black panels) and light schemes behind Material's palette toggle; the
header bar stays black in both. Fonts are self-hosted under
`docs/fonts/`; nothing is fetched from third parties at runtime. When the
landing page's `css/site.css` changes, mirror the change here.

## Architecture direction

The CLI, dashboard, reports, MCP server, and future SDK surfaces should reuse
the same application workflows and intelligence services. Registry adapters
normalize external data, services enrich and score it, and renderers present
the result for a specific surface.

The project uses dataclasses for internal domain models and explicit Pydantic
schemas at cache and external JSON boundaries.
