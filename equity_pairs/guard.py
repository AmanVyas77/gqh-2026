"""Fail-closed holdout guard.

Every price loader in this project must:
  1. call `check_request(end, end_inclusive=...)` before contacting a source, and
  2. call `check_dates(returned_dates)` on whatever the source returned.

Both raise HoldoutGuardError unless config.yaml has timeline.boundary_status ==
"frozen" with a holdout start and a max download date strictly before it, and the
config agrees with HYPOTHESIS.md's spec-check block (spec.require_consistent).
While the boundary is "unresolved" or "provisional", every download is refused.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from spec import require_consistent

PROJECT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_DIR / "config.yaml"
BOUNDARY_STATUSES = ("unresolved", "provisional", "frozen")


class HoldoutGuardError(RuntimeError):
    """A request or dataset could touch the quarantined holdout."""


def load_config(path: Path | str = CONFIG_PATH) -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise HoldoutGuardError(f"{path} did not parse to a mapping")
    return cfg


def _date(x) -> pd.Timestamp:
    ts = pd.Timestamp(x)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("America/New_York").tz_localize(None)
    return ts.normalize()


def download_limit(cfg: dict | None = None) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return (last allowed date, holdout start). Raises unless the boundary is frozen."""
    cfg = load_config() if cfg is None else cfg
    try:
        require_consistent(cfg)
    except Exception as exc:  # any inconsistency or unreadable spec keeps loaders closed
        raise HoldoutGuardError(f"spec check failed: {exc}") from exc
    tl = cfg.get("timeline") or {}
    status = tl.get("boundary_status")
    if status not in BOUNDARY_STATUSES:
        raise HoldoutGuardError(f"unknown boundary_status {status!r}; refusing")
    if status != "frozen":
        raise HoldoutGuardError(
            f"holdout boundary is {status!r}; loaders stay closed until it is frozen"
        )
    start = (tl.get("holdout") or {}).get("start")
    last = (cfg.get("data") or {}).get("max_download_date")
    if not start or not last:
        raise HoldoutGuardError("frozen boundary is missing holdout.start or data.max_download_date")
    start, last = _date(start), _date(last)
    if last >= start:
        raise HoldoutGuardError(f"max_download_date {last.date()} is not before holdout start {start.date()}")
    return last, start


def check_request(end, *, end_inclusive: bool, cfg: dict | None = None) -> None:
    """Refuse a download whose last requested date could reach the holdout.

    end_inclusive: whether the provider returns rows dated `end` (yfinance: False).
    """
    last_allowed, _ = download_limit(cfg)
    last_requested = _date(end) if end_inclusive else _date(end) - pd.Timedelta(days=1)
    if last_requested > last_allowed:
        raise HoldoutGuardError(
            f"request reaches {last_requested.date()}, past max_download_date {last_allowed.date()}"
        )


def check_dates(dates, cfg: dict | None = None) -> None:
    """Refuse any returned dataset containing a date after the download limit."""
    last_allowed, _ = download_limit(cfg)
    idx = pd.DatetimeIndex(dates)
    if idx.tz is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    if len(idx) and idx.normalize().max() > last_allowed:
        raise HoldoutGuardError(
            f"data contains {idx.max().date()}, past max_download_date {last_allowed.date()}"
        )
