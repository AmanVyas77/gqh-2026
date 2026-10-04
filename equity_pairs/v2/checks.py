"""Hand-calculated verification of the V2 engine (synthetic prices) + data-access checks.

    python v2/checks.py
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "v2")]
from engine import load_panel, metrics, select, simulate, universe_inputs  # noqa: E402
from data_v2 import formation_ends  # noqa: E402

TOL = 1e-12
D = pd.to_datetime(["2020-01-03", "2020-01-06", "2020-01-07", "2020-01-08", "2020-01-09", "2020-01-10",
                    "2020-01-13", "2020-01-14", "2020-01-15", "2020-01-16", "2020-01-17"])
A = [100, 100, 125, 125, 120, 110, 103, 103, 150, 130, 130]
B = [100, 100, 100, 100, 101, 101, 101, 101, 100, 100, 100]
adj = pd.DataFrame({"A": A, "B": B}, index=D, dtype=float)
month = [{"prev_close": D[0], "sessions": D[1:], "label": "2020-01",
          "pairs": [{"A": "A", "B": "B", "mu": 0.0, "sd": 0.1}]}]
d, ep, nt = simulate(adj, month, trade_bps=10, borrow_annual=0.03)
g = d["gross_exp"]
# 1. signal at close 01-07 (z=2.23) executes at close 01-08; nothing before
assert g.loc["2020-01-07"] == 0 and abs(g.loc["2020-01-08"] - 0.10) < 1e-12, "signal-to-execution delay / gross"
assert d.loc["2020-01-08", "gross_pnl"] == 0, "new weights must not earn the execution day's return"
# 2. short A / long B: A -4%, B +1% on 01-09 -> +0.05*0.04 + 0.05*0.01 = +0.0025 of NAV
assert abs(d.loc["2020-01-09", "gross_pnl"] - 0.0025) < 1e-12, "long/short return signs"
# 3. costs: entry trades 0.05 N per leg, N = post-cost NAV: N = 1 - 10bps * 0.10 N
n8 = d.loc["2020-01-08", "nav"]
assert abs(n8 - 1 / (1 + 1e-4)) < 1e-15 and abs(d.loc["2020-01-08", "cost"] - 1e-3 * 0.10 * n8) < 1e-15
borrow9 = 0.05 * n8 * 0.03 * 1 / 365
pre9 = n8 * (1 + 0.0025) - borrow9
N = pre9
for _ in range(50):   # hand fixed point: N = pre9 - 10bps * (|-0.05N + 0.048 n8| + |0.05N - 0.0505 n8|)
    N = pre9 - 1e-3 * (abs(-0.05 * N + 0.05 * n8 * 0.96) + abs(0.05 * N - 0.05 * n8 * 1.01))
assert abs(d.loc["2020-01-09", "nav"] - N) < 1e-14, "rebalancing cost on both legs"
assert abs(d.loc["2020-01-09", "gross_exp"] - 0.10) < 1e-12, "gross exposure exactly 10% of NAV"
# 4. borrow: 1 calendar day on 01-09; 3 calendar days over the weekend on 01-13
assert abs(d.loc["2020-01-09", "borrow"] * n8 - borrow9) < 1e-15
n10 = d.loc["2020-01-10", "nav"]
assert abs(d.loc["2020-01-13", "borrow"] - 0.05 * 0.03 * 3 / 365) < 1e-12, "weekend borrow accrual"
# 5. exit: z=0.196 at 01-13 close -> flat after 01-14 close; |z|>=4 on 01-15 -> no entry;
#    entry signal 01-16 would execute on the last session -> overridden by scheduled liquidation
assert g.loc["2020-01-13"] > 0 and g.loc["2020-01-14"] == 0 and (g.loc["2020-01-15":] == 0).all()
assert nt == 1 and abs(d["nav"].iloc[-1] - (1 + d["ret"]).prod()) < 1e-12, "NAV compounding"
# 6. NAV accounting identity: NAV change = gross pnl - borrow - cost (all relative to prior NAV)
assert np.allclose(d["ret"], d["gross_pnl"] - d["borrow"] - d["cost"], atol=1e-15)

# 7. stop with no re-entry, and the 20-session time exit
D2 = pd.bdate_range("2020-02-03", periods=30)
s2 = np.r_[0, 0.25, 0.25, 0.45, 0.25, 0.25, np.full(24, 0.25)]          # z: 0, 2.5, 2.5, 4.5, 2.5 ...
adj2 = pd.DataFrame({"A": 100 * np.exp(s2), "B": 100.0}, index=D2)
m2 = [{"prev_close": D2[0], "sessions": D2[1:], "label": "2020-02", "pairs": [{"A": "A", "B": "B", "mu": 0, "sd": 0.1}]}]
d2, _, nt2 = simulate(adj2, m2, 10, 0.03)
assert nt2 == 1 and d2["gross_exp"].iloc[1] > 0 and d2["gross_exp"].iloc[3] == 0 and (d2["gross_exp"].iloc[3:] == 0).all(), "stop, no re-entry"
s3 = np.r_[0, np.full(29, 0.25)]                                         # z stays 2.5: time exit
adj3 = pd.DataFrame({"A": 100 * np.exp(s3), "B": 100.0}, index=D2)
d3, _, _ = simulate(adj3, m2, 10, 0.03)
held = (d3["gross_exp"] > 0).to_numpy()
# signal at session 0 -> held at closes 1..20 (earning returns on sessions 2..21) -> time exit fills at close 21
assert not held[0] and held[1:21].all() and not held[21], "20 sessions of exposure, then time exit"

# 8. drawdown arithmetic
dd_d = pd.DataFrame({"ret": [0.1, -0.5, 0.2], "nav": [1.1, 0.55, 0.66], "gross_exp": 0, "active_pairs": 0,
                     "net_exp": 0, "turnover": 0, "cost": 0, "borrow": 0}, index=pd.bdate_range("2020-01-01", periods=3))
mt = metrics(dd_d, pd.DataFrame({"month": ["m"], "pair": ["p"], "pnl": [0.1], "entries": [1]}), 1)
assert abs(mt["max_drawdown"] - (-0.5)) < 1e-12
print("synthetic engine checks: all passed")

# 9. real data: nothing on/after the holdout start; eligibility uses past data only
sess, adjR, close, vol, meta = load_panel()
assert adjR.index.max() == pd.Timestamp("2024-10-02") and adjR.dropna(how="all").index.max() <= pd.Timestamp("2024-10-02")
ends = formation_ends()
info = universe_inputs(ends, sess, adjR, meta)
for e in ("2016-06-30", "2019-06-28", "2024-08-30"):
    full, _ = select(e, sess, adjR, close, vol, info[e])
    def cut(X):                                                          # erase everything after formation end
        X = X.copy()
        X.loc[X.index > pd.Timestamp(e)] = np.nan
        return X
    past, _ = select(e, sess, cut(adjR), cut(close), cut(vol), info[e])
    assert full == past, f"selection at {e} depends on post-formation data"
print("real-data checks: max date 2024-10-02; selection unchanged when post-formation data are erased")
