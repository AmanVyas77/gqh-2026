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
