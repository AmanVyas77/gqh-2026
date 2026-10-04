"""Prompt 2 structural pilot: data audit + formation diagnostics (no returns after formation).

    python pilot/run.py

Implements only eligibility, PCA, clustering, candidates, cointegration screening and
reporting, with the frozen settings in config.yaml. Every fitted quantity uses one
formation window. Writes pilot/results/*.
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pilot"))
from data import RAW, _norm, membership  # noqa: E402
from guard import check_dates, load_config  # noqa: E402
from spec import require_consistent  # noqa: E402
from split import xnys_sessions  # noqa: E402

OUT = ROOT / "pilot" / "results"
STOP = {"inc", "corp", "corporation", "company", "co", "the", "class", "ltd", "plc", "holdings",
        "group", "incorporated", "llc", "sa", "nv", "and", "com"}


def tokens(name) -> set[str]:
    if not isinstance(name, str):
        return set()
    name = re.sub(r"\(.*?\)", " ", name.lower())
    return {w for w in re.findall(r"[a-z0-9]+", name) if len(w) >= 2 and w not in STOP}


def issuer_key(name) -> str:
    if not isinstance(name, str):
        return ""
    name = re.sub(r"\(.*?\)", " ", name.lower())
    words = [w for w in re.findall(r"[a-z0-9]+", name) if w not in STOP and len(w) > 1]
    return " ".join(words)


# ------------------------------------------------------------------ formation pipeline
def bh_adjust(p: np.ndarray) -> np.ndarray:
    m = len(p)
    order = np.argsort(p, kind="mergesort")
    ranked = p[order] * m / np.arange(1, m + 1)
    adj = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(adj, 1.0)
    return out


def screen_pair(y: np.ndarray, x: np.ndarray, cfg: dict) -> dict:
    from statsmodels.tsa.stattools import coint

    ct = cfg["screening"]["cointegration_test"]
    res = {"degenerate": True, "p": np.nan, "beta": np.nan, "phi": np.nan, "half_life": np.nan}
    if not (np.isfinite(y).all() and np.isfinite(x).all()) or np.var(x) <= 1e-14:
        return res
    X = np.column_stack([np.ones_like(x), x])
    if np.linalg.cond(X) > 1e8:
        return res
    (alpha, beta), *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - alpha - beta * x
    sd = e.std(ddof=1)
    if not np.isfinite(sd) or sd <= cfg["screening"]["pass_rules"]["min_residual_std"]:
        return res
    try:
        p = coint(y, x, trend=ct["trend"], maxlag=ct["maxlag"], autolag=ct["autolag"])[1]
    except Exception:
        return res
    if not np.isfinite(p):
        return res
    Z = np.column_stack([np.ones(len(e) - 1), e[:-1]])
    (_, phi), *_ = np.linalg.lstsq(Z, e[1:], rcond=None)
    hl = -math.log(2) / math.log(phi) if 0 < phi < 1 else np.nan
    return {"degenerate": False, "p": p, "beta": beta, "phi": phi, "half_life": hl}


def knn(scores: np.ndarray, allowed: np.ndarray, k: int, ascending: bool) -> list[int]:
    idx = np.flatnonzero(allowed)
    if len(idx) == 0:
        return []
    key = scores[idx] if ascending else -scores[idx]
    order = np.lexsort((idx, key))          # primary score, then identifier (sorted index)
    return list(idx[order[:k]])


def run_formation(args) -> dict:
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import cdist

    e, panel, info, cfg = args
    t0 = time.time()
    el = cfg["universe"]["eligibility"]
    st = el["stale_price"]
    n_obs = cfg["timeline"]["formation_price_obs"]
    reasons = info["pre_reasons"]            # members already excluded before price checks
    close, adj, vol = panel["close"], panel["adj"], panel["vol"]
    eligible = []
    for tk in info["candidates"]:
        c, a, v = close[tk].to_numpy(), adj[tk].to_numpy(), vol[tk].to_numpy()
        if np.isnan(c).any() or np.isnan(a).any() or np.isnan(v).any() or len(c) != n_obs:
            reason = "incomplete_window"
        elif (c <= 0).any() or (a <= 0).any():
            reason = "nonpositive_price"
        elif (v == 0).sum() > st["max_zero_or_missing_volume_sessions"]:
            reason = "stale_zero_volume"
        elif max_run(c) > st["max_identical_close_run"]:
            reason = "stale_identical_close_run"
        elif (np.diff(a) == 0).mean() > st["max_zero_return_share"]:
            reason = "stale_zero_return_share"
        elif np.std(a[1:] / a[:-1] - 1, ddof=1) <= el["min_return_std"]:
            reason = "zero_return_variance"
        elif c[-1] < el["min_formation_end_raw_close"]:
            reason = "price_below_5_split_adjusted"
        elif np.median(c * v) < el["min_median_dollar_volume"]:
            reason = "median_dollar_volume_below_20m"
        else:
            reason = None
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
        else:
            eligible.append(tk)
    tks = np.array(sorted(eligible))
    A = adj[tks].to_numpy()                                  # 127 x N prices
    R = A[1:] / A[:-1] - 1                                   # 126 x N returns (rows = sessions)
    Zs = (R - R.mean(0)) / R.std(0, ddof=1)
    U, S, Vt = np.linalg.svd(Zs / math.sqrt(R.shape[0] - 1), full_matrices=False)
    K = cfg["features"]["pca"]["n_components"]
    V = Vt.T[:, :K]                                          # N x K: one row per stock
    flip = np.sign(V[np.abs(V).argmax(0), np.arange(K)])
    L = V * flip * S[:K]                                     # loadings = eigvec * sqrt(eigval)
    nrm = np.linalg.norm(L, axis=1)
    keep = nrm > cfg["features"]["zero_vector_tolerance"]
    if (~keep).any():
        reasons["zero_loading_vector"] = int((~keep).sum())
    tks, A, R, L = tks[keep], A[:, keep], R[:, keep], L[keep] / nrm[keep, None]
    N = len(tks)
    labels = fcluster(linkage(L, method=cfg["clustering"]["linkage"], metric="euclidean"),
                      t=cfg["clustering"]["cut_distance"], criterion="distance")
    sizes = pd.Series(labels).value_counts()
    D = cdist(L, L)
    C = np.corrcoef(R, rowvar=False)
    issuer = np.array([info["issuer"].get(t, t) for t in tks])
    sector = np.array([info["sector"].get(t) or "" for t in tks])
    k = cfg["candidates"]["neighbors_per_stock"]
    arms = {"pca": set(), "corr": set(), "sector": set()}
    for i in range(N):
        base = (np.arange(N) != i) & (issuer != issuer[i])
        for arm, allowed, score, asc in (
            ("pca", base & (labels == labels[i]), D[i], True),
            ("corr", base, C[i], False),
            ("sector", base & (sector == sector[i]) & (sector[i] != ""), C[i], False),
        ):
            for j in knn(score, allowed, k, asc):
                arms[arm].add((min(i, j), max(i, j)))
    union = sorted(set().union(*arms.values()))
    logp = np.log(A / A[0])                                  # window-local total-return index
    rows = []
    for i, j in union:
        r = screen_pair(logp[:, i], logp[:, j], cfg)
        rows.append({"i": i, "j": j, "A": tks[i], "B": tks[j], "corr": C[i, j], **r})
    sc = pd.DataFrame(rows)
    sc["p_bh"] = np.nan
    ok = ~sc["degenerate"]
    sc.loc[ok, "p_bh"] = bh_adjust(sc.loc[ok, "p"].to_numpy())
    pr = cfg["screening"]["pass_rules"]
    sc["bh_pass"] = sc["p_bh"] <= pr["max_bh_adjusted_p"]
    sc["beta_pass"] = sc["beta"].between(pr["beta_min"], pr["beta_max"])
    hl = pr["half_life"]
    sc["hl_pass"] = sc["half_life"].between(hl["min_sessions"], hl["max_sessions"])
    sc["passes"] = sc["bh_pass"] & sc["beta_pass"] & sc["hl_pass"] & ok

    out = {"formation_end": e, "members": info["n_members"], "with_yahoo_data": info["n_with_data"],
           "eligible": N, "exclusions": dict(sorted(reasons.items())),
           "n_clusters": int(len(sizes)), "n_singletons": int((sizes == 1).sum()),
           "n_multi_clusters": int((sizes >= 2).sum()), "largest_cluster": int(sizes.max()),
           "median_multi_cluster_size": float(sizes[sizes >= 2].median()) if (sizes >= 2).any() else 0.0,
           "stocks_in_multi_clusters": int(sizes[sizes >= 2].sum()),
           "n_tested_union": len(union), "n_degenerate": int((~ok).sum()),
           "n_raw_p05_union": int((sc["p"] <= 0.05).sum()), "n_bh_pass_union": int(sc["bh_pass"].sum())}
    key = sc.set_index(["i", "j"])
    sets = {}
    for arm, pairs in arms.items():
        s = key.loc[sorted(pairs)] if pairs else key.iloc[:0]
        nd = s[~s["degenerate"]]
        a_bh = nd[nd["bh_pass"]]
        a_beta = a_bh[a_bh["beta_pass"]]
        a_hl = a_beta[a_beta["hl_pass"]]
        ranked = a_hl.reset_index().sort_values(["corr", "A", "B"], ascending=[False, True, True])
        used, chosen = set(), []
        for _, r in ranked.iterrows():
            if len(chosen) >= cfg["portfolio"]["max_pairs"]:
                break
            if r.A in used or r.B in used:
                continue
            used |= {r.A, r.B}
            chosen.append((r.A, r.B))
        sets[arm] = {"cand": {(tks[i], tks[j]) for i, j in pairs},
                     "pass": set(zip(a_hl["A"], a_hl["B"])), "sel": set(chosen)}
        out.update({f"{arm}_candidates": len(pairs), f"{arm}_degenerate": int(s["degenerate"].sum()),
                    f"{arm}_raw_p05": int((nd["p"] <= 0.05).sum()), f"{arm}_bh_pass": len(a_bh),
                    f"{arm}_after_beta": len(a_beta), f"{arm}_after_half_life": len(a_hl),
                    f"{arm}_selected": len(chosen)})
    P = sets["pca"]
    for other in ("corr", "sector"):
        for stage in ("cand", "pass", "sel"):
            a, b = P[stage], sets[other][stage]
            out[f"pca_in_{other}_{stage}"] = round(len(a & b) / len(a), 4) if a else None
            out[f"jaccard_pca_{other}_{stage}"] = round(len(a & b) / len(a | b), 4) if a | b else None
    out["seconds"] = round(time.time() - t0, 1)
    out["_sets"] = {arm: {k2: sorted(v) for k2, v in d.items()} for arm, d in sets.items()}
    return out


def first_trade_date(x) -> pd.Timestamp:
    """Yahoo firstTradeDate (epoch seconds or datetime string) as a naive UTC date."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return pd.NaT
    try:
        ts = pd.to_datetime(float(x), unit="s", utc=True)
    except (TypeError, ValueError):
        ts = pd.to_datetime(x, utc=True, errors="coerce")
    return ts.tz_convert(None) if pd.notna(ts) else pd.NaT


def max_run(c: np.ndarray) -> int:
    best = run = 1
    for a, b in zip(c[:-1], c[1:]):
        run = run + 1 if a == b else 1
        best = max(best, run)
    return best


# ------------------------------------------------------------------ audit + driver
def main() -> None:
    T0 = time.time()
    cfg = load_config()
    require_consistent(cfg)
    OUT.mkdir(parents=True, exist_ok=True)
    frames = pd.read_pickle(RAW / "prices_pilot.pkl")
    meta = pd.read_csv(RAW / "prices_pilot_meta.csv").set_index("ticker")
    for df in frames.values():
        check_dates(df.index)
    ends = cfg["pilot"]["provisional_formation_ends"]
    members, cur, ch = membership(ends)
    cur["tk"] = cur["Symbol"].map(_norm)
    cur_name = dict(zip(cur["tk"], cur["Security"]))
    sector = dict(zip(cur["tk"], cur["GICS Sector"]))
    cik = dict(zip(cur["tk"], cur["CIK"]))

    sess = xnys_sessions("2015-01-01", "2016-07-01")
    sess = sess[sess >= pd.Timestamp(cfg["data"]["pilot_download"]["first_date"])]
    close = pd.DataFrame({t: f["Close"] for t, f in frames.items()}).reindex(sess)
    adj = pd.DataFrame({t: f["Adj Close"] for t, f in frames.items()}).reindex(sess)
    vol = pd.DataFrame({t: f["Volume"] for t, f in frames.items()}).reindex(sess)

    # ---- audit (pilot window only)
    all_dates = pd.DatetimeIndex(sorted(set().union(*[set(f.index) for f in frames.values()])))
    split_rows, div_dev = [], []
    for t, f in frames.items():
        sp = f.loc[f["Stock Splits"] > 0, "Stock Splits"]
        for d, ratio in sp.items():
            pos = f.index.get_loc(d)
            jump = f["Close"].iloc[pos] / f["Close"].iloc[pos - 1] - 1 if pos > 0 else np.nan
            split_rows.append({"ticker": t, "date": d.date().isoformat(), "ratio": ratio,
                               "close_change_on_split_day": round(float(jump), 4)})
        cl, ac, dv = f["Close"], f["Adj Close"], f["Dividends"]
        r_adj = ac / ac.shift() - 1
        r_cd = (cl + dv) / cl.shift() - 1
        div_dev.append((r_adj - r_cd).abs().dropna())
    dev = pd.concat(div_dev)
    big = []
    for t in adj.columns:
        r = adj[t] / adj[t].shift() - 1
        for d, v in r[r.abs() > 0.25].items():
            big.append({"ticker": t, "date": d.date().isoformat(), "adj_return": round(float(v), 4)})
    aapl = float(close.loc["2015-07-31", "AAPL"]) if "AAPL" in close else None
    rets = adj.pct_change(fill_method=None).iloc[1:]
    dup = []
    cols = [c for c in rets.columns if rets[c].notna().sum() > 100]
    cm = rets[cols].corr(min_periods=100)
    for a_ in range(len(cols)):
        for b_ in range(a_ + 1, len(cols)):
            if cm.iat[a_, b_] > 0.995:
                dup.append([cols[a_], cols[b_], round(float(cm.iat[a_, b_]), 5)])
    audit = {
        "union_tickers": len(meta), "with_rows": int((meta["rows"] > 0).sum()),
        "without_rows_current_members": sorted(t for t in meta.index[meta["rows"] == 0] if t in cur_name),
        "n_without_rows_former_members": int(sum(1 for t in meta.index[meta["rows"] == 0] if t not in cur_name)),
        "dates_not_xnys_sessions": [d.date().isoformat() for d in all_dates.difference(sess)],
        "xnys_sessions_with_no_data_at_all": [d.date().isoformat() for d in sess.difference(all_dates)],
        "n_xnys_sessions_in_window": len(sess),
        "split_events": split_rows,
        "adj_vs_close_plus_dividend_return_abs_diff": {"n": int(len(dev)), "p99": float(dev.quantile(0.99)),
                                                         "p999": float(dev.quantile(0.999)), "max": float(dev.max()),
                                                         "n_over_1e-3": int((dev > 1e-3).sum())},
        "adj_returns_over_25pct": big,
        "aapl_close_2015_07_31": aapl,
        "aapl_as_traded_close_2015_07_31_reference": 121.30,
        "near_identical_return_series_corr_gt_0.995": dup,
        "max_date_in_data": max(f.index.max() for f in frames.values()).date().isoformat(),
    }

    # ---- per-formation inputs
    jobs = []
    for e in ends:
        win = sess[sess <= pd.Timestamp(e)][-cfg["timeline"]["formation_price_obs"]:]
        wstart = win[0]
        later = ch[ch["date"] > pd.Timestamp(e)].sort_values("date")
        rem_name = {}
        for _, r in later.iterrows():
            if isinstance(r.rem_t, str) and _norm(r.rem_t) not in rem_name:
                rem_name[_norm(r.rem_t)] = r.rem_s
        pre, cands, names = {}, [], {}
        for t in sorted(members[e]):
            name = rem_name.get(t, cur_name.get(t))
            names[t] = name
            if t not in frames:
                pre["no_yahoo_data"] = pre.get("no_yahoo_data", 0) + 1
                continue
            m = meta.loc[t]
            former = t in rem_name or t not in cur_name   # identity check applies to former members only
            ftd = first_trade_date(m.get("firstTradeDate"))
            yname = tokens(m.get("longName")) | tokens(m.get("shortName"))
            if former and ((pd.notna(ftd) and ftd.normalize() > wstart) or not (yname & tokens(name))):
                pre["identity_unverified"] = pre.get("identity_unverified", 0) + 1
                continue
            cands.append(t)
        issuer = {t: (f"cik:{cik[t]}" if t in cik and t not in rem_name else f"name:{issuer_key(names[t])}") for t in cands}
        # merge share classes across CIK and name keys
        by_name = {}
        for t in cands:
            by_name.setdefault(issuer_key(names[t]), []).append(t)
        for grp in by_name.values():
            if len(grp) > 1:
                for t in grp:
                    issuer[t] = issuer[grp[0]]
        sec = {t: (sector.get(t) if t not in rem_name else None) for t in cands}
        panel = {"close": close.loc[win, cands], "adj": adj.loc[win, cands], "vol": vol.loc[win, cands]}
        info = {"pre_reasons": pre, "candidates": cands, "issuer": issuer, "sector": sec,
                "n_members": len(members[e]), "n_with_data": sum(t in frames for t in members[e])}
        jobs.append((e, panel, info, cfg))
    shared_issuers = sorted({tuple(sorted(g)) for job in jobs for g in
                             pd.Series(job[2]["issuer"]).groupby(pd.Series(job[2]["issuer"])).groups.values()
                             if len(g) > 1})
    audit["share_class_groups_excluded_from_pairing"] = [list(g) for g in shared_issuers]
    audit["no_sector_label_former_members_per_formation"] = {j[0]: sum(v is None for v in j[2]["sector"].values()) for j in jobs}

    with ProcessPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(run_formation, jobs))
    sets = {r["formation_end"]: r.pop("_sets") for r in results}
    table = pd.DataFrame(results)
    th = cfg["pilot"]["thresholds"]
    n_low = int((table["eligible"] < th["min_eligible_stocks"]).sum())
    n_pca_ok = int((table["pca_selected"] >= th["min_pca_pairs"]).sum())
    n_redund = int((table["pca_in_corr_cand"] > th["redundancy_overlap_share"]).sum())
    if len(table) < th["n_formations"] or n_low > th["max_formations_below_min_eligible"]:
        verdict = "BLOCKED"
    elif n_pca_ok < th["min_formations_with_min_pca_pairs"]:
        verdict = "NOT PROMISING"
    else:
        verdict = "PASS WITH LIMITATIONS"   # material universe/sector/borrow/price-convention limits (see report)
    stab = []
    for a_, b_ in zip(ends[:-1], ends[1:]):
        pa = {tuple(x) for x in sets[a_]["pca"]["pass"]}
        pb = {tuple(x) for x in sets[b_]["pca"]["pass"]}
        sa = {tuple(x) for x in sets[a_]["pca"]["sel"]}
        sb = {tuple(x) for x in sets[b_]["pca"]["sel"]}
        stab.append({"from": a_, "to": b_, "jaccard_pca_passing": round(len(pa & pb) / len(pa | pb), 3) if pa | pb else None,
                     "jaccard_pca_selected": round(len(sa & sb) / len(sa | sb), 3) if sa | sb else None})
    gate = {"verdict": verdict, "n_formations": len(table), "formations_below_300_eligible": n_low,
            "formations_with_ge5_pca_pairs": n_pca_ok, "formations_pca_cand_overlap_gt_90pct_with_corr": n_redund,
            "redundancy_flag": n_redund >= th["redundancy_min_formations"],
            "pipeline_seconds": round(time.time() - T0, 1)}
    table.to_csv(OUT / "formation_diagnostics.csv", index=False)
    (OUT / "audit.json").write_text(json.dumps(audit, indent=1, default=str))
    (OUT / "gate.json").write_text(json.dumps(gate, indent=1))
    (OUT / "adjacent_stability_descriptive.json").write_text(json.dumps(stab, indent=1))
    (OUT / "pair_sets.json").write_text(json.dumps(sets, indent=0, default=list))
    print(json.dumps(gate, indent=1))


if __name__ == "__main__":
    main()
