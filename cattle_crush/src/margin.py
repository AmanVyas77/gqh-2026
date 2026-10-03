"""Projected feeding margin (HYPOTHESIS.md Section 3).

    M_t = W_out * LE_t - W_in * FC_t - B * C_t - K,   B = (W_out - W_in) * FCR / 56

LE_t, FC_t and C_t are day-t final settlements of the sale, feeder and corn contracts
chosen by the Section 4 rules (contracts.py), in $/lb and $/bu. M_t is in $/head.

Calendar: M_t exists only on dates with a settlement for all three selected contracts.
Dates missing from the feed for any product are non-trading days for it and are never
forward-filled (Deviation Log 2026-10-03). Month-end = the last such date in each month.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from src import contracts
from src.config import load_config

LEGS = {"LE": "sale", "GF": "feeder", "ZC": "corn"}


def bushels(w_in: float, w_out: float, fcr: float, lb_per_bu: float) -> float:
    """B = bushels of corn eaten per head over the feeding period."""
    return (w_out - w_in) * fcr / lb_per_bu


def params(sale_min_days: int | None = None, fcr: float | None = None, k: float | None = None) -> dict:
    """Primary-spec parameters from config.yaml, with optional one-at-a-time overrides."""
    cfg = load_config()
    m, c = cfg["margin"], cfg["contracts"]
    p = {"w_in": m["w_in_lb"], "w_out": m["w_out_lb"], "fcr": m["fcr"] if fcr is None else fcr,
         "lb_per_bu": m["corn_lb_per_bu"], "k": m["k_other_cost"] if k is None else k,
         "min_days": {"LE": c["sale_min_days"] if sale_min_days is None else sale_min_days,
                      "GF": c["feeder_min_days"], "ZC": c["corn_min_days"]}}
    p["B"] = bushels(p["w_in"], p["w_out"], p["fcr"], p["lb_per_bu"])
    return p


def _validity(root: str, oos: bool) -> pd.DataFrame:
    """Each contract's published expiry versions as intervals [valid_from, valid_to)."""
    v = contracts.definition_versions(oos)
    v = (v[v["root"] == root].groupby(["contract", "last_trade_date"], as_index=False)["known_from"].min()
         .sort_values(["contract", "known_from"]))
    v["valid_to"] = v.groupby("contract")["known_from"].shift(-1).fillna(pd.Timestamp.max.normalize())
    return v.rename(columns={"known_from": "valid_from"})


@lru_cache(maxsize=32)
def selection(root: str, min_days: int, oos: bool = False) -> pd.DataFrame:
    """Selected contract on every settlement date of `root`: [date, contract, last_trade_date].
    Same rule as contracts.select(): first contract known at t whose expiry, as published by t,
    is at least t + min_days."""
    dates = pd.DataFrame({"date": sorted(contracts.settlements(root, oos).query("~cash_final")["date"].unique())})
    v = _validity(root, oos)
    x = dates.merge(v, how="cross")
    x = x[(x["valid_from"] <= x["date"]) & (x["date"] < x["valid_to"])
          & (x["last_trade_date"] >= x["date"] + pd.Timedelta(days=min_days))]
    x = x.loc[x.groupby("date")["last_trade_date"].idxmin(), ["date", "contract", "last_trade_date"]]
    return x.sort_values("date").reset_index(drop=True)


def margin_daily(sale_min_days: int | None = None, fcr: float | None = None, k: float | None = None,
                 oos: bool = False) -> pd.DataFrame:
    """Daily M_t with the selected contract, expiry and settlement of each leg, for auditing."""
    p = params(sale_min_days, fcr, k)
    out = None
    for root, leg in LEGS.items():
        sel = selection(root, p["min_days"][root], oos)
        px = contracts.settlements(root, oos).query("~cash_final")[["date", "contract", "price"]]
        sel = sel.merge(px, on=["date", "contract"], how="left")
        sel = sel.rename(columns={"contract": f"{leg}_contract", "last_trade_date": f"{leg}_ltd",
                                  "price": f"{leg}_price"})
        out = sel if out is None else out.merge(sel, on="date", how="inner")   # all three products trade
    unpriced = out[[f"{leg}_price" for leg in LEGS.values()]].isna().any(axis=1)
    out = out[~unpriced].copy()
    out["revenue"] = p["w_out"] * out["sale_price"]
    out["feeder_cost"] = p["w_in"] * out["feeder_price"]
    out["corn_cost"] = p["B"] * out["corn_price"]
    out["margin"] = out["revenue"] - out["feeder_cost"] - out["corn_cost"] - p["k"]
    out.attrs.update({"B": p["B"], "k": p["k"], "min_days": p["min_days"],
                      "dropped_unpriced_dates": int(unpriced.sum())})
    return out.reset_index(drop=True)


def month_end(daily: pd.DataFrame) -> pd.DataFrame:
    """Last date in each calendar month on which M_t exists."""
    me = daily.loc[daily.groupby(daily["date"].dt.to_period("M"))["date"].idxmax()].reset_index(drop=True)
    me.attrs = dict(daily.attrs)
    return me


def margin_at(t, sale_min_days: int | None = None, fcr: float | None = None, k: float | None = None,
              oos: bool = False) -> pd.Series:
    """M_t on a single date, built from contracts.select() directly (independent of the
    vectorized daily path). Raises if any selected contract has no settlement on t."""
    t = pd.Timestamp(t)
    p = params(sale_min_days, fcr, k)
    row = {"date": t}
    for root, leg in LEGS.items():
        c = contracts.select(root, t, p["min_days"][root], oos)
        s = contracts.settlements(root, oos)
        hit = s[(s["date"] == t) & (s["contract"] == c["contract"]) & ~s["cash_final"]]
        if hit.empty:
            raise KeyError(f"no {root} settlement for {c['contract']} on {t.date()}")
        row.update({f"{leg}_contract": c["contract"], f"{leg}_ltd": c["last_trade_date"],
                    f"{leg}_price": float(hit["price"].iloc[0])})
    row["margin"] = (p["w_out"] * row["sale_price"] - p["w_in"] * row["feeder_price"]
                     - p["B"] * row["corn_price"] - p["k"])
    return pd.Series(row)


# --------------------------------------------------------------------------- figure

INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"
SERIES = {"revenue": "#2a78d6", "feeder_cost": "#eb6834", "corn_cost": "#1baf7a"}   # validated, light mode


def plot_margin(daily: pd.DataFrame, path) -> None:
    """Two panels on a shared time axis, both in $/head: M_t (daily and month-end), and the
    month-end revenue and cost legs that make it up."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    me = month_end(daily)
    dollars = FuncFormatter(lambda v, _: f"-\\${abs(v):,.0f}" if v < 0 else f"\\${v:,.0f}")
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK_2,
                         "xtick.color": INK_2, "ytick.color": INK_2, "text.color": INK})
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 7.2), sharex=True, facecolor=SURFACE,
                                 gridspec_kw={"height_ratios": [1.15, 1], "hspace": 0.42})
    for ax in (a1, a2):
        ax.set_facecolor(SURFACE)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.tick_params(length=0)
        ax.yaxis.set_major_formatter(dollars)

    a1.axhline(0, color=INK_2, linewidth=0.9, linestyle=(0, (4, 3)))
    a1.plot(daily["date"], daily["margin"], color="#b5b3ab", linewidth=0.8, label="Daily")
    a1.plot(me["date"], me["margin"], color=INK, linewidth=1.8, label="Month-end (signal input)")
    a1.set_title(f"Projected feeding margin M_t, \\$/head  (K = \\${daily.attrs['k']:,.0f} non-corn cost; "
                 f"cancels in the z-score)", loc="left", fontsize=11, color=INK, pad=24)
    a1.legend(loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, ncol=2, borderaxespad=0.2)

    labels = {"revenue": "Sale value: 1,400 lb × sale LE",
              "feeder_cost": "Feeder cost: 800 lb × feeder GF",
              "corn_cost": f"Corn cost: {daily.attrs['B']:.1f} bu × corn ZC"}
    for col, color in SERIES.items():
        a2.plot(me["date"], me[col], color=color, linewidth=2, label=labels[col])
        a2.annotate(labels[col].split(":")[0], (me["date"].iloc[-1], me[col].iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=9, color=INK_2)
    a2.set_title("Month-end legs of the margin, \\$/head", loc="left", fontsize=11, color=INK, pad=24)
    a2.legend(loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, ncol=3, borderaxespad=0.2)
    a2.set_xlim(daily["date"].min(), daily["date"].max() + pd.Timedelta(days=420))
    fig.text(0.01, 0.005, f"In-sample {daily['date'].min():%Y-%m-%d} to {daily['date'].max():%Y-%m-%d}. "
             "CME settlements via Databento; contracts chosen by HYPOTHESIS.md Section 4.",
             fontsize=8, color=INK_2)
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
