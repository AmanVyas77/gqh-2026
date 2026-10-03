"""Append-only log of every backtest run (results/trial_log.csv). Rows are never deleted.

kind: "trial" (counts toward the Deflated Sharpe N), "diagnostic", "overlay" or "oos" (logged and
disclosed, not counted; Deviation Log 2026-10-02 / 2026-10-03). Tests point CATTLE_TRIAL_LOG at
a temporary file so they never write to the real log.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src.config import RESULTS, ROOT, config_hash

FIELDS = ["timestamp_utc", "git_commit", "config_sha256", "kind", "variant", "spec", "params",
          "sample_start", "sample_end", "n_obs", "sharpe_net", "skew", "kurt"]


def log_path() -> Path:
    return Path(os.environ.get("CATTLE_TRIAL_LOG", RESULTS / "trial_log.csv"))


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def log_trial(variant: str, params: dict, sample: tuple, sharpe: float, n_obs: int, skew: float,
              kurt: float, kind: str = "trial", spec: str = "primary") -> None:
    if kind not in {"trial", "diagnostic", "overlay", "oos"}:
        raise ValueError(f"unknown kind {kind}")
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({"timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "git_commit": _git_commit(), "config_sha256": config_hash(), "kind": kind,
                    "variant": variant, "spec": spec, "params": json.dumps(params, sort_keys=True, default=str),
                    "sample_start": str(sample[0]), "sample_end": str(sample[1]), "n_obs": n_obs,
                    "sharpe_net": f"{sharpe:.6f}", "skew": f"{skew:.6f}", "kurt": f"{kurt:.6f}"})
