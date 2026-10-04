# Submission freeze: cattle_crush (H1 main study, H2 pre-registered follow-up)

Prepared 2026-10-03 (ET), after all development work and **before any holdout evaluation**. The holdout
(trading dates on or after 2024-10-01) is locked: `results/oos_lock.json` does not exist and no holdout
data has been downloaded.

## 1. Frozen primary specifications

Neither primary was chosen by performance. Both are the specifications designated as primary in the
committed pre-registrations.

| | H1 (main study) | H2 (pre-registered follow-up) |
|---|---|---|
| Document | `HYPOTHESIS.md` (committed 2026-10-02 21:11 ET, `e9334b9`) | `HYPOTHESIS_H2.md` (committed 2026-10-03 17:50 ET, `cb7a954`) |
| Primary | **Variant A, primary spec** (Section 6, "PRIMARY") | **Two-stock basket, 1-month cattle signal, sector-ETF hedges** (Section 6, "the primary") |
| Signal | z of the projected feeding margin over the 36 prior month-ends | s = 1-month front-LE return ÷ its sd over the 36 prior months |
| Parameters | sale ≥ 150 d, feeder ≥ 30 d, corn ≥ 75 d, FCR 6.0, W_in 800 lb, W_out 1,400 lb, no seasonal adjustment, no overlay | LE contract ≥ 45 d, β over 252 d, basket vol over 60 d |
| Position | w = clip(−z/2, −1, 1) × 10% / σ̂_60d in the sale contract, \|w\| ≤ 2 | w = −clip(s/2, −1, 1) × 10% / σ̂_basket, \|w\| ≤ 2, stock + hedge gross ≤ 2 |
| Timing | month-end signal, next-day settlement execution | month-end signal, next NYSE close execution |
| Costs | 1 tick + $2.50 per contract per side; 2× stress | 5 bps (stocks), 2 bps (ETFs) per side, 0.50%/yr borrow; 2× stress |
| Holdout condition | P2: net Sharpe > 0 | Q3: net Sharpe > 0 |

**Not substituted:** the best-performing of the 25 cattle-project trials (H1 Variant B with seasonal
adjustment, development net Sharpe 0.21) is reported as a trial, not used as the submission.

## 2. Versions

- **Code:** the git commit that adds this file. It builds on `8a2d559` (H2 development results). The
  holdout lock records the commit hash at evaluation time, and `run_oos.py` refuses a first run while
  any frozen path (code, config, hypotheses, manual reference data, this file) has uncommitted changes.
- **config.yaml SHA-256:** `ef37283b9a3362b5c1749b3cff858a51d9ad511936955b1a650703ca0c80fb51`
  (unchanged since `32f2826`). `run_oos.py` refuses later runs if this hash changes.
- **Dependencies:** `requirements.txt` (pinned; Python 3.11.7). The note renderer additionally uses
  `pymupdf==1.28.2` (`requirements-note.txt`).
- **Data provenance:** `data/raw/manifest.json` (local, git-ignored) records every development pull;
  Databento batch job ids are in `data/raw/dbn/jobs.json` (local). Cited manual inputs:
  `data/manual/cftc_disruptions.csv`, `federal_closures.csv`, `cme_reference.csv`.

## 3. Trial history (preserved in full)

- `results/trial_log.csv`: 164 rows at freeze: 76 `trial` rows (including repeats of identical
  configurations from reproduction runs), 73 `overlay`, 15 `diagnostic`. Rows are never deleted.
- **Distinct cattle-project trials: 25** = 24 for H1 (8 specs × 3 variants) + 1 for H2 (primary only).
  The Deflated Sharpe Ratio is computed over these 25 (`results/tables/trials.csv`).
- H2's four pre-registered alternative trials (3-month signal, SPY hedge, TSN alone, TXRH alone)
  were **not run**.
- Deviation logs: 21 dated rows in `HYPOTHESIS.md` Section 9, 2 in `HYPOTHESIS_H2.md` Section 8.

## 4. Holdout boundary

`oos_start = 2024-10-01` (registered in both documents, unchanged). Rule as stated in `HYPOTHESIS.md`
Section 8: the most recent 20% of history, capped at two years. Databento GLBX.MDP3 ends 2026-10-03
(checked 2026-10-03): 16.33 years from 2010-06-06, 20% = 3.27 years, so the 2-year cap binds and implies
2024-10-03. The registered boundary is two days earlier, giving a 732-day rather than 730-day holdout.
It is kept as registered. The official competition rule text is not stored in this folder; the check
uses the rule as written in the pre-registration.

## 5. Checks not completed (not implied to have passed)

1. H2's four alternative trials (above).
2. H2 Fama-French five-factor + momentum regression (needs the Ken French library, not downloaded).
3. H2 ADV participation and capacity (needs equity volume data, not downloaded).
4. H2-only Deflated Sharpe over its 5 registered trials (only 1 was run; DSR is reported over the 25
   cattle-project trials instead).
5. CME exchange-set non-spot position limits / accountability levels for LE (CME rulebook files could
   not be retrieved; federal spot-month limits are cited).
6. A whole-pipeline `test_no_lookahead` (perturb every price after t and re-run M, z and w). Existing
   tests cover the z-score window, contract selection, the P1 outcome construction and the in-sample
   guards, not the full pipeline.
7. Iowa State closeout level comparison for H1's margin (optional in the build spec; skipped by decision).

## 6. Outstanding limitations

- **H1 data:** Databento's livestock feed has no data on 2012-02-06..09, 2014-06-12 and 2014-09-23..25
  (LE, GF) and 2020-02-27, 2020-06-30 (ZC); LEZ2014 lacks its final settlement (three P3 month-ends
  dropped); 24 GF contracts lack a cash-final record (four Variant B expiries closed at the last
  trading-day settlement). Before May 2017 the feed rarely flags final settlements; the last record of
  each day is used (all records agree on 99.9% of contract-days).
- **H1 method:** fractional contracts; excess returns (no collateral interest); current CME margins
  applied to historical positions; conservative CFTC availability rule for Variant C; NASS placements
  are revised values; only 15 month-ends have z < −1.
- **H2:** two stocks, so idiosyncratic events dominate; yfinance adjusted closes; universe chosen by
  business exposure with survivorship risk; H2 was conceived after H1 failed (disclosed in its header).
- **Research history:** the repository also holds other projects (a GLP-1 equity study, an equity
  pairs-trading study, a macro-equity study). Their experiments are not part of the 25-trial count.
