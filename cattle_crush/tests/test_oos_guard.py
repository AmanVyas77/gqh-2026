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
