# equity_pairs — agent instructions

Before doing anything in this project, read this file and then `STATUS.md`.

## Scope

- Work only on this strategy, and only inside `equity_pairs/`.
- Do not read, run, review, compare, summarize, or modify the other strategies in this repository, including their code, research notes, results, and backtests.
- Outside this folder you may look only at:
  - root instruction files,
  - `git status`,
  - top-level directory names,
  - dependencies and utilities that are directly needed for equity prices, data loading, or execution accounting.
- If using a shared utility would mean digging into another strategy, write a small local one here instead.
- Preserve all existing work. Do not reset, stash, check out over other files, commit, or push. The user commits.
- Do not purchase data, place trades, or connect to a brokerage.
- Never print credentials or the contents of `.env`.

## Staged process

| Prompt | Purpose |
|---|---|
| 0 | Isolate and set up the project (done 2026-10-03) |
| 1 | Pre-register the hypothesis, method, baselines, and stop/go criteria; freeze the config (done 2026-10-03) |
| 2 | Audit the data, then run a bounded **development-only** structural feasibility pilot. This means formation diagnostics only, within a 45-minute timebox; the gate is frozen in `config.yaml` under `pilot` |

The frozen specification is in `HYPOTHESIS.md` (prose, plus a machine-checked `spec-check` block) and `config.yaml` (the numbers). A substantive conflict between them fails closed: `guard.py` and every pipeline refuse to run until the two are reconciled. Do not change either file without a logged amendment and a new snapshot. The tests fail if a live file's hash is missing from the log.

- Run only the prompt the user has issued. Do not advance automatically, even when the next step looks obvious.
- **Stop after Prompt 2 for human review.** If the pilot fails the frozen feasibility criteria, end this specification. Record the failure in `STATUS.md`. Do not tweak the setup and rerun.
- Update `STATUS.md` at the end of every prompt.

## Research rules

1. **Pre-registration snapshot.** Before any fit on real data, save a dated, SHA-256-hashed snapshot of the hypothesis and config to `snapshots/YYYY-MM-DD_<label>/`, and log the hash in `research_log.csv`. Any later change is an amendment: make a new snapshot and add a log row giving the reason.
2. **Holdout.** The final holdout is the most recent **min(20% of the evaluation period, 2 years)**. Compute it for this strategy alone, from its own evaluation period; never reuse another project's split. Once frozen, the dates live in `config.yaml`.
3. **Holdout quarantine during Prompts 0–2.**
   - Do not download any price dated on or after the holdout start.
   - Do no analysis, clustering, pair selection, or performance evaluation on holdout data.
   - Every download call must pass an explicit end date before the holdout start. Check the provider's end-date semantics (in yfinance, `end` is exclusive).
   - The loader must also assert that the maximum returned date is before the holdout start.
   - Every loader must call `guard.check_request(...)` before fetching and `guard.check_dates(...)` afterwards.
   - The guard refuses everything until `timeline.boundary_status` is `frozen`. Freezing the boundary is a logged amendment, and it must happen before any price download.
4. **No look-ahead.** Fit transformations (standardization, PCA), clusters, pair-selection statistics, hedge ratios, and z-score parameters only on the formation window that precedes each trading window.
5. **Correlation alone does not establish mean reversion.** A pair is tradable only if its spread passes the pre-registered stationarity and mean-reversion tests. Whether those properties persist beyond the formation window must itself be tested.
6. **Baselines.** Compare clustering against both of the following, each built inside this project and run through identical downstream rules (tests, hedge ratios, entry/exit, sizing, and costs):
   - (a) a simple correlation-selection baseline,
   - (b) a sector-selection baseline.
7. **Logging.** Append a row to `research_log.csv` for every source query, specification, amendment, and incidental exposure. Use actual timestamps from `date -u`, plus America/New_York time. Incidental exposure means any sight of holdout-period prices or results, including prior knowledge. Never edit or backfill past rows; correct an error by adding a new row.
8. **Survivorship.** If point-in-time constituents or delisted prices are unavailable, disclose survivorship bias and its likely direction in `STATUS.md`, `CONTEXT.md`, and the research note.
9. **Net accounting before any profitability claim.** Account for transaction costs (commissions, spread, slippage), short borrow fees, dividends (paid on shorts), corporate actions, execution timing (signal versus fill), and gross exposure / capital base. Label any gross figure as gross.
10. **Synthetic data** is only for implementation checks, such as unit tests and pipeline smoke tests. Never report synthetic results as evidence.
11. **Count variants.** Count every configuration variant run on real data (`evaluation.n_variants_tried` in the config). The count feeds the multiple-testing adjustments.

## Deadline

- Submission: **Sunday, October 4, 2026, 11:00 AM America/New_York.**
- Research note: at most 5 pages.
- Code: reproducible from this folder.

## Environment

Use the project-local `equity_pairs/.venv` (Python 3.11.7; pins in `requirements.txt` and `requirements-lock.txt`). Never modify the shared root `.venv`. Run the tests with `.venv/bin/python -m pytest` from this folder.
