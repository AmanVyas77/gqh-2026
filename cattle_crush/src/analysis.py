"""Performance metrics (CLAUDE.md analysis.metrics) and small regression helpers."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from src.config import load_config


def monthly(r: pd.Series) -> pd.Series:
    """Calendar-month sums of daily returns on fixed capital."""
    return r.groupby(r.index.to_period("M")).sum()


def nw_mean_t(x: pd.Series, lags: int) -> tuple[float, float]:
    fit = sm.OLS(x.to_numpy(), np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return float(fit.params[0]), float(fit.tvalues[0])


def drawdown(r: pd.Series) -> pd.Series:
    equity = 1 + r.cumsum()
    return 1 - equity / equity.cummax()


def metrics(daily: pd.DataFrame, col: str = "net", capital: float | None = None) -> dict:
    """daily: backtest daily frame (date, gross, net, net2x, gross_notional, ...)."""
    cfg = load_config()
    capital = capital or cfg["capital_base"]
    r = daily.set_index("date")[col]
    m = monthly(r)
    years = (r.index[-1] - r.index[0]).days / 365.25
    mean_m, t_m = nw_mean_t(m, cfg["tests"]["p2_nw_lags"])
    return {
        "start": r.index[0].date(), "end": r.index[-1].date(), "n_days": len(r), "n_months": len(m),
        "ann_return": r.mean() * 252, "ann_vol": r.std(ddof=1) * np.sqrt(252),
        "sharpe": r.mean() / r.std(ddof=1) * np.sqrt(252),
        "max_drawdown": drawdown(r).max(),
        "mean_monthly": mean_m, "nw_t_monthly": t_m,
        "worst_month": m.min(), "worst_month_label": str(m.idxmin()),
        "skew_daily": stats.skew(r), "kurt_daily": stats.kurtosis(r, fisher=False),
        "avg_gross_leverage": daily["gross_notional"].mean() / capital,
        "max_gross_leverage": daily["gross_notional"].max() / capital,
        "turnover": None,
    }


def turnover(trades: pd.DataFrame, daily: pd.DataFrame, capital: float) -> float:
    """Annual sum of |traded notional| / capital."""
    if trades.empty:
        return 0.0
    years = (daily["date"].iloc[-1] - daily["date"].iloc[0]).days / 365.25
    return trades["notional"].fillna(0).sum() / capital / years


def regress_returns(y: pd.Series, x: pd.Series, lags: int) -> dict:
    """OLS of y on x with an intercept, Newey-West SEs; aligned on the common index."""
    d = pd.concat({"y": y, "x": x}, axis=1).dropna()
    fit = sm.OLS(d["y"], sm.add_constant(d["x"])).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return {"n": int(fit.nobs), "alpha": fit.params["const"], "alpha_t": fit.tvalues["const"],
            "beta": fit.params["x"], "beta_t": fit.tvalues["x"], "r2": fit.rsquared,
            "corr": d["y"].corr(d["x"])}
