"""Loads config.yaml (the machine-readable mirror of HYPOTHESIS.md) and hashes it."""
from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from macro_equity.paths import CONFIG_PATH


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def config_hash(path: Path = CONFIG_PATH) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def get_key(cfg: dict, dotted: str):
    """cfg['a']['b'] for 'a.b'; KeyError if any part is missing."""
    node = cfg
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(dotted)
        node = node[part]
    return node
