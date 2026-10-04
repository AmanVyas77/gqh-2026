"""Split convention on synthetic business-day calendars (implementation checks only)."""
import math

import pandas as pd

from split import compute_split, month_end_sessions


def _check_invariants(sessions, sp, fraction=0.20, years=2, obs=127):
    s = pd.DatetimeIndex(sessions)
    ffe = pd.Timestamp(sp.first_formation_end)
    # warmup: first month end with >= 127 sessions; the previous month end has fewer
    me = month_end_sessions(s)
    assert s.get_loc(ffe) >= obs - 1
    earlier = me[me < ffe]
    assert len(earlier) == 0 or s.get_loc(earlier[-1]) < obs - 1
    ev = s[s > ffe]
    assert sp.n_evaluation_sessions == len(ev)
    assert sp.holdout_sessions_fraction_rule == math.ceil(fraction * len(ev))
    assert sp.holdout_sessions_years_rule == int((ev > ev[-1] - pd.DateOffset(years=years)).sum())
    rule = min(sp.holdout_sessions_fraction_rule, sp.holdout_sessions_years_rule)
    hs = pd.Timestamp(sp.holdout_start)
    # holdout is exactly the last `rule` evaluation sessions (no month snapping)
    assert sp.n_holdout_sessions == rule and hs == ev[-rule]
    assert s[s.get_loc(hs) - 1] == pd.Timestamp(sp.development_end)
    assert sp.n_development_sessions + sp.n_holdout_sessions == len(ev)


def test_long_history_binds_on_two_years():
    s = pd.bdate_range("2008-01-02", "2020-06-15")   # > 10 post-warmup years
    sp = compute_split(s)
    _check_invariants(s, sp)
    assert sp.binding_rule == "years"


def test_short_history_binds_on_twenty_percent():
    s = pd.bdate_range("2017-01-02", "2020-06-15")
    sp = compute_split(s)
    _check_invariants(s, sp)
    assert sp.binding_rule == "fraction"


def test_final_truncated_month_is_not_a_month_end():
    s = pd.bdate_range("2020-01-01", "2020-03-11")
    assert pd.Timestamp("2020-03-11") not in month_end_sessions(s)
    assert list(month_end_sessions(s)) == [pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-28")]


def test_pilot_formations_are_twelve_consecutive_month_ends_from_warmup():
    s = pd.bdate_range("2015-01-02", "2020-06-15")
    sp = compute_split(s)
    ends = pd.DatetimeIndex(sp.pilot_formation_ends)
    assert len(ends) == 12 and ends[0] == pd.Timestamp(sp.first_formation_end)
    months = [p.ordinal for p in ends.to_period("M")]
    assert months == list(range(months[0], months[0] + 12))
    assert set(ends) <= set(month_end_sessions(s))
