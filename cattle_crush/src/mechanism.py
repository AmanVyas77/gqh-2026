"""Mechanism tests (HYPOTHESIS.md Section 8). P1 here; P3 and the leg decomposition follow.

P1: at each month-end t (month m), regress
    y_t = log(placements m+1..m+3) - log(placements m-11..m-9)
on z_t with an intercept, Newey-West standard errors (3 lags). Passes if beta > 0 and t > 2
(Deviation Log 2026-10-02). Placements: USDA NASS Cattle on Feed, US feedlots with 1,000+
head capacity, dated by reference month. A month-end is used only if all its outcome months
are before oos_start (Deviation Log 2026-10-02).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.config import RAW, load_config, oos_start


def placements() -> pd.Series:
    """Monthly placements (head), indexed by monthly Period. In-sample only."""
    df = pd.read_parquet(RAW / "nass_placements.parquet")
    s = df.set_index(df["month"].dt.to_period("M"))["placements_head"].astype(float).sort_index()
    if s.index.max() >= oos_start().to_period("M"):
        raise RuntimeError("placements include months on or after oos_start")
    if len(s) != (s.index.max() - s.index.min()).n + 1:
        raise RuntimeError("placements are not a complete monthly series")
    return s


def p1_outcome(plac: pd.Series) -> pd.Series:
    """y_m = log(sum of placements in m+1..m+3) - log(the same three months a year earlier)."""
    s3 = plac.rolling(3).sum()                 # s3[m] = m-2..m
    fwd = s3.shift(-3)                         # sum of m+1..m+3
    back = s3.shift(9)                         # sum of m-11..m-9
    return np.log(fwd) - np.log(back)


def nw_ols(y: pd.Series, X: pd.DataFrame, lags: int) -> sm.regression.linear_model.RegressionResultsWrapper:
    return sm.OLS(y, sm.add_constant(X)).fit(cov_type="HAC", cov_kwds={"maxlags": lags})


def p1(sig: pd.DataFrame, regressor_sets: dict[str, list[str]]) -> pd.DataFrame:
    """Run P1 for each named set of z columns in `sig` (month-end table from signals.py)."""
    cfg = load_config()["tests"]
    y = p1_outcome(placements())
    months = pd.PeriodIndex(sig.index, freq="M")
    data = sig.assign(y=y.reindex(months).to_numpy(), month=months)
    rows = []
    for name, cols in regressor_sets.items():
        d = data.dropna(subset=["y", *cols])
        last_outcome_month = d["month"].max() + 3
        if last_outcome_month >= oos_start().to_period("M"):
            raise RuntimeError("P1 outcome window reaches oos_start")
        fit = nw_ols(d["y"], d[cols], cfg["p1_nw_lags"])
        for c in cols:
            row = {"test": "P1", "spec": name, "regressor": c, "beta": fit.params[c], "se_nw": fit.bse[c],
                   "t_nw": fit.tvalues[c], "p_nw": fit.pvalues[c], "n": int(fit.nobs), "r2": fit.rsquared,
                   "first_month_end": d.index.min().date(), "last_month_end": d.index.max().date(),
                   "nw_lags": cfg["p1_nw_lags"]}
            if name == "primary":
                row["pass"] = bool(fit.params[c] > 0 and fit.tvalues[c] > cfg["p1_t_threshold"])
            rows.append(row)
    return pd.DataFrame(rows)


def plot_p1(sig: pd.DataFrame, path) -> None:
    """Scatter of the P1 outcome on the primary z, with the OLS line."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, ink2, grid, surface, blue = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb", "#2a78d6"
    y = p1_outcome(placements())
    d = sig.assign(y=y.reindex(pd.PeriodIndex(sig.index, freq="M")).to_numpy()).dropna(subset=["y", "z"])
    fit = nw_ols(d["y"], d[["z"]], load_config()["tests"]["p1_nw_lags"])
    fig, ax = plt.subplots(figsize=(7.5, 5.2), facecolor=surface)
    ax.set_facecolor(surface)
    ax.grid(color=grid, linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(grid)
    ax.tick_params(length=0, colors=ink2)
    ax.axhline(0, color=ink2, linewidth=0.8)
    ax.axvline(0, color=ink2, linewidth=0.8)
    ax.scatter(d["z"], d["y"] * 100, s=22, color=blue, edgecolor=surface, linewidth=0.8, zorder=3)
    xs = np.linspace(d["z"].min(), d["z"].max(), 50)
    ax.plot(xs, (fit.params["const"] + fit.params["z"] * xs) * 100, color=ink, linewidth=1.6)
    ax.set_xlabel("Margin z-score at month-end t (36-month window)", color=ink2)
    ax.set_ylabel("YoY change in placements, months t+1..t+3 (%)", color=ink2)
    ax.set_title(f"P1: beta = {fit.params['z'] * 100:.2f} pp per 1 sd,  Newey-West t = {fit.tvalues['z']:.2f},  "
                 f"n = {int(fit.nobs)}", loc="left", fontsize=11, color=ink)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor=surface)
    plt.close(fig)


# --------------------------------------------------------------------------- P3

P3_DROPPED = {"LEZ2014": "no final settlement in the feed (Deviation Log 2026-10-03 15:34)"}
# Month-ends whose front-contract (spot proxy) settlement is missing (Deviation Log 2026-10-03 17:31).
P3_DROPPED_FRONT = {pd.Timestamp("2014-12-31"): "front contract LEZ2014 has no settlement on its last trade date"}


def p3_data(sig: pd.DataFrame) -> pd.DataFrame:
    """Per month-end t: the sale contract's settlement at t (F_t) and at its last trade date
    (F_T), and the front LE contract (nearest unexpired) settlement at t (S_t). Only t whose
    sale contract's last trade date is before oos_start; LEZ2014 observations dropped."""
    from src import contracts, margin

    s = contracts.settlements("LE").query("~cash_final")
    px = s.set_index(["date", "contract"])["price"]
    final = s[s["date"] == s["last_trade_date"]].set_index("contract")["price"]
    front = margin.selection("LE", 0).set_index("date")["contract"]
    d = sig.dropna(subset=["z"])[["sale_contract", "sale_ltd", "sale_price", "z"]].copy()
    d = d[d["sale_ltd"] < oos_start()]
    d = d[~d["sale_contract"].isin(P3_DROPPED) & ~d.index.isin(list(P3_DROPPED_FRONT))]
    d["F_t"], d["F_T"] = d["sale_price"], d["sale_contract"].map(final)
    if d["F_T"].isna().any():
        raise RuntimeError(f"missing final settlement for {sorted(d.loc[d['F_T'].isna(), 'sale_contract'].unique())}")
    d["front_contract"] = front.reindex(d.index)
    missing = [(t.date().isoformat(), c) for t, c in zip(d.index, d["front_contract"]) if (t, c) not in px.index]
    if missing:
        raise RuntimeError(f"front LE contract has no settlement at month-end (spot proxy unavailable): {missing}")
    d["S_t"] = [px.loc[(t, c)] for t, c in zip(d.index, d["front_contract"])]
    d["fut_return"] = d["F_T"] / d["F_t"] - 1                # (i)
    d["spot_change"] = d["F_T"] - d["S_t"]                   # (ii), $/lb
    d["fut_change"] = d["F_T"] - d["F_t"]                    # (i) in $/lb (supplemental)
    d["sale_minus_front"] = d["F_t"] - d["S_t"]              # = (ii) - (i in $/lb)
    return d


def p3_kill_test(sig: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    cfg = load_config()["tests"]
    d = p3_data(sig)
    rows = []
    for name, col, unit in [("P3 (i) futures return", "fut_return", "return"),
                            ("P3 (ii) spot change", "spot_change", "$/lb"),
                            ("P3 (i) futures change, $/lb (supplemental)", "fut_change", "$/lb")]:
        fit = nw_ols(d[col], d[["z"]], cfg["p3_nw_lags"])
        rows.append({"test": "P3", "spec": name, "regressor": "z", "unit": unit, "beta": fit.params["z"],
                     "se_nw": fit.bse["z"], "t_nw": fit.tvalues["z"], "p_nw": fit.pvalues["z"], "n": int(fit.nobs),
                     "r2": fit.rsquared, "first_month_end": d.index.min().date(), "last_month_end": d.index.max().date(),
                     "nw_lags": cfg["p3_nw_lags"], "mean_outcome": d[col].mean()})
    out = pd.DataFrame(rows)
    fut, spot = out.iloc[0], out.iloc[1]
    thr = cfg["p3_t_threshold"]
    verdict = {"spot_predicted": bool(spot["beta"] < 0 and abs(spot["t_nw"]) > thr),
               "futures_not_predicted": bool(abs(fut["t_nw"]) < thr)}
    verdict["spot_predicted_futures_not"] = verdict["spot_predicted"] and verdict["futures_not_predicted"]
    verdict["dropped_month_ends"] = [t.date().isoformat() for t in sig.dropna(subset=["z"]).index
                                     if sig.at[t, "sale_contract"] in P3_DROPPED or t in P3_DROPPED_FRONT]
    return out, verdict


# --------------------------------------------------------------------------- leg decomposition

def leg_decomposition(sig: pd.DataFrame, horizon: int = 5, threshold: float = -1.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """M_{t+5} - M_t = 1,400 x dLE - 800 x dFC - B x dC, each leg on the contracts selected at each
    date. Returns (per-t contributions, summary): mean contribution of each leg when z_t < -1, and
    each leg's variance share cov(leg, dM) / var(dM) over all t with a z."""
    from src import margin

    p = margin.params()
    me = margin.month_end(margin.margin_daily()).set_index("date")
    fwd = me.shift(-horizon)
    legs = pd.DataFrame({
        "LE (sale value)": p["w_out"] * (fwd["sale_price"] - me["sale_price"]),
        "GF (feeder cost)": -p["w_in"] * (fwd["feeder_price"] - me["feeder_price"]),
        "ZC (corn cost)": -p["B"] * (fwd["corn_price"] - me["corn_price"]),
    })
    legs["dM (total)"] = fwd["margin"] - me["margin"]
    legs["z"] = sig["z"].reindex(legs.index)
    legs = legs.dropna()
    if (legs.index + pd.DateOffset(months=horizon)).max() >= oos_start() + pd.offsets.MonthEnd(0):
        raise RuntimeError("leg decomposition reaches oos_start")
    cols = ["LE (sale value)", "GF (feeder cost)", "ZC (corn cost)", "dM (total)"]
    low = legs[legs["z"] < threshold]
    summary = pd.DataFrame({
        "mean_when_z_below_-1": low[cols].mean(),
        "n_when_z_below_-1": len(low),
        "variance_share_all_t": [legs[c].cov(legs["dM (total)"]) / legs["dM (total)"].var() for c in cols],
        "n_all_t": len(legs),
    })
    return legs, summary


def plot_legs(summary: pd.DataFrame, path) -> None:
    """Mean 5-month change in M by leg when z_t < -1, $/head."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, ink2, grid, surface, blue = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb", "#2a78d6"
    v = summary["mean_when_z_below_-1"]
    fig, ax = plt.subplots(figsize=(8, 4.4), facecolor=surface)
    ax.set_facecolor(surface)
    ax.grid(axis="y", color=grid, linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0, colors=ink2)
    ax.set_axisbelow(True)
    ax.spines["bottom"].set_visible(False)
    colors = [blue, blue, blue, ink]
    bars = ax.bar(range(len(v)), v.to_numpy(), color=colors, width=0.55)
    ax.axhline(0, color=ink2, linewidth=0.9)
    for b, val in zip(bars, v.to_numpy()):
        ax.annotate(f"{'-' if val < 0 else '+'}${abs(val):,.0f}", (b.get_x() + b.get_width() / 2, val),
                    xytext=(0, 4 if val >= 0 else -4), textcoords="offset points", ha="center",
                    va="bottom" if val >= 0 else "top", fontsize=9, color=ink)
    ax.set_xticks(range(len(v)), v.index)
    ax.set_ylim(min(0, v.min()) * 1.7, max(0, v.max()) * 1.12)
    ax.set_ylabel("\\$ per head", color=ink2)
    ax.set_title(f"Change in M over the next 5 months when z_t < -1, by leg (n = {int(summary['n_when_z_below_-1'].iloc[0])})",
                 loc="left", fontsize=11, color=ink)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor=surface)
    plt.close(fig)


def write_mechanism_outputs(sig: pd.DataFrame, results_dir) -> dict:
    """P1 (primary + pre-declared diagnostics 1a, 2a), P3 and the leg decomposition: tables and figures."""
    p1_tab = p1(sig, {"primary": ["z"], "diag_1a_seasonally_adjusted": ["z_sa"],
                      "diag_2a_joint_z_and_z_le": ["z", "z_le"]})
    p3_tab, verdict = p3_kill_test(sig)
    pd.concat([p1_tab, p3_tab], ignore_index=True).to_csv(results_dir / "tables" / "mechanism.csv", index=False)
    _, legs = leg_decomposition(sig)
    legs.to_csv(results_dir / "tables" / "legs.csv")
    plot_p1(sig, results_dir / "figures" / "mechanism.png")
    plot_legs(legs, results_dir / "figures" / "legs.png")
    return {"p1": p1_tab, "p3": p3_tab, "p3_verdict": verdict, "legs": legs}
