# Secchi decision rubric

The comparison service ranks fetched `IntelligenceResult` values using a
weighted score. The score is a prioritisation aid, not a claim of objective
package quality.

## Inputs

| Signal | Weight | Meaning |
| --- | ---: | --- |
| Health score | 55% | Maintenance, community, documentation, releases, security, and testing proxies |
| Adoption momentum | 15% | Recent download/activity change when a baseline exists |
| Community | 10% | Repository resolution and GitHub star signal |
| Release recency | 10% | Age of the latest release |
| Data completeness | 10% | Whether the key signals were available to evaluate |

Unknown signals reduce confidence. They are not converted into a positive
result. A package with a high score but weak completeness should remain a
cautious recommendation.

## Hard caution rules

The service returns `Avoid` when retrieval fails, the latest version is
missing, the latest release is yanked, or the score is below 40. Otherwise the
label is selected from score and confidence:

- `Recommended`: score at least 80 and confidence at least 65%.
- `Acceptable`: score at least 65 and confidence at least 45%.
- `Use with caution`: all other usable results.

The result includes the calculated score, confidence, health score, latest
version, adoption change, GitHub stars, strengths, concerns, and evidence. An
agent should show the concerns rather than presenting only the winner.

## Comparison behavior

The comparison list is sorted by usable score descending. Failed results are
retained at the bottom so a missing package is visible rather than silently
dropped. `winner` is the highest-scoring usable candidate; it is absent when
all candidates failed.
