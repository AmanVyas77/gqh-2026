# CONTEXT — equity_pairs

## Definitions

- **Formation window.** The trailing 6 months of daily returns. Each cycle fits these on it, and only on it: transformations, clusters, pair tests, hedge ratios, and spread mean/std.
- **Trading window.** The period after a formation window, in which the pairs selected in that window are traded. Its length is set in Prompt 1.
- **Evaluation period.** The full span of trading windows evaluated, which covers many rolling cycles. It is defined in Prompt 1.
- **Holdout.** The most recent min(20% of the evaluation period, 2 years). It is quarantined during Prompts 0–2.
- **Development range.** The evaluation period minus the holdout. It is the only data used in Prompt 2.

## Hypothesis sketch (not yet pre-registered)

Clustering in a reduced return space (for example, PCA loadings) groups stocks that share common-factor exposure. Within a cluster, a cointegrated pair should be more likely to keep a stationary spread out of sample than pairs chosen by raw correlation or by sector label.

Two points shape the test:

- High correlation of returns does not imply a stationary price spread. Mean reversion has to be tested directly.
- Persistence out of the formation window is itself the main thing to measure.

Prompt 1 will formalize the sketch and its alternatives.

## Design considerations to settle in Prompt 1

- **N > T.** With about 500 stocks and about 126 daily observations, the sample covariance has rank of at most 125. Clustering on raw correlations is noisy, so it needs dimension reduction or shrinkage, fitted per formation window.
- **Multiple testing.** There are about 125k possible pairs. Even within clusters, testing many spreads at p < 0.05 produces many false cointegration findings, so the filter thresholds need correction or another form of control.
- **Back-adjusted prices.**
  - Adjusted closes downloaded today are scaled by dividends and splits that come later, including during the holdout.
  - Daily returns are unaffected, and an OLS on log prices only moves its intercept.
  - Level-based filters are affected (for example, minimum price), so they should use unadjusted closes.
- **Sector baseline look-ahead.** Free sources give current sector labels, not historical ones.
- **Shorting.** The short leg pays dividends and borrow fees. Hard-to-borrow names are not modelled without data.
- **Execution timing.** A signal at close *t* must not be filled at the same close unless that is explicitly assumed and costed.
- **Capital base.** Returns on committed capital and on employed capital can differ a lot for pairs strategies, so state which one is reported.

## Environment (inspected 2026-10-03)

- Python 3.11.7 in the repository-root `.venv`.
- Root `requirements.txt` pins `yfinance==1.7.0`, `pandas==3.0.6`, `numpy==2.4.6`, and `matplotlib==3.11.2`.
- Also installed: `scipy 1.17.1`, `requests 2.34.2`, `lxml 6.1.3`.
- **Missing:**
  - `scikit-learn`
  - `statsmodels`
  - `PyYAML`
  - `pytest`
  - `pyarrow`
  - `exchange_calendars` / `pandas_market_calendars`
- Root `.gitignore` ignores `.venv/`, `.cache/`, and `__pycache__/` only. Any raw data downloaded here would show up as untracked unless this project ignores it.
- No shared utility exists for prices, data loading, or execution accounting outside other strategies' folders, so project-local modules are needed.

## Candidate data sources (not queried; audit in Prompt 2)

- **`yfinance`** (installed): daily OHLCV and adjusted prices, mostly for currently listed tickers. Delisted coverage is poor, and the terms of use limit redistribution.
- **Wikipedia's S&P 500 list:** current GICS sector and sub-industry, plus a table of index changes for an approximate point-in-time membership. The changes table is incomplete, and prices for delisted names would still be missing.
- **A connected financial-data connector:** it exposes index, chart, and company tools. Whether it covers historical constituents and delisted prices, and under what plan and licence, is unknown.
- **CRSP/Compustat via WRDS:** the gold standard for point-in-time data. It is only an option if the user has access.

## Incidental exposure disclosures

- The research agent's pretrained knowledge runs to about mid-2026, which overlaps any likely holdout (the most recent 2 years or less). That gives it general awareness of market and sector moves, which cannot be removed. Mitigation: freeze every choice before touching data, and make no discretionary choices of stocks, sectors, or pairs.
- During setup, `git status` showed the file names of other strategies. Their contents were not read.

## Reference designs (for Prompt 1 to consider; none adopted)

- Gatev, Goetzmann & Rouwenhorst (2006), *Review of Financial Studies*: the distance (SSD) method with a 12-month formation and 6-month trading window. A natural correlation/distance baseline.
- Do & Faff (2010), *Financial Analysts Journal*: profitability of simple pairs trading declining over time.
- Sarmento & Horta (2020), *Expert Systems with Applications*: PCA plus OPTICS clustering, then cointegration, Hurst, half-life, and mean-crossing filters.
