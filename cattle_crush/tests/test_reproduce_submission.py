"""Comparison tests use synthetic tables only."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('reproduce_submission', Path(__file__).resolve().parents[1] / 'reproduce_submission.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_reproduction_detects_changed_returns(tmp_path):
    before, after = tmp_path/'old.csv', tmp_path/'new.csv'
    before.write_text('sharpe,turnover\n0.63,6.0\n')
    after.write_text('sharpe,turnover\n0.73,6.0\n')
    assert module.compare_csv(before, after)


def test_missing_output_cannot_pass(tmp_path):
    before = tmp_path/'old.csv'
    before.write_text('sharpe\n0.63\n')
    assert module.compare_csv(before,tmp_path/'missing.csv') == ['output not regenerated']


def test_only_omitted_holdout_turnover_is_exempt(tmp_path):
    before, after = tmp_path/'oos_performance.csv', tmp_path/'new.csv'
    before.write_text('sharpe,turnover\n0.63,\n')
    after.write_text('sharpe,turnover\n0.63,6.0\n')
    assert not module.compare_csv(before, after)
    after.write_text('sharpe,turnover\n0.73,6.0\n')
    assert module.compare_csv(before, after)
