"""V2 engine: monthly pair selection (simple / pca / sector) + daily total-return simulation.

    python v2/engine.py            # select, simulate all arms x {gross, base, stress}, write v2/results/

Conventions (v2/spec_v2.yaml): adjusted-close total returns; signals at close t execute at
close t+1; scheduled liquidation at each trading month's last close; +/-5% NAV legs
rebalanced daily; costs on every traded dollar; borrow per calendar day on prior-close short MV.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "pilot"), str(ROOT / "v2")]
from data import _norm, membership  # noqa: E402
from data_v2 import formation_ends  # noqa: E402
from guard import check_dates  # noqa: E402
from run import first_trade_date, issuer_key, knn, max_run, tokens  # noqa: E402
from split import xnys_sessions  # noqa: E402

SPEC = yaml.safe_load((ROOT / "v2" / "spec_v2.yaml").read_text())
RAW = ROOT / "data" / "raw"
OUT = ROOT / "v2" / "results"
ARMS = ("simple", "pca", "sector")


# ------------------------------------------------------------------ data
def load_panel():
    frames = pd.read_pickle(RAW / "prices_dev.pkl")
    for f in frames.values():
        check_dates(f.index)
    sess = xnys_sessions("2015-01-01", SPEC["holdout_locked_from"])      # 2015-01-02 .. 2024-10-02
    assert sess[-1] == pd.Timestamp(SPEC["development"]["end"])
    pick = lambda col: pd.DataFrame({t: f[col] for t, f in frames.items()}).reindex(sess)
    meta = pd.read_csv(RAW / "prices_dev_meta.csv").set_index("ticker")
    return sess, pick("Adj Close"), pick("Close"), pick("Volume"), meta


def universe_inputs(ends, sess, adj, meta):
    """Per formation: identity-checked PIT members with data, issuer and sector maps."""
    members, cur, ch = membership(ends)
    cur["tk"] = cur["Symbol"].map(_norm)
    cur_name, sector, cik = (dict(zip(cur["tk"], cur[c])) for c in ("Security", "GICS Sector", "CIK"))
    out = {}
    for e in ends:
        wstart = sess[sess <= pd.Timestamp(e)][-SPEC["formation"]["price_obs"]]
        rem_name = {}
        for _, r in ch[ch["date"] > pd.Timestamp(e)].sort_values("date").iterrows():
            if isinstance(r.rem_t, str) and _norm(r.rem_t) not in rem_name:
                rem_name[_norm(r.rem_t)] = r.rem_s
        cands, names, counts = [], {}, {"members": len(members[e]), "no_data": 0, "identity_unverified": 0}
        for t in sorted(members[e]):
            names[t] = rem_name.get(t, cur_name.get(t))
            if t not in adj.columns:
                counts["no_data"] += 1
                continue
            former = t in rem_name or t not in cur_name
            m = meta.loc[t]
            ftd = first_trade_date(m.get("firstTradeDate"))
            yname = tokens(m.get("longName")) | tokens(m.get("shortName"))
            if former and ((pd.notna(ftd) and ftd.normalize() > wstart) or not (yname & tokens(names[t]))):
                counts["identity_unverified"] += 1
                continue
            cands.append(t)
        issuer = {t: (f"cik:{cik[t]}" if t in cik and t not in rem_name else f"name:{issuer_key(names[t])}") for t in cands}
        by_name = {}
        for t in cands:
            by_name.setdefault(issuer_key(names[t]), []).append(t)
        for grp in by_name.values():
            for t in grp[1:]:
                issuer[t] = issuer[grp[0]]
        out[e] = {"cands": cands, "issuer": issuer,
                  "sector": {t: (sector.get(t) if t not in rem_name else None) for t in cands}, "counts": counts}
    return out


# ------------------------------------------------------------------ selection (formation window only)
def select(e, sess, adj, close, vol, info):
    n_obs = SPEC["formation"]["price_obs"]
    win = sess[sess <= pd.Timestamp(e)][-n_obs:]
    A, Cl, V = adj.loc[win, info["cands"]], close.loc[win, info["cands"]], vol.loc[win, info["cands"]]
    ok = A.notna().all() & Cl.notna().all() & V.notna().all()
    ok &= (A > 0).all() & (Cl > 0).all()
    ok &= (V == 0).sum() == 0
    ok &= pd.Series({c: max_run(Cl[c].to_numpy()) <= 4 if ok[c] else False for c in A.columns})
    ok &= (A.diff().iloc[1:] == 0).mean() <= 0.10
    ok &= A.pct_change(fill_method=None).iloc[1:].std() > 1e-12
    tks = np.array(sorted(A.columns[ok]))
    P = A[tks].to_numpy()
    R = P[1:] / P[:-1] - 1                                         # 126 x N, rows = sessions
    N = len(tks)
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import cdist

    Z = (R - R.mean(0)) / R.std(0, ddof=1)
    _, S, Vt = np.linalg.svd(Z / math.sqrt(R.shape[0] - 1), full_matrices=False)
    Vk = Vt.T[:, :5]
    L = Vk * np.sign(Vk[np.abs(Vk).argmax(0), np.arange(5)]) * S[:5]
    L = L / np.linalg.norm(L, axis=1, keepdims=True)
    labels = fcluster(linkage(L, method="average", metric="euclidean"), t=0.7, criterion="distance")
    D = cdist(L, L)
    C = np.corrcoef(R, rowvar=False)
    issuer = np.array([info["issuer"][t] for t in tks])
    sector = np.array([info["sector"][t] or "" for t in tks])
    Pn = P / P[0]
    logP = np.log(P)
    k = SPEC["selection"]["neighbors_per_stock"]
    chosen, diag = {}, {"formation_end": e, "eligible": N, **info["counts"],
                        "n_clusters": int(labels.max()), "largest_cluster": int(np.bincount(labels).max()),
                        "unlabelled_sector": int((sector == "").sum())}
    for arm in ARMS:
        cand = set()
        for i in range(N):
            base = (np.arange(N) != i) & (issuer != issuer[i])
            if arm == "simple":
                js = knn(C[i], base, k, ascending=False)
            elif arm == "pca":
                js = knn(D[i], base & (labels == labels[i]), k, ascending=True)
            else:
                js = knn(C[i], base & (sector == sector[i]) & (sector[i] != ""), k, ascending=False)
            cand.update((min(i, j), max(i, j)) for j in js)
        ranked = sorted(cand, key=lambda p: (float(np.mean((Pn[:, p[0]] - Pn[:, p[1]]) ** 2)), p[0], p[1]))
        used, pairs = set(), []
        for i, j in ranked:
            if len(pairs) == SPEC["selection"]["max_pairs"]:
                break
            if i in used or j in used:
                continue
            used |= {i, j}
            s = logP[:, i] - logP[:, j]
            pairs.append({"A": tks[i], "B": tks[j], "mu": float(s.mean()), "sd": float(s.std(ddof=1)),
                          "dist": float(np.mean((Pn[:, i] - Pn[:, j]) ** 2)), "corr": float(C[i, j])})
        chosen[arm] = pairs
        diag[f"{arm}_candidates"] = len(cand)
        diag[f"{arm}_selected"] = len(pairs)
    sp = {a: {(p["A"], p["B"]) for p in chosen[a]} for a in ARMS}
    diag["pca_simple_selected_overlap"] = len(sp["pca"] & sp["simple"])
    diag["pca_sector_selected_overlap"] = len(sp["pca"] & sp["sector"])
    return chosen, diag


# ------------------------------------------------------------------ simulation
def simulate(adj: pd.DataFrame, months: list[dict], trade_bps: float, borrow_annual: float,
             leg=0.05, entry=2.0, exit_=0.5, stop=4.0, max_hold=20):
    """months: [{"prev_close": Timestamp, "sessions": DatetimeIndex, "pairs": [{A,B,mu,sd}], "label": str}]"""
    cash, H, prev = 1.0, {}, months[0]["prev_close"]
    nav = 1.0
    days, episodes, n_trades = [], [], 0
    for m in months:
        pairs, S = m["pairs"], m["sessions"]
        K = len(S)
        st = [{"pos": 0, "pending": None, "stopped": False, "sig_k": None, "pnl": 0.0, "entries": 0,
               "stops": 0} for _ in pairs]
        owner = {}
        for n, p in enumerate(pairs):
            owner[p["A"]] = owner[p["B"]] = n
        for k, t in enumerate(S):
            # 1. returns on holdings set at the previous close
            pt, pp = adj.loc[t], adj.loc[prev]
            r = {tk: pt[tk] / pp[tk] - 1 for tk in H}
            if any(not np.isfinite(v) for v in r.values()):
                raise ValueError(f"missing price for a held stock on {t.date()}")
            gross = sum(H[tk] * r[tk] for tk in H)
            Hd = {tk: H[tk] * (1 + r[tk]) for tk in H}
            cal_days = (t - prev).days
            borrow = sum(-h for h in H.values() if h < 0) * borrow_annual * cal_days / 365
            for tk, h in H.items():
                st[owner[tk]]["pnl"] += (h * r[tk] - (-h * borrow_annual * cal_days / 365 if h < 0 else 0)) / nav
            nav_pre = cash - borrow + sum(Hd.values())
            # 2. executions at close t (scheduled liquidation on the last session overrides signals)
            last = k == K - 1
            for s in st:
                if last:
                    s["pos"], s["pending"] = 0, None
                elif s["pending"] is not None:
                    if s["pending"] != 0:
                        s["entries"] += 1
                    s["pos"], s["pending"] = s["pending"], None
            W = {}
            for p, s in zip(pairs, st):
                if s["pos"]:
                    W[p["A"]] = W.get(p["A"], 0) + leg * s["pos"]
                    W[p["B"]] = W.get(p["B"], 0) - leg * s["pos"]
            # target weights are fractions of post-cost NAV: solve NAV = nav_pre - cost(NAV) (contraction)
            nav_post = nav_pre
            for _ in range(6):
                Hs = {tk: w * nav_post for tk, w in W.items()}
                traded = {tk: Hs.get(tk, 0.0) - Hd.get(tk, 0.0) for tk in set(Hs) | set(Hd)}
                cost = trade_bps * 1e-4 * sum(abs(v) for v in traded.values())
                nav_post = nav_pre - cost
            for tk, v in traded.items():
                st[owner[tk]]["pnl"] -= trade_bps * 1e-4 * abs(v) / nav
            cash = cash - borrow - sum(traded.values()) - cost
            H = {tk: h for tk, h in Hs.items() if h != 0}
            nav_prev, nav = nav, cash + sum(H.values())
            # 3. signals at close t, executed at close t+1
            if not last:
                for p, s in zip(pairs, st):
                    a, b = pt[p["A"]], pt[p["B"]]
                    if not (np.isfinite(a) and np.isfinite(b)):
                        raise ValueError(f"missing price for a selected stock on {t.date()}")
                    z = (math.log(a) - math.log(b) - p["mu"]) / p["sd"]
                    if s["pending"] is not None:
                        continue
                    if s["pos"]:
                        if abs(z) >= stop:
                            s["pending"], s["stopped"] = 0, True
                            s["stops"] += 1
                        elif abs(z) <= exit_ or k - s["sig_k"] >= max_hold:
                            s["pending"] = 0
                    elif not s["stopped"] and entry <= abs(z) < stop:
                        s["pending"], s["sig_k"] = (-1 if z > 0 else 1), k
            gross_exp = sum(abs(h) for h in H.values()) / nav
            days.append({"date": t, "nav": nav, "ret": nav / nav_prev - 1, "gross_pnl": gross / nav_prev,
                         "borrow": borrow / nav_prev, "cost": cost / nav_prev,
                         "turnover": sum(abs(v) for v in traded.values()) / nav_pre,
                         "gross_exp": gross_exp, "net_exp": sum(H.values()) / nav,
                         "active_pairs": sum(1 for s in st if s["pos"])})
            prev = t
        for p, s in zip(pairs, st):
            n_trades += s["entries"]
            episodes.append({"month": m["label"], "pair": f"{p['A']}/{p['B']}", "pnl": s["pnl"],
                             "entries": s["entries"], "stops": s["stops"]})
    return pd.DataFrame(days).set_index("date"), pd.DataFrame(episodes), n_trades


# ------------------------------------------------------------------ metrics
def metrics(d: pd.DataFrame, ep: pd.DataFrame, n_trades: int) -> dict:
    r = d["ret"]
    years = len(r) / 252
    nav = d["nav"]
    dd = nav / nav.cummax() - 1
    pnl = ep["pnl"]
    tot = pnl.sum()
    by_pair = ep.groupby("pair")["pnl"].sum().sort_values(ascending=False)
    by_month = ep.groupby("month")["pnl"].sum().sort_values(ascending=False)
    return {
        "total_return": float(nav.iloc[-1] - 1), "cagr": float(nav.iloc[-1] ** (1 / years) - 1),
        "ann_vol": float(r.std() * math.sqrt(252)),
        "sharpe": float(r.mean() / r.std() * math.sqrt(252)) if r.std() > 0 else float("nan"),
        "max_drawdown": float(dd.min()), "trades": int(n_trades),
        "avg_active_pairs": float(d["active_pairs"].mean()), "pct_days_invested": float((d["gross_exp"] > 0).mean()),
        "avg_gross_exposure": float(d["gross_exp"].mean()), "max_gross_exposure": float(d["gross_exp"].max()),
        "avg_net_exposure": float(d["net_exp"].mean()), "annual_turnover": float(d["turnover"].sum() / years),
        "trading_costs_pct_nav": float(d["cost"].sum()), "borrow_pct_nav": float(d["borrow"].sum()),
        "pair_episodes": int((ep["entries"] > 0).sum()), "episode_pnl_sum": float(tot),
        "top10_episode_share": float(pnl.nlargest(10).sum() / tot) if tot > 0 else None,
        "pnl_ex_top10_episodes": float(tot - pnl.nlargest(10).sum()),
        "top_pair": by_pair.index[0], "top_pair_share": float(by_pair.iloc[0] / tot) if tot > 0 else None,
        "best_month_share": float(by_month.iloc[0] / tot) if tot > 0 else None,
        "share_positive_episodes": float((pnl[ep["entries"] > 0] > 0).mean()),
    }


def monthly(d: pd.DataFrame) -> pd.Series:
    return (1 + d["ret"]).groupby(d.index.to_period("M")).prod() - 1


def nw_t(x: pd.Series, lags=3) -> float:
    import statsmodels.api as sm

    res = sm.OLS(x.to_numpy(), np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return float(res.tvalues[0])


def build_months(sess, ends, selections, arm):
    out = []
    for n, e in enumerate(ends):
        lo = pd.Timestamp(e)
        hi = pd.Timestamp(ends[n + 1]) if n + 1 < len(ends) else sess[-1]
        S = sess[(sess > lo) & (sess <= hi)]
        out.append({"prev_close": lo, "sessions": S, "pairs": selections[e][arm], "label": S[0].strftime("%Y-%m")})
    return out


def main() -> None:
    import time

    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    sess, adj, close, vol, meta = load_panel()
    ends = formation_ends()
    info = universe_inputs(ends, sess, adj, meta)
    selections, diags = {}, []
    for e in ends:
        selections[e], dg = select(e, sess, adj, close, vol, info[e])
        diags.append(dg)
    pd.DataFrame(diags).to_csv(OUT / "formation_selection.csv", index=False)
    json.dump(selections, open(OUT / "selected_pairs.json", "w"), indent=0)
    print(f"selection done in {time.time() - t0:.0f}s")
    c = SPEC["costs"]
    settings = {"gross": (0.0, 0.0), "base": (c["trade_bps"], c["borrow_annual"]),
                "stress": (c["trade_bps"] * c["stress_multiplier"], c["borrow_annual"] * c["stress_multiplier"])}
    summary, curves, mret = {}, {}, {}
    for arm in ARMS:
        months = build_months(sess, ends, selections, arm)
        for name, (bps, bor) in settings.items():
            d, ep, nt = simulate(adj, months, bps, bor)
            summary[f"{arm}_{name}"] = metrics(d, ep, nt)
            curves[f"{arm}_{name}"] = d["nav"]
            mret[f"{arm}_{name}"] = monthly(d)
            if name == "base":
                d.to_csv(OUT / f"daily_{arm}_base.csv")
                ep.to_csv(OUT / f"episodes_{arm}_base.csv", index=False)
                annual = (1 + d["ret"]).groupby(d.index.year).prod() - 1
                summary[f"{arm}_base"]["annual_returns"] = {int(y): round(float(v), 4) for y, v in annual.items()}
    M = pd.DataFrame(mret)
    M.to_csv(OUT / "monthly_returns.csv")
    diffs = {}
    for base_arm in ("simple", "sector"):
        for name in ("base", "stress"):
            x = M[f"pca_{name}"] - M[f"{base_arm}_{name}"]
            diffs[f"pca_minus_{base_arm}_{name}"] = {"n_months": int(len(x)), "mean_monthly": float(x.mean()),
                                                      "sd_monthly": float(x.std()), "nw3_t": nw_t(x),
                                                      "share_months_positive": float((x > 0).mean())}
    summary["pca_minus_baseline_monthly"] = diffs
    summary["dates"] = {"first_trading_day": str(sess[sess > pd.Timestamp(ends[0])][0].date()),
                        "last_day": str(sess[-1].date()), "formations": len(ends)}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    pd.DataFrame(curves).to_csv(OUT / "equity_curves.csv")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4.5))
    for key, style in (("simple_gross", ":"), ("simple_base", "-"), ("pca_base", "-"), ("sector_base", "-"), ("simple_stress", "--")):
        ax.plot(curves[key].index, curves[key].values, style, lw=1.3, label=key.replace("_", " "))
    ax.axhline(1, color="grey", lw=0.6)
    ax.set_title("V2 development equity curves (2015-08-03 to 2024-10-02; holdout locked)")
    ax.set_ylabel("NAV")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png", dpi=130)
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
