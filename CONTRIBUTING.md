# Contributing to Secchi

Thanks for your interest in contributing to Secchi.

Secchi is an open source project, and community feedback and contributions are very welcome. The project is still in its early stages, with several parts of the architecture, interfaces, and roadmap actively evolving.

At this stage, the goal is to keep development focused while making it easy for the community to participate.

## Ways to Contribute

There are many ways to contribute beyond writing code.

You can help by:

* Reporting bugs
* Suggesting features or improvements
* Sharing feedback and use cases
* Improving documentation
* Reporting incorrect or missing package data
* Suggesting package ecosystems or data sources to support
* Testing Secchi across different environments
* Improving examples and guides

Issues and discussions around real-world use cases are particularly useful while the project is evolving.

## Bug Reports

If you find a bug, please open an issue with enough information to reproduce the problem.

Where possible, include:

* Secchi version
* Operating system
* Python version
* Package or registry involved
* Command you ran
* Expected behaviour
* Actual behaviour
* Relevant logs or screenshots

Before opening a new issue, please check whether a similar issue already exists.

## Feature Requests

Feature requests are welcome.

Use the [feature request template](https://github.com/kannandreams/secchi/issues/new?template=feature_request.md)
when opening an issue. Keep the request simple: describe the problem or use
case first, then explain the behavior you would like to see.

When proposing a feature, it is helpful to explain the problem or use case rather than only describing a particular implementation.

This gives us room to explore the best way to support the capability while keeping Secchi's architecture consistent.

## Code Contributions

Code contributions are welcome, but Secchi is currently in an early stage of development.

The project has an active roadmap, and some of its internal architecture, APIs, data models, and interfaces may change as the project evolves.

For small fixes, documentation improvements, tests, and clearly scoped changes, feel free to open a pull request.

### Feature Contributions

If you're planning to contribute a new feature, please open an issue first so we can discuss the idea and make sure it aligns with the current direction of the project before significant development effort is invested.

You are still welcome to submit a feature pull request without prior discussion. However, during this early stage, we cannot guarantee that every pull request will be reviewed or merged.

This approach helps keep development focused while the project's foundations and direction are still evolving.

## Working with Coding Agents

Secchi ships agent-readable engineering standards in `.claude/skills/` (with
`CLAUDE.md` as the entry point). If you build your contribution with a coding
agent such as Claude Code, the agent picks these up automatically:

* `secchi-architecture` — layering rules, design patterns, and where each kind
  of change belongs.
* `add-registry-adapter` — the full checklist for adding a new ecosystem.
* `secchi-testing` — the house testing style; behaviour changes must ship tests.
* `self-review` — a pre-push "peer review" that replays every CI and
  pre-commit gate locally and reviews your diff against the standards above.

These documents are also useful reading for human contributors — they describe
the same conventions reviewers will hold your pull request to. Before pushing,
run the self-review (or at minimum the same gates it runs):

```bash
uvx pre-commit run --all-files
uv run ruff check .
uv run ruff format --check src tests
uv run pytest
uv build
```

## Pull Requests

When submitting a pull request:

* Keep the change focused on a single problem or feature.
* Explain what the change does and why it is needed.
* Reference the related issue where applicable.
* Add or update tests when behaviour changes.
* Update documentation when introducing user-facing changes.
* Avoid unrelated refactoring within the same pull request.

Smaller, focused pull requests are generally easier to review.

## Questions and Ideas

If you're unsure whether something should be an issue, feature request, or pull request, start with an issue.

Ideas, feedback, bug reports, and real-world examples of how you're using Secchi are all valuable contributions.

Thanks for helping improve Secchi.
