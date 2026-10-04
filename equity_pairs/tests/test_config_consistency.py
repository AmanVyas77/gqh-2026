"""Configuration consistency: pre-registered values, internal logic, hashes, log format."""
import copy
import csv
import hashlib
import json

import pandas as pd
import pytest

from guard import PROJECT_DIR, load_config
from spec import SpecConflictError, conflicts, get_path, require_consistent, validate
from split import split_from_config

CFG = load_config()
LOG_PATH = PROJECT_DIR / "research_log.csv"
LOG_HEADER = ["timestamp_utc", "timestamp_ny", "prompt", "event_type", "description", "artifact", "sha256"]
EVENT_TYPES = {"setup", "environment", "source_query", "specification", "amendment",
               "snapshot", "incidental_exposure", "test", "decision"}

# Prompt 1 pre-registration. Change a value here only together with a new snapshot
# and a research_log.csv amendment row.
PREREGISTERED = {
    "timeline.target_data_start": "2015-01-01",
    "timeline.as_of_date": "2026-10-03",
    "timeline.formation_price_obs": 127,
    "timeline.formation_return_obs": 126,
    "timeline.reform_frequency": "monthly",
    "timeline.min_development_months": 36,
    "timeline.holdout.fraction": 0.20,
    "timeline.holdout.max_calendar_years": 2,
    "universe.eligibility.complete_price_obs": 127,
    "universe.eligibility.min_formation_end_raw_close": 5.0,
    "universe.eligibility.min_median_dollar_volume": 20_000_000,
    "universe.eligibility.exclude_same_issuer_pairs": True,
    "universe.eligibility.uses_future_information": False,
    "features.pca.method": "svd",
    "features.pca.n_components": 5,
    "features.pca.whitening": False,
    "features.pca.shrinkage": False,
    "features.pca.market_factor_removal": False,
    "features.pca.explained_variance_tuning": False,
    "clustering.objects": "stocks",
    "clustering.distance": "euclidean",
    "clustering.linkage": "average",
    "clustering.cut_distance": 0.7,
    "candidates.neighbors_per_stock": 3,
    "screening.cointegration_test.method": "augmented_engle_granger",
    "screening.cointegration_test.trend": "c",
    "screening.cointegration_test.maxlag": 5,
    "screening.cointegration_test.autolag": "aic",
    "screening.multiple_testing.method": "benjamini_hochberg",
    "screening.multiple_testing.q": 0.05,
    "screening.pass_rules.max_bh_adjusted_p": 0.05,
    "screening.pass_rules.beta_min": 0.25,
    "screening.pass_rules.beta_max": 4.0,
    "screening.pass_rules.half_life.min_sessions": 2,
    "screening.pass_rules.half_life.max_sessions": 20,
    "portfolio.max_pairs": 10,
    "portfolio.shared_stocks": False,
    "portfolio.per_pair_gross_max_nav": 0.10,
    "portfolio.total_gross_max_nav": 1.00,
    "trading.entry_abs_z": 2.0,
    "trading.exit_abs_z": 0.5,
    "trading.stop_abs_z": 4.0,
    "trading.max_holding_sessions": 20,
    "trading.signal_time": "close",
    "trading.fill_time": "next_session_open",
    "costs.transaction_bps_per_traded_dollar_per_leg": 10,
    "costs.short_borrow_annual_rate": 0.03,
    "costs.stress_multiplier": 2.0,
    "pilot.scope": "formation_diagnostics_only",
    "pilot.timebox_minutes": 45,
    "pilot.source_discovery_timebox_minutes": 15,
    "pilot.thresholds.n_formations": 12,
    "pilot.thresholds.min_eligible_stocks": 300,
    "pilot.thresholds.max_formations_below_min_eligible": 6,
    "pilot.thresholds.min_pca_pairs": 5,
    "pilot.thresholds.min_formations_with_min_pca_pairs": 6,
    "pilot.thresholds.redundancy_overlap_share": 0.90,
    "pilot.thresholds.redundancy_min_formations": 6,
    "validation.confirmatory_sample": "holdout",
}


@pytest.mark.parametrize("path,value", sorted(PREREGISTERED.items()))
def test_preregistered_value(path, value):
    assert get_path(CFG, path) == value


def test_robustness_set_is_exactly_the_predeclared_four():
    got = {(v["path"], v["value"]) for v in CFG["robustness"]["variants"]}
    assert got == {
        ("features.pca.n_components", 4),
        ("features.pca.n_components", 6),
        ("trading.entry_abs_z", 1.8),
        ("trading.entry_abs_z", 2.2),
    }


def test_config_is_internally_consistent_and_matches_hypothesis():
    assert validate(CFG) == []
    assert conflicts(CFG, (PROJECT_DIR / "HYPOTHESIS.md").read_text()) == []


def test_config_hypothesis_conflict_fails_closed():
    cfg = copy.deepcopy(CFG)
    cfg["clustering"]["cut_distance"] = 0.8
    with pytest.raises(SpecConflictError):
        require_consistent(cfg)


def test_recorded_dates_match_calendar_split():
    sp = split_from_config(CFG)
    tl, ho, dev = CFG["timeline"], CFG["timeline"]["holdout"], CFG["timeline"]["development"]
    assert (tl["first_formation_end"], tl["evaluation_start"], tl["evaluation_end"]) == (
        sp.first_formation_end, sp.evaluation_start, sp.evaluation_end)
    assert tl["n_evaluation_sessions"] == sp.n_evaluation_sessions
    assert (ho["sessions_fraction_rule"], ho["sessions_years_rule"]) == (
        sp.holdout_sessions_fraction_rule, sp.holdout_sessions_years_rule)
    assert (ho["start"], ho["end"], ho["n_sessions"]) == (
        sp.holdout_start, sp.holdout_end, sp.n_holdout_sessions)
    assert ho["binding_rule"] == sp.binding_rule
    assert (dev["start"], dev["end"], dev["n_sessions"], dev["n_months"]) == (
        sp.development_start, sp.development_end, sp.n_development_sessions, sp.n_development_months)
    assert tuple(CFG["pilot"]["provisional_formation_ends"]) == sp.pilot_formation_ends


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _log_rows():
    with open(LOG_PATH, newline="") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("name", ["config.yaml", "HYPOTHESIS.md"])
def test_live_file_hash_is_logged(name):
    logged = {r["sha256"] for r in _log_rows()}
    assert _sha256(PROJECT_DIR / name) in logged, (
        f"{name} differs from every logged version: record an amendment in research_log.csv")


def test_snapshots_match_their_manifests():
    manifests = sorted(PROJECT_DIR.glob("snapshots/*/MANIFEST.json"))
    assert manifests, "no snapshots found"
    for m in manifests:
        for fname, digest in json.loads(m.read_text())["files"].items():
            assert _sha256(m.parent / fname) == digest, f"{m.parent.name}/{fname} altered"


def test_research_log_is_well_formed():
    with open(LOG_PATH, newline="") as f:
        assert next(csv.reader(f)) == LOG_HEADER
    rows = _log_rows()
    utc = pd.to_datetime([r["timestamp_utc"] for r in rows], format="%Y-%m-%dT%H:%M:%SZ")
    assert utc.is_monotonic_increasing, "log rows must be appended in time order"
    assert {r["event_type"] for r in rows} <= EVENT_TYPES
    assert all(r["description"] for r in rows)
