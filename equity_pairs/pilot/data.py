"""Pilot inputs: point-in-time membership (Wikipedia) and pilot-window prices (yfinance).

    python pilot/data.py      # probe endpoint semantics, then fetch the pilot window

Every request passes guard.check_request first, and guard.check_dates on what comes back.
"""
from __future__ import annotations

import io
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from guard import check_dates, check_request, load_config  # noqa: E402

RAW = ROOT / "data" / "raw"
SRC = RAW / "sources"


def _norm(ticker: str) -> str:
    return ticker.strip().replace(".", "-")


def membership(formation_ends) -> tuple[dict[str, set[str]], pd.DataFrame, pd.DataFrame]:
    """Members at each formation end: current list with later changes reversed."""
    cur = pd.read_html(io.StringIO((SRC / "wikipedia_sp500.html").read_text()))[0]
    ch = pd.read_html(io.StringIO((SRC / "wikipedia_sp500_history.html").read_text()))[0]
    ch.columns = ["date", "add_t", "add_s", "rem_t", "rem_s", "reason", "refs"]
    ch["date"] = pd.to_datetime(ch["date"])
    ch = ch.sort_values("date", ascending=False)
    now = {_norm(t) for t in cur["Symbol"]}
    out = {}
    for e in formation_ends:
        m = set(now)
        for _, r in ch[ch["date"] > pd.Timestamp(e)].iterrows():
            if isinstance(r.add_t, str):
                m.discard(_norm(r.add_t))
            if isinstance(r.rem_t, str):
                m.add(_norm(r.rem_t))
        out[e] = m
    return out, cur, ch


def _fetch(ticker: str, start: str, end_exclusive: str) -> tuple[str, pd.DataFrame, dict]:
    import yfinance as yf

    for attempt in range(3):
        try:
            t = yf.Ticker(ticker)
            df = t.history(start=start, end=end_exclusive, auto_adjust=False, actions=True,
                           repair=False, raise_errors=False)
            meta = dict(t.history_metadata or {}) if len(df) else {}
            return ticker, df, {k: meta.get(k) for k in ("longName", "shortName", "firstTradeDate",
                                                           "exchangeTimezoneName", "currency", "instrumentType")}
        except Exception as exc:  # network hiccup or rate limit
            err = repr(exc)
            time.sleep(2 * (attempt + 1))
    return ticker, pd.DataFrame(), {"error": err}


def fetch_pilot() -> None:
    cfg = load_config()
    win = cfg["data"]["pilot_download"]
    start, end_x = win["first_date"], win["request_end_exclusive"]
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)

    # 1. endpoint semantics probe (inside the pilot window)
    check_request("2015-02-03", end_inclusive=False)
    _, probe, _ = _fetch("MMM", "2015-01-28", "2015-02-03")
    check_dates(probe.index)
    probe_last = probe.index.max().tz_convert("America/New_York").date().isoformat()
    assert probe_last == "2015-02-02", f"end not exclusive as assumed: last={probe_last}"

    # 2. pilot window for the union of members across pilot formations
    check_request(end_x, end_inclusive=False)
    ends = cfg["pilot"]["provisional_formation_ends"]
    members, _, _ = membership(ends)
    tickers = sorted(set().union(*members.values()))
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda tk: _fetch(tk, start, end_x), tickers))
    frames, metas = {}, []
    for tk, df, meta in results:
        if len(df):
            check_dates(df.index)
            idx = df.index.tz_convert("America/New_York").tz_localize(None).normalize()
            df = df.set_axis(idx)
            frames[tk] = df
        metas.append({"ticker": tk, "rows": len(df), **meta})
    pd.to_pickle(frames, RAW / "prices_pilot.pkl")
    pd.DataFrame(metas).to_csv(RAW / "prices_pilot_meta.csv", index=False)
    summary = {"probe_request": ["MMM", "2015-01-28", "2015-02-03 (exclusive)"], "probe_last_date": probe_last,
               "requested": len(tickers), "with_rows": len(frames), "seconds": round(time.time() - t0, 1),
               "window": [start, end_x + " (exclusive)"],
               "max_date_returned": max(df.index.max() for df in frames.values()).date().isoformat()}
    (RAW / "prices_pilot_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    fetch_pilot()
