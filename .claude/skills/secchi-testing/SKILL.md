---
name: secchi-testing
description: Testing standards for the secchi codebase. Use whenever writing or changing tests, adding a feature or fix that needs test coverage, or deciding where to mock (transport vs adapter vs workflow boundary). Every behaviour change must ship with tests that follow the house style described here.
---

# Secchi Testing Standards

Every PR that changes behaviour must add or update tests. Tests live flat in
`tests/`, one module per source module, named `test_<subject>.py` mirroring
`src/secchi/<module>.py`. Tests must run fully offline — no live registry
access, ever.

## Run the suite

```bash
uv run pytest                 # full suite (fast, offline)
uv run pytest tests/test_adapters.py -k crates   # focused run
```

## House style — follow it exactly

The suite is deliberately minimal: **plain test functions + stdlib + pytest
built-ins only**. Do not introduce new test infrastructure.

- **No `conftest.py`, no fixtures, no `pytest.mark`, no `parametrize`.**
  Multiple cases go into one test as consecutive asserts.
- **No `unittest.mock` / `Mock`.** Use small local fake classes defined inside
  the test function (or module-level with a leading underscore when reused).
  Fakes may subclass each other to vary one method
  (`class BuggyAdapter(PartialAdapter)` in `tests/test_intelligence.py`).
- **No `pytest-asyncio`.** Async code is tested with a sync `def test_...`
  wrapping an inner `async def exercise() -> None:` finished by
  `asyncio.run(exercise())`.
- **Every test function is annotated `-> None`** and named as a long,
  behaviour-describing sentence:
  `test_optional_enrichment_failure_keeps_package_usable`,
  `test_same_day_cache_is_a_hit_and_previous_day_cache_is_a_miss`.
- Call counting uses a plain dict (`calls = {"adapter": 0}` …
  `assert calls == {"adapter": 1}`), not `Mock.call_count`.
- Prefer comprehension assertions over element-by-element:
  `assert [v.version for v in versions] == ["2.0.0", "1.0.0"]`.

## Mock at the right boundary

Pick the boundary that matches the layer under test:

1. **Adapters (`api/`)** → `httpx.MockTransport` with a handler routing on
   `request.url.path`, falling through to `httpx.Response(404, request=request)`.
   Reuse the local helpers pattern from `tests/test_adapters.py`:

   ```python
   def client_for(handler) -> httpx.AsyncClient:
       return httpx.AsyncClient(transport=httpx.MockTransport(handler))

   def json_response(request, payload) -> httpx.Response:
       return httpx.Response(200, json=payload, request=request)
   ```

   Handlers double as assertion sites: assert outgoing headers (User-Agent)
   or capture the request body into a closure dict for later assertion.

2. **Services (`services/`)** → monkeypatch the adapter factory
   (`monkeypatch.setattr(..., "create_adapter", ...)`) to return a local fake
   adapter class, or pass a fake via the `service=` / `client=` constructor
   kwargs — production code takes dependency-injection kwargs on purpose;
   prefer injection over patching when a kwarg exists.

3. **MCP tools (`mcp_server.py`)** → call the tool functions directly (no
   stdio client). Monkeypatch the workflow object the tool delegates to
   (`monkeypatch.setattr(mcp_server.inspect_workflow, "run", fake_inspect)`).
   `types.SimpleNamespace` may stand in for result objects. Fakes assert on
   their own arguments. Validation errors use
   `pytest.raises(ValueError, match="...")`.

4. **Textual UI (`ui/`)** → three sanctioned approaches, no snapshot testing:
   - a throwaway `class Harness(App[None])` composing the widget, then
     `async with harness.run_test(size=(120, 40)):` and `query_one` asserts;
   - call `.render()` / `.compose_body()` directly and assert substrings;
   - instantiate the app without running it and assert on state/`BINDINGS`.

## Determinism

- **Filesystem**: always `tmp_path`. Prefer injecting the root
  (`root=tmp_path`); fall back to
  `monkeypatch.setattr(cache, "cache_root", lambda: tmp_path)`.
- **Time**: inject clocks as zero-arg lambdas (`now=lambda: NOW`,
  `clock=lambda: datetime(2026, 8, 9, tzinfo=timezone.utc)`). Fixed times are
  module constants (`NOW = datetime(..., tzinfo=timezone.utc)` — always
  timezone-aware). Relative dates via a `_days_ago()` helper.
- **Sleeps**: patch out — `monkeypatch.setattr("secchi.http.asyncio.sleep", no_sleep)`.
- **Config**: inline TOML heredoc written to `tmp_path / "secchi.toml"`:

  ```python
  config = tmp_path / "secchi.toml"
  config.write_text(
      """[projects.demo]
  title = "Demo"
  packages = [{ name = "duckdb", registry = "pypi" }]
  """
  )
  ```

## Required test pairs for error handling

Secchi's core contract is graceful degradation without hiding bugs. Any code
path that catches errors needs **both** tests:

1. *Expected failure degrades gracefully* — assert on the structured warnings
   list, not logs:
   ```python
   assert [(w.source, w.message) for w in result.warnings] == [
       ("versions", "registry versions endpoint unavailable")
   ]
   ```
2. *Unexpected exception is NOT swallowed* — a fake raising `RuntimeError`
   must propagate (`test_unexpected_enrichment_error_is_not_hidden`).

## Renderer / report assertions

Assert on substrings of rendered output
(`assert "Health Score      92 / 100" in output`), and for JSON additionally
parse it and assert structure — including the `schema` and `schema_version`
envelope fields. Cache/report schema changes need `ValidationError` contract
tests (see `tests/test_cache_schema.py`).

## Checklist before claiming a change is tested

- [ ] New behaviour has a test in the mirrored `tests/test_<module>.py`.
- [ ] Error-handling changes have the expected/unexpected pair.
- [ ] No network, no real home directory, no wall-clock dependence.
- [ ] `uv run pytest` passes; `uv run ruff check .` and
      `uv run ruff format --check src tests` pass.
- [ ] No new test dependencies or fixtures introduced.
