"""Reproduce every in-sample number in the note. In-sample only: nothing dated on or after
oos_start is loaded here (see run_oos.py for the one-time out-of-sample run).

Usage: python run_all.py [--yes]   (--yes confirms the Databento purchase if raw data is missing)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "data"))

import audit  # noqa: E402
import download  # noqa: E402
import pandas as pd  # noqa: E402

from src import analysis, backtest, h2, margin, mechanism, reports, signals  # noqa: E402
from src.config import PROCESSED, RAW, RESULTS, load_config  # noqa: E402

RAW_FILES = {
    "h2": ["h2_equities.parquet"],
    "databento": [f"{r}_{k}.parquet" for r in ("LE", "GF", "ZC") for k in ("definition", "statistics", "ohlcv1d")],
    "nass": ["nass_placements.parquet"],
    "cftc": ["cftc_live_cattle.parquet"],
    "spy": ["spy.parquet"],
}


def ensure_data(cfg: dict, yes: bool) -> None:
    """Download any in-sample source whose raw files are missing."""
    for source, files in RAW_FILES.items():
        if all((RAW / f).exists() for f in files):
            continue
        print(f"[data] {source} missing; downloading")
        if source == "databento":
            download.databento_estimate(cfg)
            if not yes:
                sys.exit("Databento data must be purchased; review the estimate and re-run with --yes.")
            download.pull_databento(cfg)
        else:
            getattr(download, "pull_h2_equities" if source == "h2" else f"pull_{source}")(cfg)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yes", action="store_true", help="confirm the Databento purchase if raw data is missing")
    args = ap.parse_args()
    cfg = load_config()

    ensure_data(cfg, args.yes)
    print("\n[1] Data audit")
    audit.main()

    print("\n[2] Feeding margin (primary spec)")
    daily = margin.margin_daily()
    me = margin.month_end(daily)
    PROCESSED.mkdir(parents=True, exist_ok=True)          # derived from licensed prices: not committed
    daily.to_parquet(PROCESSED / "margin_daily.parquet", index=False)
    me.to_parquet(PROCESSED / "margin_month_end.parquet", index=False)
    (RESULTS / "figures").mkdir(parents=True, exist_ok=True)
    margin.plot_margin(daily, RESULTS / "figures" / "margin.png")
    m = me["margin"]
    print(f"{len(daily)} daily and {len(me)} month-end values, {me['date'].min():%Y-%m} to {me['date'].max():%Y-%m}; "
          f"B = {daily.attrs['B']:.4f} bu; month-end M_t mean ${m.mean():,.0f}, sd ${m.std():,.0f}, "
          f"range ${m.min():,.0f} to ${m.max():,.0f} per head")


    print("\n[3] Mechanism: P1 (primary + pre-declared diagnostics 1a, 2a), P3, leg decomposition")
    sig = signals.month_end_signals()
    mech = mechanism.write_mechanism_outputs(sig, RESULTS)
    for _, r in pd.concat([mech["p1"], mech["p3"]]).iterrows():
        verdict = f"  -> {'PASS' if r['pass'] else 'FAIL'}" if r.get("spec") == "primary" else ""
        print(f"{r['test']} {r['spec']:44s} {r['regressor']:5s} beta {r['beta']:+.5f}  NW t {r['t_nw']:+.2f}  "
              f"n {r['n']}{verdict}")
    print("P3 verdict:", mech["p3_verdict"])
    print(mech["legs"].round(3).to_string())

    print("\n[4] Variant A (primary), drawdown overlay, and diagnostics 1b / 2b")
    variant_a(sig)

    print("\n[5] Variants B and C (primary), drawdown overlay, and diagnostic 1b")
    for v in ("B", "C"):
        variant_bc(v, sig)

    print("\n[6] Robustness: 7 one-at-a-time specs x 3 variants, overlay alongside (logged)")
    views = reports.robustness_views(reports.run_robustness())
    views.to_csv(RESULTS / "tables" / "robustness.csv", index=False)
    reports.plot_robustness(views, RESULTS / "figures" / "robustness.png")
    net = views[(views["returns"] == "net") & (views["overlay"] == "no_overlay")]
    print(net.pivot_table(index="spec", columns=["variant", "window"], values="sharpe").round(2).to_string())

    print("\n[7] Deflated Sharpe Ratio")
    dsr = reports.dsr_report()
    dsr.to_csv(RESULTS / "tables" / "trials.csv", index=False)
    print(dsr[["strategy", "sharpe_annual", "n_trials", "raw_logged_rows", "sr0_annual", "psr", "dsr"]]
          .to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    print("\n[8] Stress tests and liquidity/capital")
    reports.stress_episodes().to_csv(RESULTS / "tables" / "stress_episodes.csv", index=False)
    reports.limit_shock().to_csv(RESULTS / "tables" / "stress_limit_shock.csv", index=False)
    _, by_leg, cap = reports.liquidity_capital()
    by_leg.to_csv(RESULTS / "tables" / "liquidity_by_leg.csv", index=False)
    cap.to_csv(RESULTS / "tables" / "capital.csv", index=False)
    print("written: stress_episodes.csv, stress_limit_shock.csv, liquidity_by_leg.csv, capital.csv")

    print("\n[9] H2 (HYPOTHESIS_H2.md): primary specification, development data only (logged)")
    out = h2.evaluate()
    pd.DataFrame(out["tests"]).T.to_csv(RESULTS / "tables" / "h2_tests.csv")
    pd.DataFrame(out["performance"]).T.to_csv(RESULTS / "tables" / "h2_performance.csv")
    out["annual"].to_csv(RESULTS / "tables" / "h2_annual.csv")
    for k, v in out["tests"].items():
        print(f"{k}: beta {v['beta']:+.5f}  NW t {v['t_nw']:+.2f}  n {v['n']}  pass={v['pass']}")

def plot_equity(curves: dict, path, title: str = "Variant A (primary spec), in-sample") -> None:
    """Cumulative return on fixed capital, one line per curve (same units, one axis)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]      # validated categorical slots 1-4
    fig, ax = plt.subplots(figsize=(11, 5), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0, colors="#52514e")
    ax.axhline(0, color="#52514e", linewidth=0.8)
    for (label, r), color in zip(curves.items(), colors):
        cum = r.cumsum() * 100
        ax.plot(cum.index, cum.to_numpy(), color=color, linewidth=1.6, label=label)
        ax.annotate(label, (cum.index[-1], cum.iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=9, color="#52514e")
    ax.set_xlim(right=max(r.index[-1] for r in curves.values()) + pd.Timedelta(days=500))
    ax.set_ylabel("Cumulative return, % of capital (no compounding)", color="#52514e")
    ax.set_title(title, loc="left", fontsize=11, color="#0b0b0b", pad=26)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, ncol=4, borderaxespad=0.2)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="#fcfcfb")
    plt.close(fig)


def variant_a(sig: pd.DataFrame) -> None:
    cfg = load_config()
    capital, lags = cfg["capital_base"], cfg["tests"]["p2_nw_lags"]
    market = backtest.Market(("LE",))
    runs = {
        "primary": backtest.backtest_a("z", sig=sig, market=market, kind="trial"),
        "overlay": backtest.backtest_a("z", overlay=True, sig=sig, market=market, kind="overlay"),
        "diag_2b_le_only": backtest.backtest_a("z_le", sig=sig, market=market, kind="diagnostic", spec="le_only"),
        "diag_1b_seasonal_only": backtest.backtest_a("z_seasonal_only", sig=sig, market=market,
                                                    kind="diagnostic", spec="seasonal_only"),
    }
    rows = []
    for name, (res, m) in runs.items():
        for col in ("net", "gross", "net2x"):
            mm = analysis.metrics(res.daily, col, capital)
            rows.append({"run": name, "returns": col, **{k: v for k, v in mm.items() if k != "turnover"},
                         "turnover": m["turnover"], **res.events})
    perf = pd.DataFrame(rows)
    perf.to_csv(RESULTS / "tables" / "variant_a.csv", index=False)
    show = perf[perf["returns"] == "net"][["run", "start", "end", "ann_return", "ann_vol", "sharpe", "max_drawdown",
                                          "mean_monthly", "nw_t_monthly", "worst_month", "worst_month_label",
                                          "avg_gross_leverage", "turnover"]]
    print(show.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(perf[perf["run"] == "primary"][["returns", "ann_return", "sharpe", "mean_monthly", "nw_t_monthly"]]
          .to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    a = runs["primary"][1]
    p2 = a["mean_monthly"] > 0 and a["nw_t_monthly"] > cfg["tests"]["p2_t_threshold"]
    print(f"P2 in-sample (Variant A primary, net): mean monthly {a['mean_monthly']:+.4%}, "
          f"NW t {a['nw_t_monthly']:+.2f} -> {'PASS' if p2 else 'FAIL'} (OOS Sharpe part pending run_oos.py)")

    prim = runs["primary"][0]
    ma = analysis.monthly(prim.daily.set_index("date")["net"])
    diag = []
    for name in ("diag_2b_le_only", "diag_1b_seasonal_only"):
        res = runs[name][0]
        mb = analysis.monthly(res.daily.set_index("date")["net"])
        reg = analysis.regress_returns(ma, mb, lags)
        w = pd.concat({"a": prim.rebalances.set_index("signal_date")["weight"],
                       "b": res.rebalances.set_index("signal_date")["weight"]}, axis=1).dropna()
        diag.append({"diagnostic": name, **reg, "position_corr": w["a"].corr(w["b"]), "n_rebalances": len(w)})
    diag = pd.DataFrame(diag)
    diag.to_csv(RESULTS / "tables" / "variant_a_diagnostics.csv", index=False)
    print(diag.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    curves = {"Gross": prim.daily.set_index("date")["gross"],
              "Net 1x": prim.daily.set_index("date")["net"],
              "Net 2x": prim.daily.set_index("date")["net2x"],
              "Overlay, net 1x": runs["overlay"][0].daily.set_index("date")["net"]}
    PROCESSED.mkdir(parents=True, exist_ok=True)
    pd.concat({name: res.daily.set_index("date")[["gross", "net", "net2x"]] for name, (res, _) in runs.items()},
              axis=1).to_parquet(PROCESSED / "variant_a_daily.parquet")
    plot_equity(curves, RESULTS / "figures" / "equity.png")



def variant_bc(variant: str, sig: pd.DataFrame) -> None:
    cfg = load_config()
    capital, lags = cfg["capital_base"], cfg["tests"]["p2_nw_lags"]
    market = backtest.Market(backtest.VARIANT_ROOTS[variant])
    runs = {
        "primary": backtest.backtest_variant(variant, "z", sig=sig, market=market, kind="trial"),
        "overlay": backtest.backtest_variant(variant, "z", overlay=True, sig=sig, market=market, kind="overlay"),
        "diag_1b_seasonal_only": backtest.backtest_variant(variant, "z_seasonal_only", sig=sig, market=market,
                                                          kind="diagnostic", spec="seasonal_only"),
    }
    rows = []
    for name, (res, m) in runs.items():
        for col in ("net", "gross", "net2x"):
            mm = analysis.metrics(res.daily, col, capital)
            rows.append({"run": name, "returns": col, **{k: v for k, v in mm.items() if k != "turnover"},
                         "turnover": m["turnover"], **res.events})
    perf = pd.DataFrame(rows)
    perf.to_csv(RESULTS / "tables" / f"variant_{variant.lower()}.csv", index=False)
    print(f"Variant {variant}")
    print(perf[perf["returns"] == "net"][["run", "start", "end", "ann_return", "ann_vol", "sharpe", "max_drawdown",
                                          "mean_monthly", "nw_t_monthly", "worst_month", "worst_month_label",
                                          "avg_gross_leverage", "max_gross_leverage", "turnover",
                                          "deferred_trades", "gf_cash_final_closes", "gf_ltd_settlement_closes"]]
          .to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(perf[perf["run"] == "primary"][["returns", "ann_return", "sharpe", "mean_monthly", "nw_t_monthly"]]
          .to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    prim, seas = runs["primary"][0], runs["diag_1b_seasonal_only"][0]
    reg = analysis.regress_returns(analysis.monthly(prim.daily.set_index("date")["net"]),
                                   analysis.monthly(seas.daily.set_index("date")["net"]), lags)
    w = pd.concat({"a": prim.rebalances.set_index("signal_date")["weight"],
                   "b": seas.rebalances.set_index("signal_date")["weight"]}, axis=1).dropna()
    diag = pd.DataFrame([{"diagnostic": "diag_1b_seasonal_only", **reg, "position_corr": w["a"].corr(w["b"]),
                          "n_rebalances": len(w)}])
    diag.to_csv(RESULTS / "tables" / f"variant_{variant.lower()}_diagnostics.csv", index=False)
    print(diag.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    if variant == "C":
        flat = (prim.rebalances["weight"] == 0).mean()
        print(f"C: share of rebalances flat after the hedging-pressure filter: {flat:.0%}")
    curves = {"Gross": prim.daily.set_index("date")["gross"], "Net 1x": prim.daily.set_index("date")["net"],
              "Net 2x": prim.daily.set_index("date")["net2x"],
              "Overlay, net 1x": runs["overlay"][0].daily.set_index("date")["net"]}
    PROCESSED.mkdir(parents=True, exist_ok=True)
    pd.concat({name: res.daily.set_index("date")[["gross", "net", "net2x"]] for name, (res, _) in runs.items()},
              axis=1).to_parquet(PROCESSED / f"variant_{variant.lower()}_daily.parquet")
    names = {"B": "Variant B (crush spread, primary spec), in-sample",
             "C": "Variant C (A filtered by hedging pressure, primary spec), in-sample"}
    plot_equity(curves, RESULTS / "figures" / f"equity_{variant.lower()}.png", names[variant])


if __name__ == "__main__":
    main()
