# Dashboard metrics

The Secchi dashboard combines registry metadata, download activity, release
history, GitHub signals, dependency information, and security advisories into
one package view. The dashboard is a decision aid: it helps you understand a
package's current condition, but it is not a certification or a substitute for
reviewing the project directly.

## Summary cards

The summary row gives a quick read on the selected package:

| Card | Meaning |
| --- | --- |
| Adoption | Download activity for the selected period and its change versus the previous comparable period. |
| Health | Composite score from 0–100, with a grade from A to F. |
| Dependents | Number of projects known to depend on the package, plus the recent change when available. |
| Latest version | Newest version reported by the package registry and its estimated or measured adoption share. |

The project header also shows the package description, ecosystem, latest
version, repository, documentation link, license, and artifact size when those
signals are available.

## Overview panels

### Adoption trend

Shows download activity over the selected range: 30 days, 90 days, or one
year. The percentage compares the current period with the preceding period of
the same length. For example, a 30-day view compares the latest 30 daily points
with the 30 points before them.

The data source depends on the registry. Some registries provide measured
download counts; others provide an estimated trend or may not provide this
signal at all. A package can therefore have a useful health score while showing
an unavailable adoption chart.

### Health score

Shows the composite score and the contribution from each health category. The
score is calculated from the six categories below and totals 100 points.

### Ecosystem distribution

Shows the package's download share by supported ecosystem. For a package
available from one registry, the distribution is naturally 100% for that
registry. When multiple registry variants are combined, the dashboard sums the
available 30-day activity and shows each ecosystem's share.

### Reverse dependencies

Shows how many known projects depend on the package and, when history exists,
whether that number is growing or contracting. Missing registry support is
shown as unavailable rather than treated as zero.

### Health timeline

Shows the health score over monthly snapshots. A new local snapshot is recorded
when Secchi fetches package intelligence. The timeline is therefore local
history, not a universal historical record of the package.

### Version adoption

Shows how activity is distributed across recent versions. For crates.io,
Secchi uses its available per-version download data. For other registries, the
distribution is estimated by assigning download-trend periods to release
windows. The estimate should be treated as directional.

## Health score

The health score is a weighted composite with a maximum of 100 points:

| Category | Maximum |
| --- | ---: |
| Maintenance | 20 |
| Community | 15 |
| Documentation | 15 |
| Releases | 15 |
| Security | 20 |
| Testing | 15 |
| **Total** | **100** |

Missing data is generally scored as zero for that signal. This means a low
score can sometimes indicate incomplete metadata rather than a definitively
unhealthy project. GitHub-dependent categories are especially affected when a
repository cannot be resolved.

### Maintenance — 20 points

Secchi considers the more recent of the latest package release and the latest
GitHub push:

| Most recent activity | Points |
| --- | ---: |
| Within 30 days | 20 |
| Within 90 days | 16 |
| Within 180 days | 12 |
| Within 1 year | 6 |
| Older than 1 year | 2 |
| No activity date | 0 |

To improve this category, maintain a healthy release cadence and keep the
source repository active. Activity should represent meaningful maintenance,
not empty commits or unnecessary releases.

### Community — 15 points

Community is calculated from GitHub data. Secchi first calculates up to 20 raw
points, then scales that result to a maximum of 15 points.

The raw score contains:

- Stars: 0–10 points, increasing at 1, 100, 1,000, 10,000, and 100,000 stars.
- Forks: 0–5 points, increasing at 10, 100, 1,000, and 10,000 forks.
- Issue response over the last 90 days: 0–5 points.

Issue-response points work as follows:

- No issues opened: 3 neutral points.
- At least as many issues closed as opened: 5 points.
- At least half of opened issues closed: 3 points.
- Some issues closed: 1 point.
- No issues closed: 0 points.

The practical improvement is not simply collecting stars. Maintain a visible
repository, respond to issues, close completed work, and make contribution
paths clear.

### Documentation — 15 points

Secchi calculates up to 20 raw points and scales the result to 15:

- Homepage: 5 raw points.
- Documentation URL: 8 raw points.
- Detected README: 7 raw points.

Provide a working project homepage, a dedicated documentation link, and a
clear README with installation, usage, configuration, and troubleshooting
guidance.

### Releases — 15 points

This category counts package versions released within the last 365 days. The
result is scaled to 15 points:

| Releases in the last year | Points |
| --- | ---: |
| 0 | 0 |
| 1–2 | 4 |
| 3–5 | 9 |
| 6–11 | 12 |
| 12 or more | 15 |

The score rewards ongoing activity, but it does not evaluate whether releases
are useful or stable. Prefer predictable, meaningful releases with clear
release notes.

### Security — 20 points

The current score starts at 20 points and applies these deductions:

- Any of the five newest versions is yanked: −8.
- The newest version is yanked: an additional −6.
- No repository URL and no resolved GitHub repository: −4.

The score cannot fall below zero.

Secchi also displays OSV advisories in the separate Security tab. At present,
those advisories are informational and do not directly change the health
score. A package with no displayed OSV advisory is not automatically safe, and
a package with an advisory should be reviewed using the advisory's affected
and fixed-version details.

To improve this category, avoid yanking published versions when possible,
provide accurate repository metadata, respond to vulnerabilities, and publish
fixed releases. The fixed-release portion is currently visible through the
Security tab but is not yet a scoring input.

### Testing — 15 points

Testing is currently a narrow CI proxy:

- Resolved GitHub repository with at least one GitHub Actions workflow: 15
  points.
- Otherwise: 0 points.

This does not measure test coverage, test quality, branch protection, or
whether every workflow is passing. Add a real CI workflow that installs the
project, runs its test suite, and checks supported Python or runtime versions.

### Grades

| Total | Grade |
| ---: | :---: |
| 90–100 | A |
| 75–89 | B |
| 60–74 | C |
| 40–59 | D |
| 0–39 | F |

## Improving a package's score

For the largest practical improvement, use this order:

1. Make the package's repository, homepage, documentation, and README
   discoverable from registry metadata.
2. Add reliable CI and make the workflow run the real test suite.
3. Keep maintenance and releases regular and meaningful.
4. Respond to community issues and document contribution guidance.
5. Avoid yanked versions and publish fixes for security advisories.

Use the score to identify missing or weak signals, then inspect the underlying
repository and release history before making a dependency decision.
