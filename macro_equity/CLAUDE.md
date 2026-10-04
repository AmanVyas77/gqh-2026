# CLAUDE.md: macro_equity (GQH 2026, Systematic Trading track)

An isolated research project inside the gqh-2026 repo: does an independent S&P 500 earnings forecast, set against analyst consensus and combined with real-yield and credit-spread changes, time SPY against a cash proxy?
- `HYPOTHESIS.md` is the source of truth for every design choice. `config.yaml` mirrors it.
- Items marked [FIXED] change only through the §14 amendment log.
- Items marked [PROVISIONAL P#] are resolved once, at Freeze F1 at the end of Prompt 2, before anything relates a predictor to an outcome.

## Start of every session

1. Read this file, then `STATUS.md` (progress and next prompt), then `CONTEXT.md` (verified competition rules, existing holdouts, prior exposure).
2. Run `git status` and `git rev-parse HEAD`. Preserve every uncommitted change, whoever made it.
3. The prompt pack is `../Claude Code Prompts for Trading Strategy.md` (Aman may call it "GQH_Claude_Code_Prompts.md"). Run one prompt at a time, only the one Aman asks for. Execute the prompt; don't stop at a plan.
4. Finish every prompt with: changed files, checks performed, concise findings, and the next prompt's prerequisites. Update `STATUS.md` before reporting.

## Scope and isolation

- Write only inside `macro_equity/`. Treat `cattle_crush/`, `glp1_backtest.py`, `glp1_charts.py`, root-level CSV/PNG/PDF outputs, `charts/`, other hypotheses, trial logs and lock files as read-only.
- Do not run other projects' backtests. Do not open their performance outputs (`glp1_performance.csv`, `glp1_daily_returns.csv`, `robustness_grid.csv`, `glp1_*.png/pdf`, `charts/`, `cattle_crush/results/`).
- Python package `macro_equity`, always imported by its qualified name (`from macro_equity.paths import DEV_RAW`). No `src/` package, no relative imports, no `sys.path` edits; `tests/test_scaffold.py` enforces this.
- Run from the repository root: `python -m macro_equity.<module>`; tests: `python -m pytest macro_equity`.
- Interpreter for now: `cattle_crush/.venv/bin/python`. For PDF text, use the already-installed PyMuPDF in `/opt/anaconda3/bin/python` (`import fitz`); don't install packages without a verified need.
- Reuse verified conventions (pre-registration, deviation log, trial log, gated OOS lock, data audit), not cattle- or GLP-1-specific settings. Specifically, do not copy `oos_start` 2024-10-01 (cattle) or 2024-01-01 (GLP-1), cattle capital or costs, or the cattle fixed-capital cumulative-sum return convention (macro_equity compounds).

## Ground rules (non-negotiable)

1. **Deterministic runs.** No unseeded randomness; record seeds; use stable sorts and tie-breaks. The same code, config and manifests reproduce the same numbers.
2. **Publication-time alignment.** An input is used at decision time t only if it was published (timezone-aware timestamp) by t's signal cutoff, in the vintage available then. Forward-fill known values only, never backfill. A label becomes trainable only after its whole horizon has completed.
3. **Training-only fitting.** Standardization, ridge selection, clipping, scaling and every other estimated quantity are fitted only on development observations available at the fit cutoff. Use chronological folds, grouped by target quarter where relevant; never random splits.
4. **Append-only logs.** Trial log, research log, fit logs, the amendment log and lock files only ever get new rows; never edit or delete existing ones. Tests write to temporary logs.
   - Every search, source inspection, download, decision or experiment that can influence selection goes in `results/research_log.csv` via `macro_equity.research_log.append(...)`. The six trial specs are not the full attempt count (amendment A1).
   - Timestamps come from the system clock (`when=None`), never hand-typed. Mistakes are fixed by appending a correction row.
5. **No fabricated data or results.** Every number in a table, figure or the note comes from a saved artifact produced by committed code on real data. If data is missing, report BLOCKED. Never substitute current estimates for historical snapshots, revised data for real-time vintages, GAAP earnings for operating consensus, or yields for spreads.
6. **Synthetic fixtures are test-only.** They live under `tests/`, are labeled synthetic, are never written to `data/` or `results/`, and are never reported as research.
7. **No holdout evaluation outside the gated runner.** Web searches and archive listings can surface holdout-period values: restrict queries to development-period years, request metadata only (e.g. FRED pages: "do not report values"), and log any incidental exposure as an amendment (as in A2). Holdout data lives only in `data/holdout/`. Ordinary loaders reject holdout-dated observations. Nothing computes holdout signals, returns or performance until Prompt 9 explicitly authorizes `python -m macro_equity.run_oos --confirm-final`. Coverage metadata (first/last dates, row counts) may be read. The holdout boundary comes from coverage metadata, never from results.
8. **No live trading.** No paper trading, order placement or brokerage API calls.
9. **No paid downloads without separate authorization.** Each purchase needs Aman's explicit yes for that specific purchase: print the estimate and stop. No unbounded or expensive requests, and no scraping around access restrictions.

## Inherited repo conventions

10. **Never run `git commit` or `git push`.** Stage only specific `macro_equity/` paths (`git add <paths>`, never `-A` or `.`), then give Aman exact commit commands with a pathspec. No Co-Authored-By trailer.
11. **Never commit or print secrets or licensed data:** `.env`, API keys, raw or derived licensed data (see `.gitignore`, `data/README.md`).
12. **Verify external APIs against current official docs before coding.** Record URL and retrieval date; flag anything uncertain to Aman.
13. **Pre-registration.** Data-dependent details stay provisional until frozen after feasibility (Prompt 2) and before empirical exploration. After freezing, every change is appended to the amendment log with an ET timestamp, the reason, and whether any results had been seen. Frozen sections are never edited in place. If something cannot be built as specified, stop and ask Aman.
14. **Every research backtest goes through this project's own trial log** (Prompt 7), which records specification ID, git commit, dirty-code hash, and config and data hashes.

## Competition constraints (verified 2026-10-03; sources in CONTEXT.md)

- Devpost submission and final code push: **Sun 2026-10-04, 11:00 AM ET**.
- Quant note: PDF, **≤ 5 pages** including figures and tables, 11pt or larger; references and appendix excluded.
- Holdout: **most recent 20% of history or 2 years, whichever is shorter**, evaluated once.
- Net of costs, with doubled-cost results. In-sample and out-of-sample reported separately: annualized return, volatility, Sharpe, max drawdown, turnover, equity curve. Disclose the variant count and failures.
- Judges rerun the code. A mismatch with the note, lookahead, or tuning on the holdout caps the Performance score at 4.
- Everything is built during the event; cite every data source.

## Layout

```
macro_equity/
├── CLAUDE.md  STATUS.md  CONTEXT.md  README.md  DATA_FEASIBILITY.md (Prompt 2 verdict)
├── HYPOTHESIS.md         # pre-registered spec; [FIXED] / [PROVISIONAL P#]; §14 amendment log
├── config.yaml           # machine-readable mirror of HYPOTHESIS.md (hashed into trials and the lock)
├── requirements.txt  pytest.ini  .env.example  .gitignore
├── paths.py              # all project paths; dev vs quarantined holdout
├── config.py             # load_config(), config_hash(), get_key()
├── research_log.py       # append-only research-attempt log -> results/research_log.csv
├── sources/              # Prompt 2: discovery.py (coverage evidence), guard.py (fail-closed holdout guard),
│                         #           consensus_import.py (validate licensed exports against data/templates/)
├── features/             # Prompt 3: publication-aware alignment, decision and label tables
├── models/               # Prompts 4-6: earnings forecaster, replay, return models
├── portfolio/            # Prompt 7: positions, execution, costs, ledger, trial log
├── tests/
├── data/                 # see data/README.md (raw/derived/holdout git-ignored)
└── results/              # tracked summaries and logs (created when first written)
```
