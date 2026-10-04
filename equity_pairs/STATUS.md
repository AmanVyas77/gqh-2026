# STATUS — equity_pairs

Last updated: 2026-10-03, Prompt 2. Exact timestamps are in `research_log.csv`.

## Stage

| Prompt | State |
|---|---|
| 0 — Setup | Complete |
| 1 — Pre-registration | Complete. Corrected before any data was used (`snapshots/2026-10-03_prompt1_corrections/`); the original snapshot is preserved |
| 2 — Data audit + development-only feasibility pilot | **Complete. Verdict: NOT PROMISING.** See `DATA_FEASIBILITY.md` |
| Review gate | **Now.** The specification stops here |

## Verdict

**NOT PROMISING.**

- The PCA arm reached at least 5 eligible, non-overlapping pairs in 1 of 12 formations. The frozen threshold is at least 6.
- Breadth passed: 386–404 eligible stocks in every formation.
- No BLOCKED condition applies.
- The redundancy flag was not raised: 21–26% of PCA candidates overlapped the correlation baseline.
- The baselines were equally sparse (1 of 12 each).
- The binding attrition step is the union-wide Benjamini–Hochberg screen on Engle–Granger p-values from 127 observations.

Under the frozen rules this specification ends: no rescue variants, no relaxed filters, no alternate methods. Not built: the trading engine, P&L, and any evaluation of the month after formation. The holdout was never opened.

The verdict says only that this exact specification is not testable as designed. It says nothing about the economic mechanism.

## Frozen split (boundary frozen in Prompt 2, before any price request)

- **Development:** 2015-08-03 to 2024-10-02, inclusive. 2,308 sessions; 111 calendar months, the last a two-session stub.
- **Holdout:** 2024-10-03 to 2026-10-02, inclusive. 501 sessions; the two-year rule binds, at 501 versus 562 for the 20% rule.
- **Month snapping:** none.
- **Development end:** a predetermined market-on-close liquidation on 2024-10-02.
- **Data actually fetched:** only the pilot window, 2015-01-30 to 2016-06-30.

## Data limitations (from the audit)

- **Survivorship bias.** About 20% of point-in-time members (96–111 per formation) have no Yahoo history; most are former members that were later acquired or delisted.
- **No as-traded prices.** Yahoo's Close and Volume are split-adjusted, and spin-offs are encoded as splits. As a result:
  - the $5 raw-close rule falls on adjusted prices and wrongly excludes NVDA and AIV;
  - the planned raw-price accounting can't be built from this source.
- **Modern sector labels only.** About 60 former members have no label, so the sector arm's universe is smaller.
- **Identifiers.** No permanent security IDs. Ticker-based identity checks excluded 3–4 former members per formation.
- **Costs and borrow** remain assumptions. They are untested here because no P&L was computed.

## Remaining work (user's decision)

1. **Review** `DATA_FEASIBILITY.md` and the diagnostics in `pilot/results/`.
2. **Research note** (at most 5 pages), reporting the pre-registered design and this negative feasibility result. Estimated 1–2 hours of writing. No further computation is required.
3. **Any new specification** (for example a different screen, window, or representation) would be a new pre-registration made after seeing these pilot results. It must be logged as such. It is not a continuation of this specification.

## Deadline

Submission is due 2026-10-04 at 11:00 EDT. When the verdict was recorded (22:20 EDT on 2026-10-03), about 12.5 hours remained.
