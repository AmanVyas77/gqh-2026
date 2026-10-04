"""Warmup / development / holdout split for equity_pairs.

The split is computed from an exchange session calendar (XNYS holiday rules via
exchange_calendars), not from prices, so the holdout boundary can be fixed
before any price is downloaded.

Convention (frozen in config.yaml, timeline.*). Sessions are XNYS sessions,
identified by their New York calendar date.
  1. Sessions run from the first session on/after the target data start through
     the last session strictly before the as-of date (both ends inclusive).
  2. Warmup: the first formation ends at the first month-end session that has at
     least `formation_price_obs` (127) sessions from the data start, giving 126
     daily returns.
  3. Evaluation sessions: strictly after the first formation end, through
     evaluation_end inclusive. N = their count.
  4. Holdout = the last H evaluation sessions, exactly, where
     H = min(ceil(fraction * N), count of evaluation sessions in the half-open
     window (evaluation_end - max_years calendar years, evaluation_end]).
     No month snapping: monthly formation never lengthens the holdout.
  5. Development = [evaluation_start, development_end], holdout =
     [holdout_start, holdout_end], both inclusive; development_end is the session
     immediately before holdout_start. A predetermined market-on-close liquidation
     on development_end leaves the holdout flat.

Run `python split.py` to print the provisional split recorded in config.yaml.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import pandas as pd


@dataclass(frozen=True)
class Split:
    data_start: str
    first_formation_end: str
    evaluation_start: str
    evaluation_end: str
    n_evaluation_sessions: int
    holdout_sessions_fraction_rule: int
    holdout_sessions_years_rule: int
    binding_rule: str
    holdout_start: str
    holdout_end: str
    n_holdout_sessions: int
    development_start: str
    development_end: str
    n_development_sessions: int
    n_development_months: int
    pilot_formation_ends: tuple[str, ...]


def _iso(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m-%d")


def month_end_sessions(sessions: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Sessions whose next session falls in a different month.

    The final session is never treated as a month end, because the calendar is
    truncated at the as-of date and that month may be incomplete.
    """
    months = sessions.to_period("M")
    is_end = months[:-1] != months[1:]
    return sessions[:-1][is_end]


def compute_split(
    sessions,
    *,
    formation_price_obs: int = 127,
    fraction: float = 0.20,
    max_years: int = 2,
    n_pilot_formations: int = 12,
) -> Split:
    s = pd.DatetimeIndex(sessions).normalize().unique().sort_values()
    if len(s) < formation_price_obs + 1:
        raise ValueError("calendar shorter than one formation window")

    month_ends = month_end_sessions(s)
    pos = s.get_indexer(month_ends)
    warm = month_ends[pos >= formation_price_obs - 1]
    if len(warm) == 0:
        raise ValueError("no month-end session completes the warmup")
    first_formation_end = warm[0]

    ev = s[s > first_formation_end]
    n_eval = len(ev)
    end = ev[-1]
    h_frac = math.ceil(fraction * n_eval)
    h_years = int((ev > end - pd.DateOffset(years=max_years)).sum())
    h = min(h_frac, h_years)
    binding = "fraction" if h_frac < h_years else ("years" if h_years < h_frac else "tie")

    holdout_start = ev[-h]
    if holdout_start <= first_formation_end:
        raise ValueError("holdout would overlap the warmup")

    dev = ev[ev < holdout_start]
    hold = ev[ev >= holdout_start]
    dev_month_ends = month_ends[(month_ends >= first_formation_end) & (month_ends <= dev[-1])]
    pilot = tuple(_iso(t) for t in dev_month_ends[:n_pilot_formations])

    return Split(
        data_start=_iso(s[0]),
        first_formation_end=_iso(first_formation_end),
        evaluation_start=_iso(ev[0]),
        evaluation_end=_iso(end),
        n_evaluation_sessions=n_eval,
        holdout_sessions_fraction_rule=h_frac,
        holdout_sessions_years_rule=h_years,
        binding_rule=binding,
        holdout_start=_iso(holdout_start),
        holdout_end=_iso(hold[-1]),
        n_holdout_sessions=len(hold),
        development_start=_iso(dev[0]),
        development_end=_iso(dev[-1]),
        n_development_sessions=len(dev),
        n_development_months=dev.to_period("M").nunique(),
        pilot_formation_ends=pilot,
    )


def xnys_sessions(data_start: str, as_of_date: str) -> pd.DatetimeIndex:
    """XNYS sessions from data_start through the last session strictly before as_of_date."""
    import exchange_calendars as xc

    cal = xc.get_calendar("XNYS", start="2005-01-01")
    last = pd.Timestamp(as_of_date) - pd.Timedelta(days=1)
    return cal.sessions_in_range(data_start, last).tz_localize(None)


def split_from_config(cfg: dict) -> Split:
    tl = cfg["timeline"]
    ho = tl["holdout"]
    return compute_split(
        xnys_sessions(tl["target_data_start"], tl["as_of_date"]),
        formation_price_obs=tl["formation_price_obs"],
        fraction=ho["fraction"],
        max_years=ho["max_calendar_years"],
        n_pilot_formations=cfg["pilot"]["thresholds"]["n_formations"],
    )


if __name__ == "__main__":
    import json

    from guard import load_config

    print(json.dumps(asdict(split_from_config(load_config())), indent=2))
