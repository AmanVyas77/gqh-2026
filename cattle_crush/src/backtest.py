"""Daily backtest driven by month-end signals (HYPOTHESIS.md Section 6, Deviation Log).

Mechanics
- Signals are formed at month-end t on t's settlements. Targets are contract counts fixed at t
  (w x capital / (price_t x size)) and held until the next rebalance; fractional contracts.
- Execution is at the settlement of the first trading day after t on which every contract
  being traded has a settlement and none is limit-locked (official session high == low).
  A roll closes the old contract and opens the new one at the same execution settlement;
  costs are charged on both legs.
- P&L accrues within each contract on its own settlement dates; a date missing from the feed
  is skipped and the next settlement carries the change (no forward-filling).
- GF (cash-settled) held past its last trading day is closed at its cash-final settlement,
  fee only; the replacement opens at the next scheduled execution (Variant B).
- Returns are P&L / fixed capital (excess returns, no interest on collateral).
- Drawdown overlay (optional): at each signal date, if drawdown of this run's own 1x-cost net
  equity exceeds 15% the targets are halved; full size returns once drawdown is within 7.5%.
- In-sample only unless oos=True: no date on or after oos_start is simulated.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src import analysis, contracts, costs, signals, trial_log
from src.config import load_config, oos_start

OVERLAY_TRIGGER, OVERLAY_RESTORE, OVERLAY_SCALE = 0.15, 0.075, 0.5


@dataclass
class Rebalance:
    signal_date: pd.Timestamp
    targets: dict                     # root -> (contract label, signed contracts at full size)
    weight: float = np.nan            # signed notional / capital at full size (reporting)


@dataclass
class Result:
    daily: pd.DataFrame               # date, pnl, cost, gross, net, net2x, gross_notional
    trades: pd.DataFrame
    rebalances: pd.DataFrame
    events: dict = field(default_factory=dict)


class Market:
    """Settlement prices, lock flags and contract metadata for the roots a strategy trades."""

    def __init__(self, roots: tuple[str, ...], oos: bool = False):
        self.roots = roots
        self.size = {r: load_config()["specs"][r]["size"] for r in roots}
        self.px, self.cash_final, self.locked = {}, {}, set()
        tbl = contracts.contract_table(oos)
        self.root_of = dict(zip(tbl["contract"], tbl["root"]))
        self.ltd = dict(zip(tbl["contract"], tbl["last_trade_date"]))
        for r in roots:
            s = contracts.settlements(r, oos)
            self.px[r] = s[~s["cash_final"]].pivot(index="date", columns="contract", values="price")
            cf = s[s["cash_final"]]
            self.cash_final.update({(c, d): p for c, d, p in zip(cf["contract"], cf["date"], cf["price"])})
            hl = contracts.session_high_low(r, oos)
            hl = hl[hl["high"] == hl["low"]]
            self.locked.update(zip(hl["date"], hl["contract"]))
        self.dates = sorted(set().union(*(set(p.index) for p in self.px.values())))

    def price(self, contract: str, date) -> float:
        p = self.px[self.root_of[contract]]
        if contract in p.columns and date in p.index:
            v = p.at[date, contract]
            return float(v) if pd.notna(v) else np.nan
        return np.nan

    def returns(self, contract: str, end, n: int) -> pd.Series:
        """Last n daily settlement returns of `contract` up to and including `end`."""
        s = self.px[self.root_of[contract]][contract].loc[:end].dropna()
        return s.pct_change().dropna().iloc[-n:]


def run(market: Market, rebalances: list[Rebalance], capital: float, overlay: bool = False,
        oos: bool = False) -> Result:
    cfg = load_config()
    end = None if oos else oos_start()
    dates = [d for d in market.dates if (end is None or d < end) and d >= rebalances[0].signal_date]
    signals = {rb.signal_date: rb for rb in rebalances}
    missing = [t for t in signals if t not in set(dates) and (end is None or t < end)]
    if missing:
        raise RuntimeError(f"signal dates without a settlement for the traded roots: {missing[:5]}")

    holdings: dict[str, float] = {}
    last_px: dict[str, float] = {}
    pending: Rebalance | None = None
    pending_scale = 1.0
    scale, equity, peak = 1.0, 1.0, 1.0
    rows, trades, rb_rows = [], [], []
    events = {"deferred_days": 0, "deferred_trades": 0, "superseded_orders": 0, "gf_cash_final_closes": 0}
    deferred_this_order = False

    for d in dates:
        pnl, cost = 0.0, 0.0
        # 1) P&L on positions held from the previous settlement of each contract.
        for c, q in list(holdings.items()):
            p = market.price(c, d)
            if not np.isnan(p):
                pnl += q * market.size[market.root_of[c]] * (p - last_px[c])
                last_px[c] = p
            elif (c, d) in market.cash_final:                     # GF expired while held
                p = market.cash_final[(c, d)]
                root = market.root_of[c]
                pnl += q * market.size[root] * (p - last_px[c])
                cost += costs.trade_cost(root, q, fee_only=True, cfg=cfg)
                trades.append({"date": d, "signal_date": None, "contract": c, "qty": -q, "price": p,
                               "cost": costs.trade_cost(root, q, fee_only=True, cfg=cfg), "reason": "cash_final"})
                events["gf_cash_final_closes"] += 1
                del holdings[c], last_px[c]
            elif market.root_of[c] not in contracts.CASH_SETTLED and d > market.ltd[c]:
                raise RuntimeError(f"held {c} past its last trade date")

        # 2) Execute a pending order if every traded contract settles today and none is locked.
        if pending is not None and d > pending.signal_date:
            orders = _orders(holdings, pending.targets, pending_scale, market)
            blocked = [c for c, dq in orders.items() if abs(dq) > 0 and
                       (np.isnan(market.price(c, d)) or (d, c) in market.locked)]
            if blocked:
                events["deferred_days"] += 1
                deferred_this_order = True
            else:
                for c, dq in orders.items():
                    if dq == 0:
                        continue
                    root, p = market.root_of[c], market.price(c, d)
                    tc = costs.trade_cost(root, dq, cfg=cfg)
                    cost += tc
                    trades.append({"date": d, "signal_date": pending.signal_date, "contract": c, "qty": dq,
                                   "price": p, "cost": tc, "notional": abs(dq) * p * market.size[root],
                                   "reason": "rebalance"})
                    holdings[c] = holdings.get(c, 0.0) + dq
                    last_px[c] = p
                    if abs(holdings[c]) < 1e-12:
                        del holdings[c], last_px[c]
                events["deferred_trades"] += int(deferred_this_order)
                deferred_this_order = False
                pending = None

        gross_notional = sum(abs(q) * market.price(c, d) * market.size[market.root_of[c]]
                             for c, q in holdings.items() if not np.isnan(market.price(c, d)))
        rows.append({"date": d, "pnl": pnl, "cost": cost, "gross_notional": gross_notional})
        equity += (pnl - cost) / capital
        peak = max(peak, equity)

        # 3) A signal today sets the next order (overlay state uses equity through today).
        if d in signals:
            rb = signals[d]
            if overlay:
                dd = 1 - equity / peak
                if scale == 1.0 and dd > OVERLAY_TRIGGER:
                    scale = OVERLAY_SCALE
                elif scale < 1.0 and dd <= OVERLAY_RESTORE:
                    scale = 1.0
            if pending is not None:
                events["superseded_orders"] += 1
            pending, pending_scale = rb, scale
            rb_rows.append({"signal_date": d, "weight": rb.weight, "scale": scale,
                            "drawdown": 1 - equity / peak,
                            **{f"{r}_contract": t[0] for r, t in rb.targets.items()},
                            **{f"{r}_contracts": t[1] * scale for r, t in rb.targets.items()}})

    trades = pd.DataFrame(trades)
    daily = pd.DataFrame(rows)
    daily = daily[daily["date"] >= trades["date"].min()].reset_index(drop=True)   # from first execution
    daily["gross"] = daily["pnl"] / capital
    daily["net"] = (daily["pnl"] - daily["cost"]) / capital
    daily["net2x"] = (daily["pnl"] - 2 * daily["cost"]) / capital
    return Result(daily=daily, trades=trades, rebalances=pd.DataFrame(rb_rows), events=events)


def _orders(holdings: dict, targets: dict, scale: float, market: Market) -> dict:
    """Contract-level trades that move current holdings to the (scaled) targets, root by root."""
    orders = {}
    for root, (contract, qty) in targets.items():
        target = qty * scale
        for c, q in holdings.items():
            if market.root_of[c] == root and c != contract:
                orders[c] = orders.get(c, 0.0) - q                 # roll out of the old contract
        orders[contract] = orders.get(contract, 0.0) + target - holdings.get(contract, 0.0)
    for c, q in holdings.items():                                  # roots no longer targeted
        if market.root_of[c] not in targets:
            orders[c] = orders.get(c, 0.0) - q
    return orders


# --------------------------------------------------------------------------- Variant A

def variant_a_rebalances(sig: pd.DataFrame, zcol: str, market: Market, capital: float) -> list[Rebalance]:
    """w_t = clip(-z_t / 2, -1, 1) x (target_vol / sigma_hat_t), |w| <= max_gross_leverage, in the
    sale contract; sigma_hat = annualized sd of its last 60 daily settlement returns up to t."""
    s = load_config()["sizing"]
    out = []
    for t, row in sig.dropna(subset=[zcol]).iterrows():
        c, price = row["sale_contract"], row["sale_price"]
        r = market.returns(c, t, s["vol_lookback_days"])
        if len(r) < s["vol_lookback_days"]:
            raise RuntimeError(f"{c}: only {len(r)} returns before {t.date()} for the vol estimate")
        sigma = r.std(ddof=1) * np.sqrt(252)
        w = float(np.clip(-row[zcol] / s["z_clip_divisor"], -1, 1) * s["target_vol"] / sigma)
        w = float(np.clip(w, -s["max_gross_leverage"], s["max_gross_leverage"]))
        n = w * capital / (price * market.size["LE"])
        out.append(Rebalance(signal_date=t, targets={"LE": (c, n)}, weight=w))
    return out


def backtest_a(zcol: str = "z", overlay: bool = False, kind: str = "trial", spec: str = "primary",
               sig: pd.DataFrame | None = None, market: Market | None = None,
               **spec_params) -> tuple[Result, dict]:
    """Variant A for one spec. Every call is logged to the trial log (kind: trial, diagnostic,
    overlay). spec_params: sale_min_days, fcr, lookback, seasonal_years (signals.month_end_signals)."""
    capital = load_config()["capital_base"]
    sig = signals.month_end_signals(**spec_params) if sig is None else sig
    market = Market(("LE",)) if market is None else market
    res = run(market, variant_a_rebalances(sig, zcol, market, capital), capital, overlay=overlay)
    m = analysis.metrics(res.daily, "net", capital)
    m["turnover"] = analysis.turnover(res.trades, res.daily, capital)
    trial_log.log_trial("A", {"zcol": zcol, "overlay": overlay, **spec_params}, (m["start"], m["end"]),
                        m["sharpe"], m["n_days"], m["skew_daily"], m["kurt_daily"], kind=kind, spec=spec)
    return res, m
