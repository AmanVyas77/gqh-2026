"""Append-only research log (results/research_log.csv).

Records every search, source inspection, download, decision and experiment that can influence
data or model selection, so the full research-attempt count can be disclosed. This is broader
than the six pre-registered trial specifications (HYPOTHESIS.md §11). Rows are never edited or
deleted. Tests point MACRO_EQUITY_RESEARCH_LOG at a temporary file.
"""
from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from macro_equity.paths import RESULTS

FIELDS = ["timestamp_et", "prompt", "kind", "subject", "action", "outcome", "influences_selection"]
KINDS = {"search", "inspect", "download", "decision", "experiment", "amendment"}


def log_path() -> Path:
    return Path(os.environ.get("MACRO_EQUITY_RESEARCH_LOG", RESULTS / "research_log.csv"))


def append(prompt: int, kind: str, subject: str, action: str, outcome: str,
           influences_selection: bool, when: datetime | None = None) -> None:
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind}")
    when = when or datetime.now(ZoneInfo("America/New_York"))
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({"timestamp_et": when.isoformat(timespec="seconds"), "prompt": prompt, "kind": kind,
                    "subject": subject, "action": action, "outcome": outcome,
                    "influences_selection": "yes" if influences_selection else "no"})
