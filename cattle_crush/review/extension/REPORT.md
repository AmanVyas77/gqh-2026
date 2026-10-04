# Additional evidence from existing development inputs

Post-evaluation supplement, 4 October 2026. These analyses explain uncertainty and implementation risk; they are not new acceptance tests, strategy variants or tuning exercises. No holdout strategy was evaluated, no market data acquired and no original artifacts changed. The calculation plan is recorded in PLAN.md.

## Economic interpretation and statistical precision

H1 links three distinct claims: projected margin measures feeding incentives; incentives alter future placements; and subsequent supply news is not fully reflected in deferred futures prices. P1 addresses a linear margin-to-placement association. P3 uses a futures-based spot proxy to examine price response. P2 tests whether the frozen trading rule earns returns. Failure at one link does not identify the reason for failure at another. H2 adds a separate equity cost-transmission hypothesis, conceived after H1 failed; it is not independent corroboration of H1.

P1's estimated slope is 0.001970 log-placement units per margin-z unit, with 95% HAC interval [-0.007295, 0.011235]. For a one-unit fall in z, the implied placement change is -0.197%, with interval [-1.117%, +0.732%]. Applied descriptively to the sample's mean prior-year three-month placements of 5,616,511 head, this is -11,053 head, with interval [-62,749, +41,123]. This is not a causal estimate or a forecast of a specific feedlot cohort. The margin proxy still lacks the declared closeout-level calibration and placements are revised large-feedlot totals.

The estimated-SE minimum detectable slope at 80% power and the registered directional t>2 threshold is 0.01343 log units, corresponding to roughly a 1.334% placement reduction for a one-unit lower z. Formula: (2 + Phi^-1(0.80)) × HAC standard error. This is a sensitivity approximation conditional on the observed design, estimated variance and normal asymptotics; it is not "observed power" computed from the fitted effect. It uses all 133 P1 observations and does not establish power for the 15 distressed month-ends alone. There is no externally calibrated economically meaningful effect threshold in the available inputs, so the study cannot claim to exclude every useful economic effect.

| Registered quantity | Estimate | 95% HAC interval | 80%-power detectable magnitude at directional t=2 |
|---|---:|---:|---:|
| P2 A monthly net return | -0.0450% | [-0.3076%, +0.2177%] | 0.3808% monthly |
| Q3 H2 monthly net return | -0.1535% | [-0.4315%, +0.1245%] | 0.4031% monthly |
| Q2 basket response per H2 signal unit | +0.3610% | [-0.4475%, +1.1695%] | 1.1722% |

Full estimates, units, counts and lag choices for P1/P2/P3/Q1/Q2/Q3 are in uncertainty.csv. Intervals are asymptotic normal using the registered HAC choices (P1 3, P2 5, P3 6, H2 2 lags), not bootstrap or independent-observation intervals. No multiplicity correction is claimed for this descriptive supplement. The intervals show uncertainty; they do not satisfy the original acceptance rules or reverse either rejection.

## Existing-record execution audit

Across original development order legs, missing/invalid session ranges affect A LE 8/202, B LE 8/202, B GF 10/198, and C LE 8/128; B corn has none. These counts include roll legs and are not distinct dates. Their traded notionals are provided in execution_session_summary.csv. Available high/low ranges are compatible with the registered lock proxy but do not prove an order filled at settlement or detect every practical liquidity restriction.

For raw settlement records, a separate cutoff audit uses 00:00 UTC immediately after the reference date. Many selected records arrive later, including identical replays and evening US publications. Where a record exists by the cutoff, no selected price differs from that cutoff selection. All 136 development H1 margin-signal inputs for each of LE/GF/ZC have a matching price by that cutoff. This includes the final September 2024 signal and is not a count of executed development rebalances. Counts and cutoff are explicit in settlement_receipt_summary.csv. This does not certify all volatility-history availability, H2 input vintages, exact exchange execution times or the holdout.

There are 90 GF cash-final/last-available comparisons; 89 last marks are on the actual last trading date, and one is earlier because of a gap. Absolute discrepancy median is 0.149%, maximum 0.842%. Four original B closes substitute the last available settlement for missing cash finals. Applying the observed maximum relative discrepancy to their absolute notionals gives a combined absolute-dollar illustration of $14,008 (1.401% of initial capital). This is not an upper bound, imputation, estimate of bias direction or revised performance; missing true finals remain unknown. GFQ2018 accounts for about $7,519 of that illustration.

## Funding using existing positions and margin assumptions

Reconstructed saved contract holdings and daily NAV use the original development positions. Margin is the supplied current per-contract initial-margin proxy, summed without offsets. Free equity assumes all NAV is available as eligible collateral; historical margin increases, broker add-ons, eligibility haircuts, intraday calls and forced-liquidation execution remain unmodeled.

| Variant | Minimum free equity after modeled margin | Minimum NAV / margin | Largest observed five-session funding envelope |
|---|---:|---:|---:|
| A | $684,706 | 7.70× | $154,070 |
| B | $379,966 | 2.41× | $338,794 |
| C | $777,230 | 7.90× | $154,070 |

Minimum NAV/margin is the smallest uniform multiplier of the supplied margin schedule that would exhaust NAV at a sampled end-of-day position. It is not a safe funding target. The five-session envelope is the maximum, across rolling windows and every intermediate day, of modeled initial margin plus net P&L loss since the window's start. It includes intervening gains as credits, uses five observed strategy sessions and is a historical descriptive measure, not a stress forecast. One- and five-session net cash losses, daily requirements and dates are in the supplement. B's previously reported 41.6% maximum margin/NAV is consistent with a 2.41× break-even multiplier.

## Futures capacity and concentration

Actual orders, including reversals and both roll legs, are scaled linearly from $1M. These are the original registered participation illustrations, not calibrated market-impact limits.

| Variant | AUM at 1% ADV | AUM at 5% ADV | AUM at 10% ADV | Binding order |
|---|---:|---:|---:|---|
| A | $1.277M | $6.384M | $12.768M | LEG2014, 2013-09-03 |
| B | $0.764M | $3.818M | $7.636M | GFU2013, 2013-08-01 |
| C | $1.524M | $7.620M | $15.241M | LEJ2014, 2013-11-01 |

These ceilings use the largest historical order/previous-20-session ADV ratio. They assume participation scales proportionally, other traders do not react, and fills/volumes remain available. Negative starting performance establishes no profitable AUM capacity. Exchange aggregation, broker limits and margin funding can impose additional constraints; H2 capacity remains unmeasured without volumes.

The median coefficient of variation of daily volume within those windows is about 0.30 for LE and 0.35 for GF/corn; corn's maximum is 1.08. Missing bars occur in 10 A LE order windows, 8 B GF, 10 B LE, 5 B corn and 8 C LE windows. These windows can overlap. Existing methodology treats missing volume as zero, so the table reports missing counts explicitly and does not confuse them with confirmed zero-volume sessions. The UTC daily-bar convention remains imperfect for corn overnight sessions.

The five largest contracts account for 23.37% of A traded notional, 9.33% of B and 32.24% of C. Contract concentration describes execution dependence, not return attribution. It does not imply that the two-stock H2 universe is diversified.

## Offline reproducibility

`python review/offline.py verify` verifies pinned source, input and saved-artifact hashes plus direct dependency versions. `supplement` regenerates this extension without backtests. `development` explicitly runs the existing development reproduction into review/corrected, preserving original results. There is no holdout mode. Network connections/DNS, credential-file opens and holdout-data opens are refused inside the Python process; source hashes are checked before execution. This is not an operating-system sandbox for arbitrary external executables.

Inputs remain licensed/local and excluded from the package. Exact byte hashes require the same lawful snapshots; independently re-downloaded or re-encoded equivalent data may fail verification. Missing or changed inputs stop execution rather than trigger acquisition. The manifest-authoring utility is separate and never invoked automatically by verification. Python 3.12.2 was used; a runtime difference is disclosed, while mismatched direct dependencies stop execution.

## Provisional rubric reassessment

Economic Foundation 7/10: stronger effect-size interpretation and honest precision limits, with calibration still missing. Performance 8/10: frozen outcomes, comparison artifacts and offline checks remain strong; missing holdout turnover persists. Risk Management 7/10: empirical record checks and funding measures improve evidence, but historical funding and actual fills remain unverified. Liquidity & Capital 7/10: actual-order capacity, variability and concentration are now quantified; H2 volumes and the complete current rule table are still missing. Innovation 6/10: the economic framework is unchanged. Total 35/50 is a reviewer estimate, not a judging guarantee.
