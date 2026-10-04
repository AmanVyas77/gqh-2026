"""Validate a licensed consensus / actual-EPS export against the templates in data/templates/.

Validation reads schema and coverage only: timestamps, quarter labels, basis, duplicates and
counts. It computes nothing that relates consensus to outcomes. Holdout rows are routed to
data/holdout/ by the guard and never summarized beyond row counts.

Usage (from the repository root):
  python -m macro_equity.sources.consensus_import data/imports/consensus.csv data/imports/actuals.csv
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from macro_equity.paths import DATA, ROOT

TEMPLATES = DATA / "templates"
QUARTER = re.compile(r"^\d{4}Q[1-4]$")


class ImportError_(ValueError):
    """The export does not match the template."""


def _columns(name: str) -> list[str]:
    return (TEMPLATES / name).read_text().strip().split(",")


def _aware(df: pd.DataFrame, col: str) -> pd.Series:
    try:
        ts = pd.to_datetime(df[col], utc=False, format="ISO8601")
    except (ValueError, TypeError) as e:
        raise ImportError_(f"{col}: unparseable timestamp ({e})") from e
    if ts.dt.tz is None:
        raise ImportError_(f"{col}: timestamps must carry a UTC offset")
    return ts


def validate_consensus(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in _columns("consensus_snapshots_template.csv") if c not in df.columns]
    if missing:
        raise ImportError_(f"missing columns: {missing}")
    df = df.copy()
    df["snapshot_timestamp"] = _aware(df, "snapshot_timestamp")
    bad_q = ~df["target_quarter"].astype(str).str.match(QUARTER)
    if bad_q.any():
        raise ImportError_(f"target_quarter must be YYYYQn: {df.loc[bad_q, 'target_quarter'].head().tolist()}")
    if (df["index"] != "SPX").any():
        raise ImportError_("index must be SPX")
    if df.groupby("source")["eps_basis"].nunique().gt(1).any():
        raise ImportError_("one source mixes EPS bases")
    df["eps_consensus"] = pd.to_numeric(df["eps_consensus"], errors="raise")
    if df.duplicated(["source", "snapshot_timestamp", "target_quarter"]).any():
        raise ImportError_("duplicate (source, snapshot_timestamp, target_quarter) rows")
    return df


def validate_actuals(df: pd.DataFrame, consensus_basis: set[str]) -> pd.DataFrame:
    missing = [c for c in _columns("eps_actuals_template.csv") if c not in df.columns]
    if missing:
        raise ImportError_(f"missing columns: {missing}")
    df = df.copy()
    df["published_timestamp"] = _aware(df, "published_timestamp")
    if (~df["quarter"].astype(str).str.match(QUARTER)).any():
        raise ImportError_("quarter must be YYYYQn")
    if not set(df["eps_basis"]) <= consensus_basis:
        raise ImportError_(f"actuals basis {sorted(set(df['eps_basis']))} differs from consensus {sorted(consensus_basis)}")
    df["eps_actual"] = pd.to_numeric(df["eps_actual"], errors="raise")
    return df


def coverage(cons: pd.DataFrame, act: pd.DataFrame) -> dict:
    """Counts and dates only, no values."""
    ts = cons["snapshot_timestamp"]
    months = ts.dt.tz_convert("America/New_York").dt.to_period("M")
    full = pd.period_range(months.min(), months.max(), freq="M")
    first_release = act.sort_values("published_timestamp").drop_duplicates("quarter")
    return {"consensus_first_snapshot": str(ts.min()), "consensus_last_snapshot": str(ts.max()),
            "consensus_months_with_snapshot": int(months.nunique()),
            "consensus_months_missing": [str(m) for m in full.difference(pd.PeriodIndex(months.unique()))],
            "consensus_distinct_target_quarters": int(cons["target_quarter"].nunique()),
            "actuals_first_quarter": str(first_release["quarter"].min()),
            "actuals_last_quarter": str(first_release["quarter"].max()),
            "actuals_distinct_quarters": int(first_release["quarter"].nunique())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("consensus", type=Path)
    ap.add_argument("actuals", type=Path)
    args = ap.parse_args()
    cons = validate_consensus(pd.read_csv(ROOT.parent / args.consensus if not args.consensus.is_absolute() else args.consensus))
    act = validate_actuals(pd.read_csv(ROOT.parent / args.actuals if not args.actuals.is_absolute() else args.actuals),
                           set(cons["eps_basis"]))
    for k, v in coverage(cons, act).items():
        print(f"{k}: {v}")
    print("Schema valid. Splitting into data/dev and data/holdout needs the frozen boundary (sources.guard).")


if __name__ == "__main__":
    main()
