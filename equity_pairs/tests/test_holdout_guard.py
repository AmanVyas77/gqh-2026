"""Fail-closed holdout guard. Uses only dates; no market data."""
import copy

import pandas as pd
import pytest

from guard import HoldoutGuardError, check_dates, check_request, download_limit, load_config

LIVE = load_config()


def _cfg(status="frozen", start="2024-10-03", last="2024-10-02"):
    cfg = copy.deepcopy(LIVE)
    cfg["timeline"]["boundary_status"] = status
    cfg["timeline"]["holdout"]["start"] = start
    cfg["data"]["max_download_date"] = last
    return cfg


def test_live_config_is_closed_while_boundary_not_frozen():
    if LIVE["timeline"]["boundary_status"] == "frozen":
        pytest.skip("boundary has been frozen")
    with pytest.raises(HoldoutGuardError):
        check_request("2015-02-01", end_inclusive=True)
    with pytest.raises(HoldoutGuardError):
        check_dates(pd.DatetimeIndex(["2015-01-02"]))


@pytest.mark.parametrize("status", ["unresolved", "provisional", None, "FROZEN", "open"])
def test_any_status_other_than_frozen_refuses(status):
    with pytest.raises(HoldoutGuardError):
        check_request("2015-02-01", end_inclusive=True, cfg=_cfg(status=status))


@pytest.mark.parametrize("start,last", [(None, "2024-10-02"), ("2024-10-03", None),
                                        ("2024-10-03", "2024-10-03"), ("2024-10-03", "2024-10-04")])
def test_frozen_but_incomplete_or_inverted_boundary_refuses(start, last):
    with pytest.raises(HoldoutGuardError):
        download_limit(_cfg(start=start, last=last))


def test_missing_config_file_refuses(tmp_path):
    with pytest.raises((HoldoutGuardError, FileNotFoundError)):
        load_config(tmp_path / "absent.yaml")


@pytest.mark.parametrize("end,inclusive,ok", [
    ("2024-10-02", True, True),
    ("2024-10-03", True, False),
    ("2024-10-03", False, True),    # yfinance-style exclusive end
    ("2024-10-04", False, False),
    ("2026-10-02", True, False),
])
def test_request_end_dates(end, inclusive, ok):
    cfg = _cfg()
    if ok:
        check_request(end, end_inclusive=inclusive, cfg=cfg)
    else:
        with pytest.raises(HoldoutGuardError):
            check_request(end, end_inclusive=inclusive, cfg=cfg)


def test_returned_dates_are_checked_after_download():
    cfg = _cfg()
    check_dates(pd.bdate_range("2015-01-02", "2024-10-02"), cfg=cfg)
    with pytest.raises(HoldoutGuardError):
        check_dates(pd.bdate_range("2024-09-25", "2024-10-03"), cfg=cfg)


def test_timezone_aware_dates_use_new_york_calendar_date():
    cfg = _cfg()
    ny = pd.DatetimeIndex(["2024-10-02 16:00"]).tz_localize("America/New_York")
    check_dates(ny, cfg=cfg)
    check_dates(ny.tz_convert("UTC"), cfg=cfg)   # 20:00 UTC is still 2024-10-02 in New York
    with pytest.raises(HoldoutGuardError):
        check_dates(pd.DatetimeIndex(["2024-10-03 09:30"]).tz_localize("America/New_York"), cfg=cfg)
