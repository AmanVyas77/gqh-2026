"""Scaffold checks (Prompt 0): qualified imports, path layout and git-ignore coverage.

These tests read only the package's own source and git's ignore rules: no data, no results.
"""
from __future__ import annotations

import ast
import shutil
import subprocess
from pathlib import Path

import pytest

import macro_equity
from macro_equity import paths

PKG = Path(macro_equity.__file__).resolve().parent
REPO = PKG.parent


def _sibling_modules() -> set[str]:
    """Top-level module/package names elsewhere in the repo that a bare import could pick up."""
    names = set()
    for base in (REPO, REPO / "cattle_crush", REPO / "cattle_crush" / "data"):
        if not base.is_dir():
            continue
        for p in base.iterdir():
            if p.suffix == ".py":
                names.add(p.stem)
            elif p.is_dir() and not p.name.startswith(".") and p.name != "macro_equity":
                names.add(p.name)
    return names - {"__pycache__"}


def _package_sources() -> list[Path]:
    return sorted(p for p in PKG.rglob("*.py") if not {".venv", "__pycache__"} & set(p.parts))


def test_imports_are_qualified():
    """Intra-project imports use `macro_equity.`; nothing imports a sibling project or edits sys.path."""
    siblings = _sibling_modules()
    problems = []
    for f in _package_sources():
        for node in ast.walk(ast.parse(f.read_text(), filename=str(f))):
            where = f"{f.relative_to(REPO)}:{getattr(node, 'lineno', '?')}"
            if isinstance(node, ast.ImportFrom) and node.level:
                problems.append(f"{where} relative import")
            mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                    else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            for m in mods:
                if m.split(".")[0] in siblings:
                    problems.append(f"{where} imports sibling-project module {m}")
            if (isinstance(node, ast.Attribute) and node.attr == "path"
                    and isinstance(node.value, ast.Name) and node.value.id == "sys"):
                problems.append(f"{where} touches sys.path")
    assert not problems, "\n".join(problems)


def test_no_src_package():
    assert not (PKG / "src").exists(), "use qualified macro_equity subpackages, not a generic src/"


def test_paths_inside_package_and_quarantine_separate():
    for p in paths.IGNORED_DIRS + paths.TRACKED_DIRS + (paths.CONFIG_PATH,):
        assert PKG in p.parents, p
    dev = (paths.DEV_RAW, paths.DEV_PROCESSED)
    for d in dev:
        assert paths.HOLDOUT not in d.parents and d not in paths.HOLDOUT.parents and d != paths.HOLDOUT


IGNORED = [".env", "data/dev/raw/spy.parquet", "data/dev/processed/decision_table.parquet",
           "data/holdout/spy.parquet", "data/imports/consensus_export.csv", "data/cache/x.json",
           "sources/__pycache__/x.cpython-311.pyc", ".pytest_cache/v/cache/lastfailed"]
TRACKED = [".env.example", "CLAUDE.md", "STATUS.md", "README.md", "config.yaml",
           "data/manifests/source_manifest.json", "data/templates/consensus_import_template.csv",
           "results/trial_log.csv", "results/tables/development_metrics.csv"]


def _ignored(rel: str) -> bool:
    r = subprocess.run(["git", "check-ignore", "-q", "--no-index", f"macro_equity/{rel}"],
                       cwd=REPO, capture_output=True, text=True)
    if r.returncode not in (0, 1):
        pytest.skip(f"git check-ignore failed: {r.stderr.strip()}")
    return r.returncode == 0


needs_git = pytest.mark.skipif(shutil.which("git") is None or not (REPO / ".git").exists(),
                               reason="not inside the git checkout")


@needs_git
@pytest.mark.parametrize("rel", IGNORED)
def test_secrets_and_data_are_ignored(rel):
    assert _ignored(rel)


@needs_git
@pytest.mark.parametrize("rel", TRACKED)
def test_summaries_and_metadata_stay_trackable(rel):
    assert not _ignored(rel)
