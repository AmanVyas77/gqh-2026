"""Replay development and frozen holdout in an isolated directory, then compare saved results.

Usage: python reproduce_submission.py
Requires installed requirements.txt and the documented raw inputs in data/raw/.
Never downloads, buys data, changes specifications, or overwrites original results.
"""
from __future__ import annotations
import csv
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent


def same(a, b):
    if str(a) == str(b):
        return True
    try:
        x, y = float(a), float(b)
        return (math.isnan(x) and math.isnan(y)) or math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-11)
    except (ValueError, TypeError):
        return False


def compare_csv(original, regenerated):
    with original.open(newline='') as f:
        reader = csv.DictReader(f); fields = reader.fieldnames; old = list(reader)
    if not regenerated.exists():
        return ['output not regenerated']
    with regenerated.open(newline='') as f:
        new = list(csv.DictReader(f))
    if len(old) != len(new):
        return [f'row count {len(old)} vs {len(new)}']
    # Logged reproduction repetitions increase these counters, not distinct trial count.
    excluded = {'raw_logged_rows', 'trial_rows_including_repeats'} if original.name in ('trials.csv', 'h2_dsr.csv') else set()
    if original.name == 'oos_performance.csv':
        excluded.add('turnover')  # previously omitted; recovered by this replay
    return [f'row {i + 1}, {k}: {a.get(k)!r} vs {b.get(k)!r}'
            for i, (a, b) in enumerate(zip(old, new)) for k in fields
            if k not in excluded and not same(a.get(k), b.get(k))]


def write_h2_dsr_view(tables):
    """Recreate the archived H2-only column layout from the regenerated project DSR table."""
    with (tables/'trials.csv').open(newline='') as f:
        row = next(r for r in csv.DictReader(f) if r['strategy'] == 'H2 primary')
    mapping = {'strategy':'strategy','sharpe_annual':'sharpe_annual','n_obs':'n_obs_days',
               'psr':'psr','n_trials_project':'n_cattle_project_trials','sr0_annual':'sr0_annual','dsr_project':'dsr'}
    result = {key:row[value] for key,value in mapping.items()}
    result['note'] = 'H2 alternatives (4) not run; H2-only DSR undefined with one trial'
    with (tables/'h2_dsr.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(result)); writer.writeheader(); writer.writerow(result)


def main():
    needed = [f'{r}_{k}.parquet' for r in ('LE','GF','ZC') for k in ('definition','statistics','ohlcv1d')]
    files = needed + ['h2_equities.parquet','nass_placements.parquet','cftc_live_cattle.parquet','spy.parquet']
    files += ['oos/' + f for f in needed + ['h2_equities.parquet','cftc_live_cattle.parquet']]
    missing = [p for p in files if not (ROOT/'data/raw'/p).is_file()]
    if missing:
        raise SystemExit('Missing raw inputs; follow README data acquisition steps first: ' + ', '.join(missing))
    if not (ROOT/'results/oos_lock.json').is_file():
        raise SystemExit('Requires the existing holdout lock; this command cannot perform a first evaluation.')
    destination = ROOT/'review/reproduction'
    destination.mkdir(parents=True, exist_ok=True)
    report = {'started_utc': datetime.now(timezone.utc).isoformat(), 'status': 'RUNNING',
              'scope': 'Full development and frozen-holdout pipelines, empty derived-data cache, existing licensed raw inputs; no new tuning or data download. Original results and lock preserved.',
              'numeric_tolerance': {'relative':1e-9,'absolute':1e-11},
              'excluded_comparison_columns': {'trials.csv':['raw_logged_rows','trial_rows_including_repeats'], 'h2_dsr.csv':['raw_logged_rows','trial_rows_including_repeats'], 'oos_performance.csv':['turnover (recovered reporting omission)']},
              'input_sha256': {p:hashlib.sha256((ROOT/'data/raw'/p).read_bytes()).hexdigest() for p in files},
              'source_sha256': {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'run_all.py',ROOT/'run_oos.py',ROOT/'reproduce_submission.py',ROOT/'config.yaml',*sorted((ROOT/'src').glob('*.py'))]},
              'python':sys.version, 'packages':{}}
    for line in (ROOT/'requirements.txt').read_text().splitlines():
        if '==' in line:
            package, version = line.split('=='); report['packages'][package] = importlib.metadata.version(package)
            if report['packages'][package] != version:
                raise SystemExit(f'Install pinned requirements first: {package} needs {version}')
    with tempfile.TemporaryDirectory(prefix='cattle-reproduction-') as directory:
        copy = Path(directory)/'cattle_crush'
        shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns('raw','processed','.env','.venv','__pycache__','.pytest_cache','reproduction'))
        (copy/'data/raw').symlink_to((ROOT/'data/raw').resolve(), target_is_directory=True)
        (copy/'data/processed').mkdir(exist_ok=True)
        # Remove copied outputs so missing regeneration cannot accidentally pass comparison.
        shutil.rmtree(copy/'results/tables')
        (copy/'results/tables').mkdir()
        env = os.environ.copy()
        env.pop('CATTLE_TRIAL_LOG', None)
        env['MPLCONFIGDIR'] = str(Path(directory)/'matplotlib')
        report['commands'] = []
        for script in ('run_all.py', 'run_oos.py'):
            print(f'Running {script} in isolated copy...', flush=True)
            with (destination/(script+'.log')).open('w') as log:
                result = subprocess.run([sys.executable,script],cwd=copy,env=env,stdout=log,stderr=subprocess.STDOUT)
            report['commands'].append({'script':script,'exit_code':result.returncode})
            if result.returncode:
                report['status']='FAIL'; break
        if report['status'] != 'FAIL':
            write_h2_dsr_view(copy/'results/tables')
            report['comparisons'] = []
            for original in sorted((ROOT/'results/tables').glob('*.csv')):
                differences = compare_csv(original,copy/'results/tables'/original.name)
                report['comparisons'].append({'file':original.name,'status':'FAIL' if differences else 'PASS','differences':differences})
            old = json.loads((ROOT/'results/tables/h2_exposure_concentration.json').read_text())
            new = json.loads((copy/'results/tables/h2_exposure_concentration.json').read_text())
            def equivalent(a,b):
                if isinstance(a,dict): return isinstance(b,dict) and a.keys()==b.keys() and all(equivalent(a[k],b[k]) for k in a)
                if isinstance(a,list): return isinstance(b,list) and len(a)==len(b) and all(equivalent(x,y) for x,y in zip(a,b))
                return same(a,b)
            report['comparisons'].append({'file':'h2_exposure_concentration.json','status':'PASS' if equivalent(old,new) else 'FAIL'})
            report['status']='PASS' if all(c['status']=='PASS' for c in report['comparisons']) else 'FAIL'
            shutil.copy2(copy/'results/tables/oos_performance.csv',destination/'oos_performance_reproduced.csv')
        shutil.copy2(copy/'results/trial_log.csv',destination/'trial_log.csv')
    report['finished_utc']=datetime.now(timezone.utc).isoformat()
    (destination/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Reproduction '+report['status']+'; see review/reproduction/report.json',flush=True)
    raise SystemExit(0 if report['status']=='PASS' else 1)


if __name__ == '__main__':
    main()
