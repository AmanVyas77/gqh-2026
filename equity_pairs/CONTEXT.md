# CONTEXT — equity_pairs

`HYPOTHESIS.md` holds the economic argument and the frozen specification. `config.yaml` holds every number. This file collects definitions, design notes, the environment, and disclosures.

## Definitions

- **Formation window.** 127 consecutive price observations, giving 126 daily total returns. It ends at a month-end session. Everything is fit on this window only:
  - eligibility,
  - standardization,
  - PCA,
  - clusters,
  - candidate ranking,
  - cointegration,
  - hedge ratio,
  - spread mean and std.
- **Trading window.** The calendar month after a formation. All positions are liquidated at the close of its last session.
- **Evaluation period.** All XNYS sessions after the first formation end (2015-07-31, provisional) through 2026-10-02.
- **Holdout.** Exactly the last min(ceil(20% × evaluation sessions), sessions in (evaluation_end − 2 calendar years, evaluation_end]). No month snapping.
  - Frozen dates: 2024-10-03 to 2026-10-02 inclusive, 501 sessions. The two-year rule binds.
  - It is quarantined during Prompts 0–2.
- **Development range.** Evaluation sessions before the holdout.
  - Frozen dates: 2015-08-03 to 2024-10-02 inclusive.
  - That is 2,308 sessions in 111 calendar months, the last a two-session stub.
  - It ends with a predetermined market-on-close liquidation.
- **Boundary status.**
  - `frozen` since Prompt 2, set before any price request (`snapshots/2026-10-03_prompt2_boundary_freeze/`).
  - `guard.py` refuses any date after 2024-10-02.
  - It also refuses to run while config.yaml and HYPOTHESIS.md conflict.

## Representation change (recorded 2026-10-03; untested)

- **Original brief:** cluster stocks on their formation-window daily returns directly.
- **Current specification:** cluster stocks on their first five PCA loading coordinates.
- The user changed this in Prompt 1 as a research choice.
- Neither representation has been tested.

**Correction to the Prompt 0 note.** I wrote that N > T "needs dimension reduction or shrinkage." That overstated it.

- With about 500 stocks and 126 observations, the sample correlation matrix does have rank of at most 125.
- But hierarchical clustering on correlation distances works on a singular matrix.
- So PCA is a chosen representation, not a mathematical requirement.
- The five components are statistical proxies for common exposures, not identified economic factors.

## Design notes

- **Matrix orientation.**
  - R is T × N: rows are sessions, columns are stocks.
  - The SVD Z/√(T−1) = U S Vᵀ gives V as N × K, one row per stock.
  - Loadings L = V·S are the clustered objects.
  - U indexes sessions and is never clustered.
- **Multiple testing.**
  - BH runs across the union of all three arms' candidates at each formation.
  - Because candidates are chosen on the same window, and pairs share stocks, this is a screen, not true FDR control.
  - The family size depends on all three arms, so a PCA-only robustness change can also shift baseline screening slightly.
- **Corporate actions.**
  - Formation prices use a window-local total-return index. Any later adjustment only rescales a window by a constant, which moves α and not β.
  - Filters use raw closes and raw dollar volume.
  - If the source only provides split-adjusted prices, Prompt 2 reconstructs raw prices from its split ledger. The ledger will include split events after the boundary.
  - That reconstruction restores what was observable at formation time. Holdout-period split events must not be used for anything else.
- **Execution.**
  - Signals at the close; fills at the next raw open.
  - Month-end liquidation is a scheduled close-of-day fill.
  - Gap risk on stops is borne.
- **Exposure.**
  - Sizing by β makes pairs spread-neutral, not dollar- or beta-neutral.
  - Exposures are measured, not assumed away.

## Environment (Prompt 1, 2026-10-03)

- **Virtual environment:** project-local `equity_pairs/.venv`, Python 3.11.7 (base interpreter `/opt/anaconda3/bin/python3.11`). The shared root `.venv` is untouched.
- **Pinned packages** (`requirements.txt`): numpy 2.4.6, scipy 1.17.1, pandas 3.0.6, statsmodels 0.15.0, PyYAML 6.0.3, exchange_calendars 4.13.2, yfinance 1.7.0, lxml 6.1.3, pytest 9.1.1. The full resolved set is in `requirements-lock.txt`.
- **scikit-learn:** not installed. PCA uses NumPy SVD; clustering uses SciPy.
- **Tests:** `cd equity_pairs && .venv/bin/python -m pytest`. They cover config consistency, the fail-closed guard, and the split convention. They use no market data.
- **`.gitignore`:** `equity_pairs/.gitignore` excludes `.venv/`, caches, and `data/raw/`.

## Data sources (Prompt 2 findings; full record in `data/source_manifest.json`)

- **Used: Wikipedia, for membership.** Pinned revisions of the current constituent list (revid 1376729338) and the historical-components changes table (revid 1376064088). Point-in-time membership is reconstructed by reversing every change dated after a formation end. The reconstruction gives 505–508 names per date.
- **Used: yfinance, for prices.**
  - Close and Volume are **split-adjusted, not as-traded**.
  - Adj Close is adjusted for splits and dividends.
  - Spin-offs are encoded as fractional splits.
  - Former members are mostly missing, so about 20% of point-in-time members have no data and the universe is **survivorship-biased**.
- **Not used: the existing connector.** It can only be called interactively, one symbol at a time.
- **Unresolved conflicts with the frozen spec:**
  - the $5 raw-close rule had to run on split-adjusted prices, wrongly excluding NVDA and AIV;
  - raw-price accounting is not possible from this source.

### Candidates considered at Prompt 1 (kept for the record)

- **yfinance** (installed).
  - Gives daily OHLCV, split ratios and dividends.
  - Covers mostly currently listed tickers; delisted names are weak.
  - Its `Close` is split-adjusted, so raw prices must be reconstructed.
  - Its `end` parameter is exclusive.
  - Its terms limit redistribution.
- **Wikipedia's S&P 500 list.**
  - Current constituents with modern GICS sectors.
  - A table of index changes, enough for an approximate point-in-time membership. It is incomplete, and prices for removed names are still needed.
- **A connected financial-data connector.** It exposes index, chart and company tools. Whether it has historical constituents or delisted prices is unknown.
- **CRSP/Compustat via WRDS.** Gold standard, but only if the user has access.

## Incidental exposure disclosures

- **Agent background knowledge.** The research agent's knowledge runs to about mid-2026 and overlaps the provisional holdout (October 2024 to October 2026). It cannot be removed.
  - Mitigation: every choice was frozen before any data was seen, and nothing about stocks, sectors or pairs is chosen at discretion.
- **Other strategies.** Only the file names of other strategies were seen.
- **Calendar computation.** Session counts and dates through 2026-10-02 came from exchange holiday rules. They contain no price information.
- **Prompt 2, membership reconstruction.** It machine-processed the current constituent list and the index changes dated inside the holdout period. They were used only to reverse membership; no prices or returns were seen.
- **Prompt 2, price levels.** Yahoo's split-adjusted pilot-window levels embed later corporate actions, including some after the boundary. Levels were used only for the documented $5 and dollar-volume filters.

## Reference designs

- **Gatev, Goetzmann & Rouwenhorst (2006), RFS:** the distance method.
- **Avellaneda & Lee (2010), Quantitative Finance:** PCA and ETF residual statistical arbitrage.
- **Do & Faff (2010), FAJ:** profitability declining over time.
- **Sarmento & Horta (2020), ESWA:** PCA plus OPTICS clustering, with cointegration, Hurst exponent and half-life filters.

This study does not claim PCA-based pair selection is new.
