"""Holdout guard, import validation and research log. All frames here are SYNTHETIC test fixtures:
made-up numbers that are never written to data/ or results/ and never reported as research."""
from __future__ import annotations

import copy

import pandas as pd
import pytest

from macro_equity import research_log
from macro_equity.config import load_config
from macro_equity.sources import consensus_import as ci
from macro_equity.sources.guard import HoldoutAccessError, assert_development, boundary, split_development_holdout

CFG = load_config()


def _cfg_with_boundary(ts: str | None) -> dict:
    cfg = copy.deepcopy(CFG)
    cfg["holdout"]["quarantine_inputs_published_after"] = ts
    return cfg


def _synthetic_frame(stamps: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"published": pd.to_datetime(stamps), "x": range(len(stamps))})


def test_guard_fails_closed_without_boundary():
    with pytest.raises(HoldoutAccessError):
        boundary("inputs", _cfg_with_boundary(None))
    with pytest.raises(HoldoutAccessError):
        assert_development(_synthetic_frame(["2015-01-30T16:00:00-05:00"]), "published", "inputs",
                           _cfg_with_boundary(None))


def test_guard_live_config_refuses_while_unset():
    if CFG["holdout"]["quarantine_inputs_published_after"] is not None:
        pytest.skip("boundary frozen")
    with pytest.raises(HoldoutAccessError):
        boundary("inputs")


def test_guard_rejects_rows_after_boundary_and_naive_times():
    cfg = _cfg_with_boundary("2020-06-30T16:00:00-04:00")
    ok = _synthetic_frame(["2020-06-30T16:00:00-04:00", "2020-05-29T16:00:00-04:00"])
    assert_development(ok, "published", "inputs", cfg)
    late = _synthetic_frame(["2020-06-30T16:00:01-04:00"])
    with pytest.raises(HoldoutAccessError):
        assert_development(late, "published", "inputs", cfg)
    naive = pd.DataFrame({"published": pd.to_datetime(["2020-01-31"])})
    with pytest.raises(HoldoutAccessError):
        assert_development(naive, "published", "inputs", cfg)
    with pytest.raises(HoldoutAccessError):
        boundary("inputs", _cfg_with_boundary("2020-06-30"))


def test_split_routes_rows_by_timestamp():
    cfg = _cfg_with_boundary("2020-06-30T16:00:00-04:00")
    dev, hold = split_development_holdout(
        _synthetic_frame(["2020-06-30T15:00:00-04:00", "2020-07-31T16:00:00-04:00"]), "published", "inputs", cfg)
    assert len(dev) == 1 and len(hold) == 1


def _synthetic_consensus(**overrides) -> pd.DataFrame:
    row = {"snapshot_timestamp": "2015-02-27T16:00:00-05:00", "source": "SYNTH", "index": "SPX",
           "target_quarter": "2015Q1", "eps_consensus": 1.0, "eps_basis": "synthetic_basis",
           "aggregation": "synthetic", "n_companies": 1, "notes": "synthetic fixture"}
    row.update(overrides)
    return pd.DataFrame([row])


def test_consensus_validator_accepts_template_shape():
    df = ci.validate_consensus(_synthetic_consensus())
    assert str(df["snapshot_timestamp"].dt.tz) != "None"


@pytest.mark.parametrize("override", [{"snapshot_timestamp": "2015-02-27 16:00"},
                                      {"target_quarter": "Q1 2015"},
                                      {"target_quarter": "next_quarter"},
                                      {"index": "NDX"}])
def test_consensus_validator_rejects_bad_rows(override):
    with pytest.raises(ci.ImportError_):
        ci.validate_consensus(_synthetic_consensus(**override))


def test_consensus_validator_rejects_mixed_basis_and_duplicates():
    mixed = pd.concat([_synthetic_consensus(), _synthetic_consensus(target_quarter="2015Q2", eps_basis="other")])
    with pytest.raises(ci.ImportError_):
        ci.validate_consensus(mixed)
    with pytest.raises(ci.ImportError_):
        ci.validate_consensus(pd.concat([_synthetic_consensus(), _synthetic_consensus()]))


def test_actuals_must_match_consensus_basis():
    act = pd.DataFrame([{"quarter": "2014Q4", "eps_actual": 1.0, "eps_basis": "gaap", "source": "SYNTH",
                         "published_timestamp": "2015-03-31T16:00:00-04:00", "vintage": "first_release",
                         "notes": "synthetic fixture"}])
    with pytest.raises(ci.ImportError_):
        ci.validate_actuals(act, {"synthetic_basis"})


def test_research_log_is_append_only(tmp_path, monkeypatch):
    path = tmp_path / "log.csv"
    monkeypatch.setenv("MACRO_EQUITY_RESEARCH_LOG", str(path))
    research_log.append(2, "search", "s", "a", "o", True)
    first = path.read_text()
    research_log.append(2, "inspect", "s2", "a2", "o2", False)
    assert path.read_text().startswith(first)
    assert len(path.read_text().strip().splitlines()) == 3
    with pytest.raises(ValueError):
        research_log.append(2, "bogus", "s", "a", "o", True)
