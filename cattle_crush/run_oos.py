"""One-time holdout evaluation of the two frozen primary specifications (SUBMISSION_FREEZE.md).

  H1 primary: Variant A, primary spec (HYPOTHESIS.md Section 6). P2's holdout condition: net Sharpe > 0.
  H2 primary: two-stock basket, 1-month cattle signal, sector-ETF hedges (HYPOTHESIS_H2.md).
              Q3's holdout condition: net Sharpe > 0.

Both are reported regardless of outcome. Also reported, as pre-registered secondary results (never
substituted for the primaries): H1 Variants B and C at the primary spec, and the drawdown overlay
alongside each H1 variant. Holdout = dates on or after oos_start (2024-10-01) in config.yaml.

First run
- Requires --confirm-final, and refuses if results/oos_lock.json exists.
- Refuses unless the frozen specification is committed: no uncommitted changes to the code, config,
  hypotheses or manual reference data in cattle_crush/ (so the lock's git commit pins the code).
- Fetches the holdout data: Databento (prints the cost estimate; requires --yes to buy), CFTC COT,
  and a full-history re-download of the H2 equities. Removes stale holdout caches.
- Writes results/oos_lock.json (config hash, git commit, timestamp) BEFORE any holdout result is
  computed, so the lock marks the single evaluation; then evaluates and writes
  results/tables/oos_performance.csv and results/figures/oos_equity.png.

Later runs
- Allowed only if config.yaml's hash matches the lock (reproduction); otherwise refuse.

Usage
  python run_oos.py --confirm-final          # checks, prints the Databento estimate, then stops
  python run_oos.py --confirm-final --yes    # buys the holdout data and runs the one evaluation
  python run_oos.py                          # later: reproduce (config hash must match the lock)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "data"))

import pandas as pd  # noqa: E402

import download  # noqa: E402
from src import analysis, backtest, h2, signals, trial_log  # noqa: E402
from src.config import PROCESSED, RAW_OOS, RESULTS, ROOT, config_hash, load_config, oos_start  # noqa: E402

LOCK = RESULTS / "oos_lock.json"
OOS_FILES = [f"{r}_{k}.parquet" for r in ("LE", "GF", "ZC") for k in ("definition", "statistics", "ohlcv1d")] + \
            ["cftc_live_cattle.parquet", "h2_equities.parquet"]
FROZEN_PATHS = ["src", "config.yaml", "run_oos.py", "run_all.py", "data/download.py", "data/manual",
                "HYPOTHESIS.md", "HYPOTHESIS_H2.md", "SUBMISSION_FREEZE.md", "requirements.txt"]


def check_lock(confirm_final: bool, lock_path: Path, cfg_hash: str) -> str:
    """'first' for the one evaluation, 'repeat' for a reproduction with an unchanged config."""
    if not lock_path.exists():
        if not confirm_final:
            sys.exit("The first holdout run requires --confirm-final. It can be done only once.")
        return "first"
    lock = json.loads(lock_path.read_text())
    if lock["config_sha256"] != cfg_hash:
        sys.exit(f"config.yaml has changed since the holdout lock ({lock['timestamp_utc']}); refusing to run.")
    return "repeat"


def uncommitted_frozen_changes(root: Path = ROOT) -> list[str]:
    """Uncommitted (modified, staged or untracked) files among the frozen specification paths."""
    out = subprocess.run(["git", "status", "--porcelain", "--", *FROZEN_PATHS], cwd=root,
                         capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line.strip()]


def write_lock(lock_path: Path) -> dict:
    lock = {"config_sha256": config_hash(), "git_commit": trial_log._git_commit(),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "oos_start": str(oos_start().date()),
            "frozen_primaries": {"H1": "Variant A, primary spec", "H2": "primary specification"}}
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock, indent=2))
    return lock


def ensure_oos_data(cfg: dict, yes: bool) -> None:
    if all((RAW_OOS / f).exists() for f in OOS_FILES):
        return
    download.databento_estimate(cfg, oos=True)
    if not yes:
        sys.exit("Holdout Databento data must be purchased; review the estimate and re-run with --yes.")
    download.pull_databento(cfg, oos=True)
    download.pull_cftc(cfg, oos=True)
    download.pull_h2_equities(cfg, oos=True)


def clear_holdout_caches() -> None:
    for f in PROCESSED.glob("*_oos.parquet"):
        f.unlink()


def evaluate_holdout(cfg: dict) -> tuple[pd.DataFrame, dict]:
    """Holdout metrics (dates on or after oos_start) for the two primaries and the secondary reports."""
    capital = cfg["capital_base"]
    sig = signals.month_end_signals(oos=True)
    rows, curves = [], {}
    for v in ("A", "B", "C"):
        market = backtest.Market(backtest.VARIANT_ROOTS[v], oos=True)
        for overlay in (False, True):
            res, _ = backtest.backtest_variant(v, "z", overlay=overlay, kind="oos", spec="primary",
                                               sig=sig, market=market, oos=True)
            win = res.daily[res.daily["date"] >= oos_start()]
            role = "PRIMARY (H1)" if v == "A" and not overlay else "secondary (pre-registered)"
            for col in ("net", "gross", "net2x"):
                rows.append({"hypothesis": "H1", "spec": f"Variant {v}" + (" + overlay" if overlay else ""),
                             "role": role, "returns": col, **analysis.metrics(win, col, capital)})
            if not overlay:
                curves[f"H1 Variant {v}"] = res.daily.set_index("date")["net"]
    out = h2.evaluate(log=True, oos=True)
    for col in ("net", "gross", "net2x"):
        p = out["performance"][col]
        rows.append({"hypothesis": "H2", "spec": "primary", "role": "PRIMARY (H2)", "returns": col,
                     "start": out["daily"]["date"].iloc[0].date(), "end": out["daily"]["date"].iloc[-1].date(),
                     "n_days": len(out["daily"]), "ann_return": p["ann_return"], "ann_vol": p["ann_vol"],
                     "sharpe": p["sharpe"], "max_drawdown": p["max_drawdown_from_peak"],
                     "mean_monthly": p["mean_monthly"], "nw_t_monthly": p["nw_t_monthly"],
                     "worst_month": p["worst_month"], "worst_month_label": p["worst_month_label"]})
    curves["H2 primary"] = out["daily_all"].set_index("date")["net"]
    return pd.DataFrame(rows), curves


def plot_oos_equity(curves: dict, path) -> None:
    """Cumulative net return (fixed capital) over the full history, holdout shaded."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
    fig, ax = plt.subplots(figsize=(11, 5), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0, colors="#52514e")
    ax.axvspan(oos_start(), max(r.index[-1] for r in curves.values()), color="#e6e5e0", alpha=0.6, lw=0)
    ax.axhline(0, color="#52514e", linewidth=0.8)
    for (label, r), color in zip(curves.items(), colors):
        cum = r.cumsum() * 100
        ax.plot(cum.index, cum.to_numpy(), color=color, linewidth=1.6, label=label)
        ax.annotate(label, (cum.index[-1], cum.iloc[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=9, color="#52514e")
    ax.set_ylabel("Cumulative net return, % of capital (no compounding)", color="#52514e")
    ax.set_title("Primary specifications, net of 1x costs; shaded = holdout", loc="left", fontsize=11,
                 color="#0b0b0b", pad=26)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=4, frameon=False, borderaxespad=0.2)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="#fcfcfb")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--confirm-final", action="store_true", help="required for the one-time first run")
    ap.add_argument("--yes", action="store_true", help="confirm the holdout Databento purchase")
    args = ap.parse_args()
    cfg = load_config()

    mode = check_lock(args.confirm_final, LOCK, config_hash())
    if mode == "first":
        dirty = uncommitted_frozen_changes()
        if dirty:
            sys.exit("Commit the frozen specification before the holdout run. Uncommitted:\n  " + "\n  ".join(dirty))
    ensure_oos_data(cfg, args.yes)
    clear_holdout_caches()
    if mode == "first":
        print(f"Holdout lock written: {write_lock(LOCK)}")

    perf, curves = evaluate_holdout(cfg)
    (RESULTS / "tables").mkdir(parents=True, exist_ok=True)
    perf.to_csv(RESULTS / "tables" / "oos_performance.csv", index=False)
    plot_oos_equity({k: curves[k] for k in ("H1 Variant A", "H2 primary", "H1 Variant B", "H1 Variant C")},
                    RESULTS / "figures" / "oos_equity.png")
    net = perf[perf["returns"] == "net"]
    print(net[["hypothesis", "spec", "role", "start", "end", "ann_return", "ann_vol", "sharpe", "max_drawdown",
               "mean_monthly", "nw_t_monthly"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    for hyp, label in (("H1", "P2 holdout condition (H1 Variant A net Sharpe > 0)"),
                       ("H2", "Q3 holdout condition (H2 primary net Sharpe > 0)")):
        row = net[net["role"] == f"PRIMARY ({hyp})"].iloc[0]
        print(f"{label}: {row['sharpe']:+.3f} -> {'met' if row['sharpe'] > 0 else 'not met'}")


if __name__ == "__main__":
    main()
