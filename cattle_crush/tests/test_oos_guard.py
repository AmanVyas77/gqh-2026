"""Out-of-sample guard: in-sample paths never return dates on or after oos_start, and the
run_oos.py lock logic refuses a second first-run or a changed config. run_oos.py is not executed."""
import json
import sys
from pathlib import Path

import pytest

from src import contracts, margin, signals
from src.config import oos_start

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data"))
import run_oos  # noqa: E402

needs_data = pytest.mark.skipif(
    not (contracts.RAW / "LE_definition.parquet").exists(), reason="raw data not downloaded")


@needs_data
def test_in_sample_paths_end_before_oos():
    cut = oos_start()
    for r in contracts.ROOTS:
        assert contracts.settlements(r)["date"].max() < cut
        assert contracts.session_high_low(r)["date"].max() < cut
    assert margin.margin_daily()["date"].max() < cut
    assert signals.month_end_signals().index.max() < cut
    assert signals.hedging_pressure()["asof_date"].max() < cut


def test_lock_requires_confirm_final(tmp_path):
    with pytest.raises(SystemExit):
        run_oos.check_lock(False, tmp_path / "oos_lock.json", "abc")
    assert run_oos.check_lock(True, tmp_path / "oos_lock.json", "abc") == "first"


def test_lock_refuses_changed_config(tmp_path):
    lock = tmp_path / "oos_lock.json"
    lock.write_text(json.dumps({"config_sha256": "abc", "timestamp_utc": "2026-10-04T00:00:00+00:00"}))
    assert run_oos.check_lock(False, lock, "abc") == "repeat"
    with pytest.raises(SystemExit):
        run_oos.check_lock(True, lock, "different")


@needs_data
def test_holdout_code_path_on_development_data(tmp_path, monkeypatch):
    """Exercises run_oos.evaluate_holdout end to end on DEVELOPMENT data only, so a coding error
    surfaces before the one-time run. The boundary is moved to 2024-07-01 inside the evaluation
    modules; data/raw/oos points at an empty temp dir (plus a copy of the development H2 file);
    caches and the trial log go to temp paths. No holdout data exists or is read."""
    import shutil

    import pandas as pd

    import src.config as config
    from src import backtest, contracts as ct, h2
    from src.config import load_config

    fake_oos = tmp_path / "oos"
    fake_oos.mkdir()
    shutil.copy(ct.RAW / "h2_equities.parquet", fake_oos / "h2_equities.parquet")
    cut = pd.Timestamp("2024-07-01")
    for mod in (backtest, h2, run_oos):
        monkeypatch.setattr(mod, "oos_start", lambda cfg=None: cut)
    monkeypatch.setattr(ct, "RAW_OOS", fake_oos)
    monkeypatch.setattr(config, "RAW_OOS", fake_oos)
    monkeypatch.setattr(h2, "RAW_OOS", fake_oos)
    monkeypatch.setattr(ct, "PROCESSED", tmp_path / "processed")
    monkeypatch.setenv("CATTLE_TRIAL_LOG", str(tmp_path / "trial_log.csv"))

    perf, curves = run_oos.evaluate_holdout(load_config())
    roles = set(perf["role"])
    assert {"PRIMARY (H1)", "PRIMARY (H2)"} <= roles
    assert (pd.to_datetime(perf["start"]) >= cut).all()
    assert (pd.to_datetime(perf["end"]) < oos_start()).all()      # development data only
    assert {"H1 Variant A", "H2 primary"} <= set(curves)


def test_frozen_paths_check_runs():
    assert isinstance(run_oos.uncommitted_frozen_changes(), list)
