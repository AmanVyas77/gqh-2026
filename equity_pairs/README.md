# equity_pairs — PCA-clustered S&P 500 pairs

## Research question

At each month end, the method runs four steps:

1. Represent every eligible S&P 500 stock by its loadings on the first five principal components of the past six months (126 sessions) of standardized daily returns.
2. Cluster those loadings.
3. Pair each stock with its nearest neighbours inside its cluster.
4. Keep only pairs whose price spreads pass a cointegration and half-life screen.

The study asks three separate questions:

1. **Convergence.** Do the selected spreads mean-revert afterwards?
2. **Selection.** Does PCA clustering select better pairs than two baselines that use the same downstream rules?
   - Correlation baseline: pairs ranked by plain return correlation.
   - Sector baseline: same-sector pairs.
3. **Economics.** Are net returns positive after modeled costs, without being mostly factor exposure or a few concentrated outcomes?

The proposed mechanism, compensation for absorbing temporary price pressure, is a hypothesis. A price backtest cannot prove it.

## Status

- Prompt 2 (feasibility pilot) is complete. **Verdict: NOT PROMISING.** The specification stops here; see `DATA_FEASIBILITY.md`.
- Only pilot-window data (2015-01-30 to 2016-06-30) was downloaded. The holdout was never opened, and no P&L was computed.
- See `STATUS.md`.

## Layout

| Path | Purpose |
|---|---|
| `CLAUDE.md` | Agent rules: scope, staging, holdout, logging |
| `HYPOTHESIS.md` | Economic hypothesis (user), followed by the frozen specification and explicit nulls |
| `config.yaml` | Frozen numbers; governs over the prose |
| `STATUS.md` | Stage, gate, remaining decisions, risks |
| `CONTEXT.md` | Definitions, design notes, environment, disclosures |
| `split.py` | Warmup, development and holdout split from the XNYS calendar (`python split.py`) |
| `guard.py` | Fail-closed holdout guard; every loader must use it |
| `spec.py` | Config consistency checks |
| `tests/` | Config, guard and split tests (no market data) |
| `snapshots/` | Dated, hashed copies of the hypothesis and config |
| `research_log.csv` | Append-only, timestamped log |
| `DATA_FEASIBILITY.md` | Prompt 2 verdict, audit, and the 12-formation table |
| `data/source_manifest.json` | Sources, retrieval times, conventions, limitations, and commands |
| `pilot/data.py`, `pilot/run.py` | Guarded pilot fetch; structural pilot (formation diagnostics only) |
| `pilot/results/` | Diagnostics CSV and JSON outputs |
| `requirements.txt`, `requirements-lock.txt` | Pinned dependencies |

## Reproducing

```bash
cd equity_pairs
/opt/anaconda3/bin/python3.11 -m venv .venv   # any Python 3.11
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pytest
.venv/bin/python split.py
.venv/bin/python pilot/data.py   # needs the pinned Wikipedia pages in data/raw/sources/ (see data/source_manifest.json)
.venv/bin/python pilot/run.py
```

## Deliverables

Due **Sunday 2026-10-04, 11:00 America/New_York**:

- a research note of at most 5 pages;
- reproducible code in this folder.
