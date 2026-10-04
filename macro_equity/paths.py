"""Project paths, anchored to this package rather than the working directory.

Development data and the quarantined holdout area are separate trees. Ordinary loaders read
only DEV_RAW / DEV_PROCESSED; HOLDOUT is read only by the gated holdout runner
(macro_equity.run_oos, built in Prompt 8 and run once in Prompt 9).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CONFIG_PATH = ROOT / "config.yaml"            # written in Prompt 1

DATA = ROOT / "data"
DEV_RAW = DATA / "dev" / "raw"                # git-ignored: downloaded development data
DEV_PROCESSED = DATA / "dev" / "processed"    # git-ignored: derived from licensed data
HOLDOUT = DATA / "holdout"                    # git-ignored, quarantined: gated runner only
IMPORTS = DATA / "imports"                    # git-ignored: user-supplied licensed files (staging)
CACHE = DATA / "cache"                        # git-ignored
MANIFESTS = DATA / "manifests"                # tracked: source manifest, coverage metadata, checksums
TEMPLATES = DATA / "templates"                # tracked: import templates (headers only)

RESULTS = ROOT / "results"                    # tracked: permitted summaries, tables, figures, logs

IGNORED_DIRS = (DEV_RAW, DEV_PROCESSED, HOLDOUT, IMPORTS, CACHE)
TRACKED_DIRS = (MANIFESTS, TEMPLATES, RESULTS)
