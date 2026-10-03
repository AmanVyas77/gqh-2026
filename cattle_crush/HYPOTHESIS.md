# Pre-Registered Hypothesis: Feedlot Margins and Live Cattle Futures

**Gator Quant Hacks 2026 · Systematic Trading Track**
**Team:** [names]
**Status:** Written before any backtest. The commit timestamp of this file is the record.
Sections 1–8 are frozen once committed. Any later change is logged in Section 9, never made by editing 1–8.

---

## 1. Hypothesis

We expect **deferred CME Live Cattle futures** to **earn positive returns** over the **~5 months** after feedlot feeding margins turn deeply negative, because **negative margins cut feedlot placements, which shrinks fed-cattle supply 5–6 months later, and short-hedging feedlots pay speculators a premium to carry price risk**. The edge persists because **the biological feeding lag is fixed and feedlots must hedge to finance cattle inventory**.

If true, low margins should predict:
- **P1:** fewer placements over the next 3 months, and
- **P2:** positive roll-adjusted Live Cattle futures returns, net of costs.

It fails if **margins predict placements but not futures returns (P3: the futures curve already prices the supply cut).**

## 2. Economic mechanism

**Causal chain:** margin < 0 → fewer placements (1–3 months) → fewer fed cattle marketed (5–6 months after placement) → tighter supply → higher fed-cattle prices.

**Who is on the other side**
- **Feedlots** short Live Cattle futures to lock the sale price of cattle on feed. This is structural hedging, often required by lenders.
- **Cow-calf producers** sell feeder cattle and may absorb margin shocks through feeder prices.
- **Packers** buy finished cattle.

**Why it might not be arbitraged away.** USDA placement data are public, so P3 is the main threat. Any edge must come from one of two sources:
- (a) a hedging-pressure risk premium (Keynes 1930; de Roon, Nijman & Veld 2000; Basu & Miffre 2013), or
- (b) slow incorporation of supply information.

Cattle supply dynamics are described in Rosen, Murphy & Scheinkman (1994).

## 3. Feeding margin (signal input)

**M_t = W_out × LE_t − W_in × FC_t − B × C_t − K**

| Symbol | Plain-English meaning | Value / source |
|---|---|---|
| M_t | Projected profit per head, in dollars, for a steer placed on day t | computed |
| W_out | Finished sale weight | 1,400 lb |
| LE_t | Day-t settlement of the **sale contract** (Section 4), converted from cents/lb to $/lb | Databento |
| W_in | Placement weight | 800 lb |
| FC_t | Day-t settlement of the **feeder contract** (Section 4), in $/lb | Databento |
| FCR | Feed conversion ratio: lb of corn-equivalent feed per lb of weight gained | 6.0 |
| B | Bushels eaten = (W_out − W_in) × FCR ÷ 56 lb per bushel | (600 × 6.0) ÷ 56 = 64.29 bu |
| C_t | Day-t settlement of the **corn contract** (Section 4), in $/bushel | Databento |
| K | Non-corn costs per head (yardage, vet, interest, death loss) | $350, constant |

Because the signal is a z-score (Section 5), **K cancels out of the signal entirely**. K matters only when comparing margin *levels* to published feedlot closeouts (Iowa State *Estimated Livestock Returns*, K-State *Focus on Feedlots*).

## 4. Contract selection (applied on each date t, using only expiries known at t)

- **Sale contract (LE):** the first Live Cattle contract whose last trading day is at least t + 150 calendar days. 150 days ≈ 600 lb of gain at ~4 lb/day.
- **Feeder contract (GF):** the nearest Feeder Cattle contract with at least 30 calendar days to its last trading day.
- **Corn contract (ZC):** the first corn contract whose last trading day is at least t + 75 calendar days, the midpoint of the feeding period.
- **Prices and expiries:** official daily settlement prices; expiries come from exchange instrument definitions, not hard-coded calendars.

## 5. Signal

Computed at each month-end t (the last trading day of the month):

**z_t = (M_t − mean of M over the 36 prior month-ends) ÷ (standard deviation of M over the 36 prior month-ends)**

In words: how many standard deviations today's margin sits above (+) or below (−) its average over the previous three years. The window excludes month t itself.

- The primary specification has no seasonal adjustment; it is tested in robustness.
- The first valid signal is 36 months after data start.

## 6. Strategies (pre-registered; this is the complete list)

### Variant A: Outright Live Cattle (PRIMARY)

**w_t = clip(−z_t ÷ 2, −1, 1) × (σ\* ÷ σ̂_t), with |w_t| ≤ 2**

- **w_t:** notional exposure to the sale contract, as a multiple of capital.
- **clip(x, −1, 1):** x is capped between −1 and +1. This gives full long at z ≤ −2 and full short at z ≥ +2.
- **σ\*:** target annual volatility = 10%.
- **σ̂_t:** annualized standard deviation of the sale contract's daily returns over the prior 60 trading days.
- **2:** maximum gross leverage.

### Variant B: Crush spread

Hold U_t "head units". One head unit is:
- long W_out lb of the LE sale contract,
- short W_in lb of the GF contract, and
- short B bushels of the ZC contract.

This is roughly 2.19 LE : 1 GF : 0.80 ZC contracts.

**U_t = clip(−z_t ÷ 2, −1, 1) × (σ\* × Capital ÷ σ̂$_t)**

- **σ̂$_t:** annualized dollar volatility of one head unit's daily P&L over the prior 60 trading days.
- A positive U_t means long the margin, i.e., a bet that it widens.

### Variant C: Variant A filtered by hedging pressure

**HP_t = (PMPU short − PMPU long) ÷ (PMPU short + PMPU long)**, for Live Cattle, from CFTC Disaggregated Commitments of Traders (futures only).

- **PMPU:** the CFTC's "Producer/Merchant/Processor/User" category, i.e., commercial hedgers.
- **HP_t > 0:** hedgers are net short.

Rules:
- Take Variant A's long position only if HP_t is above its trailing 156-week median.
- Take Variant A's short position only if HP_t is below that median.
- Otherwise stay flat.
- HP_t counts as known only from the business day after its public release.

### Rules common to all variants

- **Rebalancing:** monthly. The signal uses the month-end settlement; trades execute at the next trading day's settlement (1-bar lag).
- **Rolling:** roll whenever the selected contract changes at a rebalance.
- **Returns:** excess returns (no interest on collateral), computed within each contract. No spliced continuous series.
- **Limit-locked days:** if a trade day is limit-locked (daily high = low), execute on the first following non-locked day.

## 7. Transaction costs

Cost per contract, per side: **1 tick of slippage + $2.50 commission and exchange fees.**

| Contract | Tick value | Cost per side | Approx. bps at reference price |
|---|---|---|---|
| LE | 0.025¢ × 40,000 lb = $10.00 | $12.50 | $12.50 ÷ ($2.25 × 40,000 = $90,000) ≈ 1.4 bps |
| GF | 0.025¢ × 50,000 lb = $12.50 | $15.00 | $15.00 ÷ ($3.00 × 50,000 = $150,000) = 1.0 bps |
| ZC | 0.25¢ × 5,000 bu = $12.50 | $15.00 | $15.00 ÷ ($4.50 × 5,000 = $22,500) ≈ 6.7 bps |

- **Stress test:** double the costs, to 2 ticks + $5.00 per side.
- **Every reported result is net of costs.**

## 8. Data split, tests, and decision rules

### Out-of-sample period

- History starts 2010-06-06 (Databento CME Globex), about 16.3 years.
- 20% of that would be 3.3 years, so the 2-year cap binds.
- **OOS = 2024-10-01 onward.**
- The OOS period is evaluated once, after all in-sample work is frozen.

### Pre-registered tests

- **P1 (mechanism):** Regress the year-over-year log change in total placements over months m+1 to m+3 on z_t. Placements are USDA NASS *Cattle on Feed*, U.S. feedlots with 1,000+ head capacity. Expect β > 0. Use Newey-West standard errors with 3 lags.
- **P2 (trading):** Variant A in-sample must have a mean monthly net return > 0 with a Newey-West t-stat > 2 (5 lags), and its OOS net Sharpe must be > 0.
- **P3 (kill test):** At each month-end t, regress two quantities on z_t:
  - (i) the sale contract's return from t to its last trading day, and
  - (ii) the "spot" change over the same period: the sale contract's final settlement minus the front Live Cattle contract's settlement at t. The front contract stands in for spot.
- **Leg decomposition:** Split the 5-month change in M into its LE, GF, and corn contributions. Report the means conditional on z_t < −1.

### Decision table

| P1 | P2 | Conclusion |
|---|---|---|
| ✓ | ✓ | **Supported:** the supply shock is underpriced or earns a premium |
| ✓ | ✗ (and P3 shows spot predicted, futures not) | **Mechanism real, curve already prices it.** Report as an efficient-market finding |
| ✗ | — | **Rejected:** no supply response at this horizon |

### Robustness (one parameter at a time around the primary spec; all runs reported, none selected after the fact)

- z lookback: 24 or 48 months
- Sale horizon: 120 or 180 days
- FCR: 5.5 or 6.5
- Seasonal adjustment on: margin minus its trailing 5-year same-calendar-month mean

That is **8 specifications per variant × 3 variants = 24 trials**. Cost stress is reported for every run but is not counted as a trial.

### Trial disclosure

- Every backtest run is logged automatically to `results/trial_log.csv`.
- The total count is disclosed in the note.
- A Deflated Sharpe Ratio (Bailey & López de Prado 2014) is computed using that count.

### Additional checks (not trials)

- Regress Variant A's returns on:
  - a long-only roll-adjusted Live Cattle position,
  - 12-month Live Cattle time-series momentum, and
  - SPY.
- Returns by calendar year.
- A capacity curve using a square-root market-impact model.

## 9. Deviation log

| Date/time (ET) | Change | Reason | Any results seen before the change? |
|---|---|---|---|
| 2026-10-02 22:32 | **OOS boundary for forward-looking tests.** P1, P3 and the leg decomposition include a month-end t only if every outcome date they use is before oos_start (2024-10-01). NASS placements are dated by reference month, not release date. | These tests use outcomes after t. Section 8 requires the OOS period to be evaluated once, so in-sample tests must not touch data dated 2024-10-01 or later. | No results seen |
| 2026-10-02 22:32 | **Hedging-pressure availability (Variant C).** HP_t counts as known from the later of (a) the COT as-of date + 6 calendar days and (b) the business day after the actual public release. Actual release dates come from CFTC's published release schedules for every week that deviates from the normal Friday release, including holiday delays and the 2013 and 2018–19 shutdown backlogs. | Section 6 says "the business day after its public release". A fixed +6-day rule would use data before its release in delayed weeks. | No results seen |
| 2026-10-02 22:32 | **P1 pass rule.** P1 passes if β > 0 with a Newey-West (3 lags) t-stat > 2. | Section 8 gives the expected sign but no significance threshold. | No results seen |
| 2026-10-02 22:32 | **P3 inference.** Both P3 regressions use Newey-West standard errors with 6 lags. "Spot predicted, futures not" means the spot-change slope on z_t is negative with an absolute NW t-stat > 2, and the futures-return slope has an absolute NW t-stat < 2. | Section 8 gives no standard errors or pass rule for P3. Outcome horizons of 5–7 months overlap across monthly observations. | No results seen |
| 2026-10-02 22:32 | **P3 units (supplemental).** In addition to (i) as a return, report the sale contract's change from t to its last trading day in $/lb (F_T − F_t), so that (ii) minus this change equals the sale-minus-front spread at t. Tests (i) and (ii) are unchanged. | (i) is a percentage return and (ii) is a $/lb change, so they are not directly comparable. | No results seen |
| 2026-10-02 22:32 | **Variant B leverage.** Variant B has no gross leverage cap, as written in Section 6. Its gross leverage is reported. | Section 6 caps only Variant A. Recorded so the uncapped choice is explicit. | No results seen |
| 2026-10-02 22:32 | **Limit-locked days in multi-leg trades.** If any leg of a Variant B trade, or either side of a roll, is limit-locked on the execution day, the whole trade moves to the first following day on which none of the contracts involved is locked. | Section 6 defines the lock rule per contract. Deferring legs separately would break the head-unit hedge or leave a roll half done. | No results seen |
| 2026-10-02 22:32 | **Trial count for the Deflated Sharpe Ratio.** Every backtest run is logged to `results/trial_log.csv`. N for the DSR is the number of distinct (variant, parameter set) configurations (24 expected), and the raw row count is also disclosed. Unit tests on synthetic data write to a temporary log, not the trial log. | Section 8 says "using that count". Reruns of an identical specification during development are not separate trials. | No results seen |
| 2026-10-02 22:32 | **Robustness reporting windows.** Every spec is reported on its full available sample and on a common window starting at the latest start date among the non-seasonal specs. The seasonal spec is also compared with the primary on the seasonal spec's own window. These are extra views of the same 24 trials, not new trials. | The specs have different first valid signal dates (24/36/48-month lookbacks; the seasonal spec needs 5 extra years), which confounds full-sample comparisons. | No results seen |
| 2026-10-02 23:13 | **Disclosure: NASS probe returned post-cutoff rows (no change to the design).** The first NASS series probe requested years 2009–2023 with `year__GE`/`year__LE`; Quick Stats ignored `year__LE`, so the response held placement rows from 2024-10 through 2026 in memory for that one run. No values from those months were displayed or saved; the only output touching them was each series' last year (2026) and row counts. The request now uses explicit `year` and `reference_period_desc` values, and `download.py` raises an error on any row dated 2024-10 or later in an in-sample request. The pinned series is CATTLE, ON FEED - PLACEMENTS, MEASURED IN HEAD (all weights, capacity 1,000+ head). | Rule 3 of the build spec: no data dated on or after oos_start outside run_oos.py. | No results seen (no backtest or test run yet) |
| 2026-10-03 15:34 | **Missing feed days.** Dates with no settlement records and no trades for a product in the Databento feed are non-trading days for that product, with no forward-filling. In-sample: LE and GF on 2012-02-06 to 2012-02-09, 2014-06-12 and 2014-09-23 to 2014-09-25; ZC on 2020-02-27 and 2020-06-30. M_t and month-ends require settlements for all three selected contracts on the same date. If an execution day has no settlement for any traded leg, the whole trade moves to the first following day on which every leg has a settlement, as for limit-locked days. P&L across a gap uses the settlements on either side of it. | Sections 4–6 assume a settlement on every trading day; the source data has none on these dates. | No results seen (data audit and contract-selection checks only) |
| 2026-10-03 15:34 | **P3: LEZ2014 has no final settlement.** The feed has no settlement or trades for LEZ2014 on its last trading day (2014-12-31). The P3 observations whose sale contract is LEZ2014 (month-ends 2014-06-30 and 2014-07-31) are dropped and disclosed; no substitute price is used. | P3 (i) and (ii) need the sale contract's final settlement. | No results seen (data audit and contract-selection checks only) |
| 2026-10-03 15:34 | **Variant B: feeder contract expiring before the next execution.** The 30-day rule can select a GF contract that expires before the next rebalance executes. When that happens, the GF leg is closed at the GF cash-final settlement (CME Feeder Cattle Index, dated the business day after the last trading day), charged the $2.50 commission/fee component only with no slippage, and the replacement GF contract is opened at the next scheduled execution. The number of such events is reported. The 30-day selection rule is unchanged. | Section 6 does not cover a selected contract expiring while held. | No results seen (data audit and contract-selection checks only) |
| 2026-10-03 15:43 | **Pre-declared diagnostic 1: seasonality (not a trial; primary spec unchanged).** (a) P1 is also reported with the seasonally adjusted z: M_t minus the mean of M at the same calendar month in each of the previous 5 years (all 5 required), z-scored over the 36 prior month-ends excluding t, the same adjustment as the pre-registered robustness spec. (b) For each trading variant, a "seasonal-only" version is reported: the same position rule applied to the z-score of the seasonal component itself (the trailing 5-year same-calendar-month mean of M, z-scored over its own 36 prior month-ends, excluding t), together with the correlation of the two variants' positions and monthly net returns, and an OLS regression of the variant's monthly net returns on its seasonal-only version (Newey-West, 5 lags). | Prompted only by an input property: calendar month explains 46% of the variance of month-end M_t, while P1's outcome (year-over-year placements) is deseasonalized. Diagnostics are reported without pass/fail, do not enter the decision table or the Deflated Sharpe trial count, and any backtest runs they need are logged in `results/trial_log.csv` flagged as diagnostics. | No results seen (margin series only; no z-scores, placement regressions or returns computed) |
| 2026-10-03 15:43 | **Pre-declared diagnostic 2: revenue-leg control (not a trial; primary spec unchanged).** z_LE is the z-score of 1,400 × the sale-contract LE settlement over the same 36 prior month-ends, excluding t. (a) P1 is also reported with z_t and z_LE as joint regressors (Newey-West, 3 lags). (b) Variant A's monthly net returns are regressed on an LE-only Variant A (the same rules with z_LE in place of z_t; Newey-West, 5 lags), and the correlation of their monthly net returns is reported. This tests whether the feeder and corn legs add information beyond LE's own price. | Prompted only by an input property: the LE leg accounts for 75% of the variance of month-to-month changes in M. Same status as diagnostic 1. | No results seen (margin series only; no z-scores, placement regressions or returns computed) |
