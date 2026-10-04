# STATUS — equity_pairs

Last updated: 2026-10-03 (Prompt 0). Exact timestamps are in `research_log.csv`.

## Stage

| Prompt | State |
|---|---|
| 0 — Setup | **Complete** (2026-10-03) |
| 1 — Pre-registration | Not started; waiting for the user to issue it |
| 2 — Data audit + development-only feasibility pilot | Not started |
| Review gate | Comes after Prompt 2 |

Do not start Prompt 1 until the user issues it.

## What exists

- Documentation, a skeleton `config.yaml`, and `research_log.csv`.
- No data, code, fits, pair selections, backtests, or snapshots yet.

## Deadline

- Submission is due 2026-10-04 at 11:00 EDT.
- At setup (2026-10-03 20:15 EDT), about **14 h 45 m** remained.
- That time has to cover Prompts 1–2, the review, any later full and holdout evaluation, and the note of at most 5 pages.

## Blockers

1. **Time.** The staged process plus a holdout evaluation and the write-up must all fit in under 15 hours, overnight. Prompt 1 should pre-register a deliberately small design.
2. **Missing packages.** The root `.venv` lacks `scikit-learn` (clustering/PCA), `statsmodels` (ADF and cointegration), `PyYAML` (config), and `pytest`. Installing them changes the shared environment, outside `equity_pairs/`, so it needs the user's approval. A project-local venv is the alternative.
3. **Point-in-time S&P 500 membership and delisted prices.** Neither is in the repo. The installed `yfinance` mainly covers currently listed tickers, so the universe will be survivorship-biased unless the Prompt 2 audit finds a better source. This must be disclosed.
4. **Point-in-time sector labels** for the sector baseline. Probably only current classifications are available, which puts look-ahead into that baseline. This must be disclosed.
5. **Short borrow fees.** No historical source has been identified. The plan is a flat assumption plus a sensitivity check.
6. **No shared utilities.** No price, data-loading, or accounting utility exists outside other strategies' folders. Small local modules will be written in Prompt 2.

## Decisions Prompt 1 must resolve

1. **Evaluation period, development range, and holdout.**
   - Define the evaluation period's start and end. One option is first-trade day to last completed session, excluding the initial formation warm-up.
   - Compute the holdout from that period: min(20%, 2 years). For any evaluation period longer than 10 years, the 2-year cap binds.
   - Decide how positions that are open at the development/holdout boundary are handled.
2. **Universe.**
   - Choose the membership source: point-in-time or current constituents.
   - Set the price, liquidity, and coverage filters.
   - Decide how stocks that delist or leave the index mid-trade are handled.
3. **Formation window.**
   - 6 calendar months or about 126 trading days.
   - The roll step.
   - Return type, and the treatment of missing data.
4. **Features.**
   - With about 500 stocks and only about 126 days, the sample covariance is singular (N > T). Prompt 1 must pick a fix: PCA with a fixed number of components, shrinkage, or both.
   - Whether to remove the market factor first.
5. **Clustering.**
   - One algorithm and fixed hyperparameters, or a pre-stated selection rule that uses formation data only.
   - The random seed.
6. **Pair selection.**
   - Cointegration test, p-value threshold, and multiple-testing control.
   - Half-life bounds, an optional Hurst or mean-crossing filter, and caps on pairs in total and per stock.
7. **Hedge ratio.** For example, OLS on formation-window log prices: which leg is the dependent variable, and is there an intercept.
8. **Trading rules,** shared by every arm:
   - trading-window length,
   - entry, exit, and stop z-scores (with parameters taken from the formation window),
   - maximum holding period,
   - signal and execution timing,
   - sizing (dollar- or beta-neutral) and the gross exposure cap.
9. **Baselines.**
   - The exact correlation rule (top-N correlation or minimum SSD) and the sector rule.
   - Whether the baselines also pass the same stationarity filter. If they do, the comparison isolates the candidate-generation step.
   - Matching the number of pairs across arms.
10. **Costs.** Commission, half-spread, and slippage (in bps); borrow fee; dividend and corporate-action treatment; capital base (committed or employed).
11. **Metrics and gates.**
    - The frozen **structural feasibility criteria** that Prompt 2 will test on development data.
    - The primary comparison metric and test against each baseline.
    - The stop/go thresholds.
    - The variant budget.
12. **Data source** for prices and sectors, and the implementation of the holdout download guard.

## Survivorship disclosure

Pending the Prompt 2 data audit. Until it shows otherwise, treat the universe as survivorship-biased: today's constituents, observed historically.
