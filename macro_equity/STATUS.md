# STATUS: macro_equity

**Last updated:** 2026-10-03 19:40 ET, after Prompt 2. (The earlier "19:20" stamp for Prompt 1 was approximate; Prompt 1 finished at about 19:15.)
**Repo state:** `main` @ 34a75e6. **The pre-registration commit has not been made.** Prompt 0–1 files are staged; Prompt 2 files are new. Aman's uncommitted GLP-1 changes are untouched.
**Deadline:** Devpost and final push, Sun 2026-10-04 11:00 AM ET.
**Environment:** `cattle_crush/.venv/bin/python` (Python 3.11.7). PDF text via the existing PyMuPDF in `/opt/anaconda3/bin/python`. Nothing installed.

## Verdict: **BLOCKED** (DATA_FEASIBILITY.md; HYPOTHESIS.md A3)

1. **Consensus.** There is no free dated S&P 500 per-share consensus EPS by calendar quarter with same-basis actuals long enough for the frozen warmups.
   - Best candidate, FactSet Earnings Insight: per-share chart from 2012-10, actuals from Q3 2009, values only in chart images.
   - That puts the first earnings forecast around 2018-Q4, the first return forecast around late 2023, and leaves **about 8–11 development walk-forward months**.
2. **Credit spread.** FRED holds only 3 years of ICE BofA corporate OAS (since April 2026); ICE restricts reproduction.

No hypothesis change, no replacement strategy, **no Freeze F1** (P1–P15 stay provisional).

## Prompt progress

| # | Step | Status |
|---|---|---|
| 0 | Inspect repo, establish workspace | Done (staged, not committed) |
| 1 | Hypothesis and provisional experiment | Done (staged, not committed) |
| 2 | Data acquisition, feasibility, Freeze F1 | **Done: BLOCKED.** F1 not performed; no bulk download |
| 3–8 | Tables, models, replay, returns, portfolio, validation | **Blocked** until a licensed export (§4 of DATA_FEASIBILITY.md) or an approved amendment |
| 9 | Holdout | Not started; holdout never accessed |
| 10 | Note and audit | Can run as a feasibility note if Aman chooses |

## Prompt 2 record

**Created:**
- `DATA_FEASIBILITY.md`
- `research_log.py` and `results/research_log.csv` (append-only; 21 rows, including one timestamp-correction row)
- `sources/discovery.py`, `sources/guard.py` (fail-closed holdout guard), `sources/consensus_import.py` (export validator)
- `data/manifests/source_manifest.json`, `data/manifests/coverage_evidence.json`
- `data/templates/` (consensus and actuals templates, README)
- `tests/test_sources.py`

**Edited:**
- `HYPOTHESIS.md` §14: A1 (the six specs are not the full research-attempt count), A2 (incidental holdout-period exposure), A3 (BLOCKED, F1 not performed)
- `config.yaml` (feasibility block, research-log path)
- `tests/test_config.py`, `CLAUDE.md`, `CONTEXT.md`, `README.md`, this file

**Checks:**
- **Tests:** `python -m pytest macro_equity` gives **59 passed**. The 14 new tests cover the guard failing closed, boundary and naive-time rejection, import schema and basis checks, research-log append-only behaviour, feasibility consistency, and sequential amendment IDs.
- **Discovery:** timeboxed to about 14 of 45 minutes. Searched the existing imports and connector (FMP: paid plan needed), FactSet Earnings Insight, S&P DJI estimate files, and the LSEG/Refinitiv scorecard. Twelve development-period FactSet reports were inspected in the scratchpad only.
- **Metadata checked:** FRED/ALFRED pages for BAMLC0A0CM, DFII10, DTWEXBGS and GDP (metadata only).
- **Not done:** no predictor–outcome computation, no model, no backtest, no deliberate holdout access, no purchase, no commit.

**Disclosures:**
- A 19:21 ET search snippet showed holdout-period consensus levels (A2).
- Research-log rows 4–17 had hand-estimated times; a correction row was appended.

## Decisions needed from Aman

1. **Does the team have legitimate access to a licensed consensus export?** That means LSEG I/B/E/S aggregates, FactSet Estimates, Bloomberg BEst SPX, or Capital IQ, with consensus from about 2003 and actuals from about 1994 on the same basis, plus ICE OAS history. If yes: drop the files in `macro_equity/data/imports/`, validate them, and rerun the Prompt 2 freeze.
2. **If not: which project gets the submission?** macro_equity can still be reported honestly as a pre-registered, BLOCKED feasibility study (Prompt 10), but it cannot produce tested results. The alternatives in this repo are cattle H1 (rejected in sample, holdout not yet run), H2 (pre-registered) and GLP-1.
3. **Not recommended before the deadline:** Option B (FactSet route with lower warmups, a different spread definition, and OCR of about 140 charts). It needs an amendment and hours of extraction.

## Prerequisites for continuing (Prompt 3 or a Prompt 2 rerun)

- Commit first. Everything is under `macro_equity/` (stage and commit; see the commands in the latest session report).
- A licensed export validated by `python -m macro_equity.sources.consensus_import`, plus an OAS history source, **or** an explicit, approved amendment recorded in HYPOTHESIS.md §14 before any data is examined.
- Then download the non-consensus sources (development range only), confirm P1–P3, P7, P9 and P10 from coverage, freeze F1, and set the holdout boundary from coverage metadata.
