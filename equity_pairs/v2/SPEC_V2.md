# V2: amended equity-pairs experiment

**Status.** Frozen on 2026-10-03, before any V2 fitting. The parameters are in `v2/spec_v2.yaml`.

- **Why it exists.** V2 was designed after the original pilot returned NOT PROMISING. It is an amendment made with knowledge of that result, not a pre-registered confirmation.
- **What is preserved.** The V1 materials are kept unchanged: `HYPOTHESIS.md`, `config.yaml`, all snapshots, `DATA_FEASIBILITY.md` and `pilot/`.

## Questions

1. **Primary.** Does the specified pairs strategy produce positive chronological *development* performance after modeled costs? The development period runs from 2015-08-03 to 2024-10-02.
2. **Secondary.** Does PCA selection improve on the simple selection baselines (the correlation and sector arms)? This is measured by paired monthly return differences.

## What changed from V1

- **No cointegration or half-life gate.** Cointegration is no longer a selection requirement.
- **Pair ranking.** Candidates are ranked by the distance between their normalized formation prices.
- **Sizing.** Every active pair holds equal-dollar legs of ±5% of NAV, rebalanced daily.
- **Price data.**
  - Adjusted-close total-return series are used, and dividends are not added a second time.
  - Raw execution prices are not reconstructed.
  - The $5 and dollar-volume filters are removed.
- **Execution.** A signal at close t executes at close t+1. Scheduled liquidations happen at the close.
- **Borrow cost.** Accrued per calendar day.

## Unchanged

- **Formation.** 126 returns from 127 prices, re-formed monthly.
- **PCA representation.** 5 components, average linkage, cut at 0.7.
- **Trading thresholds.** Entry at |z| = 2, exit at 0.5, stop at 4, with a 20-session time limit.
- **Portfolio limits.** At most 10 pairs with no shared stocks, and at most 100% gross exposure.
- **Costs.** 10 bps per traded dollar and 3% annual borrow, with a stress case that doubles both.
- **Holdout.** Locked from 2024-10-03. It is never downloaded or evaluated without a separate instruction.

## Limitations that still apply

- **Survivorship bias.** About 20% of point-in-time members have no Yahoo data. Most are former members that were later acquired or delisted, so they are missing and the universe is survivorship-biased.
- **Sector labels.** They are modern GICS, and former members have none.
- **Not a real execution record.** This is a daily total-return exposure simulation, not a verified stock-loan and raw-share execution ledger. It says nothing about real borrow availability or trading capacity.
- **Mechanism.** The economic mechanism (compensation for absorbing temporary price pressure) remains proposed, not established.
- **No tuning.** Development results will not be used to tune this specification.
