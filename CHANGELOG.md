# Changelog

All notable changes to Secchi are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

Changes not yet included in a release will be listed here.

## [0.1.4] - 2026-08-10

### Added

* Added OSV advisory pagination with a bounded page limit for complete, safe security results.
* Added repository security checks and expanded regression coverage for adapters, cache, history, configuration, and security workflows.
* Added contributor guidance and reusable coding-agent skills for architecture, testing, registry adapters, and self-review.

### Improved

* Improved compatibility with Python 3.11 through 3.14 and tightened CI and linting checks.
* Improved error messages for malformed TOML project and package configuration.
* Improved npm and crates.io version sorting when release dates are missing.

### Fixed

* Fixed Go module proxy requests for module paths containing uppercase letters.
* Fixed cache-key collisions and path traversal risks for package and security cache files.
* Fixed crash-mid-write and concurrent-update risks when saving history snapshots.
* Fixed adapter and dashboard crashes caused by missing release dates and unsupported registry labels.

## [0.1.3] - 2026-08-09

### Added

* Added structured `SUCCESS`, `WARN`, and `FAILURE` diagnostics across registry and package-processing workflows.
* Added dashboard process logs with `l` and clipboard export with `c`.
* Added CLI diagnostics through `--verbose` and `--log-file`.
* Added a simple GitHub feature-request issue template for contributors.

### Improved

* Improved cross-registry package aggregation and ecosystem distribution reporting.
* Expanded documentation for health scores, package-manager sources, workspace configuration, and favorites.
* Clarified dashboard behavior for non-fatal signal warnings and registry-specific failures.

### Fixed

* Improved crates.io request identification with a repository-specific `User-Agent`.
* Fixed case-insensitive HTTP header merging so registry adapters send the intended request headers.
* Improved diagnostics for retries, fallback requests, cache usage, and registry response failures.

## [0.1.2] - 2026-08-03

* Added: Workspace aggregation and project-scoped lazy loading.
* Added: CLI workflows for inspection, reporting, comparison, and policy checks.
* Added: MCP server support and the Secchi package-intelligence agent skill.
* Added: Homebrew, Go Modules, and CRAN ecosystem adapters.
* Added: JSON, Markdown, and HTML report examples.
* Changed: Centralized HTTP client behavior, dependency injection, cache schemas, and error handling.
* Changed: Improved package enrichment resilience when optional registry signals are unavailable.
* Changed: Expanded adapter, cache/history, workspace, MCP, and workflow test coverage.
* Fixed: Prevented unexpected service and search errors from being silently hidden.

## [0.1.1] - 2026-07-31

### Fixed

* Fixed README image assets for the PyPI project page.

## [0.1.0] - 2026-07-31

### Added

* Initial public release of Secchi.
* Terminal package intelligence dashboard and CLI workflows.
* Package health, adoption, dependency, release, and ecosystem signals.
* Registry support for PyPI, npm, crates.io, Homebrew, Go modules, and CRAN.
* JSON, Markdown, and HTML reporting.
* MCP server integration for coding agents.

[Unreleased]: https://github.com/kannandreams/secchi/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/kannandreams/secchi/releases/tag/v0.1.4
[0.1.3]: https://github.com/kannandreams/secchi/releases/tag/v0.1.3
[0.1.2]: https://github.com/kannandreams/secchi/releases/tag/v0.1.2
[0.1.1]: https://github.com/kannandreams/secchi/releases/tag/v0.1.1
[0.1.0]: https://github.com/kannandreams/secchi/releases/tag/v0.1.0
