# CLAUDE.md

Secchi is a package-intelligence CLI/TUI/MCP server: one cached pipeline
(`services/intelligence.py`) feeds every surface (CLI, Textual dashboard,
JSON/MD/HTML reports, MCP tools) across PyPI, npm, crates.io, Homebrew,
Go modules, and CRAN.

## Before you code

Load the matching skill — they are the project's design contract:

- **secchi-architecture** — layering, dataclass-vs-Pydantic boundary,
  warnings-vs-failures model, cache/schema versioning, where changes go.
  Load before touching anything in `src/secchi/`.
- **add-registry-adapter** — the ~20-site checklist for a new ecosystem.
- **secchi-testing** — house test style; every behaviour change ships tests.
- **self-review** — run before every push / PR; replays CI gates and reviews
  the diff.

## Commands

```bash
uv sync                                  # setup (uv-managed, Python >=3.10)
uv run pytest                            # offline test suite
uv run ruff check .                      # lint (CI-identical)
uv run ruff format --check src tests     # formatting (CI-identical)
uv build                                 # package build gate
uv run textual run --dev src/secchi/dev.py -- -p duckdb   # live-reload TUI
uvx pre-commit run --all-files           # hooks incl. branch-name check
```

## Non-negotiables

- Layering is downward-only: surfaces → workflows → services → adapters →
  http/cache. Never fetch from a surface; never duplicate the pipeline.
- `pydantic` only in `schemas.py`; internal domain stays dataclasses.
  Serialized shapes are versioned (`schema.py`) and must keep reading old data.
- Optional-signal failures become `SignalWarning`s (honest-empty defaults),
  fatal fetch errors become `FetchError`; unexpected exceptions must propagate
  — no bare `except`/`pass`.
- Tests are offline and deterministic: `httpx.MockTransport`, `tmp_path`,
  injected clocks. No new test frameworks, fixtures, or `unittest.mock`.
- Branch names: `<type>/<slug>` (feat|fix|docs|style|refactor|perf|test|build|
  ci|chore|revert), lowercase, hyphenated — enforced by pre-commit.
- One problem per PR; behaviour change ⇒ test change; user-facing change ⇒
  README/docs update.
