# macro_equity

Gator Quant Hacks 2026, Systematic Trading track. Tests whether an independent S&P 500 earnings forecast set against analyst consensus, plus real-yield and credit-spread changes, predicts SPY's return over a cash proxy, and whether a monthly, unlevered 0/1 SPY allocation built on that forecast survives costs.

**Status: BLOCKED on data (Prompt 2).** The hypothesis is pre-registered (`HYPOTHESIS.md`). Free sources cannot supply dated historical S&P 500 consensus EPS with matching actuals, or corporate OAS history, for the frozen design; see `DATA_FEASIBILITY.md`. No research data has been downloaded and no results exist.

Data acquisition tools:

```bash
python -m macro_equity.sources.discovery                     # regenerate coverage evidence (metadata only)
```
```bash
python -m macro_equity.sources.consensus_import data/imports/consensus.csv data/imports/actuals.csv
```

The second command validates a licensed export against `data/templates/` (paths relative to the repo root).

## Setup

Python 3.11, from the repository root:

```bash
python3.11 -m venv macro_equity/.venv
macro_equity/.venv/bin/pip install -r macro_equity/requirements.txt
cp macro_equity/.env.example macro_equity/.env    # fill in keys; never commit .env
```

## Commands

```bash
python -m pytest macro_equity                     # tests (run from the repository root)
```

Planned, not yet implemented:
- `python -m macro_equity.run_all`: development-only reproduction (Prompt 8).
- `python -m macro_equity.run_oos --confirm-final`: one-time gated holdout (Prompts 8–9).

## Data policy

Raw, licensed and derived-licensed data, the quarantined holdout area and caches are git-ignored (`.gitignore`, `data/README.md`). Source manifests, coverage metadata, import templates and result summaries are tracked. Every source is cited with URL and retrieval date in `data/manifests/source_manifest.json` (Prompt 2).

## Documents

- `HYPOTHESIS.md`: the pre-registered hypothesis, design, tests and amendment log; `config.yaml` mirrors it.
- `CLAUDE.md`: rules for anyone (human or AI) working on this project.
- `STATUS.md`: progress and next steps.
- `CONTEXT.md`: verified competition rules, existing holdouts in this repo, prior exposure of the evaluation period.
