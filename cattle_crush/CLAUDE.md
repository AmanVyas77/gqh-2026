# CLAUDE.md: Build Spec for the Feedlot Margin → Live Cattle Strategy (GQH 2026)

This repository tests the pre-registered hypothesis in `HYPOTHESIS.md`. Read that file first; it is the source of truth for every design choice.

## Ground rules (non-negotiable)

1. **HYPOTHESIS.md is frozen.** Implement exactly what it specifies.
   - If something cannot be built as written, stop and ask Aman.
   - If he approves a change, append a row to its Section 9 Deviation Log. Never edit Sections 1–8.
2. **Never run `git commit` or `git push`.** Stage files with `git add` and give Aman the exact commit and push commands to run himself.
3. **Never load out-of-sample data** (dates ≥ `oos_start`) anywhere except `run_oos.py`. Data loaders default to `end = oos_start − 1 day`.
4. **Never commit secrets or licensed data.** That means `.env`, API keys, and raw Databento data. `data/raw/` and `data/processed/` are git-ignored.
5. **Verify external APIs against current docs before coding.** This covers Databento schemas and symbology, NASS Quick Stats fields, and CFTC codes and columns. Do not guess. Flag anything uncertain to Aman.
6. **Every backtest call goes through `trial_log.log_trial()`.** Never delete rows from the trial log.
7. **Deadlines:** Devpost closes Sun Oct 4, 10:00 AM ET. Code freeze is 11:00 AM ET. Follow the build order below; ship the MVP first.
8. **Everything is deterministic:** no unseeded randomness.

## Stack

- Python 3.11
- pandas, numpy, statsmodels, matplotlib, pyyaml
- databento, requests, python-dotenv, yfinance (SPY only), pytest

## Repo layout

```
.
├── CLAUDE.md
├── HYPOTHESIS.md
├── README.md
├── requirements.txt
├── .env.example          # DATABENTO_API_KEY=, NASS_API_KEY=
├── .gitignore            # .env, data/raw/, data/processed/, __pycache__/
├── config.yaml           # every frozen parameter; mirrors HYPOTHESIS.md
├── data/
│   ├── download.py
│   └── manual/           # optional: hand-entered Iowa State closeouts for calibration
├── src/
│   ├── contracts.py
│   ├── margin.py
│   ├── signals.py
│   ├── costs.py
│   ├── backtest.py
│   ├── mechanism.py
│   ├── analysis.py
│   └── trial_log.py
├── tests/
├── run_all.py            # in-sample only; reproduces every IS number in the note
├── run_oos.py            # gated; see below
└── results/
    ├── tables/
    ├── figures/
    └── trial_log.csv
```

## config.yaml

```yaml
data_start: 2010-06-06
oos_start: 2024-10-01
capital_base: 1000000

margin:
  w_in_lb: 800
  w_out_lb: 1400
  fcr: 6.0
  corn_lb_per_bu: 56
  k_other_cost: 350

contracts:
  sale_min_days: 150
  feeder_min_days: 30
  corn_min_days: 75

specs:   # verify against CME / Databento definitions
  LE: {size: 40000, unit: lb, tick_cents: 0.025}
  GF: {size: 50000, unit: lb, tick_cents: 0.025}
  ZC: {size: 5000,  unit: bu, tick_cents: 0.25}

signal:
  z_lookback_months: 36
  seasonal_adjust: false
  seasonal_years: 5

sizing:
  target_vol: 0.10
  vol_lookback_days: 60
  z_clip_divisor: 2.0
  max_gross_leverage: 2.0

hedging_pressure:
  cftc_code_live_cattle: "057642"   # verify
  median_lookback_weeks: 156

costs:
  ticks_per_side: 1
  fee_per_contract_side: 2.50
  stress_multiplier: 2.0

robustness:   # one parameter at a time around the primary spec
  z_lookback_months: [24, 48]
  sale_min_days: [120, 180]
  fcr: [5.5, 6.5]
  seasonal_adjust: [true]

tests:
  p1_nw_lags: 3
  p2_nw_lags: 5
  p2_t_threshold: 2.0

capacity:
  aum_grid: [1.0e6, 1.0e7, 5.0e7, 1.0e8, 5.0e8, 1.0e9]
  impact_coef: 1.0
  adv_lookback_days: 20
```

## Module specs

### data/download.py

**Databento** (dataset `GLBX.MDP3`, parent symbols `LE.FUT`, `GF.FUT`, `ZC.FUT`):
- Pull three schemas from `data_start` to today:
  - `definition`: expirations, last trade dates, and contract specs.
  - `statistics`: daily settlement prices. Confirm which record is the final settlement and document the choice.
  - `ohlcv-1d`: volume, plus high/low for detecting limit-locked days.
- Keep outright futures only; calendar spreads also appear under the parent symbol.
- Call `metadata.get_cost` first and print the estimated cost before pulling anything.
- Convert prices from cents to dollars.
- Save parquet files to `data/raw/`.

**USDA NASS Quick Stats API:**
- Monthly Cattle on Feed placements, United States, feedlots with 1,000+ head capacity.
- Placements are used only in mechanism tests, never in trading signals.

**CFTC Disaggregated COT** (futures only, Live Cattle):
- Weekly PMPU long and short positions, with the as-of date (Tuesday).
- Treat the data as available from **as-of date + 6 calendar days** (the following Monday). This is conservative given the Friday release and holiday delays.

**yfinance:** SPY daily adjusted close, for the factor check only.

### src/contracts.py

- `contract_table()`: returns `[root, symbol, last_trade_date, size]`, built from definitions.
- `select(root, t, min_days)`: returns the first contract with `last_trade_date ≥ t + min_days`.
  - GF uses `min_days = 30`, which yields the nearest contract with at least 30 days left.
- `settle_panel()`: a date × symbol matrix of settlement prices.

### src/margin.py

- `B = (w_out − w_in) × fcr / corn_lb_per_bu`
- `margin(t)`: returns M_t plus the selected symbols and prices, so every value can be audited.
- Build a daily margin series and a month-end margin series.
- Optional: compare margin levels to `data/manual/isu_returns.csv` as a calibration check.

### src/signals.py

- `zscore(M_month_end, lookback)`: uses the prior `lookback` month-ends only, **excluding t**.
- Seasonal option: subtract the trailing 5-year mean of the same calendar month before computing the z-score.
- Hedging pressure:
  - `HP = (short − long) / (short + long)`, using PMPU positions, aligned to the availability date.
  - Compare against its trailing 156-week median.

### src/costs.py

- Dollar cost per side = `contracts × (ticks × tick_value + fee)`.
- `tick_value = tick_cents / 100 × size`.
- Support a cost multiplier for the 2× stress test.

### src/backtest.py

**Engine:** daily, driven by month-end signals. Execution happens at the next trading day's settlement.

**Positions** (fractional contracts allowed; note this in the README):
- **A:** `w = clip(−z/2, −1, 1) × target_vol / σ̂_60d`, capped at `|w| ≤ 2`. Contracts = `w × capital / (price × size)`.
- **B:** head units `U = clip(−z/2, −1, 1) × target_vol × capital / σ̂$_60d`. Each unit is long `w_out` lb of LE, short `w_in` lb of GF, and short `B` bushels of ZC.
- **C:** A's position, zeroed whenever the hedging-pressure filter disagrees with its sign.

**P&L and rolls:**
- Daily P&L = held contracts × size × the change in settlement price, **within each contract**.
- When the selected contract changes at a rebalance, close the old one and open the new one at the same execution settlement. Charge costs on both legs.
- **Limit-locked days:** if the execution day has `high == low`, defer the trade to the next non-locked day.

**Outputs:**
- Daily returns (gross, net, and net under 2× costs) = P&L / fixed capital.
- Positions and a trade log.
- Turnover = annual sum of |Δnotional| / capital.

**OOS guard:** `oos=False` by default, which hard-filters dates to `< oos_start`.

### src/mechanism.py

- `p1_placements()`: regress the YoY log change in placements summed over months m+1 to m+3 on z_t. Use Newey-West standard errors with 3 lags.
- `p3_kill_test()`: at each month-end, regress on z_t:
  - (i) the sale contract's return from t to its last trading day, and
  - (ii) the sale contract's final settlement minus the front LE contract's settlement at t.
- `leg_decomposition()`: split M_{t+5} − M_t into `w_out × ΔLE`, `−w_in × ΔFC`, and `−B × ΔC`. Report each leg's mean contribution when z_t < −1, and its variance share.

### src/analysis.py

**`metrics()`:**
- Annualized return, annualized volatility, Sharpe (annualized with √252), max drawdown, turnover, worst month, skew.
- Newey-West t-stat on monthly returns, with 5 lags.

**`factor_regression()`:** regress strategy returns on:
- (1) a long-only roll-adjusted LE position (sale-contract rule, w = 1),
- (2) 12-month LE time-series momentum (sign of the trailing 12-month roll-adjusted return, lagged 1 day), and
- (3) SPY.

**`deflated_sharpe()`:**
- Follow Bailey & López de Prado (2014), using the trial count and the variance of Sharpe ratios across trials from `trial_log.csv`.

**`capacity()`:**
- Impact per trade = `impact_coef × σ_daily × sqrt(contracts_traded / ADV_20d)` for that specific contract, plus fixed costs.
- Report net Sharpe at each AUM level, and the AUM at which net Sharpe falls to half of its 1× cost value.

**`by_year()`:** net returns per calendar year.

### src/trial_log.py

- `log_trial(variant, params, sample, sharpe, n_obs, skew, kurt)` appends one row to `results/trial_log.csv`.
- Each row also records the timestamp, the git commit hash, and a hash of the config.

## Run scripts

### run_all.py

- One command, in-sample only.
- Downloads data if it is missing.
- Runs A, B, and C at the primary spec, plus the full robustness set.
- Runs P1, P3, the leg decomposition, factor regressions, by-year returns, capacity, and the Deflated Sharpe Ratio.
- Writes `results/tables/*.csv` and `results/figures/*.png`, and prints the headline numbers.

### run_oos.py

**First run:**
- Requires the `--confirm-final` flag.
- Runs A, B, and C at the **primary spec only**.
- Writes `results/oos_lock.json` containing the config hash, the git commit hash, and a timestamp.
- Writes the `oos_*` tables.

**Later runs:**
- Allowed **only if the config hash matches the lock**. This lets judges reproduce the numbers.
- Otherwise, refuse and exit.

## Tests (must pass before submission)

- `test_no_lookahead`: perturb every price after t and confirm M_t, z_t, and w_t are unchanged.
- `test_contract_selection`: at least 5 hand-checked dates, one per root.
- `test_k_invariance`: z_t is identical with K = 0 and K = 350.
- `test_costs`: dollar costs match the tick math in HYPOTHESIS.md Section 7.
- `test_oos_guard`: in-sample paths never return dates ≥ `oos_start`.
- `test_roll`: no return outliers on roll days.

## Outputs for the quant note

| Output | File | Note section / rubric criterion |
|---|---|---|
| IS vs. OOS metrics for A/B/C, net at 1× and 2× costs | `tables/performance.csv` | Results / Performance |
| Equity curves (gross, net, net 2×), OOS shaded | `figures/equity.png` | Results / Performance |
| Margin z vs. placements YoY | `figures/mechanism.png` | Hypothesis / Economic Foundation |
| P1 and P3 regressions | `tables/mechanism.csv` | Economic Foundation |
| Leg decomposition | `figures/legs.png` | Economic Foundation / Innovation |
| One-at-a-time robustness | `figures/robustness.png` | Performance |
| Factor regressions | `tables/factors.csv` | Risk Management |
| Returns by year | `figures/by_year.png` | Risk Management |
| Capacity curve | `figures/capacity.png` | Liquidity & Capital |
| Trial count and Deflated Sharpe | `tables/trials.csv` | Performance |

## Build order (MVP first)

1. Write `download.py` and `contracts.py`. Hand-check contract selection on 5 dates.
2. Write `margin.py`. Sanity-plot M_t and compare its level to Iowa State closeouts.
3. Write `signals.py`, then run the **P1 mechanism test**. This result carries Economic Foundation even if the trade fails.
4. Build the Variant A backtest with costs and metrics, in-sample only.
5. Run the robustness set, the trial log, and the Deflated Sharpe Ratio.
6. Add Variants B and C, P3, and the leg decomposition.
7. Add the factor regressions, by-year returns, and capacity analysis.
8. Get all tests passing, write the README, and confirm `python run_all.py` works end to end from a clean clone.
9. **Saturday night: Aman runs `python run_oos.py --confirm-final` once.**
10. Finalize figures and tables.

## README must include

- Setup: Python 3.11, `pip install -r requirements.txt`, and copying `.env.example` to `.env`.
- The one reproduction command (`python run_all.py`) and the OOS command.
- Data sources with citations: Databento, USDA NASS, CFTC, and yfinance.
- A note that licensed data is excluded and that `download.py` fetches it.
- Disclosure that fractional contracts are used and that returns are excess returns.
