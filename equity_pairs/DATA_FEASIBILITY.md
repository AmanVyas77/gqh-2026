# DATA_FEASIBILITY — equity_pairs (Prompt 2)

## Verdict: **NOT PROMISING**

**Triggering evidence (frozen gate).**

- The PCA-clustering arm produced at least 5 eligible, non-overlapping pairs in **1 of 12** formations. Only 2015-07-31 reached it, with 10 pairs.
- The frozen threshold is at least 6 of 12.
- No BLOCKED condition applies:
  - 12 of 12 formations are available;
  - 0 formations had fewer than 300 eligible stocks (eligible counts were 386–404);
  - the data conventions are usable for formation diagnostics;
  - holdout protection held (see below);
  - the timebox completed.
- **Redundancy flag: not raised.** PCA candidates that were also correlation-baseline candidates made up 21–26% in every formation, against the 90% threshold.

Under the frozen rules this specification **stops here**. There are no rescue variants, no relaxed filters, and no alternate methods.

**What the verdict does and does not mean.** The pilot establishes only that this frozen specification yields too few tradable PCA-arm pairs, in its earliest year, for the planned test to be informative.

It is **not** evidence about:

- profitability;
- convergence in the following month;
- the value PCA adds over the baselines;
- the economic mechanism.

The baselines fared no better (each reached ≥ 5 selected pairs in 1 of 12 formations), so the binding constraint is shared by all three arms. The twelve formation windows overlap by about five-sixths, so they are not twelve independent confirmations.

## Timebox

| Event | Time (EDT, 2026-10-03) | Elapsed |
|---|---|---|
| Timer start (after Part A) | 22:11:48 | 0:00 |
| Sources resolved; boundary frozen | ≈ 22:13 | ≈ 2 min (discovery limit 15) |
| Pilot prices fetched | ≈ 22:15 | 3 min 23 s |
| First complete pilot output | ≈ 22:19 | 7 min 31 s |
| Verification done; verdict recorded | 22:20:47 | 8 min 59 s |
| Documentation finished | see `research_log.csv` | within 45 min |

## Sources and conventions

The full record is in `data/source_manifest.json`.

- **Membership.** Point-in-time S&P 500 membership was reconstructed from pinned Wikipedia revisions:
  - the changes table, revid 1376064088, with 409 changes from 1976 to 2026;
  - the current list, revid 1376729338.
  - At each formation end, every change dated after it was reversed.
  - This gives 505–508 names per formation end, consistent with the index's roughly 503–505 securities.
  - **This is evidence of consistency, not proof that the changes table is complete.**
- **Prices.** yfinance 1.7.0 with `auto_adjust=False`.
  - **Close and Volume are split-adjusted, not as-traded.** For example, the AAPL Close for 2015-07-31 is 30.33, versus 121.30 as traded.
  - Adj Close is adjusted for splits and dividends. Its returns match (Close + Div) / previous Close to a p99 difference of 1.8e-5 (max 3.4e-3).
  - The end date is exclusive; a probe returned 2015-02-02 as its last date.
- **Fetched range.** Only the pilot window was fetched: 2015-01-30 to 2016-06-30, covering 536 tickers, of which 417 returned rows.
- **Identifiers.**
  - No free permanent security ID exists, so Yahoo tickers are used.
  - The issuer is identified by SEC CIK for current members and by normalized security name for former members.
  - Share classes excluded from pairing with each other: GOOG/GOOGL and NWS/NWSA. FOX/FOXA would have been, but those tickers have no 2015–16 history on Yahoo.
- **Sectors.** Modern GICS labels from Wikipedia. About 60 former members with price data have no label, so they get no sector-arm candidates. They remain in the PCA and correlation arms.
- **Existing connector.** Its schema offers historical constituents and unadjusted prices, but only through interactive per-symbol calls that can't be scripted reproducibly. It was not used.

## Holdout protection (evidence)

- The boundary was frozen before any price request (snapshot `snapshots/2026-10-03_prompt2_boundary_freeze/`):
  - holdout 2024-10-03 to 2026-10-02, 501 sessions;
  - development ends 2024-10-02.
- `guard.check_request` ran before the probe and before the pilot request. `guard.check_dates` ran on every returned frame, both at fetch and again at run start.
- The latest date fetched is **2016-06-30**. No development data after the pilot window, and no holdout data, was requested.
- The guard also refuses to run if config.yaml and HYPOTHESIS.md conflict. The pilot calls `spec.require_consistent` before it starts.

## Audit (pilot window only)

- **Missing sessions.**
  - All 358 XNYS sessions are present in the data, with no extra dates.
  - Per stock, 0–3 eligible-looking members per formation had incomplete windows and were excluded. No values were filled.
- **Stale prices.**
  - One stock per formation failed the zero-volume rule.
  - None failed the identical-close-run rule or the zero-return-share rule.
- **Duplicates and ticker changes.**
  - No pair of tickers had near-identical return series (correlation > 0.995).
  - 3–4 former-member tickers per formation failed the frozen identity check (Yahoo first-trade date or name mismatch) and were excluded.
  - Today's tickers DOW, FOX, FOXA and SNDK belong to different entities than the 2015–16 members of those names and have no history in the window.
- **Adjustment jumps.**
  - There were 25 split events in the window. Close changes on split days stayed within ±3%, consistent with split adjustment.
  - Yahoo encodes spin-offs as fractional "splits" (EBAY 2.376 for PayPal; BAX 1.841 for Baxalta; DRI 1.119).
  - Nine daily adjusted moves exceeded 25%. All are single-stock events with no adjustment artifact (for example FCX, FOSL, WMB).
- **Survivorship gap.** 96–111 point-in-time members per formation (about 20%) have no Yahoo history, mostly former members that were later acquired or delisted. They are excluded, so **the universe is survivorship-biased**.

### Conflicts with frozen assumptions (reported, not resolved)

1. **Raw-close $5 rule.**
   - As-traded prices are unavailable, so the rule was applied to split-adjusted Close, as frozen before the fetch.
   - That wrongly excludes NVDA and AIV. Their as-traded prices were well above $5; later splits and spin-offs, some after the boundary, push the adjusted levels below $5.
   - The effect is 1–2 stocks per formation, which is immaterial to the verdict, but it is look-ahead filtering by construction.
2. **Return formula.** The spec's total-return formula on raw prices is replaced by Adj Close ratios. The difference is second-order.
3. **Accounting.** The spec assumes raw execution prices with a split/dividend ledger. That cannot be built from this source:
   - there are no as-traded prices;
   - spin-offs are encoded as splits;
   - delisting returns are absent.
4. **Sector baseline.** It uses modern labels and has a slightly smaller universe than the other two arms, because former members are unlabelled.

## Formation table (12 overlapping windows; descriptive)

| Formation end | PIT members | With Yahoo data | Eligible | Clusters (multi / singletons / largest) | Candidates PCA / corr / sector | Union tested | Raw p≤0.05 (union) | BH pass (union) | PCA: BH → β → half-life → selected | Corr selected | Sector selected | PCA∩corr candidates | Runtime (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2015-07-31 | 505 | 395 | 386 | 9 (6 / 3 / 213) | 780 / 941 / 771 | 1862 | 361 | 115 | 43 → 17 → 15 → **10** | 10 | 10 | 21% | 14.8 |
| 2015-08-31 | 505 | 395 | 386 | 7 (4 / 3 / 315) | 802 / 979 / 792 | 1890 | 211 | 1 | 1 → 1 → 0 → **0** | 0 | 0 | 23% | 14.9 |
| 2015-09-30 | 508 | 397 | 386 | 5 (4 / 1 / 284) | 807 / 975 / 791 | 1897 | 150 | 0 | 0 → 0 → 0 → **0** | 0 | 0 | 23% | 15.1 |
| 2015-10-30 | 508 | 398 | 387 | 7 (7 / 0 / 285) | 786 / 995 / 804 | 1881 | 135 | 0 | 0 → 0 → 0 → **0** | 0 | 0 | 22% | 14.9 |
| 2015-11-30 | 508 | 400 | 389 | 5 (5 / 0 / 219) | 809 / 994 / 810 | 1881 | 115 | 0 | 0 → 0 → 0 → **0** | 0 | 0 | 22% | 14.9 |
| 2015-12-31 | 507 | 401 | 390 | 6 (5 / 1 / 282) | 829 / 986 / 797 | 1890 | 152 | 0 | 0 → 0 → 0 → **0** | 0 | 0 | 22% | 15.1 |
| 2016-01-29 | 507 | 401 | 391 | 4 (4 / 0 / 313) | 830 / 986 / 795 | 1894 | 106 | 2 | 0 → 0 → 0 → **0** | 1 | 1 | 23% | 11.1 |
| 2016-02-29 | 507 | 403 | 394 | 7 (6 / 1 / 219) | 818 / 960 / 798 | 1852 | 103 | 0 | 0 → 0 → 0 → **0** | 0 | 0 | 24% | 10.8 |
| 2016-03-31 | 507 | 405 | 397 | 7 (5 / 2 / 241) | 808 / 971 / 790 | 1843 | 153 | 8 | 1 → 1 → 1 → **1** | 3 | 2 | 26% | 10.8 |
| 2016-04-29 | 508 | 406 | 398 | 7 (6 / 1 / 199) | 806 / 972 / 799 | 1853 | 181 | 12 | 6 → 5 → 4 → **3** | 2 | 2 | 26% | 11.0 |
| 2016-05-31 | 508 | 411 | 403 | 9 (6 / 3 / 240) | 828 / 986 / 803 | 1884 | 162 | 11 | 6 → 5 → 3 → **3** | 2 | 3 | 25% | 11.3 |
| 2016-06-30 | 508 | 412 | 404 | 9 (7 / 2 / 213) | 823 / 984 / 809 | 1906 | 206 | 2 | 1 → 1 → 0 → **0** | 0 | 0 | 22% | 11.3 |

### Exclusions by first failing rule

| Formation end | no_yahoo_data | identity_unverified | incomplete_window | stale_zero_volume | price_below_5_split_adjusted | median_dollar_volume_below_20m |
|---|---|---|---|---|---|---|
| 2015-07-31 | 110 | 4 | 2 | 1 | 1 | 1 |
| 2015-08-31 | 110 | 4 | 2 | 1 | 1 | 1 |
| 2015-09-30 | 111 | 4 | 2 | 1 | 2 | 2 |
| 2015-10-30 | 110 | 4 | 2 | 1 | 2 | 2 |
| 2015-11-30 | 108 | 4 | 3 | 1 | 1 | 2 |
| 2015-12-31 | 106 | 4 | 3 | 1 | 1 | 2 |
| 2016-01-29 | 106 | 4 | 1 | 1 | 2 | 2 |
| 2016-02-29 | 104 | 4 | 1 | 1 | 1 | 2 |
| 2016-03-31 | 102 | 3 | 1 | 1 | 1 | 2 |
| 2016-04-29 | 102 | 4 | 0 | 1 | 1 | 2 |
| 2016-05-31 | 97 | 4 | 0 | 1 | 1 | 2 |
| 2016-06-30 | 96 | 4 | 0 | 1 | 1 | 2 |

No formation had exclusions for non-positive prices, zero variance, identical-close runs, the zero-return share, or zero loading vectors.

## Findings

- **Where attrition binds.**
  - Each formation tests about 1,850–1,900 candidate pairs, pooled across the three arms.
  - Raw Engle–Granger p ≤ 0.05 occurs in 5.5–19% of them, against 5% expected under the null.
  - After union-wide Benjamini–Hochberg at q = 0.05, 0–12 pairs survive, except in the first formation (115).
  - With a family of about 1,880 tests, the best-ranked pair needs p of roughly 2.7e-5. With 127 observations, few spreads reach that.
  - The beta and half-life screens remove a further share of the BH survivors.
  - Several windows include the August 2015 and January–February 2016 market stress, which may weaken cointegration within those windows. This is descriptive, not tested.
- **Clusters are coarse.**
  - The 0.7 cut on unit-norm five-component loadings yields only 4–9 clusters per formation.
  - One cluster holds 199–315 of the roughly 390 eligible stocks.
  - With the market component retained, as frozen, the within-cluster restriction is weak, so the PCA arm amounts mostly to nearest neighbours in loading space.
- **Candidate overlap.**
  - 21–26% of PCA candidates are also correlation-baseline candidates.
  - 17–21% are also sector-baseline candidates.
  - So PCA proposes mostly different pairs, but they do not survive the shared screen any better.
- **Adjacent-window stability (descriptive only; windows overlap).** Whenever consecutive formations had any PCA passing or selected pairs, their Jaccard overlap was 0.0. No passing pair persisted from one month-end to the next.

## Files

| Path | Contents |
|---|---|
| `pilot/data.py` | Membership reconstruction and guarded fetch |
| `pilot/run.py` | Audit and formation pipeline |
| `pilot/results/formation_diagnostics.csv` | Per-formation diagnostics |
| `pilot/results/audit.json` | Audit results |
| `pilot/results/gate.json` | Gate inputs and verdict |
| `pilot/results/adjacent_stability_descriptive.json` | Descriptive stability between consecutive windows |
| `pilot/results/pair_sets.json` | Candidate, passing and selected pair sets per arm |
| `data/source_manifest.json` | Source record |
| `data/raw/` | Raw source and price files (gitignored) |
