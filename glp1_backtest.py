#!/usr/bin/env python3
"""GLP-1 second-order beneficiaries: cross-sectional beta-sort backtest.

Pipeline
  1. Daily adjusted closes (yfinance, or --synthetic).
  2. GLP-1 factor:  GLP_t = avg(r_LLY, r_NVO)_t - b_{t-1} * r_SPY,t
     b_{t-1} is the rolling SPY beta of the LLY/NVO basket, estimated with data through t-1.
     In words: the part of the pharma pair's daily move that the market does not explain.
  3. Each month-end t, per stock, OLS over the trailing BETA_WINDOW trading days (data through t):
         r_i = a + b_mkt * r_SPY + b_glp * GLP + e
     b_glp = how much the stock moves with GLP-1 news, holding the market move fixed.
  4. Rank stocks on b_glp; trade at the NEXT close (t+1); hold until the next rebalance.
       LS          long top quantile / short bottom quantile, equal weight, $1 long + $1 short
       LS_BN       same, but ranked within each of the 4 buckets, then combined (bucket-neutral)
       LongHedged  long top quantile, short SPY * (average b_mkt of the longs)
       EW, SPY     benchmarks
  5. Stats (Full / IS < OOS_START / OOS), monthly IC, tearsheet and CSVs.

Usage
  python glp1_backtest.py                      # real data, baseline
  python glp1_backtest.py --synthetic          # offline smoke test
  python glp1_backtest.py --grid               # + robustness_grid.csv
  python glp1_backtest.py --placebo 500        # + random-ranking null distribution
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings
from dataclasses import dataclass, replace
from datetime import datetime
from fractions import Fraction
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------- universe
UNIVERSE = {
    "CDMO/Pens": ["WST", "STVN", "TMO", "BDX"],
    "Protein/Fitness": ["SMPL", "BRBR", "PLNT", "HLF", "XPOF"],
    "Apparel": ["LULU", "TJX", "GAP", "ANF", "URBN"],
    "Telehealth": ["HIMS", "TDOC", "LFMD", "AMWL"],
}
TICKERS = [t for names in UNIVERSE.values() for t in names]
BUCKET = {t: b for b, names in UNIVERSE.items() for t in names}
MKT = "SPY"
FACTOR_LEGS = {"both": ["LLY", "NVO"], "lly": ["LLY"], "nvo": ["NVO"]}

# Real-data fixes
# Gap Inc. traded as GPS until Aug-2024; yfinance now serves the full history under GAP and 404s on
# GPS. GPS is only tried if GAP comes back empty or truncated.
ALIASES = {"GAP": ["GPS"]}
# Prices before these dates belong to a different security (SPAC shell), not the company.
LISTING_START = {"HIMS": "2021-01-21"}  # Oaktree Acquisition Corp (OAC) before the Hims & Hers merger

TRADING_DAYS = 252


@dataclass(frozen=True)
class Config:
    beta_window: int = 252       # trading days in each stock's OLS window
    factor_window: int = 252     # trading days for the LLY/NVO-vs-SPY beta used to residualize the factor
    quantile: float = 1 / 3      # fraction of names in each leg
    cost_bps: float = 10.0       # one-way cost per $ traded
    borrow_bps: float = 0.0      # annual fee on short notional (0 = original spec)
    factor: str = "both"         # both | lly | nvo
    min_obs_frac: float = 0.75   # a stock needs >= this share of the window to get a beta
    data_start: str = "2018-01-01"
    bt_start: str = "2021-01-01"  # first signal = last month-end before this date
    oos_start: str = "2024-01-01"
    end: str | None = None


# ----------------------------------------------------------------------------- data
def _extract_close(raw: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    """Return a Date x Ticker frame of closes from any yfinance column layout.

    yfinance >= 0.2.48 / 1.x returns MultiIndex (Price, Ticker); group_by='ticker' gives
    (Ticker, Price); a single symbol in older versions comes back with flat columns.
    """
    if raw is None or raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        for lvl in range(raw.columns.nlevels):
            if "Close" in raw.columns.get_level_values(lvl):
                close = raw.xs("Close", axis=1, level=lvl)
                break
        else:
            raise ValueError("yfinance output has no 'Close' column")
    else:
        close = raw[["Close"]].set_axis(symbols[:1], axis=1)
    close = close.copy()
    close.index = pd.to_datetime(close.index)
    if close.index.tz is not None:
        close.index = close.index.tz_localize(None)
    close.columns = [str(c) for c in close.columns]
    return close.sort_index()


def _yf_close(symbols: list[str], start: str, end: str | None) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(symbols, start=start, end=end, auto_adjust=True,  # adjusted for splits/dividends
                      progress=False, threads=True)
    return _extract_close(raw, symbols)


def download_prices(cfg: Config, cache_dir: str, refresh: bool) -> pd.DataFrame:
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"prices_{cfg.data_start}_{cfg.end or 'latest'}.csv")
    if os.path.exists(path) and not refresh:
        print(f"[data] cached prices: {path} (--refresh to re-download)")
        return pd.read_csv(path, index_col=0, parse_dates=True)

    wanted = TICKERS + sorted({t for legs in FACTOR_LEGS.values() for t in legs}) + [MKT]
    close = _yf_close(wanted, cfg.data_start, cfg.end)
    first_day = close.index.min()
    out = {}
    for t in wanted:
        s = close[t] if t in close else pd.Series(dtype=float)
        truncated = s.dropna().empty or s.first_valid_index() > first_day + pd.Timedelta(days=30)
        if truncated and t in ALIASES:
            alt = _yf_close(ALIASES[t], cfg.data_start, cfg.end)
            for a in ALIASES[t]:
                if a in alt and alt[a].notna().sum() > s.notna().sum():
                    print(f"[data] {t}: using yfinance symbol {a} (longer history)")
                    s = alt[a].reindex(close.index)
        if s.dropna().empty:
            print(f"[data] WARNING: no data for {t}; dropped from universe")
            continue
        out[t] = s
    prices = pd.DataFrame(out)
    prices.to_csv(path)
    print(f"[data] downloaded {prices.shape[1]} symbols, {prices.index.min().date()} -> "
          f"{prices.index.max().date()}; cached to {path}")
    return prices


def clean_prices(prices: pd.DataFrame) -> pd.DataFrame:
    p = prices.sort_index().copy()
    p = p[p[MKT].notna()]  # yfinance can append an all-NaN row for the current day
    now = datetime.now(ZoneInfo("America/New_York"))
    if len(p) and p.index[-1].date() == now.date() and (now.hour, now.minute) < (16, 30):
        p = p.iloc[:-1]  # today's bar is a live intraday price until the close
    for t, d in LISTING_START.items():
        if t in p:
            p.loc[p.index < pd.Timestamp(d), t] = np.nan
    return p


def synthetic_prices(cfg: Config, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(cfg.data_start, cfg.end or "2026-09-30")
    n = len(idx)
    mkt = rng.normal(0.0004, 0.011, n)
    glp = rng.normal(0.0003, 0.012, n)
    r = {MKT: mkt,
         "LLY": 0.6 * mkt + glp + rng.normal(0, 0.010, n),
         "NVO": 0.6 * mkt + glp + rng.normal(0, 0.010, n)}
    bucket_beta = {"CDMO/Pens": 0.25, "Protein/Fitness": 0.15, "Apparel": 0.05, "Telehealth": 0.35}
    for t in TICKERS:
        b = bucket_beta[BUCKET[t]] + rng.normal(0, 0.15)
        r[t] = rng.uniform(0.7, 1.4) * mkt + b * glp + rng.normal(0, 0.02, n)
    p = (1 + pd.DataFrame(r, index=idx)).cumprod() * 100
    ipos = {"BRBR": "2019-10-18", "AMWL": "2020-09-17", "HIMS": "2021-01-21",
            "STVN": "2021-07-16", "XPOF": "2021-07-23"}
    for t, d in ipos.items():
        p.loc[p.index < d, t] = np.nan
    return p


# ----------------------------------------------------------------------------- signal
def glp_factor(rets: pd.DataFrame, variant: str, window: int) -> pd.Series:
    raw = rets[FACTOR_LEGS[variant]].mean(axis=1, skipna=False)
    m = rets[MKT]
    beta = raw.rolling(window, min_periods=window).cov(m) / m.rolling(window, min_periods=window).var()
    return (raw - beta.shift(1) * m).rename("GLP")


def month_end_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    me = pd.Series(index, index=index).groupby(index.to_period("M")).max()
    last = index[-1]
    if last != last + pd.offsets.BMonthEnd(0):  # final month still in progress
        me = me.iloc[:-1]
    return pd.DatetimeIndex(me.values)


def estimate_betas(rets: pd.DataFrame, glp: pd.Series, sig_dates: pd.DatetimeIndex,
                   window: int, min_obs_frac: float) -> pd.DataFrame:
    """Rolling OLS r_i = a + b_mkt*SPY + b_glp*GLP on the `window` rows ending at each signal date."""
    names = [t for t in TICKERS if t in rets]
    min_obs = int(np.ceil(window * min_obs_frac))
    F = pd.concat([rets[MKT], glp], axis=1).to_numpy()
    Y = rets[names].to_numpy()
    rows = []
    for s, e in zip(sig_dates, rets.index.get_indexer(sig_dates)):
        lo = max(0, e - window + 1)
        f = F[lo:e + 1]
        f_ok = np.isfinite(f).all(axis=1)
        for j, t in enumerate(names):
            if not np.isfinite(Y[e, j]):
                continue  # not trading at t
            y = Y[lo:e + 1, j]
            ok = f_ok & np.isfinite(y)
            n = int(ok.sum())
            if n < min_obs:
                continue
            X = np.column_stack([np.ones(n), f[ok]])
            a, b_mkt, b_glp = np.linalg.lstsq(X, y[ok], rcond=None)[0]
            rows.append((s, t, a, b_mkt, b_glp, n))
    return pd.DataFrame(rows, columns=["signal_date", "ticker", "alpha", "beta_mkt", "beta_glp", "n_obs"])


@dataclass
class Signals:
    prices: pd.DataFrame
    rets: pd.DataFrame
    glp: pd.Series
    betas: pd.DataFrame              # one row per (signal_date, eligible ticker)
    trade_of: dict                   # signal_date -> trade date (next close)
    pending: pd.Timestamp | None     # latest signal whose trade date is not in the data yet


def compute_signals(prices: pd.DataFrame, cfg: Config) -> Signals:
    rets = prices.pct_change(fill_method=None)
    glp = glp_factor(rets, cfg.factor, cfg.factor_window)
    sig = month_end_dates(rets.index)
    bt_start = pd.Timestamp(cfg.bt_start)
    before = sig[sig < bt_start]
    sig = sig[sig >= (before.max() if len(before) else sig.min())]
    betas = estimate_betas(rets, glp, sig, cfg.beta_window, cfg.min_obs_frac)

    idx = rets.index
    trade_of, pending = {}, None
    for s in sig:
        p = idx.get_loc(s)
        if p + 1 < len(idx):
            trade_of[s] = idx[p + 1]
        else:
            pending = s
    # a name must also have a price at the trade close to be traded
    tradable = [s not in trade_of or np.isfinite(prices.at[trade_of[s], t])
                for s, t in zip(betas.signal_date, betas.ticker)]
    betas = betas[np.array(tradable, dtype=bool)].reset_index(drop=True)
    return Signals(prices, rets, glp, betas, trade_of, pending)


# ----------------------------------------------------------------------------- portfolios
def ls_weights(g: pd.DataFrame, q: float) -> pd.Series:
    """Equal-weight long top-q / short bottom-q by beta_glp. Leg size k = floor(n*q), at least 1."""
    s = g.set_index("ticker")["beta_glp"].sort_index()
    n = len(s)
    k = min(max(1, int(np.floor(n * q + 1e-9))), n // 2)
    w = pd.Series(0.0, index=s.index)
    if k == 0:
        return w
    order = s.sort_values(kind="mergesort").index  # ties broken alphabetically
    w[order[-k:]] = 1.0 / k
    w[order[:k]] = -1.0 / k
    return w


def ls_bucket_neutral_weights(g: pd.DataFrame, q: float) -> pd.Series:
    """Run ls_weights inside each bucket, then give every active bucket an equal 1/B share of each leg."""
    legs = [ls_weights(gb, q) for _, gb in g.groupby(g["ticker"].map(BUCKET)) if len(gb) >= 2]
    if not legs:
        return pd.Series(dtype=float)
    return pd.concat(legs) / len(legs)


def long_hedged_weights(g: pd.DataFrame, q: float) -> pd.Series:
    w = ls_weights(g, q)
    longs = w[w > 0]
    b_mkt = g.set_index("ticker").loc[longs.index, "beta_mkt"]
    return pd.concat([longs, pd.Series({MKT: -(longs * b_mkt).sum()})])


def equal_weights(g: pd.DataFrame) -> pd.Series:
    return pd.Series(1.0 / len(g), index=g["ticker"].values)


PORTFOLIOS = ["LS", "LS_BN", "LongHedged", "EW", "SPY"]


def build_targets(sig: Signals, q: float, min_names: int = 6) -> dict[str, dict]:
    targets = {p: {} for p in PORTFOLIOS}
    for s, g in sig.betas.groupby("signal_date"):
        if s not in sig.trade_of or len(g) < min_names:
            continue
        d = sig.trade_of[s]
        targets["LS"][d] = ls_weights(g, q)
        targets["LS_BN"][d] = ls_bucket_neutral_weights(g, q)
        targets["LongHedged"][d] = long_hedged_weights(g, q)
        targets["EW"][d] = equal_weights(g)
    if targets["LS"]:
        targets["SPY"][min(targets["LS"])] = pd.Series({MKT: 1.0})
    return targets


def simulate(targets: dict, rets: pd.DataFrame, start: pd.Timestamp, cost_bps: float,
             borrow_bps: float = 0.0) -> tuple[pd.Series, pd.Series]:
    """Daily NAV simulation. Positions are set at the close of each trade date and earn returns from
    the next day on; between rebalances weights drift with prices. Costs = cost_bps x $ traded."""
    cols = sorted(set().union(*[w.index for w in targets.values()]))
    R = rets.loc[start:, cols].fillna(0.0).to_numpy()
    dates = rets.loc[start:].index
    tgt = {dates.get_loc(d): w.reindex(cols).fillna(0.0).to_numpy() for d, w in targets.items() if d >= start}
    c, b = cost_bps / 1e4, borrow_bps / 1e4 / TRADING_DAYS
    h = np.zeros(len(cols))
    nav = 1.0
    out, turnover = np.zeros(len(dates)), np.zeros(len(dates))
    for k in range(len(dates)):
        pnl = h @ R[k] - b * np.clip(-h, 0, None).sum()
        h = h * (1 + R[k])
        new = nav + pnl
        if k in tgt:
            target = tgt[k] * new
            traded = np.abs(target - h).sum()
            turnover[k] = traded / new
            new -= c * traded
            h = target
        out[k] = new / nav - 1
        nav = new
    return pd.Series(out, index=dates), pd.Series(turnover, index=dates)


def backtest(sig: Signals, cfg: Config) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    targets = build_targets(sig, cfg.quantile)
    start = min(targets["LS"])
    rets, turns = {}, {}
    for p, t in targets.items():
        cost = 0.0 if p == "SPY" else cfg.cost_bps
        borrow = 0.0 if p == "SPY" else cfg.borrow_bps
        rets[p], turns[p] = simulate(t, sig.rets, start, cost, borrow)
    return pd.DataFrame(rets), pd.DataFrame(turns), targets


# ----------------------------------------------------------------------------- evaluation
def _within_bucket(x: pd.Series) -> pd.Series:
    b = x.index.map(BUCKET)
    r = x.groupby(b).rank(pct=True)
    return r - r.groupby(b).transform("mean")


def monthly_ic(sig: Signals) -> pd.DataFrame:
    """Spearman IC between beta_glp at signal t and the return actually earned over the holding period
    (trade close t+1 -> next trade close). IC_BN uses within-bucket demeaned ranks."""
    sigs = sorted(sig.trade_of)
    rows = []
    for s, s_next in zip(sigs[:-1], sigs[1:]):
        g = sig.betas[sig.betas.signal_date == s].set_index("ticker")["beta_glp"]
        if len(g) < 6:
            continue
        d0, d1 = sig.trade_of[s], sig.trade_of[s_next]
        fwd = sig.prices.loc[d1, g.index] / sig.prices.loc[d0, g.index] - 1
        ok = fwd.notna()
        g, fwd = g[ok], fwd[ok]
        rows.append((s, d0, d1, g.rank().corr(fwd.rank()),
                     _within_bucket(g).corr(_within_bucket(fwd)), len(g)))
    return pd.DataFrame(rows, columns=["signal_date", "hold_from", "hold_to", "IC", "IC_BN", "n_names"])


def ic_stats(ic: pd.Series) -> dict:
    ic = ic.dropna()
    n = len(ic)
    sd = ic.std(ddof=1)
    return {"ic_mean": ic.mean(), "ic_t": ic.mean() / (sd / np.sqrt(n)) if n > 1 and sd > 0 else np.nan,
            "ic_pct_pos": (ic > 0).mean(), "n_months": n}


def perf_stats(r: pd.Series) -> dict:
    r = r.dropna()
    n = len(r)
    if n < 2:
        return {}
    wealth = (1 + r).cumprod()
    peak = np.maximum(wealth.cummax(), 1.0)
    sd = r.std(ddof=1)
    return {"CAGR": wealth.iloc[-1] ** (TRADING_DAYS / n) - 1,
            "Vol": sd * np.sqrt(TRADING_DAYS),
            "Sharpe": r.mean() / sd * np.sqrt(TRADING_DAYS) if sd > 0 else np.nan,
            "MaxDD": (wealth / peak - 1).min(),
            "HitRate": (r > 0).mean(),
            "Years": n / TRADING_DAYS}


def periods(index: pd.DatetimeIndex, cfg: Config) -> dict:
    oos = pd.Timestamp(cfg.oos_start)
    return {"Full": index, "IS": index[index < oos], "OOS": index[index >= oos]}


def performance_table(rets: pd.DataFrame, turns: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    rows = []
    for name, idx in periods(rets.index, cfg).items():
        for p in rets:
            st = perf_stats(rets.loc[idx, p])
            t = turns.loc[idx, p]
            t = t[t > 0].iloc[1:] if name == "Full" else t[t > 0]  # skip the initial build
            st["TurnoverPerRebal"] = t.mean() if len(t) else np.nan
            rows.append({"Portfolio": p, "Period": name, "Start": idx.min().date(), "End": idx.max().date(), **st})
    return pd.DataFrame(rows)


def factor_exposure(r: pd.Series, sig: Signals) -> dict:
    """Same-day regression of a strategy's returns on SPY and GLP: how much of the P&L is the factor."""
    df = pd.DataFrame({"y": r, MKT: sig.rets[MKT].reindex(r.index), "GLP": sig.glp.reindex(r.index)}).dropna()
    df = df[df.y != 0]
    X = np.column_stack([np.ones(len(df)), df[MKT], df["GLP"]])
    coef, *_ = np.linalg.lstsq(X, df.y.to_numpy(), rcond=None)
    resid = df.y.to_numpy() - X @ coef
    return {"alpha_ann": coef[0] * TRADING_DAYS, "beta_spy": coef[1], "beta_glp": coef[2],
            "r2": 1 - resid.var() / df.y.var(ddof=0)}


def holdings_table(sig: Signals, q: float, min_names: int = 6) -> pd.DataFrame:
    """Target weights per signal date (same rules as build_targets). trade_date is NaT for a signal
    whose next close is not in the data yet, i.e. the book to trade at the next close."""
    frames = []
    for s, g in sig.betas.groupby("signal_date"):
        if len(g) < min_names:
            continue
        lh = long_hedged_weights(g, q)
        h = g.assign(trade_date=sig.trade_of.get(s, pd.NaT), bucket=g.ticker.map(BUCKET),
                     rank_pct=g.beta_glp.rank(pct=True))
        h["w_LS"] = h.ticker.map(ls_weights(g, q)).fillna(0.0)
        h["w_LS_BN"] = h.ticker.map(ls_bucket_neutral_weights(g, q)).fillna(0.0)
        h["w_LongHedged"] = h.ticker.map(lh).fillna(0.0)
        hedge = pd.DataFrame([{"signal_date": s, "trade_date": h.trade_date.iloc[0], "ticker": MKT,
                               "bucket": "Hedge", "w_LS": 0.0, "w_LS_BN": 0.0, "w_LongHedged": lh[MKT]}])
        frames += [h, hedge]
    cols = ["signal_date", "trade_date", "ticker", "bucket", "beta_glp", "beta_mkt", "alpha", "n_obs",
            "rank_pct", "w_LS", "w_LS_BN", "w_LongHedged"]
    return pd.concat(frames, ignore_index=True)[cols].sort_values(["signal_date", "ticker"])


# ----------------------------------------------------------------------------- tearsheet
COLORS = {"LS": "#2a78d6", "LS_BN": "#eb6834", "LongHedged": "#1baf7a", "EW": "#898781", "SPY": "#52514e"}
INK, INK2, GRID, AXIS = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"


def tearsheet(rets: pd.DataFrame, perf: pd.DataFrame, ic: pd.DataFrame, cfg: Config, path: str,
              source: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    plt.rcParams.update({"font.family": "sans-serif", "font.size": 9, "axes.edgecolor": AXIS,
                         "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "grid.linestyle": "-"})
    fig = plt.figure(figsize=(13, 11.5), facecolor="#fcfcfb")
    gs = GridSpec(3, 2, height_ratios=[2.3, 1.15, 1.05], hspace=0.42, wspace=0.16,
                  left=0.06, right=0.9, top=0.895, bottom=0.03)
    oos = pd.Timestamp(cfg.oos_start)
    q = str(Fraction(cfg.quantile).limit_denominator(10))
    fig.suptitle("GLP-1 second-order beneficiaries: long/short on GLP-1 factor beta",
                 x=0.06, ha="left", fontsize=14, color=INK, fontweight="bold")
    fig.text(0.06, 0.935, f"{source} | factor {cfg.factor.upper()} residual | beta window {cfg.beta_window}d | "
             f"legs {q} | costs {cfg.cost_bps:g} bps | monthly, trade next close | OOS from {oos.date()}",
             color=INK2, fontsize=9.5)

    # A. growth of $1
    ax = fig.add_subplot(gs[0, :])
    wealth = (1 + rets).cumprod()
    for p in PORTFOLIOS:
        lw = 2.0 if p in ("LS", "LS_BN", "LongHedged") else 1.3
        ax.plot(wealth.index, wealth[p], color=COLORS[p], lw=lw, label=p)
        ax.annotate(f"{p}  {wealth[p].iloc[-1]:.2f}", (wealth.index[-1], wealth[p].iloc[-1]),
                    xytext=(6, 0), textcoords="offset points", va="center", fontsize=8.5, color=INK)
    ax.set_yscale("log")
    ax.axvspan(oos, wealth.index[-1], color="#f0efec", zorder=0, lw=0)
    ax.text(matplotlib.dates.date2num(oos), 1.0, "  out-of-sample", transform=ax.get_xaxis_transform(), va="top", color=INK2, fontsize=9)
    ax.axhline(1.0, color=AXIS, lw=0.8)
    ax.set_title("Growth of $1 (log scale)", loc="left", color=INK, fontsize=11)
    ax.legend(loc="upper left", frameon=False, ncol=5)
    ax.yaxis.set_major_locator(matplotlib.ticker.FixedLocator([0.125, 0.25, 0.5, 1, 2, 4, 8]))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())

    # B. drawdowns
    ax = fig.add_subplot(gs[1, 0])
    for p in ("LS", "LS_BN", "LongHedged"):
        dd = wealth[p] / np.maximum(wealth[p].cummax(), 1.0) - 1
        ax.plot(dd.index, dd * 100, color=COLORS[p], lw=1.5, label=p)
    ax.axvspan(oos, wealth.index[-1], color="#f0efec", zorder=0, lw=0)
    ax.set_title("Drawdown (%)", loc="left", color=INK, fontsize=11)
    ax.legend(loc="upper right", frameon=False, ncol=3)

    # C. monthly IC
    ax = fig.add_subplot(gs[1, 1])
    st = ic_stats(ic.IC)
    ax.bar(ic.hold_from, ic.IC, width=20, color=COLORS["LS"], alpha=0.45, lw=0, label="monthly IC")
    ax.plot(ic.hold_from, ic.IC.rolling(12, min_periods=6).mean(), color=COLORS["LS"], lw=2, label="12-month mean")
    ax.axhline(0, color=AXIS, lw=0.8)
    ax.axvspan(oos, ic.hold_from.max(), color="#f0efec", zorder=0, lw=0)
    ax.set_title(f"Rank IC of beta_glp vs next-month return: mean {st['ic_mean']:+.3f}, t = {st['ic_t']:.2f}, "
                 f"{st['ic_pct_pos']:.0%} > 0", loc="left", color=INK, fontsize=10)
    ax.set_ylim(-1, 1)
    ax.legend(loc="upper left", frameon=False, ncol=2)

    # D. stats table
    ax = fig.add_subplot(gs[2, :])
    ax.axis("off")
    pv = perf.pivot(index="Portfolio", columns="Period").reindex(PORTFOLIOS)
    cols = [("Sharpe", "IS"), ("Sharpe", "OOS"), ("Sharpe", "Full"), ("CAGR", "IS"), ("CAGR", "OOS"),
            ("Vol", "Full"), ("MaxDD", "Full"), ("HitRate", "Full"), ("TurnoverPerRebal", "Full")]
    fmt = {"Sharpe": "{:.2f}", "CAGR": "{:+.1%}", "Vol": "{:.1%}", "MaxDD": "{:.1%}", "HitRate": "{:.1%}",
           "TurnoverPerRebal": "{:.0%}"}
    cell = [[fmt[m].format(pv.loc[p, (m, per)]) if pd.notna(pv.loc[p, (m, per)]) else "-" for m, per in cols]
            for p in PORTFOLIOS]
    labels = [f"{m.replace('TurnoverPerRebal', 'Turnover/rebal')}\n{per}" for m, per in cols]
    tb = ax.table(cellText=cell, rowLabels=PORTFOLIOS, colLabels=labels, loc="upper center", cellLoc="center",
                  bbox=[0.06, 0.0, 0.94, 0.95])
    tb.auto_set_font_size(False)
    tb.set_fontsize(9)
    for (r, c), cl in tb.get_celld().items():
        cl.set_edgecolor(GRID)
        cl.set_facecolor("#fcfcfb" if r else "#f0efec")
        cl.get_text().set_color(INK)
    ax.set_title("Performance (Sharpe uses rf = 0; IS < OOS start <= OOS)", loc="left", color=INK, fontsize=11)
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


# ----------------------------------------------------------------------------- robustness / placebo
def robustness_grid(prices: pd.DataFrame, base: Config) -> pd.DataFrame:
    rows = []
    for factor in ["both", "lly", "nvo"]:
        for window in [126, 252, 504]:
            cfg_sig = replace(base, factor=factor, beta_window=window)
            sig = compute_signals(prices, cfg_sig)
            ic = monthly_ic(sig)
            ic_all = ic_stats(ic.IC)
            ic_oos = ic_stats(ic.loc[ic.hold_from >= pd.Timestamp(base.oos_start), "IC"])
            for q in [1 / 3, 1 / 2]:
                for cost in [10.0, 25.0]:
                    cfg = replace(cfg_sig, quantile=q, cost_bps=cost)
                    rets, turns, _ = backtest(sig, cfg)
                    perf = performance_table(rets, turns, cfg).set_index(["Portfolio", "Period"])
                    rows.append({"factor": factor, "beta_window": window,
                                 "quantile": str(Fraction(q).limit_denominator(10)), "cost_bps": cost,
                                 "sharpe_oos_LS": perf.loc[("LS", "OOS"), "Sharpe"],
                                 "sharpe_is_LS": perf.loc[("LS", "IS"), "Sharpe"],
                                 "sharpe_oos_LS_BN": perf.loc[("LS_BN", "OOS"), "Sharpe"],
                                 "sharpe_is_LS_BN": perf.loc[("LS_BN", "IS"), "Sharpe"],
                                 "sharpe_full_LS": perf.loc[("LS", "Full"), "Sharpe"],
                                 "sharpe_full_LS_BN": perf.loc[("LS_BN", "Full"), "Sharpe"],
                                 "sharpe_oos_LongHedged": perf.loc[("LongHedged", "OOS"), "Sharpe"],
                                 "ic_mean": ic_all["ic_mean"], "ic_t": ic_all["ic_t"],
                                 "ic_pct_pos": ic_all["ic_pct_pos"], "ic_mean_oos": ic_oos["ic_mean"],
                                 "ic_t_oos": ic_oos["ic_t"], "n_months": ic_all["n_months"],
                                 "bt_start": rets.index.min().date()})
    return pd.DataFrame(rows)


def placebo(sig: Signals, cfg: Config, n_sims: int, seed: int = 0) -> pd.DataFrame:
    """Null distribution: same dates, same eligible names, same leg sizes and costs, but beta_glp is
    randomly shuffled across names each month. Answers: does ranking on beta_glp beat random ranking?
    The same shuffle feeds LS and LS_BN (for LS_BN it amounts to random ranks within each bucket)."""
    rng = np.random.default_rng(seed)
    groups = [(sig.trade_of[s], g) for s, g in sig.betas.groupby("signal_date") if s in sig.trade_of and len(g) >= 6]
    start = min(d for d, _ in groups)
    oos = pd.Timestamp(cfg.oos_start)
    rows = []
    for _ in range(n_sims):
        shuffled = [(d, g.assign(beta_glp=rng.permutation(g.beta_glp.to_numpy()))) for d, g in groups]
        row = {}
        for p, fn in [("LS", ls_weights), ("LS_BN", ls_bucket_neutral_weights)]:
            r, _ = simulate({d: fn(g, cfg.quantile) for d, g in shuffled}, sig.rets, start, cfg.cost_bps,
                            cfg.borrow_bps)
            row.update({f"{p}_full": perf_stats(r)["Sharpe"], f"{p}_is": perf_stats(r[r.index < oos])["Sharpe"],
                        f"{p}_oos": perf_stats(r[r.index >= oos])["Sharpe"]})
        rows.append(row)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- main
def _fraction(x: str) -> float:
    return float(Fraction(x))


def parse_args(argv=None) -> argparse.Namespace:
    d = Config()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--synthetic", action="store_true", help="use simulated prices (offline test)")
    ap.add_argument("--beta-window", type=int, default=d.beta_window)
    ap.add_argument("--factor-window", type=int, default=d.factor_window)
    ap.add_argument("--quantile", type=_fraction, default=d.quantile, help="leg size, e.g. 1/3 or 0.5")
    ap.add_argument("--cost-bps", type=float, default=d.cost_bps)
    ap.add_argument("--borrow-bps", type=float, default=d.borrow_bps, help="annual short borrow fee (default 0)")
    ap.add_argument("--factor", choices=list(FACTOR_LEGS), default=d.factor)
    ap.add_argument("--min-obs-frac", type=float, default=d.min_obs_frac)
    ap.add_argument("--data-start", default=d.data_start)
    ap.add_argument("--bt-start", default=d.bt_start)
    ap.add_argument("--oos-start", default=d.oos_start)
    ap.add_argument("--end", default=None)
    ap.add_argument("--exclude", nargs="*", default=[], metavar="TICKER",
                    help="drop names from the universe (e.g. leave-one-out checks)")
    ap.add_argument("--grid", action="store_true", help="also write robustness_grid.csv")
    ap.add_argument("--placebo", type=int, default=0, metavar="N", help="random-ranking simulations")
    ap.add_argument("--refresh", action="store_true", help="ignore the price cache")
    ap.add_argument("--outdir", default=os.path.dirname(os.path.abspath(__file__)))
    return ap.parse_args(argv)


def main(argv=None) -> int:
    a = parse_args(argv)
    cfg = Config(beta_window=a.beta_window, factor_window=a.factor_window, quantile=a.quantile,
                 cost_bps=a.cost_bps, borrow_bps=a.borrow_bps, factor=a.factor, min_obs_frac=a.min_obs_frac,
                 data_start=a.data_start, bt_start=a.bt_start, oos_start=a.oos_start, end=a.end)
    os.makedirs(a.outdir, exist_ok=True)
    out = lambda name: os.path.join(a.outdir, name)  # noqa: E731
    pd.set_option("display.width", 160)
    warnings.filterwarnings("ignore", category=FutureWarning)

    if a.synthetic:
        prices, source = synthetic_prices(cfg), "SYNTHETIC data"
    else:
        prices, source = download_prices(cfg, out(".cache"), a.refresh), "yfinance adjusted closes"
    prices = clean_prices(prices)
    if a.exclude:
        prices = prices.drop(columns=[t for t in a.exclude if t in TICKERS and t in prices])
        print(f"[data] excluded: {', '.join(a.exclude)}")
    print(f"[data] {source}: {prices.index.min().date()} -> {prices.index.max().date()}, {len(prices)} days")

    sig = compute_signals(prices, cfg)
    entry = sig.betas.groupby("ticker").signal_date.min().reindex(TICKERS)
    late = entry[entry > entry.min()]
    if len(late):
        print("[data] first signal per late-entry name (needs "
              f"{int(np.ceil(cfg.beta_window * cfg.min_obs_frac))} obs): "
              + ", ".join(f"{t} {d.date()}" if pd.notna(d) else f"{t} never" for t, d in late.items()))

    rets, turns, targets = backtest(sig, cfg)
    perf = performance_table(rets, turns, cfg)
    ic = monthly_ic(sig)
    hold = holdings_table(sig, cfg.quantile)

    perf.to_csv(out("glp1_performance.csv"), index=False, float_format="%.6f")
    hold.to_csv(out("glp1_holdings.csv"), index=False, float_format="%.6f")
    rets.to_csv(out("glp1_daily_returns.csv"), float_format="%.8f")
    ic.to_csv(out("glp1_ic.csv"), index=False, float_format="%.6f")
    tearsheet(rets, perf, ic, cfg, out("glp1_tearsheet.png"), source)

    # ---- console summary
    pv = perf.pivot(index="Portfolio", columns="Period", values="Sharpe").reindex(PORTFOLIOS)[["Full", "IS", "OOS"]]
    print(f"\nBacktest {rets.index.min().date()} -> {rets.index.max().date()} | IS < {cfg.oos_start} <= OOS")
    print("Sharpe (rf=0):\n" + pv.round(2).to_string())
    print("\n" + perf.set_index(["Portfolio", "Period"])[["CAGR", "Vol", "Sharpe", "MaxDD", "HitRate"]]
          .round(3).to_string())
    oos = pd.Timestamp(cfg.oos_start)
    for label, sub in [("Full", ic), ("IS", ic[ic.hold_from < oos]), ("OOS", ic[ic.hold_from >= oos])]:
        s, sb = ic_stats(sub.IC), ic_stats(sub.IC_BN)
        print(f"IC {label:4s}: mean {s['ic_mean']:+.3f}  t {s['ic_t']:+.2f}  >0 {s['ic_pct_pos']:.0%}  "
              f"n {s['n_months']}   | within-bucket IC {sb['ic_mean']:+.3f} (t {sb['ic_t']:+.2f})")
    for p in ("LS", "LS_BN"):
        for label, idx in periods(rets.index, cfg).items():
            fe = factor_exposure(rets.loc[idx, p], sig)
            print(f"{p:5s} {label:4s} on [SPY, GLP]: beta_glp {fe['beta_glp']:+.2f}  beta_spy {fe['beta_spy']:+.2f}  "
                  f"R2 {fe['r2']:.2f}  alpha {fe['alpha_ann']:+.1%}/yr")
    g = sig.glp[rets.index]
    print(f"GLP factor cum. return: IS {(1 + g[g.index < oos]).prod() - 1:+.1%}, "
          f"OOS {(1 + g[g.index >= oos]).prod() - 1:+.1%}")

    last = hold.signal_date.max()
    cur = hold[hold.signal_date == last]
    when = cur.trade_date.iloc[0]
    print(f"\nLatest holdings: signal {last.date()}, "
          + (f"traded at close {when.date()}" if pd.notna(when) else "to trade at the next close"))
    for side, mask in [("LONG ", cur.w_LS > 0), ("SHORT", cur.w_LS < 0)]:
        print(f"  LS {side}: " + ", ".join(f"{r.ticker} ({r.beta_glp:+.2f})"
                                           for r in cur[mask].sort_values("beta_glp", ascending=False).itertuples()))
    for side, mask in [("LONG ", cur.w_LS_BN > 0), ("SHORT", cur.w_LS_BN < 0)]:
        print(f"  LS_BN {side}: " + ", ".join(f"{r.ticker}" for r in cur[mask].itertuples()))
    hedge = cur[cur.ticker == MKT].w_LongHedged
    if len(hedge):
        print(f"  LongHedged SPY hedge: {hedge.iloc[0]:+.2f}")

    if a.grid:
        grid = robustness_grid(prices, cfg)
        grid.to_csv(out("robustness_grid.csv"), index=False, float_format="%.4f")
        print("\nRobustness grid -> robustness_grid.csv")
        print(grid[["factor", "beta_window", "quantile", "cost_bps", "sharpe_is_LS", "sharpe_oos_LS",
                    "sharpe_is_LS_BN", "sharpe_oos_LS_BN", "ic_mean", "ic_t", "ic_mean_oos"]]
              .round(3).to_string(index=False))

    if a.placebo:
        null = placebo(sig, cfg, a.placebo)
        null.to_csv(out("glp1_placebo.csv"), index=False, float_format="%.4f")
        sharpe = perf.set_index(["Portfolio", "Period"])["Sharpe"]
        print(f"\nPlacebo ({a.placebo} random rankings) -> glp1_placebo.csv")
        for p in ("LS", "LS_BN"):
            for per in ("Full", "IS", "OOS"):
                col, act = f"{p}_{per.lower()}", sharpe[(p, per)]
                print(f"  {p:5s} {per:4s}: actual Sharpe {act:+.2f}; null median {null[col].median():+.2f}, "
                      f"95th pct {null[col].quantile(0.95):+.2f}; random >= actual {(null[col] >= act).mean():.0%}")
    print(f"\nOutputs written to {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
