"""Focused tests for verify_submission.py. Standard library only; no project imports.

Each test copies the required saved artifacts into a temporary directory, breaks one thing in the
copy and checks that the matching verifier check fails. Originals are never modified.

    python -m unittest discover -s tests -p "test_verify_submission.py"
"""
import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import verify_submission as vs  # noqa: E402


def statuses(report):
    return {c['id']: c['status'] for c in report['checks']}


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'sub'
        art = json.loads((ROOT / vs.ARTIFACTS).read_text(encoding='utf-8'))
        for rel in art['required']:
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, dst)

    def tearDown(self):
        self.tmp.cleanup()

    def run_verify(self):
        report, _ = vs.verify(self.root)
        return report, statuses(report)

    def edit_csv(self, rel, match, column, value):
        path = self.root / rel
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fields, rows = reader.fieldnames, list(reader)
        hits = [r for r in rows if all(r[k] == v for k, v in match.items())]
        self.assertEqual(len(hits), 1)
        hits[0][column] = value
        with open(path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    def edit_claims(self, fn):
        path = self.root / vs.CLAIMS
        claims = json.loads(path.read_text(encoding='utf-8'))
        fn(claims)
        path.write_text(json.dumps(claims), encoding='utf-8')

    def test_copy_of_submission_passes(self):
        report, st = self.run_verify()
        self.assertEqual(report['status'], 'PASS', [c for c in report['checks'] if c['status'] == 'fail'])
        self.assertEqual(st['claims.values_and_note'], 'pass')
        self.assertEqual(report['registered_decisions']['H1']['registered_decision'], 'REJECTED')
        self.assertEqual(report['registered_decisions']['H2']['registered_decision'], 'REJECTED')

    def test_wrong_primary_designation_fails(self):
        oos = 'results/tables/oos_performance.csv'
        self.edit_csv(oos, {'hypothesis': 'H1', 'spec': 'Variant B', 'returns': 'net'}, 'role', 'PRIMARY (H1)')
        report, st = self.run_verify()
        self.assertEqual(st['roles.holdout_table'], 'fail')
        self.assertEqual(report['status'], 'FAIL')

    def test_wrong_primary_in_lock_fails(self):
        path = self.root / 'results/oos_lock.json'
        lock = json.loads(path.read_text(encoding='utf-8'))
        lock['frozen_primaries']['H1'] = 'Variant B, primary spec'
        path.write_text(json.dumps(lock), encoding='utf-8')
        _, st = self.run_verify()
        self.assertEqual(st['roles.holdout_lock'], 'fail')
        self.assertEqual(st['hashes.protected'], 'fail')

    def test_altered_headline_metric_fails(self):
        self.edit_csv('results/tables/oos_performance.csv',
                      {'hypothesis': 'H1', 'spec': 'Variant A', 'returns': 'net'}, 'sharpe', '0.7331158084088536')
        report, st = self.run_verify()
        self.assertEqual(st['claims.values_and_note'], 'fail')
        bad = {c['id'] for c in report['claims'] if c['status'] == 'fail'}
        self.assertIn('holdout_H1A_net', bad)

    def test_manuscript_divergence_fails(self):
        path = self.root / 'paper/research_note_edited.html'
        html = path.read_text(encoding='utf-8')
        self.assertEqual(html.count('<td>+0.63</td>'), 1)
        path.write_text(html.replace('<td>+0.63</td>', '<td>+0.73</td>'), encoding='utf-8')
        report, st = self.run_verify()
        bad = {c['id'] for c in report['claims'] if c['status'] == 'fail'}
        self.assertIn('holdout_H1A_net', bad)
        self.assertEqual(st['hashes.paper'], 'fail')

    def test_missing_required_artifact_fails(self):
        (self.root / 'HYPOTHESIS.md').unlink()
        _, st = self.run_verify()
        self.assertEqual(st['required_files'], 'fail')

    def test_old_note_as_current_pdf_fails(self):
        shutil.copy2(ROOT / 'note/research_note.pdf', self.root / 'paper/research_note_edited.pdf')
        _, st = self.run_verify()
        self.assertEqual(st['paper.not_superseded'], 'fail')

    def test_selector_matching_no_row_fails(self):
        def bad_selector(c):
            claim = next(x for x in c['claims'] if x['id'] == 'h1_dev_A_net')
            claim['sources'][0]['where']['returns'] = 'nett'
        self.edit_claims(bad_selector)
        report, _ = self.run_verify()
        rec = next(c for c in report['claims'] if c['id'] == 'h1_dev_A_net')
        self.assertEqual(rec['status'], 'fail')
        self.assertTrue(any('matched 0 rows' in p for p in rec['problems']))

    def test_selector_matching_two_rows_fails(self):
        def ambiguous(c):
            claim = next(x for x in c['claims'] if x['id'] == 'holdout_H1A_net')
            claim['sources'][0]['where'] = {'hypothesis': 'H1', 'spec': 'Variant A'}
        self.edit_claims(ambiguous)
        report, _ = self.run_verify()
        rec = next(c for c in report['claims'] if c['id'] == 'holdout_H1A_net')
        self.assertTrue(any('matched 3 rows' in p for p in rec['problems']))

    def append_trial(self, variant, spec):
        path = self.root / 'results/trial_log.csv'
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fields, rows = reader.fieldnames, list(reader)
        new = dict(next(r for r in rows if r['kind'] == 'trial'))
        new.update(variant=variant, spec=spec)
        with open(path, 'a', newline='', encoding='utf-8') as f:
            csv.DictWriter(f, fieldnames=fields).writerow(new)

    def test_new_configuration_breaks_trial_accounting(self):
        self.append_trial('A', 'unregistered_spec')
        report, st = self.run_verify()
        self.assertEqual(st['trials.log_counts'], 'fail')
        self.assertEqual(report['trial_accounting']['distinct_trial_configurations'], 26)

    def test_repeated_run_is_not_a_new_configuration(self):
        self.append_trial('A', 'primary')
        report, st = self.run_verify()
        self.assertEqual(report['trial_accounting']['distinct_trial_configurations'], 25)
        self.assertEqual(report['trial_accounting']['trial_rows_including_repeats'], 77)
        self.assertEqual(st['trials.log_counts'], 'fail')  # row totals changed, so the log no longer matches

    def test_missing_turnover_reported_as_zero_fails(self):
        self.edit_csv('results/tables/oos_performance.csv',
                      {'hypothesis': 'H1', 'spec': 'Variant A', 'returns': 'net'}, 'turnover', '0')
        report, st = self.run_verify()
        self.assertEqual(st['holdout.turnover_missing'], 'fail')
        detail = next(c['detail'] for c in report['checks'] if c['id'] == 'holdout.turnover_missing')
        self.assertIn('reported as zero', detail)

    def test_missing_turnover_stays_null(self):
        report, _ = self.run_verify()
        self.assertIsNone(report['missing_metrics'][0]['value'])
        holdout = [h for h in report['headline'] if h['period'] == 'holdout']
        self.assertTrue(holdout and all(h['turnover'] is None for h in holdout))

    def test_blank_value_is_not_read_as_zero(self):
        store = vs.Store(self.root)
        src = {'file': 'results/tables/oos_performance.csv', 'column': 'turnover',
               'where': {'hypothesis': 'H1', 'spec': 'Variant A', 'returns': 'net'}}
        with self.assertRaises(vs.ClaimError):
            store.value(src, {'dp': 1})

    def test_post_evaluation_source_labelled_original_fails(self):
        def relabel(c):
            next(x for x in c['claims'] if x['id'] == 'p2_hac_interval')['evidence'] = 'original_frozen'
        self.edit_claims(relabel)
        _, st = self.run_verify()
        self.assertEqual(st['claims.evidence_labels'], 'fail')

    def test_holdout_claim_from_development_table_fails(self):
        def move(c):
            claim = next(x for x in c['claims'] if x['id'] == 'h1_dev_A_net')
            claim['period'] = 'holdout'
        self.edit_claims(move)
        _, st = self.run_verify()
        self.assertEqual(st['claims.evidence_labels'], 'fail')

    def test_unregistered_note_mismatch_is_not_excused(self):
        def drop_errata(c):
            c['errata'] = []
        self.edit_claims(drop_errata)
        note = self.root / 'paper/research_note_edited.html'
        text = note.read_text(encoding='utf-8')
        self.assertIn('<td>20.6%</td>', text)
        note.write_text(text.replace('<td>20.6%</td>', '<td>20.7%</td>', 1), encoding='utf-8')
        _, st = self.run_verify()
        self.assertEqual(st['claims.values_and_note'], 'fail')

    def test_absolute_temp_path_is_detected(self):
        readme = self.root / 'README.md'
        readme.write_text(readme.read_text(encoding='utf-8') + '\nsee /private' + '/tmp/somewhere\n', encoding='utf-8')
        _, st = self.run_verify()
        self.assertEqual(st['portability.absolute_paths'], 'fail')


class GuardTests(unittest.TestCase):
    """The CLI installs an audit hook; exercise it in child processes so this process stays unhooked."""

    def child(self, body, cwd):
        code = f'import sys; sys.path.insert(0, {str(ROOT)!r}); import verify_submission as v; v.install_guards()\n{body}'
        return subprocess.run([sys.executable, '-c', code], cwd=cwd, capture_output=True, text=True, timeout=60)

    def test_network_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.child("import socket; socket.create_connection(('example.invalid', 80), timeout=1)", d)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('network access refused', r.stderr)

    def test_credential_and_market_data_reads_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, '.env').write_text('PLACEHOLDER=1\n')          # synthetic file, not a credential
            Path(d, 'data/raw').mkdir(parents=True)
            Path(d, 'data/raw/x.csv').write_text('a\n1\n')
            env = self.child("open('.env').read()", d)
            raw = self.child("open('data/raw/x.csv').read()", d)
        self.assertIn('credential file access refused', env.stderr)
        self.assertIn('licensed market data access refused', raw.stderr)

    def test_subprocess_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.child("import subprocess; subprocess.run(['true'])", d)
        self.assertIn('subprocess refused', r.stderr)

    def test_cli_on_submission_exits_zero_and_writes_json(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d, 'report.json')
            r = subprocess.run([sys.executable, str(ROOT / 'verify_submission.py'), '--json', str(out)],
                               capture_output=True, text=True, timeout=120)
            report = json.loads(out.read_text(encoding='utf-8'))
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        self.assertEqual(report['status'], 'PASS')
        self.assertTrue(report['scope'].startswith('artifact-only'))


if __name__ == '__main__':
    unittest.main()
