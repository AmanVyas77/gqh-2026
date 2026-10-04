"""config.yaml mirrors HYPOTHESIS.md: fixed values match, provisional keys exist, and no holdout
boundary is set while the specification is provisional. Reads only the two spec files."""
from __future__ import annotations

import re

import pytest

from macro_equity.config import get_key, load_config
from macro_equity.paths import ROOT

HYPOTHESIS = (ROOT / "HYPOTHESIS.md").read_text()
CFG = load_config()

STATEMENT = ("An independent S&P 500 earnings forecast above contemporaneous analyst consensus predicts "
             "higher subsequent equity excess returns. Real-yield and credit-spread changes add predictive "
             "information; one predefined interaction tests whether rate changes alter the earnings relationship.")


def test_hypothesis_statement_verbatim():
    assert STATEMENT in HYPOTHESIS


@pytest.mark.parametrize("key", CFG["provisional_keys"])
def test_provisional_keys_exist(key):
    get_key(CFG, key)


def test_register_ids_match_config():
    """Every P# in the HYPOTHESIS.md register is referenced by a config.yaml comment, and vice versa."""
    register = set(re.findall(r"^\| (P\d+) \|", HYPOTHESIS, flags=re.M))
    in_config = set(re.findall(r"\bP\d+\b", (ROOT / "config.yaml").read_text()))
    assert register == {f"P{i}" for i in range(1, 16)}
    assert register <= in_config


def test_no_holdout_boundary_while_provisional():
    if CFG["spec"]["status"] != "provisional":
        pytest.skip("specification frozen")
    h = CFG["holdout"]
    for k in ("n_eligible", "n_holdout", "first_holdout_decision", "last_development_decision",
              "quarantine_inputs_published_after", "quarantine_prices_after_open_of"):
        assert h[k] is None, k
    assert CFG["data"]["cutoff_date"] is None
    assert CFG["instruments"]["cash_proxy"]["selected"] is None


def test_fixed_values_match_hypothesis():
    assert CFG["ridge"]["lambdas"] == [0.1, 1, 10]
    assert CFG["ridge"]["intercept_penalized"] is False
    assert CFG["portfolio"]["cost_per_leg_bps"] == 5
    assert CFG["portfolio"]["stress_cost_per_leg_bps"] == 10
    assert CFG["portfolio"]["tie_break"] == "retain_current"
    assert CFG["instruments"]["allocations"] == [0, 1]
    assert not CFG["instruments"]["leverage"] and not CFG["instruments"]["shorting"]
    assert CFG["earnings"]["warmup_distinct_quarters"] >= 32
    assert CFG["returns"]["warmup_completed_months"] >= 60
    assert CFG["earnings"]["uses_analyst_data"] is False
    assert CFG["earnings"]["one_training_example_per_quarter"] is True
    assert CFG["holdout"]["fraction"] == 0.20 and CFG["holdout"]["max_decisions"] == 24
    assert CFG["holdout"]["inherited_from_other_projects"] is False
    assert CFG["returns"]["primary"]["inputs"] == ["gap", "real_yield_change", "credit_spread_change"]
    assert len(CFG["trials"]["distinct_specs"]) == 6


def test_inner_validation_fits_inside_warmup():
    assert CFG["earnings"]["inner_validation_min_quarters"] < CFG["earnings"]["warmup_distinct_quarters"]
    assert CFG["returns"]["inner_validation_min_months"] < CFG["returns"]["warmup_completed_months"]


def test_feasibility_block_is_consistent():
    f = CFG["feasibility"]
    assert f["status"] in {"BLOCKED", "FEASIBLE"}
    assert (ROOT / f["report"]).exists()
    if f["status"] == "BLOCKED":
        assert CFG["spec"]["status"] == "provisional", "a BLOCKED spec cannot be frozen"
        assert CFG["holdout"]["first_holdout_decision"] is None
        assert set(f["blocking_items"]) <= set(re.findall(r"^\| (P\d+) \|", HYPOTHESIS, flags=re.M))


def test_amendment_log_ids_are_sequential():
    ids = re.findall(r"^\| (A\d+) \| 2026", HYPOTHESIS, flags=re.M)
    assert ids == [f"A{i}" for i in range(len(ids))]
