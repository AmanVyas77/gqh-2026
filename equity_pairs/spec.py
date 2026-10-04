"""Consistency checks for config.yaml.

validate(cfg)            -> internal problems in the config (list of strings)
conflicts(cfg, text)     -> disagreements with HYPOTHESIS.md's `spec-check` block
require_consistent(cfg)  -> raises SpecConflictError on either; pipelines call this
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import yaml

HYPOTHESIS_PATH = Path(__file__).resolve().parent / "HYPOTHESIS.md"
_BLOCK = re.compile(r"```yaml spec-check\n(.*?)```", re.S)


class SpecConflictError(RuntimeError):
    """Config and operational hypothesis disagree, or the config is inconsistent."""

REQUIRED_SECTIONS = (
    "project", "deadline", "timeline", "universe", "data", "features", "clustering",
    "candidates", "screening", "portfolio", "trading", "costs", "pilot", "validation",
    "robustness", "evaluation", "synthetic",
)


def get_path(cfg: dict, path: str):
    node = cfg
    for key in path.split("."):
        node = node[key]
    return node


def validate(cfg: dict) -> list[str]:
    missing = [s for s in REQUIRED_SECTIONS if s not in cfg]
    if missing:
        return [f"missing sections: {missing}"]
    errs: list[str] = []

    def need(cond: bool, msg: str) -> None:
        if not cond:
            errs.append(msg)

    tl = cfg["timeline"]
    ho, dev = tl["holdout"], tl["development"]
    need(tl["formation_price_obs"] == tl["formation_return_obs"] + 1, "price obs must equal return obs + 1")
    need(0 < ho["fraction"] < 1, "holdout fraction must be in (0, 1)")
    need(tl["boundary_status"] in ("unresolved", "provisional", "frozen"), "bad boundary_status")
    if tl["boundary_status"] != "unresolved":
        d = {k: pd.Timestamp(v) for k, v in {
            "ffe": tl["first_formation_end"], "es": tl["evaluation_start"], "ee": tl["evaluation_end"],
            "ds": dev["start"], "de": dev["end"], "hs": ho["start"], "he": ho["end"],
            "mdd": cfg["data"]["max_download_date"],
        }.items()}
        need(d["ffe"] < d["es"] == d["ds"] <= d["de"] < d["hs"] <= d["he"] == d["ee"],
             "timeline dates out of order")
        need(d["mdd"] == d["de"], "max_download_date must equal development.end")
        need(d["ee"] < pd.Timestamp(tl["as_of_date"]), "evaluation_end must precede as_of_date")
        need(dev["n_months"] >= tl["min_development_months"], "too few development months")
        need(ho["n_sessions"] == min(ho["sessions_fraction_rule"], ho["sessions_years_rule"]),
             "holdout must be exactly the rule size")
        need(ho.get("month_snap") == "none", "holdout must not be month-snapped")
        need(dev["n_sessions"] + ho["n_sessions"] == tl["n_evaluation_sessions"], "session counts do not add up")

    tr = cfg["trading"]
    need(0 < tr["exit_abs_z"] < tr["entry_abs_z"] < tr["stop_abs_z"], "need 0 < exit < entry < stop")
    need(tr["max_holding_sessions"] > 0, "max holding must be positive")

    pr = cfg["screening"]["pass_rules"]
    need(0 < pr["beta_min"] < pr["beta_max"], "beta bounds")
    need(0 < pr["half_life"]["min_sessions"] < pr["half_life"]["max_sessions"], "half-life bounds")
    need(0 < cfg["screening"]["multiple_testing"]["q"] < 1, "BH q in (0, 1)")

    pf = cfg["portfolio"]
    need(pf["max_pairs"] * pf["per_pair_gross_max_nav"] <= pf["total_gross_max_nav"] + 1e-12,
         "max_pairs x per-pair gross exceeds total gross cap")

    need(cfg["costs"]["stress_multiplier"] == 2.0, "cost stress must double costs")
    need(cfg["features"]["pca"]["n_components"] >= 1, "n_components must be positive")
    need(cfg["clustering"]["objects"] == "stocks", "clustered objects must be stocks")

    pl = cfg["pilot"]
    th = pl["thresholds"]
    need(pl["source_discovery_timebox_minutes"] <= pl["timebox_minutes"], "discovery timebox exceeds total")
    need(len(pl["provisional_formation_ends"]) == th["n_formations"], "pilot formation list length")
    if tl["boundary_status"] != "unresolved":
        ends = pd.DatetimeIndex(pl["provisional_formation_ends"])
        need(ends[0] == pd.Timestamp(tl["first_formation_end"]), "pilot must start at the first formation")
        months = [p.ordinal for p in ends.to_period("M")]
        need(all(b - a == 1 for a, b in zip(months, months[1:])), "pilot formations must be consecutive months")
        need(ends[-1] < pd.Timestamp(dev["end"]), "pilot formations must trade inside development")

    for v in cfg["robustness"]["variants"]:
        try:
            primary = get_path(cfg, v["path"])
        except KeyError:
            errs.append(f"robustness path {v['path']} not found")
            continue
        need(v["value"] != primary, f"robustness variant {v['name']} equals the primary value")
    return errs


def conflicts(cfg: dict, hypothesis_text: str) -> list[str]:
    """Keys in HYPOTHESIS.md's spec-check block that are missing from or differ in cfg."""
    m = _BLOCK.search(hypothesis_text)
    if not m:
        return ["HYPOTHESIS.md has no spec-check block"]
    block = yaml.safe_load(m.group(1)) or {}
    out = []
    for key, expected in block.items():
        try:
            actual = get_path(cfg, key)
        except (KeyError, TypeError):
            out.append(f"{key}: in HYPOTHESIS.md but not in config.yaml")
            continue
        if actual != expected:
            out.append(f"{key}: HYPOTHESIS.md says {expected!r}, config.yaml says {actual!r}")
    return out


def require_consistent(cfg: dict, hypothesis_path: Path | str = HYPOTHESIS_PATH) -> None:
    problems = validate(cfg) + conflicts(cfg, Path(hypothesis_path).read_text())
    if problems:
        raise SpecConflictError("specification not consistent; reconcile before running:\n  "
                                + "\n  ".join(problems))
