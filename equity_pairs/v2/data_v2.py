"""V2 development data: PIT members across all development formations, Adj Close etc.

    python v2/data_v2.py
Requests end before the holdout via guard.check_request; every frame passes guard.check_dates.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "pilot")]
from data import _fetch, membership  # noqa: E402
from guard import check_dates, check_request  # noqa: E402
from split import month_end_sessions, xnys_sessions  # noqa: E402

RAW = ROOT / "data" / "raw"
SPEC = yaml.safe_load((ROOT / "v2" / "spec_v2.yaml").read_text())


def formation_ends() -> list[str]:
    dev = SPEC["development"]
    sess = xnys_sessions("2015-01-01", "2024-10-03")          # through the last development session
    me = month_end_sessions(sess)
    return [d.strftime("%Y-%m-%d") for d in me if dev["first_formation_end"] <= d.strftime("%Y-%m-%d") < dev["end"]]


def main() -> None:
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    req = SPEC["data"]["request"]
    check_request(req["end_exclusive"], end_inclusive=False)
    ends = formation_ends()
    members, _, _ = membership(ends)
    tickers = sorted(set().union(*members.values()))
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda tk: _fetch(tk, req["start"], req["end_exclusive"]), tickers))
    frames, metas = {}, []
    for tk, df, meta in results:
        if len(df):
            check_dates(df.index)
            df = df.set_axis(df.index.tz_convert("America/New_York").tz_localize(None).normalize())
            frames[tk] = df[["Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]]
        metas.append({"ticker": tk, "rows": len(df), **meta})
    pd.to_pickle(frames, RAW / "prices_dev.pkl")
    pd.DataFrame(metas).to_csv(RAW / "prices_dev_meta.csv", index=False)
    s = {"formations": len(ends), "first": ends[0], "last": ends[-1], "requested": len(tickers),
         "with_rows": len(frames), "seconds": round(time.time() - t0, 1),
         "max_date": max(f.index.max() for f in frames.values()).date().isoformat()}
    (RAW / "prices_dev_summary.json").write_text(json.dumps(s, indent=1))
    print(json.dumps(s))


if __name__ == "__main__":
    main()
