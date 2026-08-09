# Contributing

Thanks for your interest in contributing to Secchi.

The project is still evolving, so small fixes, documentation improvements,
tests, adapter improvements, and clearly scoped changes are especially useful.
For a new feature, open an issue first when possible so the direction can be
discussed before significant implementation work begins. Use the repository's
[feature request template](https://github.com/kannandreams/secchi/issues/new?template=feature_request.md)
to describe the problem, use case, and proposed behavior.

## Pull request expectations

- Keep the change focused on one problem or feature.
- Explain what changed and why.
- Add or update tests when behavior changes.
- Update documentation for user-facing changes.
- Avoid unrelated refactoring in the same pull request.

Run the local checks before opening a pull request:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check src tests
uv build
```

See the repository [contribution guide](https://github.com/kannandreams/secchi/blob/main/CONTRIBUTING.md)
for the complete contribution guidance.
