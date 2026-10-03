"""Reproduce every in-sample number in the note. In-sample only: nothing dated on or after
oos_start is loaded here (see run_oos.py for the one-time out-of-sample run).

Usage: python run_all.py [--yes]   (--yes confirms the Databento purchase if raw data is missing)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "data"))

import audit  # noqa: E402
import download  # noqa: E402
from src import margin  # noqa: E402
from src.config import PROCESSED, RAW, RESULTS, load_config  # noqa: E402

RAW_FILES = {
    "databento": [f"{r}_{k}.parquet" for r in ("LE", "GF", "ZC") for k in ("definition", "statistics", "ohlcv1d")],
    "nass": ["nass_placements.parquet"],
    "cftc": ["cftc_live_cattle.parquet"],
    "spy": ["spy.parquet"],
}


def ensure_data(cfg: dict, yes: bool) -> None:
    """Download any in-sample source whose raw files are missing."""
    for source, files in RAW_FILES.items():
        if all((RAW / f).exists() for f in files):
            continue
        print(f"[data] {source} missing; downloading")
        if source == "databento":
            download.databento_estimate(cfg)
            if not yes:
                sys.exit("Databento data must be purchased; review the estimate and re-run with --yes.")
            download.pull_databento(cfg)
        else:
            getattr(download, f"pull_{source}")(cfg)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yes", action="store_true", help="confirm the Databento purchase if raw data is missing")
    args = ap.parse_args()
    cfg = load_config()

    ensure_data(cfg, args.yes)
    print("\n[1] Data audit")
    audit.main()

    print("\n[2] Feeding margin (primary spec)")
    daily = margin.margin_daily()
    me = margin.month_end(daily)
    PROCESSED.mkdir(parents=True, exist_ok=True)          # derived from licensed prices: not committed
    daily.to_parquet(PROCESSED / "margin_daily.parquet", index=False)
    me.to_parquet(PROCESSED / "margin_month_end.parquet", index=False)
    (RESULTS / "figures").mkdir(parents=True, exist_ok=True)
    margin.plot_margin(daily, RESULTS / "figures" / "margin.png")
    m = me["margin"]
    print(f"{len(daily)} daily and {len(me)} month-end values, {me['date'].min():%Y-%m} to {me['date'].max():%Y-%m}; "
          f"B = {daily.attrs['B']:.4f} bu; month-end M_t mean ${m.mean():,.0f}, sd ${m.std():,.0f}, "
          f"range ${m.min():,.0f} to ${m.max():,.0f} per head")


if __name__ == "__main__":
    main()
