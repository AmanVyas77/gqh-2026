"""One-time out-of-sample evaluation (HYPOTHESIS.md Section 8). Aman runs this once.

First run
- Requires --confirm-final. Refuses if results/oos_lock.json already exists.
- Fetches the out-of-sample data (Databento: prints the cost estimate and requires --yes to buy;
  CFTC COT), then writes results/oos_lock.json (config hash, git commit, timestamp) BEFORE any
  out-of-sample result is computed, so the lock marks the single evaluation.
- Runs Variants A, B and C at the primary spec only, with the drawdown overlay alongside, and
  writes results/tables/oos_performance.csv and results/figures/oos_equity.png.
- P2's out-of-sample condition: Variant A's out-of-sample net Sharpe > 0.

Later runs
- Allowed only if config.yaml's hash matches the lock (reproduction by judges); otherwise refuse.

Usage
  python run_oos.py --confirm-final          # prints the Databento estimate, then stops
  python run_oos.py --confirm-final --yes    # buys the OOS data and runs the evaluation
  python run_oos.py                          # later: reproduce (config hash must match the lock)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "data"))

import pandas as pd  # noqa: E402

import download  # noqa: E402
from src import analysis, backtest, signals, trial_log  # noqa: E402
from src.config import RAW_OOS, RESULTS, config_hash, load_config, oos_start  # noqa: E402

LOCK = RESULTS / "oos_lock.json"
OOS_FILES = [f"{r}_{k}.parquet" for r in ("LE", "GF", "ZC") for k in ("definition", "statistics", "ohlcv1d")] + \
            ["cftc_live_cattle.parquet"]


def check_lock(confirm_final: bool, lock_path: Path, cfg_hash: str) -> str:
    """'first' for the one evaluation, 'repeat' for a reproduction with an unchanged config."""
    if not lock_path.exists():
        if not confirm_final:
            sys.exit("The first out-of-sample run requires --confirm-final. It can be done only once.")
        return "first"
    lock = json.loads(lock_path.read_text())
    if lock["config_sha256"] != cfg_hash:
        sys.exit(f"config.yaml has changed since the OOS lock ({lock['timestamp_utc']}); refusing to run.")
    return "repeat"


def write_lock(lock_path: Path) -> dict:
    lock = {"config_sha256": config_hash(), "git_commit": trial_log._git_commit(),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "oos_start": str(oos_start().date())}
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock, indent=2))
    return lock


def ensure_oos_data(cfg: dict, yes: bool) -> None:
    if all((RAW_OOS / f).exists() for f in OOS_FILES):
        return
    download.databento_estimate(cfg, oos=True)
    if not yes:
        sys.exit("Out-of-sample Databento data must be purchased; review the estimate and re-run with --yes.")
    download.pull_databento(cfg, oos=True)
    download.pull_cftc(cfg, oos=True)


def plot_oos_equity(curves: dict, path) -> None:
    """Cumulative net return (fixed capital) over the full history, out-of-sample shaded."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"A": "#2a78d6", "B": "#eb6834", "C": "#1baf7a"}
    fig, ax = plt.subplots(figsize=(11, 5), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0, colors="#52514e")
    ax.axvspan(oos_start(), max(r.index[-1] for r in curves.values()), color="#e6e5e0", alpha=0.6, lw=0)
    ax.axhline(0, color="#52514e", linewidth=0.8)
    for v, r in curves.items():
        cum = r.cumsum() * 100
        ax.plot(cum.index, cum.to_numpy(), color=colors[v], linewidth=1.6, label=f"Variant {v}")
        ax.annotate(f"Variant {v}", (cum.index[-1], cum.iloc[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=9, color="#52514e")
    ax.set_ylabel("Cumulative net return, % of capital (no compounding)", color="#52514e")
    ax.set_title("Primary spec, net of 1x costs; shaded = out-of-sample", loc="left", fontsize=11,
                 color="#0b0b0b", pad=26)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, frameon=False, borderaxespad=0.2)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="#fcfcfb")
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--confirm-final", action="store_true", help="required for the one-time first run")
    ap.add_argument("--yes", action="store_true", help="confirm the out-of-sample Databento purchase")
    args = ap.parse_args()
    cfg = load_config()

    mode = check_lock(args.confirm_final, LOCK, config_hash())
    ensure_oos_data(cfg, args.yes)
    if mode == "first":
        lock = write_lock(LOCK)
        print(f"OOS lock written: {lock}")

    capital = cfg["capital_base"]
    sig = signals.month_end_signals(oos=True)
    rows, curves = [], {}
    for v in ("A", "B", "C"):
        market = backtest.Market(backtest.VARIANT_ROOTS[v], oos=True)
        for overlay in (False, True):
            res, _ = backtest.backtest_variant(v, "z", overlay=overlay, kind="oos", spec="primary",
                                               sig=sig, market=market, oos=True)
            oos = res.daily[res.daily["date"] >= oos_start()]
            for col in ("net", "gross", "net2x"):
                m = analysis.metrics(oos, col, capital)
                rows.append({"variant": v, "overlay": overlay, "returns": col, **m,
                             "turnover": analysis.turnover(res.trades[res.trades["date"] >= oos_start()], oos, capital),
                             **res.events})
            if not overlay:
                curves[v] = res.daily.set_index("date")["net"]
    perf = pd.DataFrame(rows)
    (RESULTS / "tables").mkdir(parents=True, exist_ok=True)
    perf.to_csv(RESULTS / "tables" / "oos_performance.csv", index=False)
    plot_oos_equity(curves, RESULTS / "figures" / "oos_equity.png")

    net = perf[(perf["returns"] == "net") & (~perf["overlay"])]
    print(net[["variant", "start", "end", "ann_return", "ann_vol", "sharpe", "max_drawdown", "mean_monthly",
               "nw_t_monthly"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    a = net[net["variant"] == "A"].iloc[0]
    print(f"P2 out-of-sample condition (Variant A net Sharpe > 0): {a['sharpe']:+.3f} -> "
          f"{'met' if a['sharpe'] > 0 else 'not met'}")


if __name__ == "__main__":
    main()
