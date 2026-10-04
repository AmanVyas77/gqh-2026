# macro_equity: verified context

Facts gathered in Prompt 0 (2026-10-03, 18:40–18:55 ET). This file records facts, not decisions. Decisions go in HYPOTHESIS.md and config.yaml (Prompt 1 onward).

## 1. Competition rules (verified)

Sources, all retrieved 2026-10-03 at about 18:50 ET:
- Track page: https://www.gqhacks.com/tracks/systematic-trading. It says it summarizes the *Systematic Trading Track Participant Brief* and that the brief or an organizer announcement wins on any conflict.
- Massive bonus page: https://www.gqhacks.com/tracks/systematic-trading/massive
- Hacker Guide: https://gqhacks.notion.site/hacker-guide
- Devpost: https://gqhacks.devpost.com/

| Topic | Rule |
|---|---|
| Deadline | Devpost submission **and** final code push: **Sun 2026-10-04, 11:00 AM ET**. Late submissions are not judged; commits after 11:00 AM are not reviewed |
| Deliverables | Quant note as a PDF **plus** a link to a public GitHub repo; both are required |
| Note length | **At most 5 pages**, figures and tables included; 11pt font or larger; standard margins. References and an optional appendix don't count, but judges aren't required to read the appendix |
| Holdout | "the most recent 20% of your history or the most recent 2 years, whichever is shorter". Set aside before testing, never tuned on, evaluated once at the end |
| Data | Any liquid, publicly traded market. Sponsor data (Databento, Webull) is optional; free public sources (e.g., FRED, Ken French) are allowed; outside data is allowed (Hacker Guide). **Every source cited in the note** |
| Costs | Every reported result net of costs; state the cost in bps per trade and justify it; show results with doubled costs |
| Minimum results | In-sample and out-of-sample reported separately: annualized return, volatility, Sharpe, max drawdown, turnover, equity curve |
| Disclosure | Hypothesis written and committed before results; number of variants tried; failures |
| Rubric | Five criteria scored 1–10 (out of 50): Economic Foundation; Innovation; Risk Management Plan; Liquidity & Capital; Performance & Analytical Evidence. Ties go to Performance first, then Economic Foundation |
| Cap rule | Performance & Analytical Evidence is capped at 4 if judges can't run the code, if it gives materially different numbers from the note, or if they find lookahead or tuning on the out-of-sample period |
| Repo | README with setup and one command that reproduces the headline results; dependency file; all signal/backtest/analysis code; data download scripts or instructions. Never commit raw licensed data or API keys |
| Originality | No pre-existing work: everything must be built during the event (hacking began Fri 2026-10-02, 7:15 PM ET). Libraries and published research are fine if cited; a copied strategy must be clearly extended. AI tools are allowed, but the team must be able to explain every line and claim |
| Team | 1–4 people; all members listed on Devpost |
| Massive subtrack only | Fixed windows of 2024-01-01 → 2025-12-31 (development) and 2026-01-01 → 2026-08-31 (out-of-sample) replace the 20% rule for the 8-K options challenge only. **They do not apply to macro_equity** |

## 2. Unresolved rules (not invented; ask organizers or Aman)

1. **The Participant Brief itself and Discord announcements were not read.** The track page defers to them on conflicts.
2. **One note per team?** The rules describe a single ≤5-page note and one repo. This repo already holds the GLP-1 project, cattle H1 (rejected) and cattle H2 (pre-registered). Whether one submission may cover several strategies, and which one is submitted, is unresolved.
3. **What "your history" means** for the 20% rule when inputs have different start dates (e.g., SPY since 1993, credit spreads, consensus snapshots). This affects the holdout length only if the eligible evaluation history is under 10 years; otherwise the 2-year cap binds.
4. **Holdout when the benchmark path is already known.** The rules forbid tuning on the out-of-sample period but say nothing about prior projects that already displayed the same market's returns (see §4).
5. **Data from Prompt 2's sources:** whether licensed consensus data obtained during the event is acceptable if it can't be redistributed. The track allows outside data and forbids committing licensed raw data, which suggests yes, provided download or import instructions are given.

## 3. Existing holdout boundaries in this repository

Recorded from code and config only. No performance file was opened.

| Project | Boundary | Defined in | Holdout status (checked 2026-10-03 ~18:45 ET) |
|---|---|---|---|
| cattle_crush H1 (feedlot margin → Live Cattle) | `oos_start: 2024-10-01` (data from 2010-06-06; 2-year cap binds) | `cattle_crush/config.yaml`, `HYPOTHESIS.md` §8 | **Not evaluated.** No `results/oos_lock.json`, no `data/raw/oos/`; commit 34a75e6 says run_oos.py was not run |
| cattle_crush H2 (cattle → TSN/TXRH hedged) | OOS 2024-10-01; equity development data stops 2024-09-30 | `cattle_crush/HYPOTHESIS_H2.md` §6 | Pre-registered at 17:50 ET; no equity data for its universe loaded per that file; not run |
| GLP-1 beta sort (root `glp1_backtest.py`) | `Config.oos_start = "2024-01-01"`; data from 2018-01-01, backtest from 2021-01; price cache runs through 2026-10-02 | `glp1_backtest.py` `Config` | **Evaluated.** The code reports Full / IS / OOS statistics for every portfolio, including an SPY buy-and-hold benchmark. Tracked outputs exist (`glp1_performance.csv`, `glp1_tearsheet.png`, `robustness_grid.csv` with OOS Sharpe columns; untracked `charts/03_is_vs_oos.png`, `glp1_results.pdf`) |

Neither boundary is inherited by macro_equity. Its boundary is set from its own coverage metadata in Prompt 2.

Observation, for Aman only (no action implied): GLP-1's 2024-01-01 boundary gives about 2.75 years of holdout. On its own 2018–2026 history, the track rule would give about 1.75 years (20% binds). Changing it now, after its OOS results exist, would itself be a contamination issue.

## 4. Prior exposure of macro_equity's equity evaluation period

macro_equity trades SPY against a cash proxy. If its eligible monthly history exceeds 10 years, the 2-year cap binds, and the holdout will be roughly the last two years of matured labels. That is approximately 2024-10 → 2026-09; the exact dates are fixed in Prompt 2 from coverage metadata.

- **SPY buy-and-hold over that window has already been computed in this repo.** `glp1_backtest.py` simulates an "SPY" benchmark from the first 2021 rebalance to the latest close (2026-10-02 in the cache). It reports SPY Sharpe/CAGR separately before and after 2024-01-01 and plots SPY's growth of $1 in the tearsheet. Those outputs predate macro_equity and are tracked in git. **The macro_equity holdout is therefore not untouched with respect to SPY's return path or market direction**, and the note must say so.
- **cattle H1** downloaded SPY daily adjusted closes for 2010-06 → 2024-09 for factor checks (development period only). **cattle H2** names SPY as one hedge variant (not run).
- **macro_equity's own signals are untouched.** A repo-wide search (2026-10-03) found no code or document that builds an earnings-forecast gap, consensus EPS, real-yield (DFII10) or corporate-spread series, or a cash-proxy (BIL) timing rule. No project here has evaluated these signals or their timing returns over any period.
- **Public knowledge:** the 2024–2026 paths of equities, real yields and credit spreads are widely known to anyone working in October 2026. This is general look-ahead risk, to be disclosed.
- **Hypothesis origin:** the hypothesis was supplied by the prompt pack (reviewed commit 34a75e6). It is motivated by Sharpe & Gil de Rubio Cruz (2024), "Predicting Analysts' S&P 500 Earnings Forecast Errors and Stock Market Returns using Macroeconomic Data and Nowcasts", FEDS 2024-049 (https://doi.org/10.17016/FEDS.2024.049; abstract checked 2026-10-03).
  - The paper uses Blue Chip GDP forecasts and dollar moves, finds that a macro model predicts errors in bottom-up S&P 500 consensus, and finds that the macro-minus-analyst discrepancy predicts 3-month returns.
  - It was published in July 2024, so its sample predates our likely holdout but overlaps our development period. This is disclosed in HYPOTHESIS.md §0.

- **Incidental exposure during Prompt 2 (2026-10-03 19:21 ET):** a web-search results page displayed FactSet bottom-up consensus EPS levels for Q4 2025 and Q1 2026, a later Q3 estimate, and Q1 2026 reported growth. No gap, signal or return was computed (HYPOTHESIS.md A2).

## 5. Feasibility and time

**Prompt 2 verdict: BLOCKED** (DATA_FEASIBILITY.md). There is no free dated per-share consensus with matching actuals long enough for the frozen warmups, and no free ICE OAS history. The original estimate below is kept for the record.


On 2026-10-03 at 18:55 ET, about 16 hours remain before the 11:00 AM deadline. Prompts 1–10 also compete with cattle H1's unrun OOS evaluation and H2. The main data risk, flagged for Prompt 2 (not investigated here), is **dated historical S&P 500 consensus EPS snapshots with target quarters**. Free sources typically provide current estimates only. The prompt pack treats a missing consensus history as a genuine blocker: no substitution, and no change of hypothesis.
