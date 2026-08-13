# GitHub Actions

Secchi is available as a GitHub Marketplace Action:

[Secchi Package Intelligence](https://github.com/marketplace/actions/secchi-package-intelligence)

Use it when you want package intelligence to run automatically in CI and appear
in the GitHub Actions job summary or, for pull request workflows, as a PR
comment.

## Run after merges to `main`

For a simple post-merge scan of the published Secchi package:

```yaml
name: secchi-scan

"on":
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  issues: write

jobs:
  secchi:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - uses: kannandreams/secchi-action@v1
        with:
          package: pypi:secchi
          comment: "false"
```

On `push` events there is no pull request to comment on, so `comment: "false"`
keeps the run focused on the Actions job summary.

## Comment on pull requests

For dependency-review style feedback on PRs:

```yaml
name: secchi-scan

"on":
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  issues: write

jobs:
  secchi:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - uses: kannandreams/secchi-action@v1
        with:
          package: pypi:duckdb
```

The action creates or updates a single Secchi PR comment. Re-runs update the
existing comment instead of creating a new one.

## Workspace project reports

If a repository has a `secchi.toml`, run a configured project report:

```yaml
- uses: kannandreams/secchi-action@v1
  with:
    config: secchi.toml
    project: duckdb
```

This calls `secchi report --format md` and publishes the Markdown report.

## Permissions and forked PRs

PR comments require:

```yaml
permissions:
  contents: read
  issues: write
```

GitHub may make `GITHUB_TOKEN` read-only for pull requests from forks depending
on repository settings. In that case, the Secchi report still appears in the
job summary, but the PR comment may be skipped or fail.
