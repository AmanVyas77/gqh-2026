# Pre-Registered Hypothesis H2: Cattle Prices and Beef-Buying Equities

**Gator Quant Hacks 2026 · Systematic Trading Track**
**Status:** Written 2026-10-03, after H1 (HYPOTHESIS.md) was rejected on every pre-registered test, and before any TSN, TXRH, XLP or XLY price data was loaded. SPY daily prices were downloaded earlier for H1's factor checks only. The commit timestamp of this file is the record. Sections 1–7 are frozen once committed; later changes go in Section 8.

---

## 1. Hypothesis

We expect **beef-buying equities (Tyson Foods, Texas Roadhouse)** to **underperform their sectors in the month after Live Cattle futures rise, and outperform after they fall**, because **cattle are a major input cost for both firms, but investors in these stocks underreact to input-cost news that originates in a separate market**. The edge persists because **cattle futures and food/restaurant equities are followed by different investors, and beef is only one segment (Tyson) or one cost line (Texas Roadhouse), which slows how fast the news is priced** (Hong, Torous & Valkanov 2007; Cohen & Frazzini 2008; Menzly & Ozbas 2010; Cohen & Lou 2012).

If true:
- **Q1:** hedged returns fall in the same month cattle prices rise (the exposure exists);
- **Q2:** this month's cattle move predicts *next* month's hedged returns, with a negative sign; so
- **Q3:** shorting the basket after cattle rallies (and buying it after cattle falls) earns positive returns net of costs.

It fails if **the exposure exists (Q1) but next-month returns are not predicted (Q2): the equities price cattle news immediately.**

## 2. Relationship to H1

H1 found that the futures-implied feedlot margin had no forward-looking information about cattle prices. H2 does not use the margin or any H1 diagnostic. Its signal is the realized cattle price move, and its outcome (equity returns) has not been examined. It is a separate hypothesis, conceived after H1 failed, and is disclosed as such.

## 3. Universe and data

| Ticker | Role | Cattle exposure |
|---|---|---|
| TSN | Traded | Packer; its Beef segment buys fed cattle |
| TXRH | Traded | Steakhouse chain; beef is its largest commodity cost (10-K) |
| XLP | Hedge for TSN | Consumer Staples Select Sector SPDR ETF |
| XLY | Hedge for TXRH | Consumer Discretionary Select Sector SPDR ETF |

- **Equity prices:** daily split- and dividend-adjusted closes from yfinance, cited.
- **Cattle prices:** the existing in-sample Live Cattle settlement panel from H1.
- **Excluded:** JBS, whose U.S. listing (2025) falls entirely in the out-of-sample window; restaurants where beef is a small share of costs (e.g., MCD).
- **Survivorship:** the universe is chosen by business exposure as of 2010, not by later performance. Beef-exposed firms that were private or delisted are not covered; this is disclosed as a limitation.

## 4. Signal and positions

**Cattle signal**, computed at each month-end t:

**s_t = r_LE(t) ÷ σ_LE(t)**

- **r_LE(t):** the month's return on the front Live Cattle contract with at least 45 calendar days to its last trading day at the start of the month, computed within that contract (no splicing). The 45-day rule keeps the holding month out of the delivery month.
- **σ_LE(t):** the standard deviation of r_LE over the 36 prior months, excluding month t.
- **In words:** how large this month's cattle move was, relative to a normal month.

**Hedged basket.** For each stock i, the daily hedged return is h_i = r_i − β_i × r_sector(i), where β_i is the stock's beta on its sector ETF estimated over the prior 252 trading days and re-estimated at each month-end. The basket is the equal-weighted average of the two hedged returns.

**Position:**

**w_t = −clip(s_t ÷ 2, −1, 1) × (10% ÷ σ̂_basket), with |w_t| ≤ 2**

- **The minus sign:** cattle up means short the basket; cattle down means long.
- **clip(x, −1, 1):** x is capped between −1 and +1, so conviction is full at |s_t| ≥ 2.
- **σ̂_basket:** annualized volatility of the basket's daily hedged returns over the prior 60 trading days.
- **Timing:** rebalance monthly. The signal uses the month-end Live Cattle settlement; trades execute at the close of the next trading day (1-day lag).
- **Legs:** each stock gets w_t ÷ 2 of capital, hedged with −(w_t ÷ 2) × β_i in its sector ETF.

## 5. Costs

- 5 bps per side on TSN and TXRH; 2 bps per side on XLP and XLY (large, liquid names: half-spread plus slippage).
- Short borrow: 0.50% a year on short notional.
- **Stress test:** double all costs. **Every reported result is net of costs.**

## 6. Tests, sample and decision rules

**Out-of-sample:** 2024-10-01 onward, the same split as H1. Equity data for development stops at 2024-09-30. Evaluated once.

- **Q1 (exposure):** regress the basket's monthly hedged return on the same month's r_LE. Expect β < 0 with Newey-West t < −2 (2 lags).
- **Q2 (lag):** regress next month's basket hedged return on this month's s_t. Expect β < 0 with Newey-West t < −2 (2 lags).
- **Q3 (trading):** in-sample mean monthly net return > 0 with Newey-West t > 2; out-of-sample net Sharpe > 0.

| Q1 | Q2 and Q3 | Conclusion |
|---|---|---|
| ✓ | ✓ | **Supported:** the equities underreact to cattle cost news |
| ✓ | ✗ | **Exposure real, priced immediately:** an efficient-market finding |
| ✗ | — | **Rejected:** no measurable cattle exposure in these stocks |

**Trials (the complete list):** the primary (two-stock basket, 1-month signal), plus four one-at-a-time alternatives: a 3-month cattle return as the signal; SPY as the hedge instead of the sector ETFs; TSN alone; TXRH alone. That is **5 trials for H2**, reported alongside H1's 24 (29 for the project). The Deflated Sharpe Ratio is reported for H2's 5 trials and for all 29.

**Additional checks (not trials):** Fama-French five factors plus momentum (Ken French library, monthly); returns by calendar year; and the same stress tests and liquidity reports used for H1 (named episodes, ADV participation, capacity).

## 7. Risk limits

- Gross exposure ≤ 2× capital; each stock ≤ 1× capital.
- Idiosyncratic risk is high with two names (earnings surprises, non-beef segments). It is reported, not hedged.

## 8. Deviation log

| Date/time (ET) | Change | Reason | Any results seen before the change? |
|---|---|---|---|
| 2026-10-03 23:17 | **Implementation choices for the primary specification (no rule changed).** (a) r_LE(t) runs from the last LE settlement of month t−1 to the last LE settlement of month t, on the contract selected at the month t−1 settlement date as the first LE contract whose last trading day is at least 45 calendar days later. (b) σ_LE is the sample standard deviation (ddof = 1) of the 36 prior monthly r_LE; the first signal is July 2013. (c) Month-end t is the last LE settlement date of the calendar month; trades execute at the close of the first NYSE trading day after t. (d) β_i is the OLS slope (with intercept) of the stock's daily return on its sector ETF's daily return over the 252 trading days ending at t, held until the next rebalance. (e) σ̂_basket is the annualized (×√252, ddof = 1) standard deviation of the basket's daily hedged returns over the 60 trading days ending at t, using the β_i estimated at t. (f) Section 7's "gross exposure ≤ 2× capital" counts stock and hedge legs: if \|w\|/2 × (2 + β_TSN + β_TXRH) > 2, w is scaled down to meet it; "each stock ≤ 1×" follows from \|w\| ≤ 2. (g) Positions are set in dollars at the execution close and held (notional drifts with price) until the next rebalance; each rebalance trades the difference, and costs apply per side to the traded notional. (h) Borrow of 0.50% a year accrues on short notional (stock or ETF legs), per trading day at 0.50%/252; doubled in the cost stress. (i) Returns are P&L on fixed capital with no interest on cash, as in H1. (j) Monthly returns are sums of daily returns within the calendar month; Q1 and Q2 use calendar-month sums of the daily hedged basket return built with the β_i estimated at the prior month-end; Q3's Newey-West t uses 2 lags, the lag count Section 6 gives for H2's tests. (k) Equity data: yfinance split- and dividend-adjusted closes from 2009-01-01 to 2024-09-30; back-adjustment for later dividends rescales the whole in-sample history by a constant and leaves in-sample returns unchanged. (l) Only the primary trial is run in this step; the four alternative trials are not run. | The specification leaves these points open; recorded before any TSN, TXRH, XLP or XLY data was loaded. | No H2 results seen (no equity data loaded) |
| 2026-10-03 23:23 | **Bug fix (reporting only; no strategy change).** The intercept-only Newey-West helper in `src/h2.py` returned NaN, so the first run printed no t-statistic for Q3 or the benchmark mean. It was fixed and those t-statistics were recomputed from the saved daily returns; positions, returns, costs and Q1/Q2 are unaffected and the backtest was not re-run. | Implementation error. | Yes: primary results had been printed (the fix changes only the missing t-statistics) |
