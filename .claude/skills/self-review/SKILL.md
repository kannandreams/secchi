---
name: self-review
description: Pre-push / pre-PR self review for secchi. Run this before pushing a branch or opening a pull request. It replays every CI and pre-commit gate locally, then performs a structured peer-style review of the branch diff against secchi's architecture and testing standards, and produces a PASS/FAIL report. Use when the user says "review my changes", "am I ready to push", "raise a PR", or after finishing any feature/fix.
---

# Secchi Self Review (pre-PR)

Act as the peer reviewer this PR will eventually get. Two phases: first the
**mechanical gates** (exactly what CI runs), then a **review pass** over the
diff. Do not push or open a PR while any gate fails or any blocking finding
is open.

## Phase 1 — Mechanical gates (replay CI locally)

Run each gate and record PASS/FAIL with the failing output:

```bash
# 0. Branch name must match <type>/<slug> (feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)
scripts/check-branch-name.sh

# 1. Hooks (trailing whitespace, EOF, toml/yaml validity, ruff, branch name)
uvx pre-commit run --all-files

# 2. Lint + formatting — same commands as .github/workflows/ci.yml
uv run ruff check .
uv run ruff format --check src tests

# 3. Full offline test suite
uv run pytest

# 4. Package build must still succeed (CI runs this on every push)
uv build
```

Notes:
- CI runs the suite on Python 3.10–3.13; if the change uses newer syntax
  (e.g. `match`, `tomllib` alternatives, 3.11+ typing), flag it — local pass
  on one version is not enough. `requires-python = ">=3.10"`.
- If a gate fails, fix it and re-run **all** gates, not just the failed one.
- Never "fix" a failure by loosening a test, deleting an assertion, or adding
  a lint suppression — that is a blocking finding in itself.

## Phase 2 — Review pass over the diff

Review the actual change set:

```bash
git fetch origin main
git diff --stat origin/main...HEAD
git diff origin/main...HEAD
```

Read the full diff, then check each item and collect findings:

### Scope and shape
- [ ] One problem/feature per PR; no unrelated refactoring mixed in
      (CONTRIBUTING.md requirement).
- [ ] Commits and the intended PR description explain **what and why**, and
      reference the related issue when one exists.
- [ ] No stray files: build artifacts, coverage output, `.DS_Store`, editor
      config, debugging leftovers, commented-out code.

### Architecture conformance (see the secchi-architecture skill)
- [ ] Layering respected: `cli/workflows → services → api adapters → http/cache`;
      renderers and `ui/` consume services — no layer reaches around another.
- [ ] Internal domain models stay **dataclasses**; **Pydantic models only at
      serialized boundaries** (cache files, JSON reports, MCP responses).
- [ ] Any change to a serialized shape bumps/handles `schema` /
      `schema_version` and keeps reading legacy entries.
- [ ] Optional-signal failures become structured **warnings**, never a failed
      result and never a silent `except: pass`. Unexpected exceptions still
      propagate.
- [ ] New behaviour is reachable from every relevant surface (CLI, dashboard,
      report, MCP) via the shared workflow/service — not implemented twice.

### Tests (see the secchi-testing skill)
- [ ] Behaviour change ⇒ test change, in the mirrored `tests/test_<module>.py`.
- [ ] Tests follow house style (no new fixtures/plugins/mocks; offline;
      injected clocks and `tmp_path`).
- [ ] Error-handling changes include the expected-degrades /
      unexpected-propagates test pair.

### Docs and user surface
- [ ] User-facing changes update `README.md` and the relevant `docs/*.md`
      page; new CLI flags appear in `docs/commands.md` and `--help` text.
- [ ] `CHANGELOG.md` updated when the change is release-noteworthy.

## Phase 3 — Report

Output a report in this exact shape, then act on it:

```
## Self-review: <branch>

### Gates
| Gate | Result |
| --- | --- |
| branch-name | PASS |
| pre-commit  | PASS |
| ruff check / format | PASS |
| pytest | PASS (N passed) |
| uv build | PASS |

### Findings
1. [BLOCKING] <file:line> — <problem, and which standard it violates>
2. [ADVISORY] <file:line> — <suggestion>

### Verdict
READY TO PUSH  —  or  —  NOT READY: fix blocking findings above.
```

Severity rules: violations of gates, layering, boundary contracts, missing
tests for changed behaviour, or swallowed exceptions are **BLOCKING**.
Style preferences beyond ruff's verdict are **ADVISORY** — do not block on
taste.

Only after "READY TO PUSH": push the branch, and if asked to open the PR, use
a title in `<type>: <summary>` form matching the branch type, a body that
states the problem, the change, and the test evidence, and link the issue.
