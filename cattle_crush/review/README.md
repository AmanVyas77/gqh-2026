# Post-evaluation review material (4 October 2026)

Everything in this directory was produced **after** the one-time holdout evaluation (lock: commit
`58d6299`, 2026-10-04 04:45:01 UTC). It is post-evaluation evidence: audits, corrections, uncertainty
intervals and funding/capacity supplements computed from existing development records. It is not
preregistered confirmation, it does not replace either frozen primary, and no holdout evaluation was
rerun to produce it. Both registered decisions (H1 and H2 rejected) are unchanged.

The original frozen artifacts are in `../results/` and are hash-checked by `../verify_submission.py`.

## Included (hashes in `../submission/artifacts.json`)

The original review material was copied unchanged. The prospective risk assessment was subsequently added during paper integration; it is qualitative and introduces no new strategy calculations.

| Path | Content |
|---|---|
| `risk_methodology_assessment.md` | Four prospective governance scenarios, capital definitions, responsibilities and unresolved dependencies; not an effectiveness test |
| `extension/REPORT.md` | Uncertainty intervals, settlement-receipt checks, GF final-price uncertainty, funding requirements, actual-order capacity |
| `extension/tables/*.csv` | Summary tables behind the note's [14] figures (intervals, placements interpretation, order capacity, funding envelopes, execution-session counts, receipt audit, GF finals, concentration, volume variability) |
| `corrected/tables/*.csv` | Current-NAV risk, order participation, the post-evaluation execution correction (development only) and corrected robustness windows |
| `editorial_revision/EDITORIAL_NOTES.md` | Material moved out of the note, raw-log snapshot reconciliation, holdout drawdown rounding fix |
| `deviation_chronology.csv` | All 23 deviation-log rows with first introducing commits and timestamps |
| `regulatory_check.md` | Official sources for limits and margins, with completeness qualifications |

## Deliberately not included

- **Per-date detail tables** (`*_detail.csv`) and the GF missing-final exposure rows. They carry dated
  prices, volumes or NAV paths derived from licensed CME data.
- **`offline.py` and its manifest**, plus `run_development.py`,
  `extension_analysis.py`, the patched `src/` files and the review trial log. The offline entry point
  pins the review checkout's patched sources and exact licensed local inputs, so it would refuse to run
  here, by design. For a market-data-free check of this submission, run `python verify_submission.py`.
- Pre-edit note drafts and PDF QA renders (superseded).

## Corrections made in the review (development only)

1. Running-peak drawdown includes initial NAV (H1 analysis and H2).
2. Common and seasonal robustness comparisons use all A/B/C starts.
3. Deflated Sharpe generation runs after the development stages; the H2 DSR table was regenerated.
4. Unknown execution-session status is tracked; the stricter `require_verified_session` correction is
   development-only and refuses holdout use. No threshold, signal or sizing parameter changed.
5. Held exposure is carried at its last mark when a settlement is missing (exposure reporting, not P&L).
6. Orders are measured against signal-date ADV, including roll legs; margin and gross exposure are also
   reported against current NAV.
7. Future-price perturbation tests at three predetermined development cutoffs.

## Limitations that remain

- **Holdout turnover is missing**: no holdout trade ledger was saved, and it is not inferred.
- H2 volume-based capacity, factor attribution and its four registered alternative trials were not run;
  no five-trial H2-only DSR is claimed.
- Funding uses current margin proxies, not historical margin calls; capacity figures are participation
  illustrations, not profitable capacity; fills are not verified.
- The 2 October NASS probe returned post-cutoff rows in memory before the boundary was enforced (see the
  note, Section 4); absolute claims that no holdout data was accessed are unsupported.
