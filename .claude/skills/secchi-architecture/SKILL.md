---
name: secchi-architecture
description: Secchi's architecture rules and design patterns. Load before writing or changing any code in src/secchi/ — adding features, fixing bugs, or refactoring. Defines the layering, the dataclass-vs-Pydantic boundary, the warnings-vs-failures model, cache/schema versioning, and where each kind of change goes so contributions don't deviate from the design.
---

# Secchi Architecture Rules

Secchi is a package-intelligence CLI/TUI/MCP server. One pipeline serves every
surface. Changes that respect these rules merge easily; changes that bypass a
layer or duplicate the pipeline will be rejected.

## Layering (strict, downward-only)

```
cli.py  /  mcp_server.py  /  ui/app.py            ← surfaces
        ↓
workflows/<cmd>.py   (async def run(...))          ← use-case orchestration
        ↓
services/   intelligence · resolver · search · comparison
        ↓
api/base.create_adapter → api/<registry>.py        ← normalize to models.py
        ↓
http.py (SecchiAsyncClient) · cache.py · history.py · security.py
```

Pure leaf modules (no upward imports, no I/O): `models.py`, `derived.py`,
`aggregate.py`, `policy.py`, `errors.py`, `schema.py`, `schemas.py`,
`utils.py`, `diagnostics.py`. Renderers (`renderers/`) and widgets (`ui/`)
consume service results; they never fetch.

Hard rules:
- A surface never calls an adapter or `httpx` directly; it goes through a
  workflow or service. New behaviour must be reachable from **every** relevant
  surface (CLI, dashboard, report, MCP) by living in the shared
  workflow/service — never implemented twice.
- `PackageIntelligenceService.fetch_package` (`services/intelligence.py`) is
  THE pipeline: cache check → adapter fetch → optional enrichments → OSV →
  history deltas → `derive.compute_all` → cache write. Do not create parallel
  fetch paths.
- `derived.py` stays I/O-free so scoring is unit-testable without HTTP mocks.
- Adapters never construct HTTP clients; they receive a shared client and use
  `async with self._client_scope() as client:` for every request.

## Dataclasses inside, Pydantic at the edges

- Internal domain = plain `@dataclass` (`models.py` and per-service result
  types). `@dataclass(frozen=True)` for value objects/results. Collections use
  `field(default_factory=...)`; copy-with-changes via `dataclasses.replace`.
- **`pydantic` is imported in exactly one module: `schemas.py`.** Never import
  it anywhere else in `src/secchi/`.
- Serialized boundaries (cache files, JSON reports, MCP payloads, comparison
  export) are validated by the models in `schemas.py`, versioned by the
  constants in `schema.py` (constants live in `schema.py`, shapes in
  `schemas.py`).
- Contract rules: `extra="forbid"` for outbound contracts; `extra="ignore"`
  only for data secchi itself wrote and must keep reading (`CacheEnvelope`).
  The JSON `schema` key is an alias (`schema_name = Field(..., alias="schema")`),
  so always dump with `by_alias=True` (and `mode="json"` for dicts). Every
  model validates `schema_version` and keeps reading legacy version `0`.
- Changing a serialized shape ⇒ bump the constant in `schema.py`, update the
  validator, keep old data readable, and add a `ValidationError` contract test.

## Warnings vs failures — the central error model

| Kind | Type | Effect |
|---|---|---|
| Fatal (package itself unfetchable) | `FetchError` on `IntelligenceResult.error` | Workflow converts via `workflows/common.require_package` → `SecchiError`; CLI exits 2 |
| Non-fatal (one optional signal failed) | frozen `SignalWarning(source, message)` on `result.warnings` | Result stays usable; warning shown/rendered everywhere |

- Optional enrichments go through the single funnel `_optional_signal`
  (`services/intelligence.py`): pass a human-readable source label, the
  awaitable, and a **typed honest-empty default** (`[]`, `{}`, `""`,
  `DownloadCounts()`, `None`) — never return `None` for a list field.
- The expected-exception tuple is `(httpx.HTTPError, OSError, ValueError,
  KeyError, TypeError)`. **Unexpected exceptions must propagate** — never
  `except Exception: pass`.
- Search: one failing registry = WARN + drop its results; all failing =
  FAILURE.
- User-facing events go to `DiagnosticLog` (threaded down as an explicit
  `diagnostics=` kwarg, never a global). `logging` is developer-debug only
  (`logger.debug(..., exc_info=True)`).

## Errors and exit codes

- `errors.py` hierarchy: `SecchiError` ← `PackageNotFoundError`,
  `RegistryUnavailableError`, `ConfigError`, `ReportError` (+ `WorkflowError`).
- Library/service layers never call `sys.exit`; they raise `SecchiError`
  subclasses or return `FetchError`/`SignalWarning`.
- CLI catches `(SecchiError, ValueError)` → `parser.error(str(exc))` (exit 2).
  The only explicit exit code is the `check` policy gate: `SystemExit(1)`.
- MCP tools never exit: validate inputs with `raise ValueError("...")`, put
  failures in the payload.

## Caching rules

- Roots: `$XDG_CACHE_HOME/secchi` else `~/.cache/secchi`; keys sanitized
  (`/`→`_`, `:`→`__`). Expiry is same-calendar-day, not TTL.
- Package cache is a Pydantic `CacheEnvelope`; security cache is separate and
  keyed on package version. Cache writes swallow `OSError` — caching is
  best-effort and never fails a run.
- **Adding a field to `PackageInfo` requires three edits**: `models.py`, the
  hand-written decoder `cache._decode_package_info` (or it silently drops on
  round-trip), and `export._serialize_package_info` (or it never reaches
  reports/MCP).

## Adding a CLI command

argparse (not click). Steps: subparser in `build_parser()` (`cli.py`) with
prefixed `dest=` names to avoid collisions with top-level flags; append the
parser to the shared `--verbose`/`--log-file` loop (uses
`default=argparse.SUPPRESS`); import + dispatch block in `main()` calling
`asyncio.run(<workflow>.run(...))` inside `try/except (SecchiError,
ValueError) → parser.error`; new `src/secchi/workflows/<name>.py` exposing
`async def run(...)` that is keyword-only after the positional, accepts
`service: PackageIntelligenceService | None = None` for injection, and returns
a **frozen dataclass**, never a dict. Reuse `workflows/common.fetch_package`
and `require_package`.

## Conventions

- `from __future__ import annotations`; PEP 604 unions (`X | None`); builtin
  generics; full annotations including `-> None`.
- `snake_case` functions, `PascalCase` classes, `_`-prefixed module-private
  helpers; adapters `<Registry>Adapter`; workflows export `run`; services are
  `<Noun>Service`; endpoint constants `UPPER_SNAKE` at module top.
- One-line module docstring on every file. Comments justify non-obvious
  tradeoffs only.
- Timezone-aware datetimes only (`tzinfo=timezone.utc`); normalize with the
  `derived.py` `_aware` helpers when consuming external data.

## Where things go (quick reference)

| Adding… | Touch |
|---|---|
| A registry | Use the **add-registry-adapter** skill — ~20 sites must change |
| A CLI command | `cli.py` (subparser + shared-flag loop + dispatch), new `workflows/<x>.py` |
| An MCP tool | `@server.tool` in `mcp_server.py` reusing an existing workflow; update `docs/mcp.md`, `README.md`, `skills/secchi-package-intelligence/SKILL.md` |
| A `PackageInfo` field | `models.py` + `cache._decode_package_info` + `export._serialize_package_info` (+ `derived.py`/widgets) |
| A health signal | `derived.py` `_score_*` + `compute_health_score`; document in `docs/metrics.md` |
| A policy check | `policy.evaluate_default_policy` + CLI flag + MCP param |
| A report format | `renderers/reports.py` dispatch + `cli.py` `--format` choices |

Known duplication (do not extend it): `aggregate.py` and
`workspace/aggregate.py` are near-identical forks — registry-related changes
must currently be made in **both**; prefer unifying over adding a third copy.

Always pair code changes with tests per the **secchi-testing** skill, and run
the **self-review** skill before pushing.
