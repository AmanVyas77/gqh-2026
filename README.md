# Gator Quant Hacks 2026, Systematic Trading track

**Submission: [`cattle_crush/`](cattle_crush/)** — feedlot margins, Live Cattle futures and
beef-exposed equities. Authors: Aman Vyas, Zhicheng Li, Nicolas Slenko.

- **Note (PDF):** [`cattle_crush/paper/research_note_edited.pdf`](cattle_crush/paper/research_note_edited.pdf),
  five main pages plus references. Editable source: `cattle_crush/paper/research_note_edited.html`.
- **Result:** both frozen primaries are rejected under their registered decisions. Development net
  Sharpe: H1 −0.08, H2 −0.29. The once-evaluated holdout (2024-10-01 to 2026-10-02): H1 +0.63, H2 −0.15.
  H1's positive holdout Sharpe does not reverse its failed development conditions.

## Check the submission (no data, no credentials, standard library only)

```bash
cd cattle_crush
python verify_submission.py
```

This verifies artifact hashes, maps the numerical claims in the note to saved result rows, confirms the registered
decisions and trial accounting, and checks recovered holdout turnover against a frozen-strategy replay. It is an artifact
check, not a backtest rerun. Full development and holdout reproduction (`python reproduce_submission.py` from `cattle_crush/`) needs licensed
Databento data and API keys; see [`cattle_crush/README.md`](cattle_crush/README.md) for setup,
dependencies (`cattle_crush/requirements.txt`, Python 3.11), data acquisition and limitations.

| Where | What |
|---|---|
| `cattle_crush/HYPOTHESIS.md`, `HYPOTHESIS_H2.md`, `SUBMISSION_FREEZE.md` | Frozen specifications and provenance |
| `cattle_crush/src/`, `run_all.py`, `run_oos.py` | Signal, backtest and analysis code |
| `cattle_crush/data/download.py`, `.env.example` | Data acquisition (licensed data and keys are never committed) |
| `cattle_crush/results/` | Original saved results, trial log and holdout lock |
| `cattle_crush/review/` | Post-evaluation corrections and supplements, labelled as such |
| `cattle_crush/submission/`, `verify_submission.py`, `tests/` | Claims and hash manifests, verifier, tests |

The other top-level folders (`equity_pairs/`, `macro_equity/`, the `glp1_*` files) are separate team
projects and are not part of this submission.
