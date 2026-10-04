"""Fetch every raw input for the study.

Sources
- Databento GLBX.MDP3 (LE.FUT, GF.FUT, ZC.FUT): definition, statistics, ohlcv-1d.
- USDA NASS Quick Stats: monthly Cattle on Feed placements (mechanism tests only).
- CFTC Disaggregated COT, futures only, Live Cattle: PMPU long/short (Variant C).
- yfinance: SPY adjusted close (factor check only).

In-sample by default: every source stops before oos_start (Databento `end` is
exclusive, so the last day pulled is oos_start - 1). Out-of-sample data is fetched
only by run_oos.py, which calls the pull functions with oos=True and writes to
data/raw/oos/. The CLI has no OOS option.

Usage
  python data/download.py --estimate            # Databento cost only; pulls nothing
  python data/download.py --probe-nass          # list NASS series matching config.nass.query
  python data/download.py --pull databento --yes
  python data/download.py --pull nass cftc spy
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import RAW, RAW_OOS, ROOT, data_start, load_config, oos_start  # noqa: E402

SCHEMAS = ["definition", "statistics", "ohlcv-1d"]

# Statistics kept after download (stat_type): settlement, session low/high,
# cleared volume, open interest, upper/lower price limit.
KEEP_STAT_TYPES = {3, 4, 5, 6, 9, 17, 18}

# Definition columns kept. Price-valued ones are converted from cents to dollars.
DEF_COLS = [
    "instrument_id", "raw_symbol", "asset", "instrument_class", "security_type", "cfi",
    "expiration", "activation", "maturity_year", "maturity_month", "maturity_day",
    "unit_of_measure", "unit_of_measure_qty", "min_price_increment", "display_factor",
    "contract_multiplier", "high_limit_price", "low_limit_price", "trading_reference_price",
    "security_update_action",
]
DEF_PRICE_COLS = ["min_price_increment", "high_limit_price", "low_limit_price", "trading_reference_price"]

# Loose sanity bounds on settlements after conversion to dollars, 2010-2026.
PRICE_BOUNDS = {"LE": (0.5, 4.0), "GF": (0.5, 5.0), "ZC": (1.5, 10.0)}

NASS_URL = "https://quickstats.nass.usda.gov/api/api_GET/"
CFTC_URL = "https://publicreporting.cftc.gov/resource/{dataset}.json"


# --------------------------------------------------------------------------- helpers

def _env(name: str) -> str:
    load_dotenv(ROOT / ".env")
    val = os.environ.get(name, "").strip()
    if not val:
        sys.exit(f"{name} is not set. Copy .env.example to .env and fill it in.")
    return val


def _window(cfg: dict, oos: bool, dataset_end: str | None = None) -> tuple[pd.Timestamp, pd.Timestamp]:
    """[start, end) for a pull. In-sample ends at oos_start (exclusive)."""
    if oos:
        end = pd.Timestamp(dataset_end) if dataset_end else pd.Timestamp.now(tz="UTC").normalize()
        if end.tzinfo is not None:
            end = end.tz_convert("UTC").tz_localize(None)
        return oos_start(cfg), end
    return data_start(cfg), oos_start(cfg)


def _out_dir(oos: bool) -> Path:
    d = RAW_OOS if oos else RAW
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_manifest(out: Path, key: str, info: dict) -> None:
    path = out / "manifest.json"
    manifest = json.loads(path.read_text()) if path.exists() else {}
    manifest[key] = {**info, "pulled_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    path.write_text(json.dumps(manifest, indent=2, default=str))


def _assert_before(df: pd.DataFrame, col: str, boundary: pd.Timestamp, label: str) -> None:
    """Hard OOS guard on what gets written for an in-sample pull."""
    ts = pd.to_datetime(df[col])
    if ts.dt.tz is not None:                       # Databento timestamps are UTC-aware
        ts = ts.dt.tz_convert("UTC").dt.tz_localize(None)
    if len(df) and ts.max() >= boundary:
        raise RuntimeError(f"{label}: found {col} >= {boundary.date()} in an in-sample pull")


# --------------------------------------------------------------------------- Databento

def _db_client():
    import databento as db
    return db.Historical(_env("DATABENTO_API_KEY"))


def databento_estimate(cfg: dict, oos: bool = False) -> pd.DataFrame:
    """Free metadata calls: record count, billable size and cost per root x schema."""
    client = _db_client()
    dcfg = cfg["databento"]
    dataset_end = client.metadata.get_dataset_range(dcfg["dataset"])["end"] if oos else None
    start, end = _window(cfg, oos, dataset_end)
    rows = []
    for root, parent in dcfg["parents"].items():
        for schema in SCHEMAS:
            kw = dict(dataset=dcfg["dataset"], symbols=[parent], stype_in="parent",
                      schema=schema, start=start, end=end)
            rows.append({
                "root": root, "schema": schema,
                "records": client.metadata.get_record_count(**kw),
                "size_mb": client.metadata.get_billable_size(**kw) / 1e6,
                "cost_usd": client.metadata.get_cost(**kw),
            })
    est = pd.DataFrame(rows)
    label = "OUT-OF-SAMPLE" if oos else "IN-SAMPLE"
    print(f"\nDatabento {dcfg['dataset']} cost estimate, {label} window "
          f"[{start.date()}, {end.date()})  (end exclusive; parent symbols incl. spreads)\n")
    print(est.to_string(index=False, formatters={"records": "{:,}".format,
                                                  "size_mb": "{:,.1f}".format,
                                                  "cost_usd": "${:,.2f}".format}))
    print(f"\nTOTAL: {est.records.sum():,} records, {est.size_mb.sum():,.1f} MB, "
          f"${est.cost_usd.sum():,.2f}\n")
    return est


def _submit_batch_jobs(client, cfg: dict, start, end, dbn_dir: Path) -> dict:
    """Submit one batch job per root x schema, once. Job ids are recorded in jobs.json so a
    re-run downloads the existing job (free for 30 days) instead of buying the data again.

    Batch download is used instead of streaming: the streaming endpoint delivered ~4.5 KB/s
    for these long date ranges. Both are priced identically (checked with get_cost)."""
    dbn_dir.mkdir(parents=True, exist_ok=True)
    jobs_path = dbn_dir / "jobs.json"
    jobs = json.loads(jobs_path.read_text()) if jobs_path.exists() else {}
    dcfg = cfg["databento"]
    for root, parent in dcfg["parents"].items():
        for schema in SCHEMAS:
            key = f"{root}_{schema}"
            if key in jobs or (dbn_dir / f"{key}.dbn.zst").exists():
                continue
            job = client.batch.submit_job(dataset=dcfg["dataset"], symbols=[parent], stype_in="parent",
                                          schema=schema, start=start, end=end, encoding="dbn",
                                          compression="zstd", split_duration="none")
            jobs[key] = {"id": job["id"], "cost_usd": job.get("cost_usd"),
                         "start": str(start), "end_exclusive": str(end)}
            jobs_path.write_text(json.dumps(jobs, indent=2))   # persist after every submit
            print(f"  submitted {key}: job {job['id']}", flush=True)
    return jobs


def _fetch_batch_files(client, jobs: dict, dbn_dir: Path, poll_seconds: int = 20) -> None:
    """Wait for the submitted jobs and download each finished one to <root>_<schema>.dbn.zst."""
    import time
    pending = {k: v["id"] for k, v in jobs.items() if not (dbn_dir / f"{k}.dbn.zst").exists()}
    while pending:
        states = {j["id"]: j["state"] for j in client.batch.list_jobs(states="received,queued,processing,done,expired")}
        for key, job_id in list(pending.items()):
            state = states.get(job_id)
            if state == "expired":
                raise RuntimeError(f"batch job {job_id} ({key}) expired; it must be resubmitted (re-billed)")
            if state != "done":
                continue
            files = client.batch.download(job_id=job_id, output_dir=dbn_dir / "jobs")
            data = [f for f in files if str(f).endswith(".dbn.zst")]
            if len(data) != 1:
                raise RuntimeError(f"{key}: expected one .dbn.zst file, got {files}")
            data[0].rename(dbn_dir / f"{key}.dbn.zst")
            print(f"  downloaded {key}", flush=True)
            del pending[key]
        if pending:
            print(f"  waiting on {len(pending)} job(s): {', '.join(pending)}", flush=True)
            time.sleep(poll_seconds)


def _load_dbn(dbn_dir: Path, root: str, schema: str):
    import databento as db
    return db.DBNStore.from_file(dbn_dir / f"{root}_{schema}.dbn.zst")


def pull_databento(cfg: dict, oos: bool = False) -> None:
    client = _db_client()
    dcfg = cfg["databento"]
    dataset_end = client.metadata.get_dataset_range(dcfg["dataset"])["end"] if oos else None
    start, end = _window(cfg, oos, dataset_end)
    out = _out_dir(oos)
    div = dcfg["price_divisor"]
    dbn_dir = out / "dbn"
    jobs = _submit_batch_jobs(client, cfg, start, end, dbn_dir)
    _fetch_batch_files(client, jobs, dbn_dir)

    for root in dcfg["parents"]:
        # 1) Definitions -> outright futures only (calendar spreads share the parent).
        store = _load_dbn(dbn_dir, root, "definition")
        d = store.to_df()
        d = d[d["instrument_class"] == "F"]
        d = d[[c for c in DEF_COLS if c in d.columns]].copy()
        d.index.name = "ts_recv"
        d = d.reset_index()
        for c in DEF_PRICE_COLS:
            if c in d.columns:
                d[c] = d[c] / div
        outright_ids = set(d["instrument_id"].unique())
        outright_syms = set(d["raw_symbol"].unique())
        d.to_parquet(out / f"{root}_definition.parquet", index=False)
        print(f"  {root} definition: {len(d):,} rows, {len(outright_syms)} outright contracts")

        # 2) Statistics -> outrights, kept stat types; prices to dollars.
        store = _load_dbn(dbn_dir, root, "statistics")
        parts = []
        for chunk in store.to_df(count=2_000_000):
            chunk = chunk[chunk["instrument_id"].isin(outright_ids)
                          & chunk["symbol"].isin(outright_syms)
                          & chunk["stat_type"].isin(KEEP_STAT_TYPES)]
            parts.append(chunk)
        s = pd.concat(parts)
        s.index.name = "ts_recv"
        s = s.reset_index()
        s["price"] = s["price"] / div
        if not oos:
            _assert_before(s.dropna(subset=["ts_ref"]), "ts_ref", oos_start(cfg), f"{root} statistics")
        # Non-positive settlements are placeholders for unsettled far-deferred contracts
        # (2010); contracts.py drops them. Bounds are checked on the rest.
        settle = s[(s["stat_type"] == dcfg["settlement_stat_type"]) & (s["price"] > 0)]
        lo, hi = PRICE_BOUNDS[root]
        inside = settle["price"].between(lo, hi).mean() if len(settle) else 0.0
        if inside < 0.99:
            raise RuntimeError(f"{root}: only {inside:.1%} of settlements within ${lo}-${hi}; "
                               f"check the cents-to-dollars conversion")
        s.to_parquet(out / f"{root}_statistics.parquet", index=False)
        print(f"  {root} statistics: {len(s):,} rows ({len(settle):,} settlement records, "
              f"median ${settle['price'].median():.4f})")

        # 3) Daily OHLCV (UTC-day bars; used for volume / ADV).
        store = _load_dbn(dbn_dir, root, "ohlcv-1d")
        o = store.to_df()
        o = o[o["instrument_id"].isin(outright_ids) & o["symbol"].isin(outright_syms)].copy()
        o.index.name = "ts_event"
        o = o.reset_index()
        for c in ["open", "high", "low", "close"]:
            o[c] = o[c] / div
        if not oos:
            _assert_before(o, "ts_event", oos_start(cfg), f"{root} ohlcv-1d")
        o.to_parquet(out / f"{root}_ohlcv1d.parquet", index=False)
        print(f"  {root} ohlcv-1d: {len(o):,} rows")

        _write_manifest(out, f"databento_{root}", {
            "dataset": dcfg["dataset"], "parent": dcfg["parents"][root], "schemas": SCHEMAS,
            "start": str(start.date()), "end_exclusive": str(end.date()),
            "rows": {"definition": len(d), "statistics": len(s), "ohlcv-1d": len(o)},
        })


# --------------------------------------------------------------------------- NASS

MONTH_NAMES = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
MONTHS = {m: i for i, m in enumerate(MONTH_NAMES, start=1)}
NASS_FIRST_YEAR = 2009   # YoY change in placements needs a year before the first signal (2013)


def _nass_get(cfg: dict, extra: list[tuple]) -> pd.DataFrame:
    params = [("key", _env("NASS_API_KEY")), ("format", "JSON"), *cfg["nass"]["query"].items(), *extra]
    r = requests.get(NASS_URL, params=params, timeout=120)
    if r.status_code != 200:
        sys.exit(f"NASS API error {r.status_code}: {r.text[:500]}")
    return pd.DataFrame(r.json()["data"])


def _nass_fetch(cfg: dict, extra: list[tuple], oos: bool = False) -> pd.DataFrame:
    """Fetch by explicit year (and, in the boundary year, explicit month).

    Quick Stats ignores `year__LE`, and drops `year__LT` when it is combined with
    `year__GE` (tested 2026-10-02), so range operators cannot enforce the OOS cutoff.
    Repeated `year=` and `reference_period_desc=` parameters are honoured, and the
    result is checked again client-side.
    """
    b = oos_start(cfg)
    if oos:
        calls = [[("year", y) for y in range(b.year, pd.Timestamp.now().year + 1)]]
    else:
        calls = [[("year", y) for y in range(NASS_FIRST_YEAR, b.year)]]
        if b.month > 1:
            calls.append([("year", b.year)] + [("reference_period_desc", m) for m in MONTH_NAMES[:b.month - 1]])
    df = pd.concat([_nass_get(cfg, extra + c) for c in calls], ignore_index=True)
    df = df[df["reference_period_desc"].isin(MONTHS)].copy()
    df["month"] = pd.to_datetime(pd.DataFrame({"year": df["year"].astype(int),
                                               "month": df["reference_period_desc"].map(MONTHS),
                                               "day": 1}))
    if not oos and (df["month"] >= b).any():
        raise RuntimeError("NASS returned months on/after oos_start in an in-sample request")
    return df[df["month"] >= b] if oos else df


def probe_nass(cfg: dict) -> None:
    """List every series the configured query returns, so the exact one can be pinned."""
    df = _nass_fetch(cfg, [])
    keys = ["short_desc", "domain_desc", "domaincat_desc", "unit_desc"]
    summary = (df.groupby(keys, dropna=False)
                 .agg(rows=("Value", "size"), first_year=("year", "min"), last_year=("year", "max"))
                 .reset_index())
    pd.set_option("display.width", 250, "display.max_colwidth", 90)
    print(summary.to_string(index=False))
    sample = df[(df["year"] == 2023)][keys[:1] + ["reference_period_desc", "Value"]]
    print("\n2023 values (compare against the published Cattle on Feed reports):")
    print(sample.sort_values(["short_desc", "reference_period_desc"]).to_string(index=False))


def pull_nass(cfg: dict, oos: bool = False) -> None:
    ncfg = cfg["nass"]
    if not ncfg["short_desc"]:
        sys.exit("config.nass.short_desc is not set; run --probe-nass and pin the series first.")
    # Dated by reference month, not release date (Deviation Log).
    df = _nass_fetch(cfg, [("short_desc", ncfg["short_desc"]), ("domaincat_desc", ncfg["domaincat_desc"])], oos)
    df["placements_head"] = df["Value"].str.replace(",", "").astype(int)
    df = df[["month", "placements_head", "short_desc", "domaincat_desc", "load_time"]].sort_values("month")
    if df["month"].duplicated().any():
        raise RuntimeError("NASS: more than one value per month; the series filter is not unique")
    if not oos:
        _assert_before(df, "month", oos_start(cfg), "NASS")
    out = _out_dir(oos)
    df.to_parquet(out / "nass_placements.parquet", index=False)
    _write_manifest(out, "nass", {"short_desc": ncfg["short_desc"], "domaincat_desc": ncfg["domaincat_desc"],
                                  "rows": len(df),
                                  "first_month": str(df["month"].min().date()),
                                  "last_month": str(df["month"].max().date())})
    print(f"  NASS placements: {len(df)} months, {df['month'].min():%Y-%m} to {df['month'].max():%Y-%m}")


# --------------------------------------------------------------------------- CFTC

def pull_cftc(cfg: dict, oos: bool = False) -> None:
    hp = cfg["hedging_pressure"]
    start, end = _window(cfg, oos)
    lo = start if oos else pd.Timestamp("2006-01-01")   # 156-week median needs history before 2013
    where = (f"cftc_contract_market_code='{hp['cftc_code_live_cattle']}' "
             f"AND report_date_as_yyyy_mm_dd >= '{lo:%Y-%m-%d}T00:00:00' "
             f"AND report_date_as_yyyy_mm_dd < '{end:%Y-%m-%d}T00:00:00'")
    params = {"$where": where, "$order": "report_date_as_yyyy_mm_dd", "$limit": 50000,
              "$select": "report_date_as_yyyy_mm_dd,market_and_exchange_names,futonly_or_combined,"
                         "open_interest_all,prod_merc_positions_long,prod_merc_positions_short"}
    r = requests.get(CFTC_URL.format(dataset=hp["cftc_dataset"]), params=params, timeout=120)
    r.raise_for_status()
    df = pd.DataFrame(r.json())
    if df.empty:
        sys.exit("CFTC: no rows returned")
    if set(df["futonly_or_combined"]) != {"FutOnly"}:
        raise RuntimeError(f"CFTC: unexpected report type {set(df['futonly_or_combined'])}")
    df["asof_date"] = pd.to_datetime(df.pop("report_date_as_yyyy_mm_dd")).dt.normalize()
    for c in ["open_interest_all", "prod_merc_positions_long", "prod_merc_positions_short"]:
        df[c] = df[c].astype(int)
    df = df.sort_values("asof_date").reset_index(drop=True)
    if not oos:
        _assert_before(df, "asof_date", oos_start(cfg), "CFTC")
    out = _out_dir(oos)
    df.to_parquet(out / "cftc_live_cattle.parquet", index=False)
    _write_manifest(out, "cftc", {"code": hp["cftc_code_live_cattle"], "rows": len(df),
                                  "first_asof": str(df["asof_date"].min().date()),
                                  "last_asof": str(df["asof_date"].max().date())})
    print(f"  CFTC: {len(df)} weekly reports, as-of {df['asof_date'].min():%Y-%m-%d} "
          f"to {df['asof_date'].max():%Y-%m-%d}")


# --------------------------------------------------------------------------- SPY

def pull_spy(cfg: dict, oos: bool = False) -> None:
    import yfinance as yf
    start, end = _window(cfg, oos)
    h = yf.Ticker(cfg["spy_ticker"]).history(start=f"{start:%Y-%m-%d}", end=f"{end:%Y-%m-%d}",
                                             auto_adjust=True)   # yfinance `end` is exclusive
    if h.empty:
        sys.exit("yfinance returned no SPY data")
    df = pd.DataFrame({"date": h.index.tz_localize(None).normalize(), "close_adj": h["Close"].to_numpy()})
    if not oos:
        _assert_before(df, "date", oos_start(cfg), "SPY")
    out = _out_dir(oos)
    df.to_parquet(out / "spy.parquet", index=False)
    _write_manifest(out, "spy", {"rows": len(df), "first": str(df["date"].min().date()),
                                 "last": str(df["date"].max().date())})
    print(f"  SPY: {len(df)} days, {df['date'].min():%Y-%m-%d} to {df['date'].max():%Y-%m-%d}")


# --------------------------------------------------------------------------- H2 equities

H2_TICKERS = ["TSN", "TXRH", "XLP", "XLY"]


def pull_h2_equities(cfg: dict, oos: bool = False) -> None:
    """Daily split- and dividend-adjusted closes for H2 (HYPOTHESIS_H2.md Section 3).
    Development window 2009-01-01 to oos_start - 1 day; yfinance `end` is exclusive."""
    import yfinance as yf
    start = oos_start(cfg) if oos else pd.Timestamp("2009-01-01")
    end = _window(cfg, oos)[1]
    frames = {}
    for tk in H2_TICKERS:
        h = yf.Ticker(tk).history(start=f"{start:%Y-%m-%d}", end=f"{end:%Y-%m-%d}", auto_adjust=True)
        if h.empty:
            sys.exit(f"yfinance returned no data for {tk}")
        frames[tk] = pd.Series(h["Close"].to_numpy(), index=h.index.tz_localize(None).normalize())
    df = pd.DataFrame(frames).rename_axis("date").reset_index()
    if not oos:
        _assert_before(df, "date", oos_start(cfg), "H2 equities")
    out = _out_dir(oos)
    df.to_parquet(out / "h2_equities.parquet", index=False)
    _write_manifest(out, "h2_equities", {"tickers": H2_TICKERS, "rows": len(df),
                                         "first": str(df["date"].min().date()), "last": str(df["date"].max().date())})
    print(f"  H2 equities: {len(df)} days, {df['date'].min():%Y-%m-%d} to {df['date'].max():%Y-%m-%d}; "
          f"missing values: {int(df[H2_TICKERS].isna().sum().sum())}")


# --------------------------------------------------------------------------- CLI

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--estimate", action="store_true", help="print the Databento cost estimate and exit")
    ap.add_argument("--probe-nass", action="store_true", help="list NASS series for config.nass.query")
    ap.add_argument("--pull", nargs="+", choices=["databento", "nass", "cftc", "spy", "h2", "all"])
    ap.add_argument("--yes", action="store_true", help="confirm the Databento purchase after the estimate")
    args = ap.parse_args()
    cfg = load_config()

    if args.estimate:
        databento_estimate(cfg)
        return
    if args.probe_nass:
        probe_nass(cfg)
        return
    if not args.pull:
        ap.print_help()
        return

    sources = ["databento", "nass", "cftc", "spy"] if "all" in args.pull else args.pull
    if "databento" in sources:
        databento_estimate(cfg)
        if not args.yes:
            sys.exit("Databento pull not confirmed. Re-run with --yes after reviewing the estimate.")
        pull_databento(cfg)
    if "nass" in sources:
        pull_nass(cfg)
    if "cftc" in sources:
        pull_cftc(cfg)
    if "spy" in sources:
        pull_spy(cfg)
    if "h2" in sources:
        pull_h2_equities(cfg)


if __name__ == "__main__":
    main()
