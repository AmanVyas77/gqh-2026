"""Month-end signals (HYPOTHESIS.md Section 5, robustness spec, and Section 9 diagnostics).

z_t = (X_t - mean(X over the `lookback` prior month-ends)) / sd(X over the same window),
excluding month t itself; sd is the sample standard deviation (ddof=1). The first valid
z is `lookback` months after the series starts.

Series z-scored:
- primary:        X = M_t (feeding margin)
- seasonal_adj:   X = M_t - S_t, where S_t is the mean of M at the same calendar month in each
                  of the previous `seasonal_years` years (all required)   [robustness spec, diag 1a]
- seasonal_only:  X = S_t                                                [diagnostic 1b]
- le_only:        X = 1,400 x the sale-contract LE settlement            [diagnostic 2]

Hedging pressure for Variant C is added with Variant C (it needs the CFTC release calendar).
"""
from __future__ import annotations

import pandas as pd

from src import margin
from src.config import load_config


def zscore(x: pd.Series, lookback: int) -> pd.Series:
    """Trailing z-score using only the `lookback` observations before t."""
    past = x.shift(1).rolling(lookback, min_periods=lookback)
    return (x - past.mean()) / past.std(ddof=1)


def seasonal_component(x: pd.Series, years: int) -> pd.Series:
    """Mean of x at the same calendar month in each of the previous `years` years.
    `x` must be a regular monthly series (one value per month, no gaps)."""
    _check_monthly(x)
    lags = pd.concat([x.shift(12 * k) for k in range(1, years + 1)], axis=1)
    return lags.mean(axis=1).where(lags.notna().all(axis=1))


def _check_monthly(x: pd.Series) -> None:
    months = pd.PeriodIndex(x.index, freq="M")
    if months.has_duplicates or len(months) != (months.max() - months.min()).n + 1:
        raise ValueError("series must have exactly one value per calendar month")


def month_end_signals(sale_min_days: int | None = None, fcr: float | None = None,
                      lookback: int | None = None, seasonal_years: int | None = None,
                      k: float | None = None, oos: bool = False) -> pd.DataFrame:
    """Month-end table indexed by the month-end trading date: M, its seasonal parts, the LE leg,
    and z for each signal definition. Contract columns are kept for auditing."""
    cfg = load_config()["signal"]
    lookback = cfg["z_lookback_months"] if lookback is None else lookback
    seasonal_years = cfg["seasonal_years"] if seasonal_years is None else seasonal_years
    me = margin.month_end(margin.margin_daily(sale_min_days, fcr, k, oos=oos)).set_index("date")
    out = me[["sale_contract", "sale_ltd", "sale_price", "feeder_contract", "corn_contract",
              "revenue", "margin"]].copy()
    out["seasonal"] = seasonal_component(out["margin"], seasonal_years)
    out["margin_sa"] = out["margin"] - out["seasonal"]
    out["z"] = zscore(out["margin"], lookback)
    out["z_sa"] = zscore(out["margin_sa"], lookback)
    out["z_seasonal_only"] = zscore(out["seasonal"], lookback)
    out["z_le"] = zscore(out["revenue"], lookback)
    out.attrs.update({"lookback": lookback, "seasonal_years": seasonal_years})
    return out


def signal_z(sig: pd.DataFrame, seasonal_adjust: bool | None = None) -> pd.Series:
    """The z that drives positions for a spec: seasonally adjusted or not (config default)."""
    if seasonal_adjust is None:
        seasonal_adjust = load_config()["signal"]["seasonal_adjust"]
    return sig["z_sa"] if seasonal_adjust else sig["z"]
