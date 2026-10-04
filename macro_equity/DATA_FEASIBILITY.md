# DATA_FEASIBILITY: macro_equity (Prompt 2)

**Prepared:** 2026-10-03, 19:16–19:40 ET.
**Verdict: BLOCKED.** The pre-registered strategy cannot be tested as specified with legitimate free data. Two independent inputs fail:

1. **Consensus and matching actuals (P4–P6).** No free source has dated S&P 500 per-share consensus EPS for identifiable calendar quarters together with same-basis actuals long enough for the frozen warmups. The best candidate is FactSet Earnings Insight. Its same-basis per-share actuals start in Q3 2009, which puts the first return forecast around late 2023, leaving **under 12 development walk-forward months** before the holdout. Its values also exist only inside chart images.
2. **Credit spread (P8).** FRED now carries only 3 years of ICE BofA corporate OAS (since April 2026), and ICE restricts reproduction. Decades of option-adjusted spread history are not available free.

The hypothesis is **not** changed. No replacement strategy (earnings revisions, macro-only) is adopted. **Freeze F1 is not performed:** all P1–P15 items remain provisional. No predictor–outcome relationship was computed, no model was fitted, no backtest was run, and no holdout value was opened deliberately (one incidental exposure is disclosed in §6).

Sources searched: the full step-by-step record is in `results/research_log.csv` (append-only); the coverage metadata is reproducible with `python -m macro_equity.sources.discovery` (writes `data/manifests/coverage_evidence.json`); the per-source details are in `data/manifests/source_manifest.json`.

## 1. Candidate consensus sources (timeboxed discovery, about 14 of 45 minutes)

| Source | Dated snapshots? | Numeric per-share EPS for an identifiable quarter? | Matching actuals | History | Verdict |
|---|---|---|---|---|---|
| Existing imports / connections | None present in `data/imports/`; no licensed export | — | — | — | None available |
| FMP connector (analyst estimates) | No (current estimates) | Per company, not index | — | — | Rejected: needs a higher paid plan |
| **FactSet Earnings Insight** (weekly PDFs; Wayback 2011–2016, FactSet host 2017+) | Yes, weekly report dates | Yes, but only in a raster chart (current quarter plus about 4–5 later quarters); narrative gives start/end-of-quarter values only. **Pre-2012 reports give sector share-weighted earnings in $B, a different measure** | FactSet-basis actuals in the same chart, **from Q3 2009** | Per-share chart from 2012-10-05 | Rejected for the frozen design: too little matching history; image-only values; extraction terms unverified |
| S&P DJI `sp-500-eps-est.xlsx` (Wayback versions) | Sparse versions only | Yes (S&P operating EPS estimates) | S&P operating actuals 1988+ | 0 versions in 2008, 2011, 2012; 1–3 in several other years | Rejected: not monthly |
| LSEG/Refinitiv S&P 500 Earnings Scorecard (Lipper Alpha PDFs) | Yes | Growth rates and share-weighted $B; per-share not confirmed | Not confirmed | Archive from 2016, dense from 2022 | Rejected |
| Excluded by definition | Yardeni forward 12-month EPS (no target quarter); Shiller/multpl (realized only); SPF corporate profits (NIPA); Zacks (not investigated in the timebox) | | | | Not compatible |

**Development-period examples inspected (scratchpad only, not stored in the repo).** FactSet reports dated 2011-04-01, 2011-09-30, 2012-03-30, 2012-10-05, 2013-04-05, 2013-10-04, 2014-03-28, 2014-10-03, 2015-01-16, 2015-04-24, 2016-04-01 and 2016-05-20. Findings:
- **Publication date:** printed on each report (weekly, normally Friday); prices as of the prior Thursday's close. The intraday release time is unknown, so the conservative rule would be "available from the next NYSE session".
- **Forecast quarter:** explicit (e.g. "Q1 2016"; chart labels such as "Q116").
- **Definition:** "an aggregation of the estimates for all the companies in the index", i.e. FactSet bottom-up EPS for current constituents, in index points.
- **Index coverage:** the S&P 500.
- **Compatibility with actuals:** only FactSet's own chart actuals share the basis. S&P DJI operating EPS is a different definition and is not combined.
- **Quarter-end behaviour:** the month-3 (quarter-end) target is still shown as an estimate, so the §4.1 mapping (P15) would work.

## 2. Coverage and timestamp evidence (metadata only)

| Item | Evidence | Retrieved (ET) |
|---|---|---|
| FactSet report PDFs | 454 report dates with a PDF capture. ≥ 1 per month for 2011-04→2016-12 and 2022-01→2026-09 (none in 2022-02). 2017–2021 almost absent from Wayback; on the FactSet host, sampled February 2017–2019 files exist (HTTP 200), and probing stopped at HTTP 429 | 19:17–19:30 |
| FactSet per-share EPS chart | Absent 2011-09-30 and 2012-03-30; present 2012-10-05 onward; earliest chart's first actual is Q3 2009 | 19:20–19:27 |
| S&P DJI estimate file versions | 2003–2010: 43 (none in 2008); 2013–2019: about 50 (summed across URLs); 2020–2026: 39 | 19:29 |
| Refinitiv scorecard PDFs | 2016: 39; 2017: 18; 2018: 4; 2019: 29; 2020: 53; 2021: 76; 2022+: 200+/yr | 19:29 |
| ICE BofA US Corporate OAS (FRED `BAMLC0A0CM`) | Daily close, percent. "Starting in April 2026, this series will only include 3 years of observations." Proprietary to ICE; reproduction needs permission | 19:26 |
| 10-year TIPS yield (FRED `DFII10`) | Daily, percent, H.15. Usable; start date to confirm at download | 19:26 |
| Broad dollar (FRED `DTWEXBGS`) | Daily, index Jan 2006 = 100, weekly H.10 release (observation for 09-25 updated 09-28): up to about 10 days' lag. Predecessor TWEXB discontinued | 19:26 |
| Nominal GDP vintages (ALFRED `GDP`) | Vintages from 1991-12-04 to 2026-09-30 | 19:26 |
| SPY / BIL prices | Not downloaded. Sponsor (Databento) equities history doesn't reach 2007; yfinance raw-price and distribution conventions to be verified against docs at download | — |
| FRED key | None found; FRED series pages and ALFRED metadata need no key. Whether downloads need one is not yet tested (no download made) | 19:17 |

## 3. Warmups, independent quarters and the development window (coverage arithmetic only)

The warmups are frozen at ≥ 32 distinct target quarters (earnings) and ≥ 60 completed months (returns). The arithmetic below uses the FactSet route, with a quarter's actual available about 1–2 quarters after quarter end (as seen in the charts).

| Quantity | Count |
|---|---|
| FactSet-basis per-share actual quarters, Q3 2009 → Q2 2024 | 60 |
| Signed-growth training targets (need the base quarter q−4), Q3 2010 → Q2 2024 | 56 distinct quarters |
| 32nd training quarter | Q2 2018, so the **first earnings forecast is about 2018-Q4** |
| Per-share consensus target quarters with an archived snapshot, 2012-Q4 → 2024-Q3 | up to 48 (2017–2021, 20 quarters, unverified month by month) |
| Replay-gap target quarters in development (E1 sample), about 2018-Q4 → 2024-Q3 | about 24 independent quarters (3 monthly snapshots each, not independent) |
| First return forecast (60 matured labels on replay gaps, t−2 lag) | about 2023-11 to 2024-01 |
| **Development walk-forward months for R and T before a 2024-09 holdout** | **about 8–11**: too few for R1/T1 or for the 36-observation inner λ validation |

**Holdout size (rule only, not frozen):** under the §9 rule with per-share consensus from 2012-10, N ≈ 167 eligible decisions through 2026-08, so 20% ≈ 33 and the 2-year cap binds: **N_h = 24**. Boundary dates are not frozen while BLOCKED.

## 4. What would resolve the blocker

**A legitimate export matching `data/templates/consensus_snapshots_template.csv` and `eps_actuals_template.csv`:**
- **Consensus:** monthly or more frequent dated snapshots of S&P 500 bottom-up EPS per index share by calendar target quarter, starting no later than about 2003.
- **Actuals:** same-basis actuals with first-publication dates, starting no later than about 1994.

Candidate products include LSEG I/B/E/S index aggregates (Workspace/Datastream), FactSet Estimates index aggregates, Bloomberg BEst for SPX with quarter overrides, and S&P Capital IQ. University library access to one of these would suffice.

**For credit spreads:** licensed ICE BofA US Corporate OAS daily history (from the same terminals, or ICE). Alternatively, an amendment adopting a different, publicly available spread definition; that would be a hypothesis change requiring Aman's approval before any data is examined.

## 5. Fallback-feasibility assessment (assessed, NOT adopted)

| Option | What changes | Feasibility |
|---|---|---|
| A. Licensed export (§4) | Nothing; the design as frozen | Feasible if access exists; import and validation code is ready |
| B. FactSet public route with reduced warmups (e.g. 20 quarters / 36 months) | Amendment lowering warmups. Credit-spread definition change or removal. OCR or manual transcription of about 140 chart images, with cross-checks. Licence confirmation | First earnings forecast about 2015-Q4, first return forecast about 2018-12, about 69 development months. **Several hours of extraction alone; not realistic before the 2026-10-04 11:00 ET deadline alongside Prompts 3–10** |
| Earnings-revision or macro-only strategies | A different hypothesis | Not adopted, per the prompt pack |

## 6. Disclosures

- **Incidental holdout-period exposure (19:21 ET).** A web-search results page displayed FactSet consensus levels for Q4 2025 and Q1 2026, a later Q3 estimate, and Q1 2026 reported growth. No gap or return was computed, and later searches were restricted to pre-2024 years. This is recorded in the research log and HYPOTHESIS.md §14.
- **Research-attempt count.** The six pre-registered specifications (§11) are **not** the complete count of research attempts. Every search, inspection, download and decision that can influence selection is appended to `results/research_log.csv`; the Prompt 2 rows are the start of that record.
- **Research-log timestamps.** Rows 4–17 carried manually estimated times; a correction row records the actual wall-clock window (19:17–19:27 ET).

## 7. Status of the provisional register

| ID | Status after Prompt 2 |
|---|---|
| P1 | Open (no download yet) |
| P2 | Open: BIL coverage to verify at download |
| P3 | Open: yfinance conventions to verify; sponsor route not suitable for 2007+ history |
| P4 | **BLOCKED** (§1) |
| P5 / P6 | **BLOCKED** with P4 (FactSet basis is only matchable from Q3 2009) |
| P7 | Candidate confirmed (DFII10) |
| P8 | **BLOCKED** on the free route |
| P9 | Candidate confirmed (ALFRED GDP vintages from 1991-12-04) |
| P10 | Candidate confirmed (DTWEXBGS; pre-2006 chaining to verify) |
| P11–P13 | Unchanged defaults |
| P14 | Rule gives N_h = 24 on the FactSet route; not frozen |
| P15 | Compatible with FactSet charts (quarter-end target still an estimate); open for other sources |

## 8. Next steps (no hypothesis change made)

- **If Aman can provide a licensed export:**
  1. drop it in `data/imports/`;
  2. run `python -m macro_equity.sources.consensus_import <consensus.csv> <actuals.csv>`;
  3. rerun Prompt 2's freeze step.
- **Otherwise:** macro_equity remains a pre-registered, BLOCKED specification. Prompt 10 can report it as a feasibility note with untested scaffold status, and the submission should be another project. That choice is Aman's.
