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
| — | — | — | — |
