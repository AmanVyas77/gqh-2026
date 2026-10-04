# V2 development results (holdout still locked)

**Window.** Trading ran from 2015-08-03 to 2024-10-02: 2,308 sessions and 111 monthly formations. The specification is in `v2/SPEC_V2.md` and was frozen before fitting. The raw numbers are in `v2/results/summary.json`.

**Universe.**

- Point-in-time S&P 500 membership was reconstructed. There were 504–508 members per formation, of which 388–489 were eligible.
- 14–103 members per formation had no Yahoo history, mostly former members. Their absence makes the sample **survivorship-biased**.
- 0–12 former members per formation failed the identity check.
- Sector labels are modern GICS. 23–64 eligible former members per formation have no label, so the sector arm cannot use them.
- Prices are adjusted-close total returns. This is an exposure simulation, not a raw-share or stock-loan execution ledger.

## Headline: negative after costs in every arm

| Arm | Run | Total return | CAGR | Ann. vol | Sharpe | Max DD |
|---|---|---|---|---|---|---|
| Simple (primary) | gross | +1.0% | +0.1% | 1.3% | 0.09 | −3.1% |
| Simple (primary) | base costs | **−17.0%** | −2.0% | 1.3% | −1.55 | −17.1% |
| Simple (primary) | 2× costs | −31.7% | −4.1% | 1.3% | −3.11 | −31.8% |
| PCA | gross | +6.2% | +0.7% | 1.3% | 0.51 | −2.6% |
| PCA | base costs | **−12.8%** | −1.5% | 1.3% | −1.13 | −12.9% |
| PCA | 2× costs | −28.4% | −3.6% | 1.4% | −2.70 | −28.4% |
| Sector | gross | +2.8% | +0.3% | 1.3% | 0.24 | −2.9% |
| Sector | base costs | **−15.5%** | −1.8% | 1.3% | −1.44 | −15.7% |
| Sector | 2× costs | −30.6% | −3.9% | 1.3% | −3.05 | −30.6% |

## Activity, exposure and costs (base costs)

Figures are for the simple arm; the other two arms are within about 1%.

- **Trades.** 750 entries, in 716 pair-months with at least one trade.
- **Activity.** On average 2.9 of the 10 selected pairs held a position, and the book held something on 87% of days.
- **Exposure.**
  - Gross exposure averaged 29% and peaked at 80%.
  - Net dollar exposure was 0 by construction, since legs are equal-dollar and rebalanced daily.
- **Turnover.** About 17× NAV a year. Roughly 16× comes from entering and exiting, and about 1× from daily rebalancing.
- **Cumulative costs.** Trading costs came to 15.6% of NAV and borrow to 4.0%. Together that is about 2.1% a year, against a gross return of 0.1–0.7% a year.

## Annual net returns (base costs)

| Year | Simple | PCA | Sector |
|---|---|---|---|
| 2015 (Aug–Dec) | −1.5% | −1.8% | −1.1% |
| 2016 | −2.0% | −2.5% | −2.0% |
| 2017 | −1.7% | −0.1% | −1.7% |
| 2018 | −2.4% | −2.2% | −1.8% |
| 2019 | −2.7% | −2.7% | −3.0% |
| 2020 | −0.9% | +0.6% | +0.3% |
| 2021 | −2.7% | −1.8% | −2.8% |
| 2022 | −2.2% | −1.3% | −1.9% |
| 2023 | −1.1% | −0.2% | −1.2% |
| 2024 (Jan to Oct 2) | −1.4% | −1.7% | −1.5% |

## Concentration

Net profit is negative in every arm, so the pre-set concentration criteria do not apply. The gross results show:

- **PCA gross.** The top 10 pair-month episodes account for 74% of gross P&L, and P&L excluding them is +1.6%. The largest single pair (CSX/UNP) contributes 14% and the best month 31%.
- **Simple gross.** Total gross P&L is close to zero (+1.0%), and the 10 best episodes contribute about 3.7 times that total, so without them the arm loses money (−2.8%).
- **Episodes.** About 53–55% of pair-months with a trade were profitable gross; after base costs, only about 42% were.

## PCA versus the baselines

These are paired monthly differences in net return over 111 development months. They are descriptive, not confirmatory.

| Comparison | Mean per month | SD per month | Newey–West t (3 lags) | Months positive |
|---|---|---|---|---|
| PCA − simple, base costs | +0.044% | 0.37% | 1.42 | 51% |
| PCA − simple, 2× costs | +0.043% | 0.37% | 1.41 | 52% |
| PCA − sector, base costs | +0.028% | 0.38% | 0.89 | 54% |
| PCA − sector, 2× costs | +0.027% | 0.38% | 0.87 | 51% |

PCA lost less than the baselines, but the difference is not statistically distinguishable from zero. All three arms lose money after costs.

## Verification performed before reading these results

**`v2/checks.py`** confirmed:

- the delay from signal at close t to execution at close t+1;
- long and short return signs;
- gross exposure of exactly 10% per pair;
- costs charged on both legs and on rebalancing;
- borrow accrual over one calendar day and over a weekend;
- the exit, stop-with-no-re-entry, 20-session time exit and scheduled-liquidation rules;
- the NAV identity and the drawdown calculation;
- that no data falls after 2024-10-02, and that selection is unchanged when post-formation data is erased.

**Real-data hand replay.** The largest PCA episode (CSX/UNP, October 2020) was replayed from prices by hand. Its gross P&L of 0.007243 of NAV matches the engine exactly.

**Price gaps.** Across all three arms and 111 months, no selected stock had a price gap inside its trading month.

## Decision

The development result is **materially negative after modeled costs** in all three arms, and it gets worse when costs are doubled.

- Gross performance is close to zero: 0.1–0.7% a year on about 29% average gross exposure.
- The strategy's turnover makes the 10 bps cost assumption binding.

No parameter search follows. The holdout stays locked.
