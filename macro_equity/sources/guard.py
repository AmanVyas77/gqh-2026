"""Holdout guard (HYPOTHESIS.md §9): development code may only see development observations.

Fails closed: while the holdout boundary is unset (spec provisional or BLOCKED), every guarded
load refuses rather than guessing a boundary. Boundaries come from config.yaml `holdout`:
  quarantine_inputs_published_after   signal inputs published after this timestamp are holdout
  quarantine_prices_after_open_of     asset prices after this execution open are holdout
"""
from __future__ import annotations

import pandas as pd

from macro_equity.config import load_config

KINDS = {"inputs": "quarantine_inputs_published_after", "prices": "quarantine_prices_after_open_of"}


class HoldoutAccessError(RuntimeError):
    """Raised when development code would touch holdout observations or no boundary is set."""


def boundary(kind: str, cfg: dict | None = None) -> pd.Timestamp:
    cfg = cfg if cfg is not None else load_config()
    value = cfg["holdout"][KINDS[kind]]
    if value is None:
        raise HoldoutAccessError(f"holdout boundary for {kind} is not set (spec status "
                                 f"{cfg['spec']['status']!r}); refusing to load")
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        raise HoldoutAccessError(f"holdout boundary for {kind} must be timezone-aware: {value}")
    return ts


def _timestamps(df: pd.DataFrame, col: str) -> pd.Series:
    ts = pd.to_datetime(df[col])
    if ts.dt.tz is None:
        raise HoldoutAccessError(f"column {col} must be timezone-aware")
    return ts


def assert_development(df: pd.DataFrame, col: str, kind: str, cfg: dict | None = None) -> pd.DataFrame:
    """Return df unchanged if every timestamp is on or before the boundary; otherwise refuse."""
    cut = boundary(kind, cfg)
    late = int((_timestamps(df, col) > cut).sum())
    if late:
        raise HoldoutAccessError(f"{late} rows in {col} are after the {kind} boundary {cut}")
    return df


def split_development_holdout(df: pd.DataFrame, col: str, kind: str,
                              cfg: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """For acquisition and imports only: route rows to development or quarantine without computing on them."""
    cut = boundary(kind, cfg)
    late = _timestamps(df, col) > cut
    return df[~late].copy(), df[late].copy()
