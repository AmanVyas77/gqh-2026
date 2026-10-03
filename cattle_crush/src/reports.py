"""Robustness, Deflated Sharpe Ratio, stress tests, and liquidity/capital reports
(HYPOTHESIS.md Section 8 and Section 9 pre-declarations). In-sample only."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import analysis, backtest, contracts, signals
from src.config import PROCESSED, RAW, load_config

# One parameter at a time around the primary spec (Section 8). Seasonal adjustment uses z_sa.
ROBUSTNESS_SPECS = {
    "z_lookback_24": {"params": {"lookback": 24}},
    "z_lookback_48": {"params": {"lookback": 48}},
    "sale_horizon_120": {"params": {"sale_min_days": 120}},
    "sale_horizon_180": {"params": {"sale_min_days": 180}},
    "fcr_5.5": {"params": {"fcr": 5.5}},
    "fcr_6.5": {"params": {"fcr": 6.5}},
    "seasonal_adjust": {"params": {}, "zcol": "z_sa"},
}
VARIANTS = ("A", "B", "C")


# --------------------------------------------------------------------------- robustness

def run_robustness() -> pd.DataFrame:
    """Run every robustness spec for A, B, C, with the drawdown overlay alongside. Each run is
    logged (spec runs as trials, overlays as overlays). Daily returns are saved for the views."""
    series = {}
    markets = {v: backtest.Market(backtest.VARIANT_ROOTS[v]) for v in VARIANTS}
    for name, spec in ROBUSTNESS_SPECS.items():
        sig = signals.month_end_signals(**spec["params"])
        for v in VARIANTS:
            for overlay in (False, True):
                res, _ = backtest.backtest_variant(v, spec.get("zcol", "z"), overlay=overlay,
                                                   kind="overlay" if overlay else "trial", spec=name,
                                                   sig=sig, market=markets[v], **spec["params"])
                d = res.daily.set_index("date")
                for col in ("net", "net2x", "gross"):
                    series[(v, name, "overlay" if overlay else "no_overlay", col)] = d[col]
    out = pd.DataFrame(series)
    out.columns = pd.MultiIndex.from_tuples(out.columns, names=["variant", "spec", "overlay", "returns"])
    out.to_parquet(PROCESSED / "robustness_daily.parquet")
    return out


def _primary_series() -> pd.DataFrame:
    """Primary-spec daily returns saved by run_all steps 4-5 (no re-run, so no extra trial rows)."""
    parts = {}
    for v in VARIANTS:
        d = pd.read_parquet(PROCESSED / f"variant_{v.lower()}_daily.parquet")
        for run, label in (("primary", "no_overlay"), ("overlay", "overlay")):
            for col in ("net", "net2x", "gross"):
                parts[(v, "primary", label, col)] = d[(run, col)]
    out = pd.DataFrame(parts)
    out.columns = pd.MultiIndex.from_tuples(out.columns, names=["variant", "spec", "overlay", "returns"])
    return out


def _view_metrics(r: pd.Series) -> dict:
    r = r.dropna()
    cfg = load_config()
    m = analysis.monthly(r)
    mean_m, t_m = analysis.nw_mean_t(m, cfg["tests"]["p2_nw_lags"])
    return {"start": r.index[0].date(), "end": r.index[-1].date(), "n_days": len(r),
            "ann_return": r.mean() * 252, "ann_vol": r.std(ddof=1) * np.sqrt(252),
            "sharpe": r.mean() / r.std(ddof=1) * np.sqrt(252), "max_drawdown": analysis.drawdown(r).max(),
            "mean_monthly": mean_m, "nw_t_monthly": t_m}


def robustness_views(rob: pd.DataFrame) -> pd.DataFrame:
    """Every spec on (a) its full sample, (b) the common window starting at the latest first
    execution among the non-seasonal specs, and (c) for the seasonal spec and the primary, the
    seasonal spec's own window (Deviation Log 2026-10-02)."""
    allr = pd.concat([_primary_series(), rob], axis=1)
    firsts = {spec: allr.xs(("A", spec, "no_overlay", "net"), axis=1, level=[0, 1, 2, 3]).dropna().index[0]
              for spec in ["primary", *ROBUSTNESS_SPECS] if spec != "seasonal_adjust"}
    common_start = max(firsts.values())
    seasonal_start = allr[("A", "seasonal_adjust", "no_overlay", "net")].dropna().index[0]
    rows = []
    for (v, spec, ov, col), r in allr.items():
        views = {"full": r, "common": r[r.index >= common_start]}
        if spec in ("primary", "seasonal_adjust"):
            views["seasonal_window"] = r[r.index >= seasonal_start]
        for view, rr in views.items():
            if rr.dropna().empty or (view == "common" and spec == "seasonal_adjust"):
                continue
            rows.append({"variant": v, "spec": spec, "overlay": ov, "returns": col, "window": view,
                         **_view_metrics(rr)})
    out = pd.DataFrame(rows)
    out.attrs.update({"common_start": common_start.date(), "seasonal_start": seasonal_start.date()})
    return out


def plot_robustness(views: pd.DataFrame, path) -> None:
    """Net Sharpe by spec and variant: common window for the non-seasonal specs, the seasonal
    window for the seasonal spec (marked)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"A": "#2a78d6", "B": "#eb6834", "C": "#1baf7a"}
    specs = ["primary", *ROBUSTNESS_SPECS]
    v = views[(views["overlay"] == "no_overlay") & (views["returns"] == "net")]
    fig, ax = plt.subplots(figsize=(9, 5.2), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ax.grid(axis="x", color="#e6e5e0", linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0, colors="#52514e")
    ax.axvline(0, color="#52514e", linewidth=0.9)
    for j, var in enumerate(("A", "B", "C")):
        xs, ys = [], []
        for i, spec in enumerate(specs):
            window = "seasonal_window" if spec == "seasonal_adjust" else "common"
            row = v[(v["variant"] == var) & (v["spec"] == spec) & (v["window"] == window)]
            xs.append(row["sharpe"].iloc[0])
            ys.append(i + (j - 1) * 0.22)
        ax.scatter(xs, ys, s=46, color=colors[var], edgecolor="#fcfcfb", linewidth=1.5, label=f"Variant {var}", zorder=3)
    labels = [s.replace("_", " ") + (" (2018-07 on)" if s == "seasonal_adjust" else "") for s in specs]
    ax.set_yticks(range(len(specs)), labels)
    ax.invert_yaxis()
    ax.set_xlabel("Net Sharpe ratio (1x costs)", color="#52514e")
    ax.set_title(f"One-at-a-time robustness, common window from {views.attrs['common_start']}",
                 loc="left", fontsize=11, color="#0b0b0b", pad=26)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, frameon=False, borderaxespad=0.2)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="#fcfcfb")
    plt.close(fig)


# --------------------------------------------------------------------------- Deflated Sharpe

def dsr_report() -> pd.DataFrame:
    """N = distinct (variant, params) trials in the trial log; variance of their daily Sharpe ratios;
    DSR for the pre-registered primary (Variant A) and for the best trial; PSR for reference."""
    from src import trial_log

    import json
    log = pd.read_csv(trial_log.log_path())
    # A configuration is (variant, params); the "note" field on a restored row is not a parameter.
    key = log["params"].map(lambda p: json.dumps({k: v for k, v in json.loads(p).items() if k != "note"}, sort_keys=True))
    trials = log[log["kind"] == "trial"].assign(config=key).drop_duplicates(["variant", "config"])
    sr_daily = trials["sharpe_net"] / np.sqrt(252)
    n, var = len(trials), float(sr_daily.var(ddof=1))
    sr0 = analysis.expected_max_sharpe(var, n)
    rows = []
    primary = trials[(trials["variant"] == "A") & (trials["spec"] == "primary")].iloc[0]
    best = trials.loc[trials["sharpe_net"].idxmax()]
    for label, r in (("Variant A primary (pre-registered)", primary), ("Best of all trials", best)):
        sr = r["sharpe_net"] / np.sqrt(252)
        rows.append({"strategy": label, "variant": r["variant"], "spec": r["spec"],
                     "sharpe_annual": r["sharpe_net"], "n_obs": int(r["n_obs"]), "skew": r["skew"], "kurt": r["kurt"],
                     "n_trials": n, "raw_logged_rows": len(log), "trial_rows": int((log["kind"] == "trial").sum()),
                     "var_sharpe_daily": var, "sr0_annual": sr0 * np.sqrt(252),
                     "psr": analysis.deflated_sharpe(sr, int(r["n_obs"]), r["skew"], r["kurt"], 0.0),
                     "dsr": analysis.deflated_sharpe(sr, int(r["n_obs"]), r["skew"], r["kurt"], sr0)})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- stress tests

EPISODES = {"Holcomb plant fire, Aug 2019": ("2019-08-01", "2019-08-30"),
            "COVID packer shutdowns, Mar-May 2020": ("2020-03-02", "2020-05-29")}


def _cme(item: str, root: str) -> float:
    from src.config import MANUAL
    ref = pd.read_csv(MANUAL / "cme_reference.csv")
    return float(ref[(ref["item"] == item) & (ref["root"] == root)]["value"].iloc[0])


def stress_episodes() -> pd.DataFrame:
    rows = []
    for v in VARIANTS:
        d = pd.read_parquet(PROCESSED / f"variant_{v.lower()}_daily.parquet")
        for run in ("primary", "overlay"):
            r = d[(run, "net")].dropna()
            m = analysis.monthly(r)
            worst = m.idxmin()
            windows = {**EPISODES, f"Worst month ({worst})": (worst.start_time.date(), worst.end_time.date())}
            for name, (a, b) in windows.items():
                w = r[(r.index >= pd.Timestamp(a)) & (r.index <= pd.Timestamp(b))]
                rows.append({"variant": v, "run": run, "episode": name, "start": w.index[0].date(),
                             "end": w.index[-1].date(), "cum_net_return": w.sum(), "worst_day": w.min(),
                             "worst_day_date": w.idxmin().date(), "max_drawdown": analysis.drawdown(w).max()})
    return pd.DataFrame(rows)


def limit_shock() -> pd.DataFrame:
    """Two consecutive LE limit moves against the position: normal limit, then expanded limit,
    at the last in-sample sale-contract settlement. A and C at |w| = 2; B at its largest LE-leg
    position (GF and ZC unchanged). Pre-declared 2026-10-03 17:13."""
    cfg = load_config()
    capital, size = cfg["capital_base"], cfg["specs"]["LE"]["size"]
    lim1, lim2 = _cme("daily_price_limit", "LE"), _cme("expanded_price_limit", "LE")
    sig = signals.month_end_signals()
    last = sig.index.max()
    price = float(sig.at[last, "sale_price"])
    rows = []
    n_max = cfg["sizing"]["max_gross_leverage"] * capital / (price * size)
    for v in ("A", "C"):
        rows.append({"variant": v, "position": f"|w| = {cfg['sizing']['max_gross_leverage']:.0f} (cap)",
                     "le_contracts": n_max})
    mkt = backtest.Market(backtest.VARIANT_ROOTS["B"])
    from src import margin
    rbs = backtest.variant_b_rebalances(sig, "z", mkt, capital, margin.params()["B"])
    le = max((abs(rb.targets["LE"][1]), rb.signal_date) for rb in rbs)
    rows.append({"variant": "B", "position": f"largest in-sample LE leg ({le[1].date()})", "le_contracts": le[0]})
    out = pd.DataFrame(rows)
    out["price_at_shock"] = price
    out["price_date"] = last.date()
    out["day1_loss_pct"] = out["le_contracts"] * size * lim1 / capital
    out["day2_loss_pct"] = out["le_contracts"] * size * lim2 / capital
    out["two_day_loss_pct"] = out["day1_loss_pct"] + out["day2_loss_pct"]
    out["limit_day1"], out["limit_day2"] = lim1, lim2
    return out


# --------------------------------------------------------------------------- liquidity and capital

def volume_panel(root: str) -> pd.DataFrame:
    o = pd.read_parquet(RAW / f"{root}_ohlcv1d.parquet")
    ids = contracts.definition_versions().query("root == @root")[["instrument_id", "contract"]].drop_duplicates()
    o = o.merge(ids, on="instrument_id")
    o["date"] = o["ts_event"].dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize()
    return o.pivot_table(index="date", columns="contract", values="volume", aggfunc="sum")


def oi_panel(root: str) -> pd.DataFrame:
    s = pd.read_parquet(RAW / f"{root}_statistics.parquet")
    s = s[(s["stat_type"] == 9) & (s["update_action"] == 1) & s["quantity"].notna()]
    ids = contracts.definition_versions().query("root == @root")[["instrument_id", "contract"]].drop_duplicates()
    s = s.merge(ids, on="instrument_id")
    # Dated by ts_ref (trading date) where present; older records lack it and are dated by receipt
    # (UTC date of ts_recv), which is when the value was known.
    ref = s["ts_ref"].dt.tz_localize(None).dt.normalize()
    recv = s["ts_recv"].dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize()
    s["date"] = ref.fillna(recv)
    s = s.sort_values("ts_recv").drop_duplicates(["date", "contract"], keep="last")
    return s.pivot(index="date", columns="contract", values="quantity").astype(float)


def _rebalance_positions(v: str, sig: pd.DataFrame, capital: float) -> list:
    from src import margin
    mkt = backtest.Market(backtest.VARIANT_ROOTS[v])
    if v == "A":
        return backtest.variant_a_rebalances(sig, "z", mkt, capital)
    if v == "B":
        return backtest.variant_b_rebalances(sig, "z", mkt, capital, margin.params()["B"])
    return backtest.variant_c_rebalances(sig, "z", mkt, capital, signals.hp_at(sig.index))


def liquidity_capital() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Per rebalance and leg: |contracts| as % of 20-day ADV and of open interest; AUM at which
    positions reach 1/5/10% of ADV; margin-to-equity; LE position vs the federal spot-month limit.
    Positions are the full-size targets at $1M (rebalances with a zero position are excluded)."""
    cfg = load_config()
    capital, n_adv = cfg["capital_base"], cfg["capacity"]["adv_lookback_days"]
    sig = signals.month_end_signals()
    roots = ("LE", "GF", "ZC")
    vol = {r: volume_panel(r) for r in roots}
    oi = {r: oi_panel(r) for r in roots}
    cal = {r: pd.DatetimeIndex(sorted(contracts.settlements(r).query("~cash_final")["date"].unique())) for r in roots}
    im = {r: _cme("maintenance_margin", r) * _cme("initial_to_maintenance_ratio", "ALL") for r in roots}
    rows = []
    for v in VARIANTS:
        for rb in _rebalance_positions(v, sig, capital):
            t = rb.signal_date
            for root, (c, n) in rb.targets.items():
                if n == 0:
                    continue
                days = cal[root][cal[root] <= t][-n_adv:]
                adv = vol[root][c].reindex(days).fillna(0).mean() if c in vol[root] else 0.0
                oi_t = oi[root][c].loc[:t].dropna() if c in oi[root] else pd.Series(dtype=float)
                rows.append({"variant": v, "signal_date": t, "leg": root, "contract": c, "contracts": abs(n),
                             "adv20": adv, "open_interest": oi_t.iloc[-1] if len(oi_t) else np.nan,
                             "initial_margin": abs(n) * im[root]})
    pos = pd.DataFrame(rows)
    pos["pct_adv"] = pos["contracts"] / pos["adv20"]
    pos["pct_oi"] = pos["contracts"] / pos["open_interest"]
    by_leg = pos.groupby(["variant", "leg"]).agg(
        rebalances=("signal_date", "nunique"), contracts_median=("contracts", "median"), contracts_max=("contracts", "max"),
        pct_adv_median=("pct_adv", "median"), pct_adv_max=("pct_adv", "max"),
        pct_oi_median=("pct_oi", "median"), pct_oi_max=("pct_oi", "max")).reset_index()
    reb = pos.groupby(["variant", "signal_date"]).agg(binding_pct_adv=("pct_adv", "max"),
                                                       margin=("initial_margin", "sum")).reset_index()
    cap_rows = []
    for v, g in reb.groupby("variant"):
        row = {"variant": v, "margin_to_equity_median": g["margin"].median() / capital,
               "margin_to_equity_max": g["margin"].max() / capital}
        for x in (0.01, 0.05, 0.10):
            row[f"aum_at_{int(x * 100)}pct_adv_median_rebalance"] = capital * x / g["binding_pct_adv"].median()
            row[f"aum_at_{int(x * 100)}pct_adv_largest_rebalance"] = capital * x / g["binding_pct_adv"].max()
        le = pos[(pos["variant"] == v) & (pos["leg"] == "LE")]["contracts"]
        limit = _cme("federal_spot_month_limit_step1", "LE")
        row.update({"le_contracts_max": le.max(), "federal_spot_month_limit": limit,
                    "aum_at_which_largest_le_position_equals_spot_limit": capital * limit / le.max()})
        cap_rows.append(row)
    return pos, by_leg, pd.DataFrame(cap_rows)
