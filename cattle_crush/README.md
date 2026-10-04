# Cattle markets: two pre-registered tests (Gator Quant Hacks 2026)

**H1 (main study):** do deeply negative feedlot margins predict fewer cattle placements and positive
returns on deferred Live Cattle futures? **H2 (pre-registered follow-up):** do Tyson and Texas
Roadhouse, hedged with their sector ETFs, react with a lag to cattle price moves?

**Status:** both hypotheses are **not supported** for their frozen primary specifications. In
development, H1 failed P1 (t = 0.42) and P2's in-sample condition (net Sharpe −0.08), and H2 failed Q1,
Q2 and Q3 (t = 0.10, 0.88, −1.08). The two-year holdout (2024-10-01 to 2026-10-02) was **evaluated once on
2026-10-04** (lock at commit `58d6299`): H1's primary earned a net Sharpe of **+0.63** (meeting P2's holdout
condition; H1 remains rejected because P1 and P2's in-sample condition failed) and H2's primary earned
**−0.15** (Q3 not met).

**Current note:** [`paper/research_note_edited.pdf`](paper/research_note_edited.pdf) (five main pages plus
references; editable source `paper/research_note_edited.html`). `note/research_note.pdf` is the
superseded 4-page note from the freeze.

## Verify the submission without market data (judges start here)

```bash
cd cattle_crush
python verify_submission.py
```

Python 3.9+ standard library only: no install, no credentials, no network, no market data. It checks the
hashes of the frozen specifications, saved results, trial log and holdout lock; checks that 55 numerical
claims in the note (`submission/claims.json`: source file, row selector, column, units, rounding) match
the saved rows and the editable note; recomputes the registered pass/fail conditions from saved tables
and confirms both decisions remain **rejected**; reconciles the trial log; and reports holdout turnover as
**missing**. It prints a report, writes `submission/verification_report.json`, and exits 1 on any missing
or inconsistent required artifact. If PyMuPDF happens to be installed, it also checks the values in the
PDF text and the minimum font size.

**What it does not prove:** that the code regenerates these tables. That computational reproduction
needs the licensed inputs below and the pinned environment; it was not performed by this command.
Tests for the verifier: `python -m unittest discover -s tests -p "test_verify_submission.py"`.

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
| `run_oos.py` | One-time holdout evaluation (run once on 2026-10-04; now reproduces it only while `config.yaml` matches the lock) |
| `results/` | Original saved tables, figures, the append-only `trial_log.csv` and `oos_lock.json` |
| `paper/` | Current note, editable HTML, renderer and recorded formatting QA |
| `review/` | Post-evaluation audits, corrections and supplements (labelled as such; not preregistered evidence) |
| `submission/` | Claims manifest, hash manifest and the latest verification report |
| `verify_submission.py`, `tests/test_verify_submission.py` | Artifact-only verifier and its focused tests |

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

## Holdout evaluation: completed once (2026-10-04)

`run_oos.py --confirm-final --yes` evaluated the two frozen primaries once on trading dates from 2024-10-01
to 2026-10-02 (504 days). `results/oos_lock.json` records config SHA-256 `ef37283b…`, git commit `58d6299`
and the lock time (2026-10-04 04:45:01 UTC), written before any holdout result was computed. A first
attempt stopped on a Databento HTTP 502 during the data download, before the lock and before any result;
the re-run completed. Outputs: `results/tables/oos_performance.csv`, `results/figures/oos_equity.png`, and 7
`oos` rows in `results/trial_log.csv`.

| Holdout, net of 1× costs | Ann. return | Sharpe | Max DD | Monthly mean (NW t) | Condition |
|---|---:|---:|---:|---:|---|
| **H1 primary (Variant A)** | +3.88% | **+0.63** | 5.4% | +0.31% (0.97) | P2 holdout: Sharpe > 0, met |
| **H2 primary** | −1.03% | **−0.15** | 7.6% | −0.08% (−0.27) | Q3 holdout: Sharpe > 0, not met |
| H1 Variant B (secondary) | +8.03% | +0.86 | 6.5% | +0.64% (1.40) | reported, not substituted |
| H1 Variant C (secondary) | +2.14% | +0.43 | 5.6% | +0.17% (0.80) | reported, not substituted |

P2 required both its in-sample condition (failed) and the holdout condition, and P1 had failed, so H1
remains rejected under the pre-registered decision table. A two-year Sharpe has a standard error of about
0.7, so +0.63 is not statistically distinguishable from zero.

`python run_oos.py` now only reproduces this evaluation, and only while `config.yaml` matches the lock.
It needs the holdout-window licensed data; it was not rerun for any later audit or supplement.

Holdout max drawdown for H1 is the saved fraction 0.054466625142137515, shown as 5.4% at one decimal
(earlier versions of this README showed 5.5%). **Holdout turnover is missing**: no holdout trade ledger
was saved, the `turnover` column of `results/tables/oos_performance.csv` is blank, and it is not inferred.

## Original results, post-evaluation material and errata

- `results/` holds the original frozen outputs: development tables from `run_all.py` and the single
  holdout evaluation from `run_oos.py`. Their hashes are checked by `verify_submission.py`.
- `review/` holds post-evaluation audits, corrections and supplements (uncertainty intervals, execution
  session checks, funding and order-capacity diagnostics). They were made after the holdout evaluation,
  are labelled as post-evaluation in the note and in `submission/claims.json`, and change no registered
  decision. See [`review/README.md`](review/README.md).
- Trial accounting: `results/trial_log.csv` has 171 rows (76 trial, 73 overlay, 15 diagnostic, 7 oos);
  164 are development rows, as recorded in `SUBMISSION_FREEZE.md`. The 76 trial rows contain 25 distinct
  configurations (24 H1, 1 H2); repeats from reproduction runs are not new trials.
  `results/tables/trials.csv` was written from an earlier 162-row / 75-trial-row snapshot of the log and
  uses the same 25 configurations. Post-evaluation reproduction rows were kept in a separate review log
  that is not part of this repository.
- **Erratum:** the note shows 20.7% maximum drawdown for the supplemental development row "A + overlay,
  net"; the saved fraction 0.2064627979599919 rounds to 20.6%. No decision or headline uses it. Details in
  [`paper/README.md`](paper/README.md).
