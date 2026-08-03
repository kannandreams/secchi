# Changelog

All notable changes to Secchi are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

Changes not yet included in a release will be listed here.

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

[Unreleased]: https://github.com/kannandreams/secchi/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/kannandreams/secchi/releases/tag/v0.1.2
[0.1.1]: https://github.com/kannandreams/secchi/releases/tag/v0.1.1
[0.1.0]: https://github.com/kannandreams/secchi/releases/tag/v0.1.0
