# Economic Hypothesis — written before any backtest

**Proposed edge source:** Compensation for absorbing temporary price pressure and bearing convergence risk.

**Hypothesis.** US large-cap stocks with similar estimated statistical factor exposures, identified through formation-window PCA and clustering, exhibit stable relative-price relationships. Among pairs that pass a cointegration screen over approximately six months, unusually large spread deviations partially reverse over days to a few weeks. Clustering improves pair selection relative to simple correlation and sector-based selection.

**Who is on the other side.** Fund flows, index and portfolio rebalances, and investors demanding immediate liquidity temporarily move one stock relative to a comparable stock. Taking the opposite position earns compensation as that pressure fades. This is a proposed mechanism: price data alone cannot identify the counterparties or distinguish informational from non-informational trading.

**Why the edge persists.** Borrow costs, recall risk, interim losses, and permanent relationship breaks make convergence trades costly and risky, which limits the arbitrage capital competing for this premium.

**Testable predictions.**
1. Cluster-selected pairs outperform correlation-selected and sector-selected pairs after modeled costs in chronological forward testing, under identical spread filters, execution rules, and exposure limits.
2. Previously identified spreads exhibit subsequent convergence. Portfolio returns are not predominantly explained by market and sector exposures.
3. Performance remains economically positive under doubled modeled costs and is reasonably stable across a small, predeclared set of nearby parameters.
4. Results are not dominated by one period or a small number of pairs.

**What would weaken or reject the hypothesis.**
- Forward spreads fail to converge reliably.
- Clustering fails to improve on both selection baselines.
- Net profitability disappears under the predeclared cost stress.
- Returns are predominantly factor exposure or concentrated in a few outcomes.

Insufficient observations or wide uncertainty intervals produce an inconclusive result. Numerical definitions of outperformance, robustness, and concentration are frozen in `config.yaml` before testing.

**Prior work and contribution.** Gatev, Goetzmann & Rouwenhorst (2006); Avellaneda & Lee (2010); Sarmento & Horta (2020). Our contribution is a reproducible, controlled evaluation of PCA-based clustering against correlation and sector selection for daily US large-cap pairs, with identical downstream rules, explicit cost assumptions, chronological validation, and a locked final holdout. We do not claim that PCA-based pair selection is new.

---

## Pre-registered specification — Prompt 1 (frozen 2026-10-03)

*Amended 2026-10-03 (Prompt 1 corrections, before any data):*

- The holdout is now exactly the rule size, with no month snapping.
- Market-on-close liquidation is now explicit.
- The full-period result is a descriptive pooled summary only.
- Attribution is limited to exposure diagnostics.
- Spec consistency now fails closed.

The original pre-registration is preserved in `snapshots/2026-10-03_prompt1_preregistration/`.

The text above is the user's economic hypothesis, kept word for word. A copy as received is in `snapshots/2026-10-03_hypothesis_as_received/` (SHA-256 `8c94b0bb…`).

Everything below turns that hypothesis into one executable specification:

- `config.yaml` holds every number. The `spec-check` block at the end of this section repeats the substantive ones in machine-readable form.
- **A conflict fails closed.** If this section and the config disagree, `guard.py` and the pilot refuse to run until the two are reconciled through a logged amendment.
- These are research choices, not settings proven to be optimal.
- There are no competing algorithms and no parameter searches.

### Proposed mechanism (operational clarification)

The original text proposes that pairs earn compensation for absorbing temporary price pressure and bearing convergence risk. Operationally, that means:

- **The setup.** Two stocks have similar estimated statistical exposures, and their log-price spread was stationary over the past six months.
- **The pressure.** Flows unrelated to new information push one stock away from the other. Examples are fund flows, rebalancing, and demand for immediate liquidity.
- **The signal.** The spread moves far from its formation mean, to \|z\| ≥ 2.
- **The trade.** Taking the other side supplies liquidity. If the pressure was temporary, the spread partly reverts within days to a few weeks, consistent with the 2–20 session half-life screen.
- **The risk.** If the move reflects information instead, the relationship breaks and the stop at \|z\| ≥ 4 or the time exit realizes a loss. That convergence risk, plus borrow costs and capital limits, is the proposed reason the premium is not competed away.

Price data can show whether the predicted reversal pattern appears. It cannot identify the flows or the counterparties.

### What a price backtest can and cannot show

The proposed mechanism is compensation for absorbing temporary price pressure and for bearing convergence risk. It is a hypothesis.

A price backtest **can** show:

- whether spreads converge;
- whether one selection rule beats another;
- whether net returns are positive.

It **cannot**:

- identify who was on the other side of the trades;
- separate informational trading from non-informational trading;
- prove that returns are a liquidity premium rather than unpriced factor exposure or luck.

Results are therefore described as *consistent* or *inconsistent* with the mechanism, never as proof of it.

### Three questions, explicit nulls

The holdout is the confirmatory sample for all three tests.

| Question | Null hypothesis | Test | Maps to |
|---|---|---|---|
| Q1. Do selected spreads mean-revert afterwards? | H0₁: E[D10] ≥ 0 for executed entries in the PCA arm (D10 defined below) | One-sided t-test; standard errors clustered by trading month; α = 0.05 | Prediction 2, first half |
| Q2. Does PCA clustering improve selection? | H0₂ᵇ: E[d_m] ≤ 0 for each baseline b ∈ {correlation, sector} (d_m defined below) | One-sided Newey–West t-test (3 lags); Holm correction across the two baselines; "improves on both" judged by intersection–union | Prediction 1 |
| Q3. Are returns positive after costs, and not mostly factor exposure or a few outcomes? | H0₃: E[PCA-arm monthly net NAV return] ≤ 0 | One-sided Newey–West t-test (3 lags), plus the cost-stress, attribution and concentration criteria below | Prediction 2 (second half), predictions 3 and 4 |

Definitions:

- **D10** = \|z\| ten sessions after the signal close, minus \|z\| at the signal close. The horizon is cut short at month end. If the spread is a random walk, \|z\| is a submartingale, so E[D10] ≥ 0.
- **d_m** = the PCA arm's monthly net NAV return minus the baseline's.

**Outcomes.** Each question ends as *supported*, *evidence against*, or *inconclusive*.

- **Q1.**
  - Supported if p ≤ 0.05.
  - Evidence against if the point estimate is ≥ 0 and the 95% CI lower bound is above −0.25 z-units (the smallest effect of interest).
  - Otherwise inconclusive.
- **Q2.**
  - Supported if the Holm-adjusted p ≤ 0.05.
  - No meaningful improvement if the 95% CI upper bound of E[d_m] is below 0.10% of NAV per month.
  - Otherwise inconclusive.
  - Every result also reports the minimum detectable effect, MDE = (1.645 + 0.842)·sd(d_m)/√n, so that "no improvement" can be told apart from "too little power".
- **Q3.** Supported only if all four of these hold:
  - H0₃ is rejected;
  - doubling the modeled costs still leaves a positive mean net return;
  - returns are not predominantly explained by the measured equal-weighted market and sector exposures. This is a limited diagnostic: it cannot show that returns are unexplained by standard asset-pricing factors, and it cannot prove the liquidity-provision mechanism;
  - the concentration criteria hold.

Insufficient evidence is *inconclusive*. It is not proof that the economic mechanism is false.

**Samples.**

- The holdout covers about 24 months and is the confirmatory sample. With so few months, power is low and inconclusive outcomes are likely.
- The full walk-forward (development + holdout) is reported only as a **descriptive pooled summary**. It is not a second, independent confirmation of the holdout result, because it contains the holdout.

### Change of representation (recorded, untested)

- **Before:** the original brief clustered stocks directly on their formation-window daily returns.
- **Now:** this specification clusters stocks on their first five PCA loading coordinates. The user made this change in Prompt 1 as a research choice.
- **Not forced by the data:** a singular correlation matrix does not require PCA. Hierarchical clustering could run on correlation distances directly.
- **Untested:** neither representation has been tested on any data.
- **Interpretation:** the five components are statistical proxies for common exposures, not identified economic factors.

### Frozen methodology

**A. History and holdout**

- **Calendar.** XNYS exchange holiday rules; no prices are needed. Target data start: 2015-01-01. Evaluation runs through the last session before 2026-10-03, which is 2026-10-02.
- **Formation.** 126 daily returns from 127 consecutive price observations, re-run at every month-end session.
- **Warmup.** The first formation ends at the first month-end with at least 127 sessions of data.
- **Evaluation sessions.** All sessions after the first formation end.
- **Sessions.** XNYS sessions, identified by their New York calendar date. Evaluation sessions run from strictly after the first formation end through evaluation_end, inclusive.
- **Holdout size.** The holdout is exactly the last H evaluation sessions, where H = min(ceil(20% × N_eval), number of evaluation sessions in the half-open window (evaluation_end − 2 calendar years, evaluation_end]).
- **No month snapping.** Monthly formation never lengthens the holdout. (Corrected from the original pre-registration, which snapped the start back to the beginning of its month.)
- **Bounds.** Development = [evaluation_start, development_end] and holdout = [holdout_start, holdout_end], both inclusive. development_end is the session immediately before holdout_start.
- **Provisional dates** (computed by `split.py`):

  | Item | Value |
  |---|---|
  | First formation end | 2015-07-31 |
  | Development | 2015-08-03 → 2024-10-02 (2,308 sessions; 111 calendar months, the last a two-session stub; at least 36 required) |
  | Holdout | 2024-10-03 → 2026-10-02 (501 sessions) |
  | Binding rule | Two years (501 sessions, versus 562 under the 20% rule) |

  These dates stay provisional until Prompt 2 confirms the source's data start and freezes them before any price request. A later data start can only move the boundary later.
- **Trading windows.** Calendar months intersected with each segment, so the boundary splits October 2024:
  - a development stub, 2024-10-01 to 10-02, using the formation ending 2024-09-30;
  - a holdout stub, 2024-10-03 to 10-31, using the formation ending 2024-10-02.
  Each window's formation ends at the session immediately before the window starts.
- **Boundary.** A predetermined market-on-close liquidation at the 2024-10-02 close leaves no position entering the holdout. The holdout starts flat.
- **Download guard.** `guard.py` refuses every download until the boundary is frozen and the spec is consistent. After that, it refuses anything dated after 2024-10-02.
- No other project's cutoff is used.

**B. Universe**

- **Membership.**
  - Preferred: point-in-time S&P 500 membership, including former members and their price histories.
  - Fallback, if that is not found within the 15-minute discovery timebox: a dated snapshot of current constituents, run as an explicitly survivorship-biased exploratory experiment.
  - If historical sector labels are unavailable, the use of modern labels is disclosed.
- **Eligibility** uses formation-time information only. A stock must:
  - be an index member at formation end;
  - have 127 complete price observations, all positive;
  - have nonzero return variance;
  - have a raw close of at least $5 at formation end;
  - have a median raw close × raw volume over the window of at least $20 million.
- **Stale-price exclusion,** fixed before seeing any prices. A stock is excluded if it has:
  - any session with zero or missing volume;
  - any run of 5 or more consecutive identical raw closes;
  - more than 10% of its 126 returns exactly zero.
- Alternate share classes of the same issuer are never paired with each other.
- No filter uses later survival or later data completeness.

**C. PCA and clustering**

- **Returns.** Daily simple total returns built from the raw close, split ratio and cash dividend: r_t = k_t(P_t + D_t)/P_{t−1} − 1.
- **Matrix orientation.**
  - R is a T × N matrix. Its rows are the 126 formation sessions; its columns are the eligible stocks, sorted by permanent identifier.
  - Each column is demeaned and divided by its sample standard deviation over this window only. The result is Z.
  - Take the SVD Z/√(T−1) = U S Vᵀ. The squared singular values S² are the eigenvalues λ of the N × N return correlation matrix.
  - V is N × K, with one row per stock. Loadings are L[i,k] = V[i,k]·√λ_k.
  - **Stocks are the rows of L. Sessions never become the clustered objects.** U is T × K, indexes sessions, and is not used.
- **Components.** Exactly five.
  - No explained-variance tuning, whitening, market-factor removal or shrinkage.
  - Component signs are fixed (largest-\|V\| entry positive) for reproducibility. Distances do not depend on them.
- **Clustering.**
  - Each stock's 5-vector is scaled to unit length. Vectors with norm below 1e−10 are excluded.
  - Distance is Euclidean between the unit vectors.
  - Average-linkage hierarchical clustering (SciPy), cut at distance 0.7.

**D. Candidates and baselines**

- **PCA arm:** each stock's three nearest neighbours within its cluster, by loading-vector distance.
- **Correlation baseline:** each stock's three most correlated neighbours across the eligible universe, using formation daily returns.
- **Sector baseline:** each stock's three most correlated neighbours within its sector.
- **Shared rules:**
  - Same-issuer neighbours are removed before ranking.
  - Ties are broken by identifier.
  - Pairs are canonicalised (lower id first) and deduplicated.
- **Overlap reporting.** Overlap between arms is reported at three stages: candidates, passing pairs and selected pairs. PCA is not assumed to add value.

**E. Spread screening (identical for all arms)**

- **Regression.** Leg A is the lower permanent identifier; the symbol fallback is logged. OLS on the formation window only: log TR_A = α + β·log TR_B + e, where TR is a total-return index local to the window.
- **Cointegration test.** Augmented Engle–Granger via statsmodels `coint`, with a constant, maxlag 5 and AIC autolag.
- **Multiple-testing screen.** Benjamini–Hochberg at q = 0.05, applied at each formation to the deduplicated union of all three arms' candidates.
  - This is a screening heuristic, not guaranteed false-discovery control: the pairs are dependent and were chosen on the same observations.
  - Because the family is shared, its size depends on all three arms.
- **Pass rules.** A pair passes if all of these hold:
  - BH-adjusted p ≤ 0.05;
  - 0.25 ≤ β ≤ 4;
  - the residual standard deviation is finite and above 1e−8;
  - the half-life is between 2 and 20 sessions. Half-life = −log 2 / log φ, from the AR(1) e_t = c + φe_{t−1} + u_t, requiring 0 < φ < 1.
- **Degeneracy rejects:** non-finite values, zero-variance regressors, ill-conditioned designs (condition number above 1e8), and failed tests.
- **Assumptions and limits.**
  - Both log prices are assumed to be I(1), with a linear, stable relationship.
  - The test has low power with 127 observations.
  - The result depends on which leg is the dependent variable.
  - Cointegration within a formation window does not mean it persists into the trading month. That persistence is what Q1 measures.

**F. Trading rules (specified now; engine not built)**

- **Pair selection and limits.**
  - Up to ten pairs per arm, chosen greedily by formation return correlation, with no stock shared between pairs.
  - At most 10% of NAV gross per pair, and 100% in total.
  - Unused allocation stays in cash. Returns are measured on total NAV.
- **Frozen parameters.** α, β, and the spread's mean and standard deviation are fixed from formation for the next calendar month.
- **Signals.**
  - Enter when flat and 2 ≤ \|z\| < 4.
  - Exit at \|z\| ≤ 0.5.
  - Stop at \|z\| ≥ 4.
  - Time exit after 20 sessions.
  - Precedence at a close: stop, then convergence exit, then time exit.
  - After a stop, no re-entry in that pair for the rest of the month. After any other exit, re-entry is allowed from the next close.
- **Execution conventions** (identical for all arms).
  - **Signal-driven trades.** Every signal-driven entry, exit, stop or time exit is computed at a close and fills at the next session's open. No signal ever fills at the close it was computed from.
  - **Scheduled liquidation.** Each trading window's last session carries a predetermined market-on-close order that closes every position. The calendar fixes it before the window starts, and it does not depend on any signal. It is modeled at that session's closing price plus transaction costs.
  - **Final-close signals.** Signals computed at a window's final close are ignored.
  - **Development end.** Development ends with this scheduled liquidation on its final session (2024-10-02).
  - **Caveat.** Historical closing prices are execution proxies, not guaranteed MOC fills.
- **Sizing.**
  - Gross G = 10% of NAV.
  - Long spread: +G/(1+β) in A and −Gβ/(1+β) in B. Short spread: the reverse. P&L is then roughly G/(1+β) × the change in the spread.
  - Fractional shares, held fixed until exit.
  - Dollar, market-beta and sector exposures are measured. Neutrality is not assumed.
- **Corporate actions.**
  - Raw execution prices, with a split/dividend ledger. Dividends are credited to longs and debited to shorts on the ex-date.
  - If a leg delists, both legs close at the last available close.
- **Costs (assumptions).**
  - 10 bps per traded dollar per leg, covering commission, spread and slippage together.
  - 3% annual borrow fee on short market value.
  - Borrow is assumed always available.
  - Stress case: both costs doubled.
- **Funding.** Short proceeds are credited to cash, and cash earns 0%. NAV = cash + long MV − short MV.

### Machine-checked specification (`spec-check`)

`spec.require_consistent` compares every key below with `config.yaml`. Any difference fails closed.

```yaml spec-check
timeline.target_data_start: "2015-01-01"
timeline.as_of_date: "2026-10-03"
timeline.formation_price_obs: 127
timeline.formation_return_obs: 126
timeline.reform_frequency: monthly
timeline.min_development_months: 36
timeline.holdout.fraction: 0.20
timeline.holdout.max_calendar_years: 2
timeline.holdout.month_snap: none
timeline.holdout.start: "2024-10-03"
timeline.holdout.end: "2026-10-02"
timeline.holdout.n_sessions: 501
timeline.development.start: "2015-08-03"
timeline.development.end: "2024-10-02"
data.max_download_date: "2024-10-02"
universe.eligibility.complete_price_obs: 127
universe.eligibility.min_formation_end_raw_close: 5.0
universe.eligibility.min_median_dollar_volume: 20000000
universe.eligibility.exclude_same_issuer_pairs: true
universe.eligibility.uses_future_information: false
features.pca.method: svd
features.pca.n_components: 5
features.pca.whitening: false
features.pca.shrinkage: false
features.pca.market_factor_removal: false
clustering.objects: stocks
clustering.distance: euclidean
clustering.linkage: average
clustering.cut_distance: 0.7
candidates.neighbors_per_stock: 3
screening.cointegration_test.trend: c
screening.cointegration_test.maxlag: 5
screening.cointegration_test.autolag: aic
screening.multiple_testing.method: benjamini_hochberg
screening.multiple_testing.q: 0.05
screening.pass_rules.beta_min: 0.25
screening.pass_rules.beta_max: 4.0
screening.pass_rules.half_life.min_sessions: 2
screening.pass_rules.half_life.max_sessions: 20
portfolio.max_pairs: 10
portfolio.per_pair_gross_max_nav: 0.10
portfolio.total_gross_max_nav: 1.00
trading.entry_abs_z: 2.0
trading.exit_abs_z: 0.5
trading.stop_abs_z: 4.0
trading.max_holding_sessions: 20
trading.signal_time: close
trading.fill_time: next_session_open
trading.conventions_identical_across_arms: true
costs.transaction_bps_per_traded_dollar_per_leg: 10
costs.short_borrow_annual_rate: 0.03
costs.stress_multiplier: 2.0
pilot.thresholds.n_formations: 12
pilot.thresholds.min_eligible_stocks: 300
pilot.thresholds.max_formations_below_min_eligible: 6
pilot.thresholds.min_pca_pairs: 5
pilot.thresholds.min_formations_with_min_pca_pairs: 6
pilot.thresholds.redundancy_overlap_share: 0.90
pilot.thresholds.redundancy_min_formations: 6
validation.confirmatory_sample: holdout
```

### Prompt 2 feasibility gate (formation diagnostics only)

- **Pilot formations:** the earliest twelve consecutive eligible development month-end formations, provisionally 2015-07-31 to 2016-06-30.
- **Excluded:** subsequent returns, P&L, Sharpe and equity curves.
- **Timebox:** 45 minutes in total, with at most 15 minutes for source discovery.

| Verdict | Condition |
|---|---|
| BLOCKED | Any of: insufficient history; fewer than 12 formations; fewer than 300 eligible stocks in more than 6 formations; unusable data conventions; inadequate holdout protection; a required audit or pilot step incomplete when the timebox expires |
| NOT PROMISING | Inputs are usable, but the PCA arm yields at least 5 eligible non-overlapping pairs in fewer than 6 of the 12 formations |
| PASS WITH LIMITATIONS | Data and breadth gates pass, but universe, delisting, sector or borrow assumptions limit the claims |
| PASS | Data and breadth gates pass, with historical coverage adequate for the stated scope |
| Redundancy flag (not a verdict) | More than 90% of PCA-arm candidates are also correlation-baseline candidates in at least 6 formations |

These are practical feasibility thresholds, not statistical validation. They will not be relaxed after results are seen. A pass establishes neither profitability nor any added value from PCA clustering.

### Later validation (defined now; not run in Prompt 2)

- **Primary economic comparison.** Paired monthly net NAV return differences, PCA arm minus each baseline (Q2 above). The 95% CI comes from a stationary block bootstrap: mean block length 3 months, 10,000 resamples, seed 20261003.
- **Convergence diagnostics (Q1).** Reported for every arm:
  - D10, as defined above;
  - the shares of entries that reach the exit band, are stopped, or are time-exited;
  - the median number of sessions to exit;
  - the share of selected pairs whose spread crosses its formation mean during the trading month.
- **Factor attribution.**
  - Daily net returns are regressed on two models: (i) the equal-weighted eligible-universe return, and (ii) equal-weighted sector returns. Standard errors are HAC with 5 lags.
  - Returns count as *predominantly factor-explained* if the sector model's R² ≥ 0.50, or if the fitted factor component is at least 50% of a positive mean return.
  - These equal-weighted regressions are **limited exposure diagnostics**. They do not establish that returns are unexplained by standard asset-pricing factors, and they do not prove the liquidity-provision mechanism.
- **Concentration.** Applies when total net P&L is positive, and every criterion must hold:
  - the best month contributes at most 25% of total net P&L;
  - P&L stays positive without the best 3 months;
  - P&L stays positive without the 10 largest pair-month episodes;
  - no single pair contributes more than 20%;
  - in the full-period sample, no calendar year contributes more than 50%.
- **Cost stress.** To support economic robustness, the mean monthly net return must stay above 0 with both costs doubled.
- **Robustness set.**
  - Four predeclared variants, each changing one setting from the primary: 4 PCA components; 6 PCA components; entry \|z\| = 1.8; entry \|z\| = 2.2.
  - "Reasonably stable" means that in at least 3 of the 4 variants, the PCA arm's mean net return is above 0 and its difference against both baselines keeps the primary result's sign.
  - The final strategy is never chosen by the best robustness result.
- **Supporting metrics.** Sharpe ratio (monthly and daily, annualised), maximum drawdown, turnover, gross exposure, trade counts, exposures and concentration.

### Known limitations at pre-registration

- **Survivorship bias,** if point-in-time membership or delisted prices are unavailable. The likely effect is to overstate convergence and understate stop-outs, because delisted, distressed and acquired stocks would be missing, and those are where pair relationships tend to break.
- **Sector look-ahead,** if only modern sector classifications are available.
- **Costs and borrow** are assumptions, not historical evidence.
- **Statistical power** is limited over a 24-month holdout.
- **Prior knowledge.** The research agent's background knowledge overlaps the holdout period. This is logged as incidental exposure.
