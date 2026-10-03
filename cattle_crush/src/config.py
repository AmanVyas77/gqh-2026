"""Config loading, project paths, and the in-sample / out-of-sample boundary."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"
RAW = ROOT / "data" / "raw"
RAW_OOS = RAW / "oos"          # written only when download is called with oos=True (run_oos.py)
PROCESSED = ROOT / "data" / "processed"
MANUAL = ROOT / "data" / "manual"
RESULTS = ROOT / "results"


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def config_hash(path: Path = CONFIG_PATH) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def oos_start(cfg: dict | None = None) -> pd.Timestamp:
    cfg = cfg if cfg is not None else load_config()
    return pd.Timestamp(cfg["oos_start"])


def data_start(cfg: dict | None = None) -> pd.Timestamp:
    cfg = cfg if cfg is not None else load_config()
    return pd.Timestamp(cfg["data_start"])
