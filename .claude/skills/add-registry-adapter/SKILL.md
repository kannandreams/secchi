---
name: add-registry-adapter
description: Step-by-step checklist for adding a new package registry/ecosystem to secchi (a new api/ adapter). Use whenever adding support for a new registry, ecosystem, or package index. Roughly 20 places in the codebase must change; missing one causes KeyError crashes or silently absent features.
---

# Adding a Registry Adapter to Secchi

The `Registry` enum in `models.py` is the single source of truth — there is no
`constants.py`. Several lookup dicts index with `[registry]` (not `.get`), so a
missed site fails fast with `KeyError`. Work through every step below.

## 1. The adapter module — `src/secchi/api/<name>.py`

- One-line module docstring naming the upstream API; endpoint base URLs as
  `UPPER_SNAKE` module constants.
- Full-signal registry → `class XAdapter(AdapterBase, RegistryAdapter)`.
  Metadata-only registry (no download time-series API) →
  `class XAdapter(SparseAdapter)` — it inherits honest-empty implementations,
  so you only implement `registry`, `fetch_package`, and optionally
  `fetch_versions`/`search` (see `api/homebrew.py` for the minimal form).
- `default_headers: ClassVar` if the API requires a User-Agent/Accept
  (crates.io does — see `api/crates.py`).
- `@property registry -> Registry.X`, and set `registry=Registry.X` on every
  `PackageInfo`/`SearchResult` you return.
- Full-protocol methods: `fetch_package`, `fetch_versions`,
  `fetch_dependencies`, `fetch_download_trend`, `fetch_download_counts`,
  `fetch_release_notes`; optional: `fetch_reverse_dependencies`,
  `fetch_reverse_dependency_count`, `fetch_version_download_breakdown`,
  `search` (set `exact` via casefold comparison).
- Every request inside `async with self._client_scope() as client:` — never
  construct your own httpx client. Call `resp.raise_for_status()` and let the
  service layer's `_optional_signal` degrade failures to warnings. Return
  honest empties (`[]`, `""`, `{}`), never `None` for list fields.
- Parse defensively: `.get(key, default)` everywhere,
  `contextlib.suppress` for date parsing, timezone-aware datetimes only.
  When sorting by optional dates, use an **aware** sentinel
  (`datetime.min.replace(tzinfo=timezone.utc)`) — a naive `datetime.min`
  raises `TypeError` against aware dates.
- Mind upstream URL encoding rules (e.g. the Go module proxy requires
  `Upper` → `!upper` case-encoding). Verify against a real API response
  captured into the test payloads.

## 2. Registration sites (fail-fast if missed)

| Site | File | Note |
|---|---|---|
| Enum member `X = "x"` | `src/secchi/models.py` (`Registry`) | Enum **declaration order** is also the `compare` tie-break preference — insert deliberately |
| `display_name` dict | `models.py` | `KeyError` if missed |
| `icon` dict | `models.py` | `KeyError` if missed |
| `language` dict | `models.py` | `KeyError` if missed |
| `install_command` dict | `models.py` | `KeyError` if missed |
| Adapter factory | `src/secchi/api/base.py` `create_adapter` | function-local import + dict entry; `KeyError` if missed |

## 3. Signal & UI sites

| Site | File | Note |
|---|---|---|
| OSV ecosystem mapping | `src/secchi/security.py` | Omit only if OSV has no ecosystem name for it (advisories then skipped, like Homebrew today) — document that in README |
| Adoption-trend caption | `src/secchi/ui/widgets/overview.py` `_downloads_source` | Indexed dict — add an entry |
| Ecosystem icon | `src/secchi/ui/widgets/detail.py` `ECOSYSTEM_ICONS` | `.get`-ed, optional but recommended |
| Primary-source preference | `src/secchi/aggregate.py` `pick_primary_info` **and** `src/secchi/workspace/aggregate.py` | Two near-duplicate files — change **both** |
| Reverse-dep source | both `aggregate.py` files | only if the registry exposes dependents |
| Per-version adoption | `src/secchi/derived.py` `compute_release_adoption` | only if real per-version downloads exist |
| `secchi init` prompt text | `src/secchi/cli.py` (hardcoded registry list string) | update |

Automatic (no change, but be aware): CLI `--registry` choices, config
validation, resolver and cache decode all derive from the enum; the new
registry is also queried on **every** cross-registry search — consider
rate-limit implications.

## 4. Tests (required — see secchi-testing skill)

In `tests/test_adapters.py`, using `httpx.MockTransport` and the local
`client_for`/`json_response` helpers:
- parse test: realistic JSON payload → `PackageInfo` fields, versions order,
  dependencies;
- search test: exact-match flag and result shape;
- header assertion inside the handler if `default_headers` is set;
- sparse adapters: assert the empty-signal behaviours
  (see `test_sparse_adapters_...`).

## 5. Docs (hand-maintained ecosystem lists)

- `README.md`: ecosystem table, capabilities row, MCP tool descriptions,
  `--registry` examples, OSV coverage note if applicable
- `docs/index.md`, `docs/workspace.md`, `docs/metrics.md`
- `skills/secchi-package-intelligence/SKILL.md` ecosystem list
- `CHANGELOG.md` entry

## 6. Verify

Run the **self-review** skill. Additionally smoke-test each surface with a
real package name: `secchi show x:<pkg>`, `secchi search <pkg>`,
`secchi dashboard x:<pkg>` (check the Adoption Trend panel renders),
`secchi report x:<pkg> --format json`, and `compare` across registries.
