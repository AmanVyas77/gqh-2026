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
    """Deflated Sharpe over the cattle-project trials only: N = distinct (variant, params) rows of
    kind "trial" in results/trial_log.csv (24 H1 + 1 H2 = 25). It does not cover experiments in
    other projects in the repository. Rows: H1 primary, H2 primary, and the best of the N trials."""
    import json
    from src import trial_log

    log = pd.read_csv(trial_log.log_path())
    # A configuration is (variant, params); the "note" field on a restored row is not a parameter.
    key = log["params"].map(lambda p: json.dumps({k: v for k, v in json.loads(p).items() if k != "note"}, sort_keys=True))
    trials = log[log["kind"] == "trial"].assign(config=key).drop_duplicates(["variant", "config"])
    sr_daily = trials["sharpe_net"] / np.sqrt(252)
    n, var = len(trials), float(sr_daily.var(ddof=1))
    sr0 = analysis.expected_max_sharpe(var, n)
    picks = {"H1 primary (Variant A)": trials[(trials["variant"] == "A") & (trials["spec"] == "primary")].iloc[0],
             "H2 primary": trials[(trials["variant"] == "H2") & (trials["spec"] == "primary")].iloc[0],
             f"Best of the {n} cattle-project trials": trials.loc[trials["sharpe_net"].idxmax()]}
    rows = []
    for label, r in picks.items():
        sr = r["sharpe_net"] / np.sqrt(252)
        rows.append({"strategy": label, "variant": r["variant"], "spec": r["spec"],
                     "sharpe_annual": r["sharpe_net"], "n_obs_days": int(r["n_obs"]), "skew": r["skew"], "kurt": r["kurt"],
                     "n_cattle_project_trials": n, "raw_logged_rows": len(log),
                     "trial_rows_including_repeats": int((log["kind"] == "trial").sum()),
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


# --------------------------------------------------------------------------- development verification

def _primary(v: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    d = pd.read_parquet(PROCESSED / f"variant_{v.lower()}_daily.parquet")["primary"]
    return d, pd.read_parquet(PROCESSED / f"variant_{v.lower()}_trades.parquet")


def h1_accounting() -> pd.DataFrame:
    """Signal-to-execution lag, exposure, cost arithmetic, drawdown from initial NAV and data
    cutoff for the three H1 primary runs (saved by run_all steps 4-5)."""
    from src import costs
    from src.config import oos_start
    capital = load_config()["capital_base"]
    rows = []
    for v in VARIANTS:
        d, tr = _primary(v)
        roots = backtest.VARIANT_ROOTS[v]
        cal = pd.DatetimeIndex(sorted(set().union(*(set(contracts.settlements(r).query("~cash_final")["date"]) for r in roots))))
        reb = tr[tr["reason"] == "rebalance"].copy()
        lag = cal.searchsorted(pd.DatetimeIndex(reb["date"])) - cal.searchsorted(pd.DatetimeIndex(reb["signal_date"]))
        reb["root"] = reb["contract"].str[:2]
        expected = reb["root"].map(lambda r: costs.cost_per_side(r))
        per_side = reb["cost"] / reb["qty"].abs()
        eq = 1 + d["net"].cumsum()
        rows.append({"variant": v, "rebalance_trades": len(reb),
                     "exec_lag_trading_days_min": int(lag.min()), "exec_lag_trading_days_max": int(lag.max()),
                     "trades_deferred_beyond_next_day": int((lag > 1).sum()),
                     "cost_per_contract_side_matches_section7": bool(np.allclose(per_side, expected)),
                     "fee_only_closes": int((tr["reason"] != "rebalance").sum()),
                     "avg_gross_exposure": d["gross_notional"].mean() / capital,
                     "max_gross_exposure": d["gross_notional"].max() / capital,
                     "max_drawdown_from_peak": float((1 - eq / eq.cummax()).max()),
                     "max_loss_below_initial_nav": float(min(0.0, (eq - 1).min())),
                     "nav_low_date": eq.idxmin().date(), "end_nav": float(eq.iloc[-1]),
                     "first_date": d.index.min().date(), "last_date": d.index.max().date(),
                     "ends_before_oos": bool(d.index.max() < oos_start())})
    return pd.DataFrame(rows)


def factor_regression() -> pd.DataFrame:
    """Section 8: Variant A monthly net returns on (1) a long-only roll-adjusted LE position (w = 1,
    sale-contract rule), (2) 12-month LE time-series momentum (sign of the trailing 252-day
    long-only return, lagged one day, times the next day's long-only return), (3) SPY.
    Newey-West, 5 lags."""
    import statsmodels.api as sm
    cfg = load_config()
    sig = signals.month_end_signals()
    lo = backtest.backtest_long_only_le(sig, backtest.Market(("LE",))).daily.set_index("date")["gross"]
    trailing = lo.rolling(252, min_periods=252).sum()
    tsmom = (np.sign(trailing).shift(1) * lo).dropna()
    spy = pd.read_parquet(RAW / "spy.parquet").set_index("date")["close_adj"].pct_change().dropna()
    a = _primary("A")[0]["net"]
    X = pd.concat({"long_only_LE": analysis.monthly(lo), "LE_TSMOM_12m": analysis.monthly(tsmom),
                   "SPY": analysis.monthly(spy)}, axis=1)
    data = pd.concat([analysis.monthly(a).rename("A"), X], axis=1).dropna()
    fit = sm.OLS(data["A"], sm.add_constant(data[X.columns])).fit(cov_type="HAC",
                                                                  cov_kwds={"maxlags": cfg["tests"]["p2_nw_lags"]})
    rows = [{"term": k, "coef": fit.params[k], "t_nw": fit.tvalues[k]} for k in fit.params.index]
    for r in rows:
        if r["term"] == "const":
            r["term"], r["annualized"] = "alpha (monthly)", r["coef"] * 12
    out = pd.DataFrame(rows)
    out["n_months"], out["r2"] = int(fit.nobs), fit.rsquared
    out["first_month"], out["last_month"] = str(data.index.min()), str(data.index.max())
    return out


def returns_by_year() -> pd.DataFrame:
    cols = {}
    for v in VARIANTS:
        d = _primary(v)[0]
        for c in (["net", "gross", "net2x"] if v == "A" else ["net"]):
            cols[f"H1 {v} {c}"] = d[c].groupby(d.index.year).sum()
    h = pd.read_parquet(PROCESSED / "h2_daily.parquet").set_index("date")
    for c in ("net", "gross", "net2x"):
        cols[f"H2 {c}"] = h[c].groupby(h.index.year).sum()
    return pd.DataFrame(cols)


def plot_by_year(by_year: pd.DataFrame, path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    series = {"H1 primary (Variant A)": ("H1 A net", "#2a78d6"), "H2 primary": ("H2 net", "#eb6834")}
    years = by_year.index.to_numpy()
    fig, ax = plt.subplots(figsize=(9, 3.6), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
    ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
    ax.tick_params(length=0, colors="#52514e")
    ax.axhline(0, color="#52514e", linewidth=0.8)
    for i, (label, (col, color)) in enumerate(series.items()):
        ax.bar(years + (i - 0.5) * 0.38, by_year[col].fillna(0).to_numpy() * 100, width=0.36, color=color, label=label)
    ax.set_xticks(years, [str(y) for y in years])
    ax.set_ylabel("Net return, % of capital", color="#52514e")
    ax.set_title("Calendar-year net returns, primary specifications (2013 and 2024 partial)",
                 loc="left", fontsize=11, color="#0b0b0b", pad=26)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, borderaxespad=0.2)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="#fcfcfb")
    plt.close(fig)


def capacity_curve() -> pd.DataFrame:
    """Section 8 square-root impact model for Variant A: impact per trade = impact_coef x
    sigma_daily x sqrt(contracts / ADV_20d) of traded notional, for that contract (sigma and ADV
    over the 20 settlement dates before the trade); positions scale linearly with AUM."""
    cfg = load_config()
    capital, coef, n = cfg["capital_base"], cfg["capacity"]["impact_coef"], cfg["capacity"]["adv_lookback_days"]
    size = cfg["specs"]["LE"]["size"]
    d, tr = _primary("A")
    vol = volume_panel("LE")
    px = contracts.settle_panel("LE")
    cal = px.index
    tr = tr[tr["qty"].abs() > 0].copy()
    sig_d, adv = [], []
    for _, t in tr.iterrows():
        days = cal[cal < t["date"]][-n:]
        sig_d.append(px[t["contract"]].reindex(days).pct_change().std(ddof=1))
        adv.append(vol[t["contract"]].reindex(days).fillna(0).mean() if t["contract"] in vol else np.nan)
    tr["sigma_daily"], tr["adv20"] = sig_d, adv
    base = d["net"]
    rows = []
    for aum in (float(a) for a in cfg["capacity"]["aum_grid"]):   # YAML reads "1.0e6" as a string
        k = aum / capital
        frac = coef * tr["sigma_daily"] * np.sqrt(k * tr["qty"].abs() / tr["adv20"]) * tr["qty"].abs() * tr["price"] * size / capital
        impact = frac.groupby(tr["date"]).sum().reindex(base.index).fillna(0)
        r = base - impact
        rows.append({"aum": aum, "sharpe_net": r.mean() / r.std(ddof=1) * np.sqrt(252), "ann_return_net": r.mean() * 252,
                     "impact_drag_per_year": impact.mean() * 252})
    out = pd.DataFrame(rows)
    out["note"] = "net Sharpe at $1M is negative, so the half-Sharpe AUM is undefined"
    return out


def plot_capacity(cap: pd.DataFrame, path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.5, 3.4), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ax.grid(color="#e6e5e0", linewidth=0.8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(length=0, colors="#52514e")
    ax.plot(cap["aum"], cap["sharpe_net"], color="#2a78d6", linewidth=2, marker="o", markersize=6)
    ax.set_xscale("log")
    ax.set_xlabel("AUM (USD, log scale)", color="#52514e")
    ax.set_ylabel("Net Sharpe", color="#52514e")
    ax.set_title("H1 primary: net Sharpe after square-root impact", loc="left", fontsize=11, color="#0b0b0b")
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="#fcfcfb")
    plt.close(fig)


def h2_episodes() -> pd.DataFrame:
    h = pd.read_parquet(PROCESSED / "h2_daily.parquet").set_index("date")["net"]
    m = analysis.monthly(h)
    worst = m.idxmin()
    windows = {**EPISODES, f"Worst month ({worst})": (worst.start_time.date(), worst.end_time.date())}
    rows = []
    for name, (a, b) in windows.items():
        w = h[(h.index >= pd.Timestamp(a)) & (h.index <= pd.Timestamp(b))]
        rows.append({"episode": name, "start": w.index[0].date(), "end": w.index[-1].date(),
                     "cum_net_return": w.sum(), "worst_day": w.min(), "worst_day_date": w.idxmin().date(),
                     "max_drawdown": analysis.drawdown(w).max()})
    return pd.DataFrame(rows)


def assert_in_sample_outputs() -> None:
    """Every saved development series must end before oos_start."""
    from src.config import oos_start
    checks = {"margin_daily.parquet": "date", "h2_daily.parquet": "date"}
    for f, col in checks.items():
        if pd.read_parquet(PROCESSED / f)[col].max() >= oos_start():
            raise RuntimeError(f"{f} contains dates on or after oos_start")
    for f in ["variant_a_daily.parquet", "variant_b_daily.parquet", "variant_c_daily.parquet", "robustness_daily.parquet"]:
        if pd.read_parquet(PROCESSED / f).index.max() >= oos_start():
            raise RuntimeError(f"{f} contains dates on or after oos_start")
