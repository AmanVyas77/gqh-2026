# Import templates (headers only)

These templates are for a legitimate licensed export: LSEG I/B/E/S aggregates, FactSet Estimates, Bloomberg BEst, or S&P Capital IQ. Drop exports in `data/imports/` (git-ignored) and validate them with `macro_equity.sources.consensus_import`. Exports are never committed.

## consensus_snapshots_template.csv: one row per (snapshot, target quarter)

| Column | Meaning |
|---|---|
| `snapshot_timestamp` | When this consensus value was published or available. ISO 8601 **with UTC offset**, e.g. `2015-02-27T16:00:00-05:00`. If the provider gives only an as-of date, use that date's 16:00 America/New_York and say so in `notes` |
| `source` | Provider and product, e.g. `IBES_AGG`, `FACTSET_ESTIMATES`, `BLOOMBERG_BEST` |
| `index` | `SPX` (S&P 500) |
| `target_quarter` | Calendar quarter the forecast is for, `YYYYQn` (e.g. `2015Q1`). Never a rolling "next quarter" label |
| `eps_consensus` | Bottom-up index-level EPS per index share for that quarter (index points) |
| `eps_basis` | The provider's EPS definition, e.g. `operating_street`. Must be identical to the actuals' basis |
| `aggregation` | How firm estimates are combined, e.g. `sum_of_mean_estimates_per_index_share` |
| `n_companies` | Optional: constituents covered |
| `notes` | Optional |

## eps_actuals_template.csv: one row per (quarter, vintage)

| Column | Meaning |
|---|---|
| `quarter` | `YYYYQn` |
| `eps_actual` | Index-level actual EPS per index share, same basis as the consensus |
| `eps_basis` | Must equal the consensus `eps_basis` |
| `source` | As above |
| `published_timestamp` | When this value was first published (ISO 8601 with offset) |
| `vintage` | `first_release` or `revised_YYYY-MM-DD` |
| `notes` | Optional |

**Minimum history needed for the pre-registered warmups** (HYPOTHESIS.md §5–6):
- Actuals: about 9 years (36 quarters, including 4 base quarters) before the first gap.
- Consensus snapshots: at least 60 months before the first return forecast.
- To leave about 10+ years of development walk-forward before a holdout in 2024–2026, consensus snapshots should start no later than about 2003, and actuals no later than about 1994.
