---
name: secchi-package-intelligence
description: Use Secchi to inspect, compare, and assess package choices before an agent recommends, installs, upgrades, or replaces a dependency. Trigger when package health, adoption, maintenance, ecosystem, or dependency suitability is relevant.
---

# Secchi Package Intelligence

Use this skill when a coding agent needs evidence before making a dependency
choice. Secchi is advisory and read-only: it gathers package signals, ranks
options, and explains uncertainty. It must not install, remove, upgrade, or
modify a dependency without a separate explicit user instruction.

## Decision workflow

1. Identify the exact package and ecosystem. Prefer an explicit reference such
   as `pypi:duckdb`, `npm:duckdb`, `crates.io:duckdb`, `homebrew:duckdb`,
   `go:example.com/pkg`, or `cran:duckdb` when names could be ambiguous.
2. Inspect one package with `inspect_package` or compare alternatives with
   `compare_packages` through MCP when available.
3. Use `--refresh` or `refresh: true` only when current data is needed. Cached
   results are the default to reduce registry and GitHub API pressure.
4. Check the recommendation, confidence, evidence, strengths, and concerns.
5. Independently verify compatibility, license policy, security advisories,
   supported runtime, and project-specific constraints before proposing a
   change.

## Preferred interfaces

MCP is preferred because it returns structured data:

- `inspect_package(package, registry?, refresh?)` for one package or exact
  cross-ecosystem matches.
- `compare_packages(packages, registry?, refresh?)` for two or more choices.
- `check_package(package, registry?, min_health?, require_ci?, refresh?)` for
  explicit policy gates.
- `inspect_project(project, config?, refresh?)` for configured workspaces.

CLI fallback:

```bash
secchi show pypi:duckdb
secchi compare pypi:duckdb pypi:polars --format json
secchi check pypi:duckdb --min-health 70 --require-ci
```

Use `--format json` for agent parsing. Use terminal text for a human summary.

## Interpreting decisions

Secchi uses these labels:

- **Recommended**: strongest available option with adequate evidence.
- **Acceptable**: reasonable option, but not the leading choice or has some
  limitations.
- **Use with caution**: material concerns or incomplete evidence require human
  review.
- **Avoid**: failed retrieval, missing release information, a yanked latest
  release, or materially weak signals.

A recommendation is not a security approval. Unknown data lowers confidence;
it must not be treated as a positive signal. A comparison winner is the best
available candidate in the supplied set, not proof that it is suitable for the
repository being changed.

## What to include in an agent response

When using Secchi evidence, state:

- the exact package and registry selected;
- the recommendation and confidence;
- health score, adoption change, latest version, and community signal;
- the strongest supporting evidence and material concerns;
- any checks still required, especially compatibility and security review.

If Secchi cannot resolve or fetch a package, report that explicitly and ask for
an ecosystem or repository URL when ambiguity remains. Do not silently select a
different package with a similar name.

## Boundaries

Secchi does not decide whether a dependency is licensed for a specific product,
whether an advisory applies to the user's exact usage, or whether an API is
compatible. It also does not replace lockfile review, reproducibility checks,
maintainer verification, or security scanning. Treat its output as a compact
decision aid and preserve the raw evidence when making an important change.

For the scoring rubric and output shape, see
[references/decision-rubric.md](references/decision-rubric.md).
