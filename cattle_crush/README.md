# Cattle markets: two pre-registered tests (Gator Quant Hacks 2026)

**H1 (main study):** do deeply negative feedlot margins predict fewer cattle placements and positive
returns on deferred Live Cattle futures? **H2 (pre-registered follow-up):** do Tyson and Texas
Roadhouse, hedged with their sector ETFs, react with a lag to cattle price moves?

**Status:** development work is complete and both hypotheses are **not supported** for their frozen
primary specifications (H1: P1 t = 0.42, P2 net Sharpe −0.08; H2: Q1 t = 0.10, Q2 t = 0.88, net
Sharpe −0.29). The holdout (trading dates from 2024-10-01) is **locked and not yet evaluated**. Draft
note: [`note/research_note.pdf`](note/research_note.pdf) (4 pages).

| File | Purpose |
|---|---|
| `HYPOTHESIS.md`, `HYPOTHESIS_H2.md` | Frozen pre-registrations; all later choices are in their dated deviation logs |
| `SUBMISSION_FREEZE.md` | Frozen primaries, code/config versions, trial history, uncompleted checks, limitations |
| `CLAUDE.md` | Build specification |
| `config.yaml` | Every H1 parameter (its SHA-256 is recorded in the trial log and the holdout lock) |
| `data/download.py` | Fetches all inputs; development window by default |
| `data/audit.py` | Contract-definition and settlement audit |
| `src/` | Contracts, margin, signals, backtest, costs, mechanism tests, reports, H2, trial log |
| `run_all.py` | Reproduces every development number (no holdout access) |
| `run_oos.py` | One-time holdout evaluation (not run) |
| `results/` | Tables, figures and the append-only `trial_log.csv` |

## Setup

Python 3.11 (developed on 3.11.7).

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add DATABENTO_API_KEY and NASS_API_KEY
```

**Access requirements**
- **Databento** account and API key. CME data is licensed and is **not** included in this repository.
  The in-sample pull (GLBX.MDP3 `definition`, `statistics`, `ohlcv-1d` for LE, GF, ZC, 2010-06-06 to
  2024-09-30) was quoted at **$8.96** on 2026-10-03; `download.py --estimate` prints the current price
  before anything is bought.
- **USDA NASS Quick Stats** API key (free).
- Internet access for the CFTC public reporting API and yfinance (no key).

## Development-only reproduction

```bash
python data/download.py --estimate          # free: prints the Databento cost, buys nothing
python data/download.py --pull all --yes    # buys the in-sample Databento data; NASS, CFTC, SPY, H2 equities
python run_all.py                           # about 1 minute once data is present
python -m pytest tests/ -q
pip install -r requirements-note.txt && python note/build_note.py   # optional: rebuild the note PDF
```

`python run_all.py --yes` also downloads any missing development source (it buys Databento data only
with `--yes`). Every download stops before 2024-10-01 and is checked for later dates; `run_all.py` never
calls a holdout path and finishes by asserting that every saved series ends before 2024-10-01. Each
backtest is appended to `results/trial_log.csv`, so a re-run adds rows that repeat configurations already
logged; the Deflated Sharpe counts distinct configurations (25 cattle-project trials).

**What `run_all.py` produces** (steps print as they run)

| Step | Output |
|---|---|
| 1 Data audit | `results/tables/data_audit.txt` |
| 2 Feeding margin | `results/figures/margin.png` |
| 3 P1, P3, leg decomposition (H1) | `tables/mechanism.csv`, `tables/legs.csv`, `figures/mechanism.png`, `figures/legs.png` |
| 4–5 H1 Variants A, B, C, overlay, diagnostics | `tables/variant_{a,b,c}.csv`, `tables/variant_*_diagnostics.csv`, `figures/equity*.png` |
| 6 Robustness (21 specs, overlay alongside) | `tables/robustness.csv`, `figures/robustness.png` |
| 7 Deflated Sharpe (25 cattle-project trials) | `tables/trials.csv` |
| 8 Stress, liquidity, capital (H1) | `tables/stress_*.csv`, `tables/liquidity_by_leg.csv`, `tables/capital.csv` |
| 9 H2 primary | `tables/h2_tests.csv`, `h2_performance.csv`, `h2_annual.csv`, `h2_exposure_concentration.json` |
| 10 Accounting and additional checks | `tables/h1_accounting.csv`, `factors.csv`, `by_year.csv`, `capacity_curve.csv`, `h2_stress_episodes.csv`, `figures/by_year.png`, `figures/capacity.png` |
| 11 In-sample guard | assertion only |

Expected headline output: P1 FAIL (β +0.00197, t 0.42); P2 in-sample FAIL (mean monthly −0.0450%,
t −0.34); H2 Q1/Q2/Q3 all fail (t +0.10, +0.88, −1.08).

## Data provenance

| Source | Content | Citation / access |
|---|---|---|
| Databento GLBX.MDP3 | CME Globex Live Cattle (LE), Feeder Cattle (GF), Corn (ZC): instrument definitions, final settlement prices (statistics schema, stat_type 3), session high/low, open interest, daily bars | databento.com, licensed |
| USDA NASS Quick Stats | "CATTLE, ON FEED - PLACEMENTS, MEASURED IN HEAD", capacity 1,000+ head, US, monthly | quickstats.nass.usda.gov |
| CFTC | Disaggregated Commitments of Traders, futures only, code 057642 (Live Cattle), dataset 72hh-3qpy | publicreporting.cftc.gov |
| yfinance | Adjusted closes: SPY (H1 factor check); TSN, TXRH, XLP, XLY (H2) | Yahoo Finance via yfinance |
| `data/manual/` | CFTC release disruptions, federal closures, CME price limits, margins and federal position limits, each with source URL and retrieval date | cited in the files |

**Method notes.** Futures positions use fractional contracts. Returns are excess returns on fixed
capital ($1M) with no interest on collateral. Contract expiries come from exchange definitions as
published at each date; returns are computed within each contract (no spliced series). Costs: H1 one
tick plus $2.50 per contract per side; H2 5 bps (stocks) and 2 bps (ETFs) per side plus 0.50%/yr borrow;
all results are also reported at 2× costs.

## Holdout evaluation: PENDING (not run)

The two frozen primaries (H1 Variant A primary; H2 primary) are evaluated **once**, on trading dates from
2024-10-01, and both are reported regardless of outcome. H1 Variants B and C and the drawdown overlay are
reported alongside as pre-registered secondary results.

1. Commit the frozen specification (`run_oos.py` refuses a first run while code, config, hypotheses,
   manual reference data or `SUBMISSION_FREEZE.md` have uncommitted changes).
2. `python run_oos.py --confirm-final` runs the checks and prints the holdout Databento cost, then stops.
3. `python run_oos.py --confirm-final --yes` buys the holdout data (Databento, CFTC, a full-history H2
   equity re-download), writes `results/oos_lock.json` (config hash, git commit, time) **before any
   holdout result is computed**, then writes `results/tables/oos_performance.csv` and
   `results/figures/oos_equity.png`.
4. Pass conditions: P2 requires H1's holdout net Sharpe > 0; Q3 requires H2's holdout net Sharpe > 0.
5. Later runs are allowed only if `config.yaml` is unchanged (reproduction).

No holdout results exist in this repository yet.
