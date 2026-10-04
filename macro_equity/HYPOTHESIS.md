# Pre-Registered Hypothesis: Independent Earnings Forecasts, Consensus, and SPY Timing

**Gator Quant Hacks 2026 · Systematic Trading Track · project `macro_equity`**
**Status:** Provisional specification, written 2026-10-03 (Prompt 1) before any data for this project was pulled and before any model, test or backtest existed. The commit timestamp of this file is the record.

**Status key.** **[FIXED]** items are frozen once this file is committed and change only through an amendment (§14). **[PROVISIONAL P#]** items depend on data that Prompt 2 must verify. Each is listed in the register (§13) with its default or candidates, and is resolved once, by amendment rows, at **Freeze F1**. F1 happens at the end of Prompt 2 and before any predictive relationship or performance is examined. "Examined" means any computation that relates a predictor to an outcome (earnings surprises or returns), any model fit, or any backtest. Before F1, only coverage metadata and single-input properties (dates, units, missingness, ranges) may be inspected, and any change they prompt is logged as such. After F1, every change is an amendment.

`config.yaml` is the machine-readable mirror of this file. Whether this study becomes the team's submitted strategy is undecided until data feasibility is known (see STATUS.md).

---

## 0. Disclosure of prior exposure [FIXED]

- **SPY's path has already been observed.** The GLP-1 project in this repository (`glp1_backtest.py`, run before this project existed) computed and charted SPY buy-and-hold returns from early 2021 through 2026-10-02, reported separately before and after 2024-01-01. The future macro_equity evaluation period therefore **is not untouched**: SPY's realized path and the market's direction over any plausible holdout were seen by the team.
- **What has not been observed:** no code or document in this repository has built or evaluated this strategy's signals (independent earnings forecast, gap to consensus, real-yield or credit-spread changes) or their timing returns, over any period. This was checked by a repository search on 2026-10-03.
- **Public knowledge:** the 2024–2026 paths of equities, real yields and credit spreads are widely known in October 2026.
- **Motivating study:** Sharpe & Gil de Rubio Cruz (2024) was published in July 2024, so its sample ends before our likely holdout. It overlaps our development period, which is therefore not independent of the evidence that motivated the hypothesis.

## 1. Hypothesis [FIXED]

> "An independent S&P 500 earnings forecast above contemporaneous analyst consensus predicts higher subsequent equity excess returns. Real-yield and credit-spread changes add predictive information; one predefined interaction tests whether rate changes alter the earnings relationship."

The hypothesis contains three separate claims. Each has its own null hypothesis, its own test and its own verdict (§10). A verdict on one is never borrowed for another.

| Claim | Statement | Null hypothesis |
|---|---|---|
| **E: earnings forecasting** | The independent forecast contains information about S&P 500 earnings that consensus lacks: when the model forecast exceeds consensus, realized EPS tends to exceed consensus | H0-E: the gap has no positive association with the subsequent consensus forecast error (slope ≤ 0) |
| **R: return forecasting** | The combined predictors (gap, real-yield change, credit-spread change) forecast next-month SPY excess returns better than the expanding historical mean | H0-R: out-of-sample mean squared forecast error is no lower than the historical mean's (out-of-sample R² ≤ 0) |
| **T: profitable trading** | A monthly, unlevered 0/1 SPY / cash-proxy allocation driven by those forecasts beats SPY buy-and-hold on a risk-adjusted basis, net of costs | H0-T: net excess-return Sharpe is no higher than buy-and-hold's, and alpha against SPY is ≤ 0 |

**Consensus is a benchmark, not the market's view.** Analysts' consensus measures one group's published expectations. It is not a complete measure of what stock prices imply, so E can hold while R fails.

**Independence.** The earnings model uses no analyst data, so the gap is not built mechanically from consensus.

## 2. Economic mechanism [FIXED]

**Causal chain:**
1. Macro conditions (nominal GDP growth, the dollar, recent earnings momentum) drive aggregate S&P 500 earnings.
2. Bottom-up consensus, aggregated from firm-level analyst forecasts, absorbs macro information slowly. Sharpe & Gil de Rubio Cruz (2024) find that a macro model predicts significant errors in bottom-up S&P 500 forecasts, and that the macro-minus-analyst discrepancy predicts 3-month returns. Hugon, Kumar & Lin (2016) find analysts under-use macro news.
3. Investors partly anchor on analyst forecasts (So 2013). Measured subjective earnings expectations move prices (De La O & Myers 2021; Bordalo, Gennaioli, La Porta & Shleifer 2019).
4. When the macro forecast is above consensus, positive surprises follow during the reporting season and prices adjust upward.

**Rates and credit.** Real-yield changes act through the discount-rate channel. Credit-spread changes summarize funding conditions and default risk that lead activity (Gilchrist & Zakrajšek 2012). Both are tested as additional predictors with **no sign restrictions**. For interpretation only, the expected signs are: gap positive, real-yield change negative, spread change negative. The single interaction (gap × real-yield change) asks whether rising real yields weaken the earnings channel (expected negative). It is a diagnostic only.

**Who is on the other side.** Investors who price the index off consensus-anchored expectations; benchmarked managers who stay fully invested; and analysts whose incentives (firm focus, management guidance, optimism) slow aggregate macro updating.

**Why it may persist.** It is an index-level timing signal with only about four independent earnings cycles a year. Evidence accumulates slowly and tracking-error limits deter arbitrage.

**What would kill it:**
- E fails: no mechanism.
- E holds but R fails: prices already see past consensus (an efficient-market finding).
- R holds but T fails: the predictability is too small to survive costs or to beat holding SPY.

**Relation to the motivating study (track originality rule).** We take the macro-versus-consensus idea from Sharpe & Gil de Rubio Cruz (2024) and change it as follows:
- Their GDP *forecasts* (Blue Chip) are replaced by the latest *published* real-time GDP vintage.
- The return horizon is one month, not three.
- Real-yield and credit-spread predictors are added, with one predeclared interaction.
- The forecasts are turned into a costed, executable 0/1 SPY / cash-proxy rule with a pre-registered holdout that falls after the study's publication.

## 3. Instruments, calendar and execution [FIXED unless marked]

- **Risky asset:** SPY (SPDR S&P 500 ETF Trust).
- **Cash proxy [PROVISIONAL P2]:**
  - Preferred: BIL (SPDR Bloomberg 1-3 Month T-Bill ETF), a traded ETF with fees and some price risk (disclosed).
  - Fallback, only if BIL's coverage cannot support the required history: a non-traded account accruing the 3-month Treasury bill rate.
  - The choice sets the number of traded legs in §7.
- **Decision dates:** the last NYSE regular session of each calendar month. The **signal cutoff** is that session's scheduled close: 16:00 America/New_York, or 13:00 on early-close days. All timestamps are timezone-aware. The NYSE session calendar is [PROVISIONAL P3].
- **Information rule:** an input is usable at decision t only if its publication timestamp is at or before t's cutoff, in the vintage published by then. Later releases wait for the next decision. Known values may be carried forward; nothing is ever backfilled.
- **Execution:** at the official opening price of the first NYSE session after the cutoff (E_t). Both legs trade at that open.
- **Allocations:** w_t ∈ {0, 1}, where 1 = 100% of NAV in SPY and 0 = 100% in the cash proxy. No leverage, no shorting.
- **Return label:** y_t = TR_SPY(E_t → E_{t+1}) − TR_cash(E_t → E_{t+1}), measured open to open.
  - Total return is built from raw opening prices, explicit cash distributions (reinvested at the ex-date open) and split factors.
  - No adjusted closes are mixed with raw opens, and no distribution is counted twice. Source conventions are verified in Prompt 2 [P3].
- **Label maturity:** y_t becomes trainable only at a cutoff after E_{t+1}. In practice, at decision t the newest trainable label is y_{t−2}.

## 4. Earnings target, consensus and the gap

**4.1 Target quarter [FIXED].** At decision t, the target quarter q(t) is the calendar quarter that contains t's month. Each target quarter therefore has exactly three monthly decisions: the ends of months 1, 2 and 3. At the month-3 decision the quarter has ended, but index EPS has not yet been published.
- The target never rolls within a quarter. A change between successive monthly forecasts is a forecast update, never a horizon change.
- Repeated monthly forecasts of one quarter are **not** independent observations.
- Whether the consensus source supports this mapping is checked in [PROVISIONAL P15].

**4.2 EPS definition [PROVISIONAL P5].** S&P 500 index-level operating EPS per index share for the calendar quarter, as defined by the consensus provider.
- Realized EPS must use the identical definition and basis: the same provider's actuals, or a documented exact match.
- GAAP / as-reported earnings are never mixed with operating consensus.

**4.3 Consensus snapshot [PROVISIONAL P4].** C_t is the latest bottom-up consensus EPS for q(t) published at or before t's cutoff.
- Never substituted: current estimates do not stand in for historical snapshots.
- If dated historical snapshots with target quarters are unavailable, claims E, R and T are **BLOCKED**. They are not re-specified.

**4.4 Realized-outcome vintage [PROVISIONAL P6].** This is fixed before any fit. Order of preference:
- (a) the first complete published value, with its publication timestamp;
- (b) if vintages do not exist, the provider's value with a documented conservative availability lag after quarter end, disclosed as possibly revised.

**4.5 Signed growth with a scale floor [FIXED form; constants PROVISIONAL P11].** Aggregate EPS can approach zero or turn negative in deep recessions, so growth uses a floor:

  F_t = k × median(|E|) over the L most recent quarters published by t's cutoff (default k = 0.5, L = 8)
  g(q) = (E_q − E_{q−4}) / max(|E_{q−4}|, F)
  Model EPS: Ê = E_{q−4} + ĝ × max(|E_{q−4}|, F)

  All quantities use values published by the relevant cutoff; F is recomputed at each cutoff.

**4.6 Earnings gap [FIXED form; floor PROVISIONAL P11].**

  gap_t = (Ê_t − C_t) / max(|C_t|, F_t)

  This is the prompt-pack formula (model − consensus) / |consensus|, with the same floor used as the near-zero-consensus rule. It is dimensionless.

## 5. Independent earnings model [FIXED structure]

- **Target:** realized signed growth g(q(t)) (§4.5) of the target quarter.
- **Features** (all real-time; sources and lags [PROVISIONAL P9, P10, P5]):
  1. nominal GDP year-over-year growth from the latest quarter in the GDP vintage published by the cutoff;
  2. broad trade-weighted dollar log change, log(D_t / D_{t−3}), where D_t is the latest value published by cutoff t and t−3 is three decisions earlier;
  3. signed EPS growth (§4.5) of the latest quarter whose realized EPS (same definition) was published by the cutoff.
- **Training examples:** exactly one per target quarter, taken at the cutoff of that quarter's **second month-end**, with features in their original vintages. Quarter q is admitted at fit cutoff t only if E_q and its base E_{q−4} were published by t.
- **Estimator:** ridge regression, sum of squared residuals + λ‖β‖².
  - Features standardized with training-sample mean and standard deviation (ddof 0); intercept unpenalized.
  - λ ∈ {0.1, 1, 10}.
  - Note: with this objective the effective shrinkage is roughly λ / n, so the grid is mild for n ≥ 32. Disclosed, not changed.
- **λ selection:** expanding chronological validation grouped by target quarter (one example per quarter).
  - The first 20 admissible quarters serve only as initial training [PROVISIONAL P13].
  - Each later quarter is predicted by a model fit only on quarters whose outcomes were published before its snapshot cutoff.
  - The λ with the lowest validation MSE wins; ties go to the larger λ.
- **Refitting:** at every decision date, with the training quarters admissible at that cutoff (expanding window). The first forecast requires **at least 32 distinct admissible target quarters** [minimum PROVISIONAL P12].
- **Live replay:** at each monthly decision, the current model is applied to that date's features. Month-1, month-2 and month-3 forecasts of a quarter carry different information; this is disclosed. Training uses only month-2 snapshots.
- **Forbidden:** recessions removed after seeing errors; coefficients copied from published studies; random splits.

## 6. Return model [FIXED structure; transformations PROVISIONAL P11]

- **Label:** y_t (§3).
- **Predictors at t:**
  - gap_t (§4.6), from the genuine walk-forward replay, never in-sample fitted values;
  - Δry_t: change in the 10-year TIPS real yield, in basis points, between the latest value published by cutoff t and the latest published by cutoff t−1 [series and lag P7];
  - Δcs_t: the same for the US investment-grade corporate option-adjusted spread, in basis points [series, history and lag P8].
- **Primary model:** combined additive ridge on [gap, Δry, Δcs].
- **Predeclared diagnostics** (fixed roles; never promoted to primary, whatever their results):
  - D1, earnings-only: [gap];
  - D2, rates/credit-only: [Δry, Δcs];
  - D3, combined plus one interaction: [gap, Δry, Δcs, gap × Δry]. The interaction is the product of the standardized inputs, then re-standardized.
- **Fitting at decision t:**
  - Training uses labels matured by t's cutoff (y_s with s ≤ t−2); unfinished labels are purged at every fold boundary.
  - Standardization uses training data only. Standardized predictors are clipped at ±4 [P11].
  - Ridge as in §5, λ ∈ {0.1, 1, 10}. λ is selected by one-step-ahead expanding validation inside the training set, after an initial 36 observations [P13], with the same purge. Lowest MSE wins; ties go to the larger λ.
  - Refit every decision.
- **Warmup:** the first return forecast requires **at least 60 completed monthly observations** whose three predictors all come from the replay [minimum P12].
- **Benchmark forecast:** the expanding historical mean of matured labels, evaluated on the same dates.
- **Output:** μ̂_t, the predicted next-month excess return in decimal.

## 7. Positions, execution costs and accounting [FIXED]

- **Rule:** at each decision, choose w_t ∈ {0, 1} to maximize w × μ̂_t − κ × |w − w_current|. w_current is the SPY weight held going into the decision. Exact ties keep the current position.
- **Cost:** c = 0.0005, i.e. 5 bps per one-way dollar traded, **charged on each ETF leg**.
  - With a traded cash ETF, a full switch sells one ETF and buys the other, so κ = 2c = 0.0010 per unit switched. With a non-traded cash account, κ = c (one leg) [P2].
  - The same per-leg charge is applied in the decision rule and in the accounting.
- **Cost stress:** 10 bps per leg, applied to the frozen base-cost positions (pure cost stress). A separately labeled diagnostic also re-optimizes positions with doubled κ; it is not a trial and not a replacement.
- **Accounting:**
  - A daily share and cash ledger with distributions on ex-dates, cash-proxy returns, gross and net P&L. Costs are charged on actual dollars traded.
  - Returns compound; there is no fixed-capital cumulative sum.
  - Each evaluation window starts fully in the cash proxy, as if already held (no entry cost). The first decision's trade is charged.
  - Terminal value is marked at the final label's ending open, with no liquidation cost; this is disclosed.
- **Justification of 5 bps per leg:** must be documented with cited spread and slippage evidence for SPY and the cash proxy in Prompt 2/10.

## 8. Benchmarks [FIXED]

All benchmarks use the same dates, execution opens, per-leg costs, distribution handling and annualization:
1. SPY buy-and-hold (total return);
2. cash proxy;
3. 12-month trend rule: hold SPY when its trailing 12-month total return at the signal cutoff exceeds the cash proxy's, otherwise hold the cash proxy; executed at the same next open;
4. constant mix: a fixed SPY weight equal to the primary strategy's average SPY exposure over the development walk-forward, rebalanced monthly, with that weight frozen for the holdout. Realized exposure differences are reported.

## 9. Sample, holdout and warmup [rules FIXED; dates PROVISIONAL P1, P14]

- **Track rule (verified 2026-10-03):** the holdout is the most recent 20% of history or the most recent 2 years, whichever is shorter. It is evaluated once.
- **Eligible history:** month-end decision dates at which every primary input has a published observation. The inputs are SPY and cash-proxy prices, the consensus snapshot, realized EPS history, the GDP vintage, the dollar, the real yield and the spread. The history runs through the last decision whose label has matured by the common data cutoff D [P1].
  - Warmup months are included, since this is the strategy's raw data history.
  - The alternative readings of "history" are recorded in CONTEXT.md §2.
- **Holdout size:** N_h = min(round(0.2 × N), 24) decisions, where N is the eligible count. The holdout is the last N_h eligible decisions; development is everything earlier.
- **Quarantine:** let d_h be the first holdout decision and E_h its execution open.
  - Development data = signal inputs published at or before the last development cutoff, plus asset prices and distributions through the open of E_h (needed to complete the final development label).
  - Everything later is stored only in `data/holdout/` and read only by the gated runner (Prompt 9).
  - Development code never builds a decision row at or after d_h.
- **Boundary source:** dates come from coverage metadata only, never from results. They are not inherited from cattle_crush (2024-10-01) or GLP-1 (2024-01-01); any coincidence would come from the same 2-year cap applied to a similar data end.
- **Illustration, not a decision:** if the cap binds and D falls in early October 2026, the holdout would be the 24 decisions from 2024-09-30 to 2026-08-31.
- **Warmup:** earnings ≥ 32 distinct quarters; returns ≥ 60 completed months (§5–6). The development walk-forward evaluation runs from the first return forecast to the last development decision. Its length and independent-quarter count are reported in Prompt 2. If it is too short to be informative, that is reported as a feasibility finding, not fixed by relaxing warmups.

## 10. Tests and verdicts [FIXED]

Statistics are computed on development walk-forward output (Prompts 5–8) and, once, on the holdout (Prompt 9).

**Claim E: earnings forecasting**
- **E1 (primary).** Regression with one observation per target quarter, at the month-2 snapshot: s_q = a + b × gap_q + e, where s_q = (E_q − C_q) / max(|C_q|, F) is the consensus surprise. Pass if b > 0 with Newey-West (2 lags) t > 1.96.
- **E2 (accuracy, reported).** Model versus consensus MAE and RMSE in index EPS points on the same quarters, plus a Diebold-Mariano test (Newey-West, 2 lags). The model need not beat consensus to be informative.
- **Descriptive only.** All three monthly snapshots, with standard errors clustered by target quarter. Independent-quarter counts are always stated.
- **Verdict:** *Supported* if E1 passes in development and b > 0 in the holdout; *Development only* if E1 passes but the holdout b ≤ 0; otherwise *Not supported*.

**Claim R: return forecasting**
- **R1 (primary, development).** Out-of-sample R² = 1 − Σ(y − μ̂)² / Σ(y − ȳ_expanding)² > 0. Clark-West MSPE-adjusted test, one-sided, t > 1.645 (Newey-West, 3 lags).
- **R2 (holdout).** Out-of-sample R² of the frozen primary > 0, with the Clark-West statistic reported.
- **Incremental content (diagnostic; never a gate or a replacement).** Clark-West nested tests of primary versus D2 (does the gap add?), primary versus D1 (do rates and credit add?), and D3 versus primary (the interaction). Also reported: a Mincer-Zarnowitz slope of y on μ̂ (Newey-West), and the coefficient paths.
- **Verdict:** *Supported* if R1 and R2 pass; *Development only* if R1 passes and R2 fails; otherwise *Not supported*.

**Claim T: profitable trading** (net of base costs; doubled costs reported alongside)
- **T1 (development walk-forward).** The strategy's net excess-return Sharpe exceeds SPY buy-and-hold's on the same dates, **and** monthly alpha against SPY excess returns has Newey-West (3 lags) t > 2.
- **T2 (holdout).** Net excess-return Sharpe exceeds SPY buy-and-hold's.
- **Verdict:** *Supported* if T1 and T2 pass; *Development only* if T1 passes and T2 fails; otherwise *Not supported*. A result that fails at doubled costs is stated with the verdict.
- **Low power:** with about 24 holdout months, the standard error of an annualized Sharpe difference is large (roughly 0.7 or more). Holdout verdicts are statements about a small sample.

**Combined reading**

| E | R | T | Conclusion |
|---|---|---|---|
| ✓ | ✓ | ✓ | Supported end to end |
| ✓ | ✓ | ✗ | Predictability exists but does not survive costs or beat holding SPY |
| ✓ | ✗ | — | The gap predicts earnings, but prices already reflect it: consensus ≠ what prices imply |
| ✗ | ✓ | — | Returns are predicted, but not through the earnings channel; read D1/D2 |
| ✗ | ✗ | — | Rejected |

## 11. Robustness, diagnostics and trial accounting [FIXED]

- **Development-only robustness (primary specification only).** Δry and Δcs measured over the 20 and over the 40 trading days ending at the latest value published by the cutoff, instead of month-end to month-end. Doubled costs. Two chronological halves of the development walk-forward (split by decision count). The best run is never promoted.
- **Distinct specifications (trials).**
  - S0 primary; D1; D2; D3; R20; R40, for **6 trials** in total.
  - Cost stress, subperiods and benchmarks are views, not trials.
  - Any additional specification needs an amendment and counts as a trial.
  - The Deflated Sharpe Ratio (Bailey & López de Prado 2014) uses N = distinct specifications, with raw logged rows also disclosed.
- **Holdout runs:** the frozen primary plus only the diagnostics and benchmarks listed in the release spec (Prompt 8). No parameter sweeps on the holdout.

## 12. Reporting metrics and claim/evidence checklist [FIXED]

**Metrics** (development walk-forward and holdout shown separately; base and doubled costs):
- compounded annual return;
- annualized volatility (daily ledger, √252);
- excess-return Sharpe against the same cash proxy;
- maximum drawdown;
- turnover (annual dollars traded across both legs ÷ average NAV);
- switches per year, trade count, time invested in SPY;
- market beta and alpha against SPY;
- forecast accuracy (MAE, RMSE, out-of-sample R², sign hit rate);
- earnings MAE and RMSE by target quarter;
- uncertainty: Newey-West standard errors and stationary block-bootstrap 95% intervals (mean block 6 months, 2,000 draws, seed in config);
- the compounded equity curve and drawdown chart.

| Claim / requirement | Evidence (artifact, prompt) | Status |
|---|---|---|
| Hypothesis committed before data and results | This file's commit timestamp | Pending commit |
| Coverage-driven choices frozen before any predictive examination | F1 amendment rows (§14), Prompt 2 | Not started |
| Publication-time alignment, no lookahead | Alignment tests and five traced decisions (Prompts 3, 5, 8) | Not started |
| E: gap predicts consensus surprise | E1/E2 tables, by target quarter (Prompt 5) | Not started |
| R: out-of-sample predictability | R1 and diagnostics with matched dates (Prompt 6) | Not started |
| T: net trading value against buy-and-hold | Ledger, metrics, benchmarks, doubled costs (Prompts 7–8) | Not started |
| All trials disclosed; Deflated Sharpe | Trial log (Prompt 7) | Not started |
| Holdout evaluated once, after freeze | Release spec and lock (Prompts 8–9) | Not started |
| Prior SPY exposure disclosed | §0, CONTEXT.md §4, note (Prompt 10) | Recorded |

## 13. Provisional register (resolved at Freeze F1, end of Prompt 2)

| ID | Item | Default / candidates | Resolution criterion |
|---|---|---|---|
| P1 | Common data cutoff D | Retrieval date in Prompt 2 | Same cutoff for every source |
| P2 | Cash proxy and number of legs | BIL (traded, 2 legs); fallback 3-month T-bill account (1 leg) | BIL if its coverage supports the eligible history; record fees and price risk |
| P3 | Price source, distribution and split conventions, NYSE calendar and early closes | To be verified (sponsor or public sources) | Raw opens plus explicit distributions verified on known ex-dates |
| P4 | Consensus source and snapshot semantics | Dated bottom-up S&P 500 calendar-quarter EPS with target quarter | Must be historical snapshots with dates; otherwise BLOCKED |
| P5 | EPS definition and matching realized source | Operating EPS, same provider basis | Definition match documented |
| P6 | Realized-outcome vintage and availability lag | First release; else conservative lag | Fixed before any fit |
| P7 | Real-yield series and publication lag | FRED DFII10 (10-year TIPS constant maturity) | Coverage and release timing verified |
| P8 | Credit-spread series, history and lag | ICE BofA US Corporate OAS (FRED BAMLC0A0CM) | Actual available history checked; no yield substituted for a spread |
| P9 | Nominal GDP real-time vintages and release timestamps | ALFRED GDP vintages | Vintage dates verified |
| P10 | Broad dollar series and lag | FRED DTWEXBGS; earlier history chained by log changes from DTWEXB | Overlap and release timing verified |
| P11 | Numerical transformations | Floor k = 0.5, L = 8; clip ±4 standard deviations | Changed only for a documented input property |
| P12 | Warmup minimums | 32 quarters; 60 months | Confirmed, or raised; never lowered without an amendment |
| P13 | Inner-validation initial sizes | 20 quarters; 36 months | Must fit inside the warmups |
| P14 | Holdout N, N_h, boundary decisions, quarantine timestamps | Rule in §9 | From coverage metadata only |
| P15 | Target-quarter mapping against the consensus source | Calendar quarter containing the decision month | The source provides the quarter at all three month-ends |

## 14. Amendment log (append only)

| ID | Date/time (ET) | Section(s) | Change | Reason | Any results seen before the change? |
|---|---|---|---|---|---|
| A0 | 2026-10-03 19:10 | All | Initial provisional specification (Prompt 1) | Pre-registration before data | None for this strategy; no macro_equity data pulled. SPY's 2021–2026 path previously seen through GLP-1 (§0) |
| A1 | 2026-10-03 19:37 | §11 (clarification; no design change) | The six distinct specifications are the trial count for the Deflated Sharpe Ratio, **not** the complete research-attempt count. Every search, source inspection, download, decision and experiment that can influence data or model selection is appended to `results/research_log.csv` (append-only, `macro_equity.research_log`), and the full count is disclosed in the note | Aman's Prompt 2 instruction; makes the disclosure complete | No results seen (source discovery only) |
| A2 | 2026-10-03 19:37 | §0 (added disclosure) | **Incidental holdout-period exposure:** at 19:21 ET a web-search results page showed FactSet bottom-up consensus EPS levels for Q4 2025 and Q1 2026, a later Q3 estimate, and Q1 2026 reported year-over-year growth. No gap, signal or return was computed. Later searches were restricted to pre-2024 years | Disclosure under ground rule 7; §0 is fixed, so the addition is logged here | No predictor-outcome results seen; holdout-period consensus levels seen incidentally (stated) |
| A3 | 2026-10-03 19:37 | §13 register; Freeze F1 | **Feasibility verdict: BLOCKED. Freeze F1 not performed; P1–P15 remain provisional.** Free sources do not provide (i) dated per-share consensus with same-basis actuals long enough for the frozen warmups (best candidate, FactSet Earnings Insight: actuals from Q3 2009, so under 12 development walk-forward months), or (ii) ICE BofA corporate OAS history (FRED keeps 3 years since April 2026; ICE restricts reproduction). No warmup, definition or predictor is changed. Details: DATA_FEASIBILITY.md | Coverage, definitions and licensing only | No results seen (coverage metadata and a few development-period report pages; no outcome data) |

## References

- Bailey, D. H., & López de Prado, M. (2014). The Deflated Sharpe Ratio. *Journal of Portfolio Management*, 40(5).
- Bordalo, P., Gennaioli, N., La Porta, R., & Shleifer, A. (2019). Diagnostic Expectations and Stock Returns. *Journal of Finance*, 74(6).
- Campbell, J. Y., & Thompson, S. B. (2008). Predicting Excess Stock Returns Out of Sample. *Review of Financial Studies*, 21(4).
- Clark, T. E., & West, K. D. (2007). Approximately Normal Tests for Equal Predictive Accuracy in Nested Models. *Journal of Econometrics*, 138(1).
- De La O, R., & Myers, S. (2021). Subjective Cash Flow and Discount Rate Expectations. *Journal of Finance*, 76(3).
- Diebold, F. X., & Mariano, R. S. (1995). Comparing Predictive Accuracy. *Journal of Business & Economic Statistics*, 13(3).
- Gilchrist, S., & Zakrajšek, E. (2012). Credit Spreads and Business Cycle Fluctuations. *American Economic Review*, 102(4).
- Hoerl, A. E., & Kennard, R. W. (1970). Ridge Regression. *Technometrics*, 12(1).
- Hugon, A., Kumar, A., & Lin, A.-P. (2016). Analysts, Macroeconomic News, and the Benefit of Active In-House Economists. *The Accounting Review*, 91(2).
- Sharpe, S. A., & Gil de Rubio Cruz, A. (2024). Predicting Analysts' S&P 500 Earnings Forecast Errors and Stock Market Returns using Macroeconomic Data and Nowcasts. FEDS 2024-049, Federal Reserve Board. https://doi.org/10.17016/FEDS.2024.049
- So, E. C. (2013). A New Approach to Predicting Analyst Forecast Errors: Do Investors Overweight Analyst Forecasts? *Journal of Financial Economics*, 108(3).
