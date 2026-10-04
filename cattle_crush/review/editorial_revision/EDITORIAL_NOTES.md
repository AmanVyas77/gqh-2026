# Editorial revision, 4 October 2026

This revision changes reporting and organization only. It does not change hypotheses, parameters, original result artifacts, trial decisions or the holdout evaluation. The pre-edit HTML/PDF are preserved here as before_research_note_extended.html/pdf. No research code, backtest, download, or holdout evaluation was run.

## Reporting corrections and existing evidence

- H1 primary holdout net maximum drawdown: saved fraction 0.054466625142137515 = 5.4466625%, rounded to 5.4% at one decimal, replacing 5.5%. Gross and doubled-cost values remain 5.4% and 5.5%. Original tables remain unchanged.
- Missing settlement prices deferred orders; unknown high/low ranges originally counted as unlocked. The stricter execution correction is explicitly post-evaluation and development-only.
- H2 gross attribution of -12.1% and -4.5% belongs to TXRH/XLY and TSN/XLP pairs, not standalone stocks.
- Low z denotes relative margin distress; it does not establish absolute negative profit. P3 spot is a front-futures proxy. Arithmetic returns use fixed initial capital, not CAGR.
- Added existing HAC intervals: H1 P2 [-0.3076%, +0.2177%] and H2 Q3 [-0.4315%, +0.1245%] monthly; normal asymptotic intervals use the registered lags. No new inference was calculated.
- Existing A seasonal-only diagnostic: 75 months, return correlation 0.860119 and R² 0.739805. Joint P1 margin coefficient t=1.793458. Diagnostics do not replace primaries.
- Root README now identifies the current six-page PDF and completed holdout evaluation; the saved-result rounding is aligned.

## Material moved from main prose (retained evidence)

Chronology: H1 registration e9334b9 precedes its first backtest. CFTC/GF deviations were committed at 17:44:37 ET on 3 October, after C 17:38:46 and B 17:40:27. H2 registration cb7a954 was at 17:50 ET; detailed implementation choices were committed at 23:27:33 after its first logged run at 23:21:58. The t-statistic reporting fix was post-result. See ../deviation_chronology.csv; declared row times cannot prove prior commitment.

The holdout lock records 2026-10-04T04:45:01Z and config hash ef37283b9a3362b5c1749b3cff858a51d9ad511936955b1a650703ca0c80fb51. H1/H2 reject under their registered decisions. B/C overlays remained half-size throughout the holdout because their own drawdowns remained beyond the 7.5% restore threshold; identical Sharpes under constant scaling do not establish improved performance.

Trial accounting: archived original log has 171 rows: 76 trial, 73 overlay, 15 diagnostic, 7 oos. The first 164 are development rows, consistent with SUBMISSION_FREEZE.md. There are 25 distinct trial variant/spec pairs. Original tables/trials.csv carries an earlier 162-row / 75-trial-row snapshot, while DSR uses the same 25 distinct configurations. Later review reproduction logs are separate. Four registered H2 alternatives were not run; no five-trial H2-only DSR or complete 29-trial analysis is claimed. Other team projects and diagnostic/overlay searches remain outside this count. DSR uses daily units/non-excess kurtosis; correlation and serial dependence qualify its assumptions.

H1 precision: the estimated-SE sensitivity is about a 1.33% placement response per z unit for 80% power at directional t>2, using all 133 P1 observations. It is not observed power or assurance of adequate power for 15 distressed observations. Formula and intervals remain in ../extension/REPORT.md.

H2 supplementary detail: gross/net/2x-cost losses below initial NAV were -26.1%/-28.9%/-31.6%, distinct from peak drawdown. Mean stock exposure was 0.23x, net near zero. Largest absolute gross months were March 2020 -7.8%, October 2015 -7.1%, December 2023 +6.1%; excluding them, cumulative gross P&L remains -7.8%, with 51% positive months. These are descriptive diagnostics, not revised strategy results.

Execution: original executions generally lagged one day, with one B order deferred an extra day. All 136 H1 development margin inputs per root match prices available by following midnight UTC; this includes the final September 2024 signal, not 136 executed rebalances. It does not certify all volatility inputs, H2 vintages, actual fills or holdout inputs. Future-price perturbation tests at three development cutoffs cover M, z and A/B/C/H2 targets, not every metadata/publication vintage. Missing feed observations are not verified holidays; last marks retain exposure without synthetic P&L.

Four missing B GF cash finals remain unknown. Applying the largest observed discrepancy from other contracts to their notionals gives $14,008; this is neither an upper bound nor imputed loss. Details remain in ../extension/REPORT.md. Gross and 2x costs for the overlay use the same positions.

Regulation: 600 contracts is a spot-month limit, not a deferred ceiling; 6,300 is a qualified recent LE single-month benchmark, not a verified complete current rule assessment. See ../regulatory_check.md. Funding uses current margin proxies without historical intraday calls, broker add-ons or collateral haircuts. Capacity is a participation illustration, not calibrated profitable AUM.

Reproduction: offline verification pins exact source/input/artifact hashes and dependencies and refuses downloads and holdout-data reads in its Python process. It is not an OS sandbox or a demonstration of judge-side reproduction of every headline result. Licensed/local inputs remain necessary. No holdout ledger is supplied; turnover remains missing.

## Presentation and format

Main text retains five pages plus references, at least 11-point text and standard margins. References are excluded under the official track page, independently read in the browser during the review. The archived curve pixels are retained unchanged; chart production details were removed from the caption. Full prior prose is retained in the pre-edit HTML. Protected source/result hashes are recorded in protected_hashes.json and checked after rendering.
