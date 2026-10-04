# equity_pairs — clustering-selected S&P 500 pairs

**Research question.** We cluster each stock's trailing six months of daily S&P 500 returns, without supervision. Do pairs drawn from the same cluster form spreads that are stable and mean-reverting out of sample? And do they trade better, net of costs and under identical trading rules, than pairs chosen by plain correlation ranking or by same-sector matching?

Six months is the **rolling formation window**, not the whole sample. Each cycle runs in three steps:

1. Fit on the formation window.
2. Trade the selected pairs over the following trading window.
3. Roll forward.

The evaluation period spans many cycles. Its most recent part is reserved as the final holdout (see `CLAUDE.md`).

**Status:** Prompt 0 (setup) is complete. No data has been downloaded and nothing has been fitted. See `STATUS.md`.

## Layout

| Path | Purpose |
|---|---|
| `CLAUDE.md` | Agent rules: scope, staging, holdout, logging |
| `STATUS.md` | Current stage, blockers, open decisions |
| `CONTEXT.md` | Definitions, design considerations, environment, disclosures |
| `config.yaml` | Configuration skeleton; Prompt 1 freezes it |
| `research_log.csv` | Append-only, timestamped log of queries, specs, amendments, and exposure |

Planned but not yet created:

- `snapshots/` — hashed pre-registration
- `data/` — development-range downloads only
- source modules
- `tests/`
- `results/`

## Reproducing

Nothing is runnable yet. The environment is the repository-root `.venv` (Python 3.11.7). Some additional packages are required; see `STATUS.md`.

## Deliverables

Due **Sunday, 2026-10-04, 11:00 America/New_York**:

- a research note of at most 5 pages,
- reproducible code in this folder.
