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


# --------------------------------------------------------------------------- hedging pressure (Variant C)

def _closed_days() -> pd.DatetimeIndex:
    """US federal holidays plus documented federal closures (data/manual/federal_closures.csv)."""
    from pandas.tseries.holiday import USFederalHolidayCalendar
    from src.config import MANUAL

    extra = pd.to_datetime(pd.read_csv(MANUAL / "federal_closures.csv")["date"])
    return USFederalHolidayCalendar().holidays("2005-01-01", "2027-12-31").union(pd.DatetimeIndex(extra))


def cftc_known_from(asof: pd.Series) -> pd.Series:
    """Date from which a COT report counts as known (Deviation Log 2026-10-03 17:36):
    documented disruption date if the as-of date falls in one; else as-of + 6 days, or + 8 if a
    federal holiday/closure falls in [as-of + 1, as-of + 6]; rolled to the next business day."""
    from src.config import MANUAL

    closed = _closed_days()
    bday = pd.offsets.CustomBusinessDay(holidays=closed)
    out = []
    for a in pd.to_datetime(asof):
        lag = 8 if ((closed > a) & (closed <= a + pd.Timedelta(days=6))).any() else 6
        out.append(bday.rollforward(a + pd.Timedelta(days=lag)))
    known = pd.Series(out, index=asof.index)
    dis = pd.read_csv(MANUAL / "cftc_disruptions.csv", parse_dates=["asof_first", "asof_last", "known_from"])
    for _, w in dis.iterrows():
        inside = (asof >= w["asof_first"]) & (asof <= w["asof_last"])
        known[inside] = w["known_from"]
    return known


def hedging_pressure(oos: bool = False) -> pd.DataFrame:
    """Weekly HP = (PMPU short - PMPU long) / (short + long), Live Cattle, futures only, with the
    median of the previous `median_lookback_weeks` reports (excluding the current one)."""
    from src.config import RAW, RAW_OOS

    weeks = load_config()["hedging_pressure"]["median_lookback_weeks"]
    files = [RAW / "cftc_live_cattle.parquet"] + ([RAW_OOS / "cftc_live_cattle.parquet"] if oos else [])
    df = pd.concat([pd.read_parquet(f) for f in files if f.exists()]).drop_duplicates("asof_date")
    df = df.sort_values("asof_date").reset_index(drop=True)
    long, short = df["prod_merc_positions_long"], df["prod_merc_positions_short"]
    df["hp"] = (short - long) / (short + long)
    df["hp_median_prior"] = df["hp"].shift(1).rolling(weeks, min_periods=weeks).median()
    df["known_from"] = cftc_known_from(df["asof_date"])
    return df[["asof_date", "known_from", "hp", "hp_median_prior"]]


def hp_at(dates, oos: bool = False) -> pd.DataFrame:
    """Latest COT report known at each date: its as-of date, HP and prior-156-week median."""
    hp = hedging_pressure(oos).sort_values("known_from")
    rows = []
    for t in pd.DatetimeIndex(dates):
        known = hp[hp["known_from"] <= t]
        if known.empty:
            rows.append({"date": t, "asof_date": pd.NaT, "hp": float("nan"), "hp_median_prior": float("nan")})
            continue
        r = known.loc[known["asof_date"].idxmax()]
        rows.append({"date": t, "asof_date": r["asof_date"], "hp": r["hp"], "hp_median_prior": r["hp_median_prior"]})
    return pd.DataFrame(rows).set_index("date")
