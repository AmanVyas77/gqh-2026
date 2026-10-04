"""H2: cattle prices and beef-buying equities (HYPOTHESIS_H2.md), primary specification only.
Implementation choices are recorded in HYPOTHESIS_H2.md Section 8 (2026-10-03 23:17).
Development data only: nothing dated on or after oos_start is loaded."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from src import analysis, contracts, trial_log
from src.config import RAW, load_config, oos_start

PAIRS = {"TSN": "XLP", "TXRH": "XLY"}            # stock -> sector hedge
COST_BPS = {"TSN": 5.0, "TXRH": 5.0, "XLP": 2.0, "XLY": 2.0}
BORROW_RATE = 0.005
TARGET_VOL, CLIP_DIV, MAX_W, GROSS_CAP = 0.10, 2.0, 2.0, 2.0
BETA_DAYS, VOL_DAYS, SIG_LOOKBACK, LE_MIN_DAYS, NW_LAGS = 252, 60, 36, 45, 2


def equities() -> pd.DataFrame:
    df = pd.read_parquet(RAW / "h2_equities.parquet").set_index("date").sort_index()
    if df.index.max() >= oos_start():
        raise RuntimeError("H2 equity data includes dates on or after oos_start")
    return df


def cattle_signal() -> pd.DataFrame:
    """Per LE month-end e: the contract chosen at the prior month-end b (first with last trading
    day >= b + 45 days), its return from b to e, sigma over the 36 prior months, and s = r / sigma."""
    s = contracts.settlements("LE").query("~cash_final")
    px = s.set_index(["date", "contract"])["price"]
    dates = pd.Series(sorted(s["date"].unique()))
    month_ends = dates.groupby(dates.dt.to_period("M")).max().tolist()
    rows = []
    for b, e in zip(month_ends[:-1], month_ends[1:]):
        c = contracts.select("LE", b, LE_MIN_DAYS)["contract"]
        if (e, c) not in px.index:
            raise RuntimeError(f"{c} has no settlement at month-end {e.date()}")
        rows.append({"month_end": e, "base_date": b, "contract": c, "r_le": px[(e, c)] / px[(b, c)] - 1})
    out = pd.DataFrame(rows).set_index("month_end")
    out["sigma"] = out["r_le"].shift(1).rolling(SIG_LOOKBACK, min_periods=SIG_LOOKBACK).std(ddof=1)
    out["s"] = out["r_le"] / out["sigma"]
    return out


def _beta(y: pd.Series, x: pd.Series) -> float:
    return float(sm.OLS(y.to_numpy(), sm.add_constant(x.to_numpy())).fit().params[1])


def rebalances(sig: pd.DataFrame, rets: pd.DataFrame, capital: float) -> pd.DataFrame:
    """Targets set at month-end t, executed at the close of the first NYSE day after t."""
    rows = []
    for t, row in sig.dropna(subset=["s"]).iterrows():
        hist = rets.loc[:t].dropna()
        if len(hist) < BETA_DAYS:
            continue
        after = rets.index[rets.index > t]
        if len(after) == 0:                                   # execution would fall after the data
            continue
        win = hist.iloc[-BETA_DAYS:]
        beta = {stk: _beta(win[stk], win[sec]) for stk, sec in PAIRS.items()}
        last60 = hist.iloc[-VOL_DAYS:]
        basket = sum(last60[stk] - beta[stk] * last60[sec] for stk, sec in PAIRS.items()) / len(PAIRS)
        sigma_b = basket.std(ddof=1) * np.sqrt(252)
        w = -float(np.clip(row["s"] / CLIP_DIV, -1, 1)) * TARGET_VOL / sigma_b
        w_uncapped = w
        w = float(np.clip(w, -MAX_W, MAX_W))
        gross_per_w = (len(PAIRS) + sum(beta.values())) / len(PAIRS)   # stock + hedge notional per unit |w|
        if abs(w) * gross_per_w > GROSS_CAP:
            w = np.sign(w) * GROSS_CAP / gross_per_w
        targets = {}
        for stk, sec in PAIRS.items():
            targets[stk] = w / 2 * capital
            targets[sec] = -(w / 2) * beta[stk] * capital
        rows.append({"signal_date": t, "exec_date": after[0], "s": row["s"], "r_le": row["r_le"],
                     "contract": row["contract"], "sigma_basket": sigma_b, "w_uncapped": w_uncapped, "w": w,
                     **{f"beta_{k}": v for k, v in beta.items()}, **{f"tgt_{k}": v for k, v in targets.items()}})
    return pd.DataFrame(rows)


def run(rb: pd.DataFrame, rets: pd.DataFrame, capital: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Daily P&L: dollar holdings drift with prices between rebalances; costs per side on traded
    notional at the execution close; borrow accrues daily on short notional."""
    assets = list(COST_BPS)
    execs = rb.set_index("exec_date")
    dates = rets.index[rets.index >= rb["exec_date"].min()]
    hold = pd.Series(0.0, index=assets)
    rows, contrib = [], []
    for d in dates:
        r = rets.loc[d, assets]
        pnl_by = hold * r
        borrow = float((-hold[hold < 0]).sum() * BORROW_RATE / 252)
        hold = hold * (1 + r)
        cost, traded = 0.0, 0.0
        if d in execs.index:
            tgt = pd.Series({a: execs.loc[d, f"tgt_{a}"] for a in assets})
            trade = tgt - hold
            cost = float(sum(abs(trade[a]) * COST_BPS[a] / 1e4 for a in assets))
            traded = float(trade.abs().sum())
            hold = tgt
        rows.append({"date": d, "pnl": float(pnl_by.sum()), "cost": cost, "borrow": borrow, "traded": traded,
                     "gross_notional": float(hold.abs().sum()),
                     "stock_notional": float(hold[list(PAIRS)].abs().sum()),
                     "net_notional": float(hold.sum())})
        contrib.append({"date": d, **{a: float(pnl_by[a]) for a in assets}})
    daily = pd.DataFrame(rows)
    daily["gross"] = daily["pnl"] / capital
    daily["net"] = (daily["pnl"] - daily["cost"] - daily["borrow"]) / capital
    daily["net2x"] = (daily["pnl"] - 2 * daily["cost"] - 2 * daily["borrow"]) / capital
    return daily, pd.DataFrame(contrib).set_index("date")


def basket_monthly(rets: pd.DataFrame, sig: pd.DataFrame) -> pd.Series:
    """Calendar-month sum of the daily hedged basket return, using betas estimated at the prior
    month-end (the hedge in force during the month)."""
    out = {}
    month_ends = list(sig.index)
    for b, e in zip(month_ends[:-1], month_ends[1:]):
        hist = rets.loc[:b].dropna()
        if len(hist) < BETA_DAYS:
            continue
        win = hist.iloc[-BETA_DAYS:]
        beta = {stk: _beta(win[stk], win[sec]) for stk, sec in PAIRS.items()}
        month = rets[(rets.index.to_period("M") == e.to_period("M"))]
        h = sum(month[stk] - beta[stk] * month[sec] for stk, sec in PAIRS.items()) / len(PAIRS)
        out[e.to_period("M")] = h.sum()
    return pd.Series(out)


def nw(y: pd.Series, x: pd.Series | None = None, lags: int = NW_LAGS) -> dict:
    """Newey-West OLS: slope on x (with intercept), or the mean of y when x is None."""
    d = pd.concat({"y": y, "x": x}, axis=1).dropna() if x is not None else y.dropna().to_frame("y")
    if x is not None:
        fit = sm.OLS(d["y"], sm.add_constant(d["x"])).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
        beta, t, r2 = float(fit.params["x"]), float(fit.tvalues["x"]), float(fit.rsquared)
    else:
        fit = sm.OLS(d["y"].to_numpy(), np.ones(len(d))).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
        beta, t, r2 = float(fit.params[0]), float(fit.tvalues[0]), np.nan
    return {"beta": beta, "t_nw": t, "n": len(d), "first": str(d.index.min()), "last": str(d.index.max()), "r2": r2}


def evaluate(log: bool = True) -> dict:
    cfg = load_config()
    capital = cfg["capital_base"]
    px = equities()
    rets = px.pct_change().iloc[1:]
    sig = cattle_signal()
    rb = rebalances(sig, rets, capital)
    daily, contrib = run(rb, rets, capital)

    # Pre-registered tests (Section 6)
    hb = basket_monthly(rets, sig)
    r_le = sig["r_le"].copy(); r_le.index = r_le.index.to_period("M")
    s = sig["s"].copy(); s.index = s.index.to_period("M")
    q1 = nw(hb, r_le.reindex(hb.index))
    q2 = nw(hb.shift(-1), s.reindex(hb.index))
    m_net = analysis.monthly(daily.set_index("date")["net"])
    q3 = nw(m_net)
    tests = {"Q1": {**q1, "pass": q1["beta"] < 0 and q1["t_nw"] < -2},
             "Q2": {**q2, "pass": q2["beta"] < 0 and q2["t_nw"] < -2},
             "Q3_in_sample": {**q3, "pass": q3["beta"] > 0 and q3["t_nw"] > 2}}

    # Performance
    def perf(col: str) -> dict:
        r = daily.set_index("date")[col]
        eq = 1 + r.cumsum()
        mm = analysis.monthly(r)
        return {"ann_return": r.mean() * 252, "ann_vol": r.std(ddof=1) * np.sqrt(252),
                "sharpe": r.mean() / r.std(ddof=1) * np.sqrt(252),
                "max_drawdown_from_peak": float((1 - eq / eq.cummax()).max()),
                "max_loss_below_initial_nav": float(min(0.0, (eq - 1).min())),
                "mean_monthly": mm.mean(), "nw_t_monthly": nw(mm)["t_nw"], "worst_month": mm.min(),
                "worst_month_label": str(mm.idxmin()), "best_month": mm.max(), "total_return": r.sum()}
    years = (daily["date"].iloc[-1] - daily["date"].iloc[0]).days / 365.25
    performance = {c: perf(c) for c in ("gross", "net", "net2x")}
    exposure = {"avg_gross_exposure": daily["gross_notional"].mean() / capital,
                "max_gross_exposure": daily["gross_notional"].max() / capital,
                "avg_stock_exposure": daily["stock_notional"].mean() / capital,
                "avg_net_exposure": daily["net_notional"].mean() / capital,
                "turnover_per_year": daily["traded"].sum() / capital / years,
                "cost_drag_per_year": daily["cost"].sum() / capital / years,
                "borrow_drag_per_year": daily["borrow"].sum() / capital / years,
                "avg_abs_w": rb["w"].abs().mean(), "rebalances_capped_by_gross": int((rb["w"].abs() < rb["w_uncapped"].abs() - 1e-12).sum()),
                "share_full_conviction": float((rb["s"].abs() >= 2).mean())}
    annual = daily.set_index("date")[["gross", "net", "net2x"]].groupby(lambda d: d.year).sum()

    # Concentration
    by_asset = contrib.sum() / capital
    by_pair = {stk: by_asset[stk] + by_asset[sec] for stk, sec in PAIRS.items()}
    mon = daily.set_index("date")["pnl"].groupby(lambda d: d.to_period("M")).sum() / capital
    top = mon.abs().sort_values(ascending=False)
    conc = {"pnl_by_asset": by_asset.to_dict(), "pnl_by_pair": by_pair,
            "top5_months": {str(k): float(mon[k]) for k in top.index[:5]},
            "gross_pnl_total": float(mon.sum()), "gross_pnl_ex_top3_abs_months": float(mon.drop(top.index[:3]).sum()),
            "hit_rate_months": float((mon > 0).mean())}

    out = {"signal": sig, "rebalances": rb, "daily": daily, "contrib": contrib, "basket_monthly": hb,
           "tests": tests, "performance": performance, "exposure": exposure, "annual": annual,
           "concentration": conc}
    if log:
        r = daily["net"]
        from scipy import stats
        trial_log.log_trial("H2", {"spec": "primary", "signal": "1-month LE return / 36m sd", "hedge": "sector ETFs"},
                            (daily["date"].iloc[0].date(), daily["date"].iloc[-1].date()),
                            performance["net"]["sharpe"], len(r), float(stats.skew(r)),
                            float(stats.kurtosis(r, fisher=False)), kind="trial", spec="primary")
    return out
