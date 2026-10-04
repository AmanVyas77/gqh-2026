#!/usr/bin/env python3
"""Artifact-only verifier for the GQH 2026 cattle-markets submission.

    python verify_submission.py              # report, plus submission/verification_report.json
    python verify_submission.py --json PATH  # write the JSON report elsewhere
    python verify_submission.py --no-json    # print only

Standard library only (Python 3.9+). It reads the committed result tables, the frozen holdout lock,
the editable note and two manifests in submission/. It never fetches data, opens credentials or
licensed inputs, imports project modules, runs a backtest, evaluates the holdout or rewrites a
manifest. Exit status 0 means every required check passed; 1 means a required artifact is missing
or inconsistent.

A pass shows that the saved artifacts, the note and the manifests agree with each other. It is not
a computational reproduction: rerunning the backtests needs the licensed inputs and the pinned
environment described in README.md.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARTIFACTS = 'submission/artifacts.json'
CLAIMS = 'submission/claims.json'
DEFAULT_REPORT = 'submission/verification_report.json'

SCOPE = ('artifact-only: checks saved tables, the holdout lock, the note and manifests for consistency; '
         'no data download, backtest, holdout evaluation or computational reproduction')
NOT_PROVEN = [
    'That the code reproduces these tables from raw inputs (requires licensed Databento data, NASS/CFTC/'
    'yfinance downloads and the pinned Python 3.11 environment; see README.md).',
    'That no lookahead exists in the code, beyond the saved artifacts and the existing unit tests.',
    'That the holdout was accessed only once, or that the trial log is complete outside the recorded project.',
    'That the PDF pixels match the editable HTML, except where the optional PyMuPDF text check runs.',
    'Executable fills, historical margin-call funding or profitable capacity.',
]

_NET_EVENTS = {'socket.connect', 'socket.getaddrinfo', 'socket.gethostbyname', 'socket.gethostbyaddr',
               'socket.sendto', 'socket.sendmsg', 'socket.bind', 'urllib.Request', 'http.client.connect'}
_PROC_EVENTS = {'subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn', 'os.spawn', 'os.startfile'}
_SECRET_NAMES = {'credentials', 'id_rsa', 'id_ed25519', '.netrc', '.pgpass'}
_DATA_SUFFIXES = ('.parquet', '.dbn', '.zst', '.feather')
_SELECTOR_KEYS = ('column', 'json_path', 'where', 'multiply', 'agg', 'by', 'expect_rows')
# Bracketed letters keep this pattern from matching its own source line.
_ABS_PATH = re.compile(r'/privat[e]/tmp|/tm[p]/gqh|/Use[r]s/[^/\s]+/|/hom[e]/[^/\s]+/|[A-Z]:\\Use[r]s\\')


def refused_path(path):
    """Return why a path is off-limits to this verifier, or None."""
    p = Path(os.fsdecode(path))
    if p.name == '.env' or (p.name.startswith('.env.') and p.name != '.env.example'):
        return 'credential file'
    if p.name in _SECRET_NAMES or '.aws' in p.parts or '.ssh' in p.parts:
        return 'credential file'
    for a, b in zip(p.parts, p.parts[1:]):
        if a == 'data' and b in ('raw', 'processed'):
            return 'licensed market data'
    if p.name.endswith(_DATA_SUFFIXES):
        return 'market data file'
    return None


def install_guards():
    """Refuse network, subprocesses, credential files and market data in this Python process.

    An in-process audit hook, not an operating-system sandbox; once installed it stays installed.
    """
    def hook(event, args):
        if event in _NET_EVENTS:
            raise RuntimeError(f'verify_submission: network access refused ({event})')
        if event in _PROC_EVENTS:
            raise RuntimeError(f'verify_submission: subprocess refused ({event})')
        if event == 'open' and args and isinstance(args[0], (str, bytes, os.PathLike)):
            why = refused_path(args[0])
            if why:
                raise RuntimeError(f'verify_submission: {why} access refused: {os.fsdecode(args[0])}')
    sys.addaudithook(hook)


class ClaimError(Exception):
    pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def norm(text):
    text = text.replace('−', '-').replace('–', '-').replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def fmt_value(x, spec):
    """Format a saved value the way the note displays it (Decimal, ROUND_HALF_UP)."""
    if spec.get('kind') == 'str':
        s = str(x)
        return s[:spec['slice']] if 'slice' in spec else s
    d = Decimal(repr(float(x))) * Decimal(str(spec.get('scale', 1)))
    if not d.is_finite():
        raise ClaimError('non-finite numerical claim')
    if spec.get('round_to'):
        step = Decimal(str(spec['round_to']))
        d = (d / step).quantize(Decimal(1), ROUND_HALF_UP) * step
    dp = spec.get('dp', 0)
    d = d.quantize(Decimal(1).scaleb(-dp), ROUND_HALF_UP)
    body = format(abs(d), f',.{dp}f' if spec.get('thousands') else f'.{dp}f')
    sign = spec.get('sign', 'minus')
    lead = '+' if sign == 'plus' and d > 0 else '-' if sign != 'abs' and d < 0 else ''
    return lead + spec.get('prefix', '') + body + spec.get('suffix', '')


def contains_value(text, value):
    """True if value occurs in text as a whole number token (no adjacent digits)."""
    return re.search(r'(?<![\d.])' + re.escape(value) + r'(?![\d])', text) is not None


class _NoteParser(HTMLParser):
    """Collect normalized prose and table cells from the editable note."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.chunks = [], []
        self._row = self._cell = None
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('style', 'script', 'title'):
            self._skip += 1
        elif tag == 'table':
            self.tables.append([])
        elif tag == 'tr' and self.tables:
            self._row = []
        elif tag in ('td', 'th') and self._row is not None:
            self._cell = []
        elif tag == 'br':
            self.handle_data(' ')

    def handle_endtag(self, tag):
        if tag in ('style', 'script', 'title'):
            self._skip -= 1
        elif tag in ('td', 'th') and self._cell is not None:
            self._row.append(norm(''.join(self._cell)))
            self._cell = None
            self.chunks.append(' | ')
        elif tag == 'tr' and self._row is not None:
            self.tables[-1].append(self._row)
            self._row = None
            self.chunks.append('\n')
        elif tag in ('p', 'h1', 'h2', 'section', 'table', 'figure'):
            self.chunks.append('\n')

    def handle_data(self, data):
        if self._skip:
            return
        if self._cell is not None:
            self._cell.append(data)
        self.chunks.append(data)


class Note:
    def __init__(self, html_text):
        parser = _NoteParser()
        parser.feed(html_text)
        parser.close()
        self.text = norm(''.join(parser.chunks))
        self.tables = {t[0][0]: t for t in parser.tables if t and t[0]}

    def cell(self, table, row, col):
        if table not in self.tables:
            raise ClaimError(f'note has no table headed {table!r}')
        rows = [r for r in self.tables[table][1:] if r and r[0] == row]
        if len(rows) != 1:
            raise ClaimError(f'note table {table!r} has {len(rows)} rows labelled {row!r}')
        if col >= len(rows[0]):
            raise ClaimError(f'note table {table!r} row {row!r} has no column {col}')
        return rows[0][col]


class Store:
    """Read-only access to saved CSV/JSON artifacts with exact-one-row selection."""

    def __init__(self, root):
        self.root = root
        self._cache = {}

    def _load(self, rel):
        if rel not in self._cache:
            path = self.root / rel
            if not path.is_file():
                raise ClaimError(f'missing source file {rel}')
            with open(path, newline='', encoding='utf-8') as f:
                self._cache[rel] = json.load(f) if rel.endswith('.json') else list(csv.DictReader(f))
        return self._cache[rel]

    def rows(self, rel, where):
        rows = self._load(rel)
        if rows and any(k not in rows[0] for k in where):
            raise ClaimError(f'{rel}: selector column(s) {sorted(k for k in where if k not in rows[0])} absent')
        return [r for r in rows if all(r.get(k) == v for k, v in where.items())]

    def raw(self, src):
        rel = src['file']
        if 'json_path' in src:
            node = self._load(rel)
            for key in src['json_path']:
                if not isinstance(node, dict) or key not in node:
                    raise ClaimError(f'{rel}: key path {src["json_path"]} not found')
                node = node[key]
            return node
        hits = self.rows(rel, src.get('where', {}))
        col = src['column']
        if 'agg' in src:
            if 'expect_rows' in src and len(hits) != src['expect_rows']:
                raise ClaimError(f'{rel}: aggregate selector {src.get("where")} matched {len(hits)} rows, '
                                 f'expected {src["expect_rows"]}')
            if not hits:
                raise ClaimError(f'{rel}: aggregate selector {src.get("where")} matched 0 rows')
            by = src.get('by', col)
            pick = (min if src['agg'] in ('min', 'argmin') else max)(hits, key=lambda r: float(r[by]))
            return pick[col]
        if len(hits) != 1:
            raise ClaimError(f'{rel}: selector {src.get("where", {})} matched {len(hits)} rows (need exactly 1)')
        if col not in hits[0]:
            raise ClaimError(f'{rel}: no column {col!r}')
        return hits[0][col]

    def value(self, src, spec):
        raw = self.raw(src)
        if raw is None or (isinstance(raw, str) and raw.strip() == ''):
            raise ClaimError(f'{src["file"]}: selected value is missing (blank); refusing to treat it as zero')
        if spec.get('kind') == 'str':
            return raw
        return float(raw) * src.get('multiply', 1)


class Report:
    def __init__(self):
        self.checks = []

    def add(self, cid, ok, detail, level='required'):
        status = 'pass' if ok else ('fail' if level == 'required' else 'warn')
        self.checks.append({'id': cid, 'status': status, 'detail': detail})
        return ok

    @property
    def failed(self):
        return [c for c in self.checks if c['status'] == 'fail']


def check_files(root, art, rep):
    missing = [p for p in art['required'] if not (root / p).is_file()]
    rep.add('required_files', not missing,
            f'{len(art["required"]) - len(missing)}/{len(art["required"])} present'
            + (f'; missing: {missing}' if missing else ''))
    for section in ('protected', 'code', 'paper', 'post_evaluation'):
        entries = art['hashes'][section]['files']
        bad = []
        for rel, expected in sorted(entries.items()):
            path = root / rel
            if Path(rel).is_absolute() or '..' in Path(rel).parts:
                bad.append(f'{rel}: unsafe path')
            elif not path.is_file():
                bad.append(f'{rel}: missing')
            elif sha256(path) != expected:
                bad.append(f'{rel}: hash mismatch')
        rep.add(f'hashes.{section}', not bad,
                f'{len(entries) - len(bad)}/{len(entries)} match ({art["hashes"][section]["scope"]})'
                + (f'; problems: {bad}' if bad else ''))


def check_paper(root, art, claims, note, rep):
    pdf = root / claims['paper_pdf']
    data = pdf.read_bytes() if pdf.is_file() else b''
    digest = hashlib.sha256(data).hexdigest()
    old = art.get('superseded_pdf_sha256', {})
    rep.add('paper.not_superseded', bool(data) and digest not in old,
            'current note is not a superseded version' if digest not in old
            else f'{claims["paper_pdf"]} is a superseded note: {old.get(digest)}')
    pages = len(re.findall(rb'/Type\s*/Page(?![a-zA-Z])', data))
    exp = claims['paper_layout']
    rep.add('paper.page_count', pages == exp['total_pages'],
            f'{pages} PDF pages counted; expected {exp["total_pages"]} '
            f'({exp["main_pages"]} main + references, which the track rules exclude)')
    qa_path = root / exp['recorded_qa']
    qa = json.loads(qa_path.read_text(encoding='utf-8')) if qa_path.is_file() else {}
    rep.add('paper.recorded_format_qa',
            qa.get('main_pages') == exp['main_pages'] and qa.get('pages') == exp['total_pages']
            and float(qa.get('minimum_font_pt', 0)) >= 11,
            f'recorded editorial QA: {qa.get("main_pages")} main pages, minimum font {qa.get("minimum_font_pt")} pt '
            '(recorded at build time, not re-measured here)')
    authors = claims['paper_authors']
    rep.add('paper.authors', authors in note.text, f'authors in order: {authors}')
    missing = [t for t in claims['required_paper_text'] if norm(t) not in note.text]
    rep.add('paper.required_statements', not missing,
            f'{len(claims["required_paper_text"]) - len(missing)}/{len(claims["required_paper_text"])} '
            'decision/labelling statements present' + (f'; missing: {missing}' if missing else ''))
    cited = sorted(set(re.findall(r'\b(?:[\w-]+/)*[\w-]+\.(?:md|py|csv|json)\b', note.text)))
    excluded = art.get('excluded_paper_references', {})
    unknown = [c for c in cited if not (root / c).is_file() and c not in excluded]
    rep.add('paper.cited_files', not unknown,
            f'{len(cited)} repository paths cited by the note; all present or explicitly excluded'
            if not unknown else f'note cites files absent from the submission: {unknown}')
    for ref in sorted(c for c in cited if c in excluded and not (root / c).is_file()):
        rep.add(f'paper.excluded_reference.{ref}', False, f'note cites {ref}, not shipped: {excluded[ref]}',
                level='advisory')


def _cell_display(store, sources, spec, formats):
    fmt = formats[spec['fmt']]
    parts = [fmt_value(store.value({**sources[i], 'column': spec['column']}, fmt), fmt)
             for i in spec.get('parts', [0])]
    for i in spec.get('agree', []):
        other = fmt_value(store.value({**sources[i], 'column': spec['column']}, fmt), fmt)
        if other != parts[0]:
            raise ClaimError(f'{spec["column"]}: note shows one value for rows that display {parts[0]} and {other}')
    return ' / '.join(parts)


def check_claims(root, claims, note, store, rep):
    formats = claims['formats']
    errata = {(e['claim'], e['column'], e['note_shows'], e['saved_displays']): e for e in claims.get('errata', [])}
    results, noted = [], []
    for c in claims['claims']:
        rec = {k: c.get(k) for k in ('id', 'category', 'evidence', 'period')}
        rec['sources'] = sorted({s['file'] for s in c['sources']})
        problems, shown, rec['errata'] = [], [], []
        try:
            if c['type'] == 'cells':
                for spec in c['cells']:
                    disp = _cell_display(store, c['sources'], spec, formats)
                    shown.append(disp)
                    cell = note.cell(c['paper']['table'], c['paper']['row'], spec['col'])
                    if disp != spec['expected']:
                        problems.append(f'{spec["column"]}: saved value displays {disp}, manifest expects {spec["expected"]}')
                    ok = contains_value(cell, disp) if spec.get('contains') else cell == disp
                    known = errata.get((c['id'], spec['column'], cell, disp))
                    if not ok and known:
                        rec['errata'].append({'column': spec['column'], 'note_shows': cell, 'saved_displays': disp})
                        noted.append(f'{c["id"]}.{spec["column"]}: note shows {cell}, saved value displays {disp} '
                                     f'({known["cause"]})')
                    elif not ok:
                        problems.append(f'{spec["column"]}: note cell {cell!r} does not show {disp}')
            else:
                snippet = norm(c['paper_text'])
                if snippet not in note.text:
                    problems.append('note text no longer contains the claimed sentence')
                for v in c['values']:
                    fmt = formats[v['fmt']]
                    src = {**c['sources'][v.get('source', 0)], **{k: v[k] for k in _SELECTOR_KEYS if k in v}}
                    disp = fmt_value(store.value(src, fmt), fmt)
                    label = v.get('column') or '/'.join(v.get('json_path', []))
                    shown.append(disp)
                    if disp != v['expected']:
                        problems.append(f'{label}: saved value displays {disp}, manifest expects {v["expected"]}')
                    if not contains_value(snippet, disp):
                        problems.append(f'{label}: claimed sentence does not show {disp}')
            for x in c.get('cross_checks', []):
                fmt = formats[x['fmt']]
                disp = fmt_value(store.value(x, fmt), fmt)
                if disp != x['expected']:
                    problems.append(f'cross-check {x["file"]}: displays {disp}, expected {x["expected"]}')
        except ClaimError as e:
            problems.append(str(e))
        rec.update(displayed=shown, status='pass' if not problems else 'fail', problems=problems)
        results.append(rec)
    bad = [r for r in results if r['status'] == 'fail']
    rep.add('claims.values_and_note', not bad,
            f'{len(results) - len(bad)}/{len(results)} claims match saved rows and the editable note'
            + ''.join(f'\n      - {r["id"]}: {"; ".join(r["problems"])}' for r in bad))
    for text in noted:
        rep.add('claims.erratum', False, f'registered erratum, disclosed in README: {text}', level='advisory')
    return results


def check_labels(claims, rep):
    """Evidence status must follow the source; holdout numbers must come from the once-evaluated table."""
    holdout_files = set(claims['holdout_sources'])
    bad = []
    for c in claims['claims']:
        files = {s['file'] for s in c['sources']}
        if c['evidence'] not in ('original_frozen', 'post_evaluation'):
            bad.append(f'{c["id"]}: unknown evidence label {c["evidence"]!r}')
        if any(f.startswith('review/') for f in files) and c['evidence'] != 'post_evaluation':
            bad.append(f'{c["id"]}: post-evaluation source labelled {c["evidence"]}')
        if all(f.startswith('results/') for f in files) and c['evidence'] != 'original_frozen':
            bad.append(f'{c["id"]}: original saved result labelled {c["evidence"]}')
        if c['period'] == 'holdout' and not files <= holdout_files:
            bad.append(f'{c["id"]}: holdout claim sourced from {sorted(files - holdout_files)}')
        if c['period'] == 'development' and files & holdout_files:
            bad.append(f'{c["id"]}: development claim sourced from the holdout table')
        if c['category'] not in claims['categories']:
            bad.append(f'{c["id"]}: unknown category {c["category"]!r}')
    rep.add('claims.evidence_labels', not bad,
            'original vs post-evaluation labels follow source locations; holdout/development sources separated'
            + (f'; problems: {bad}' if bad else ''))


def check_roles(claims, store, rep):
    reg = claims['registered']
    lock = store._load(reg['lock_file'])
    ok = lock.get('frozen_primaries') == reg['lock_primaries'] and lock.get('oos_start') == reg['oos_start']
    rep.add('roles.holdout_lock', ok, f'lock frozen_primaries={lock.get("frozen_primaries")}, '
            f'oos_start={lock.get("oos_start")}, commit={str(lock.get("git_commit"))[:7]}')
    rows = store._load(reg['holdout_table'])
    prim = sorted({f'{r["hypothesis"]}:{r["spec"]}' for r in rows if r['role'].upper().startswith('PRIMARY')})
    sec = {f'{r["hypothesis"]}:{r["spec"]}': r['role'] for r in rows}
    bad_sec = [s for s in reg['secondary'] if not sec.get(s, '').lower().startswith('secondary')]
    rep.add('roles.holdout_table', prim == sorted(reg['primary']) and not bad_sec,
            f'primary rows: {prim}; secondary: {reg["secondary"]}' + (f'; mislabelled: {bad_sec}' if bad_sec else ''))


def _condition(store, cond):
    raw = store.raw(cond['source'] | {'column': cond['estimate']})
    est = float(raw)
    sign_ok = est > 0 if cond['direction'] == '+' else est < 0
    t = None
    if cond.get('t'):
        t = float(store.raw(cond['source'] | {'column': cond['t']}))
        t_ok = t > cond['t_threshold'] if cond['direction'] == '+' else t < -cond['t_threshold']
    else:
        t_ok = True
    passed = sign_ok and t_ok
    saved = None
    if cond.get('saved_pass_column'):
        saved = store.raw(cond['source'] | {'column': cond['saved_pass_column']})
    return {'id': cond['id'], 'rule': cond['rule'], 'estimate': est, 't': t, 'passed': passed,
            'saved_pass': saved, 'saved_agrees': saved is None or str(passed) == saved}


def check_decisions(claims, store, rep):
    out = {}
    for hyp, spec in claims['registered']['decisions'].items():
        conds = [_condition(store, c) for c in spec['conditions']]
        by = {c['id']: c['passed'] for c in conds}
        gate = by[spec['gate']]
        rest = all(by[i] for i in spec['support_requires'])
        derived = 'SUPPORTED' if gate and rest else ('REJECTED' if not gate else spec['gate_only_outcome'])
        agree = all(c['saved_agrees'] for c in conds)
        out[hyp] = {'primary': spec['primary'], 'registered_decision': spec['registered_decision'],
                    'derived_from_saved_tables': derived, 'conditions': conds}
        rep.add(f'decisions.{hyp}', derived == spec['registered_decision'] and agree,
                f'{spec["primary"]}: registered {spec["registered_decision"]}, saved tables give {derived}'
                + ('' if agree else '; a saved pass/fail column disagrees with its estimate'))
    return out


def check_trials(root, claims, store, rep):
    ta = claims['trial_accounting']
    rows = store._load(ta['trial_log'])
    kinds = {}
    for r in rows:
        kinds[r['kind']] = kinds.get(r['kind'], 0) + 1
    dev = [r for r in rows if r['sample_end'] < ta['oos_start']]
    trial = [r for r in rows if r['kind'] == 'trial']
    configs = sorted({(r['variant'], r['spec']) for r in trial})
    h2 = [c for c in configs if c[0] == 'H2']
    got = {'total_rows': len(rows), 'kinds': kinds, 'development_rows': len(dev),
           'holdout_rows': len(rows) - len(dev), 'trial_rows_including_repeats': len(trial),
           'distinct_trial_configurations': len(configs), 'distinct_h1_configurations': len(configs) - len(h2),
           'distinct_h2_configurations': len(h2)}
    exp = ta['expected']
    diffs = {k: (got[k], v) for k, v in exp.items() if got.get(k) != v}
    rep.add('trials.log_counts', not diffs,
            f'{got["total_rows"]} rows = ' + ' + '.join(f'{v} {k}' for k, v in sorted(kinds.items()))
            + f'; {got["development_rows"]} development; {got["distinct_trial_configurations"]} distinct trial '
            f'configurations ({got["trial_rows_including_repeats"]} trial rows incl. repeats)'
            + (f'; mismatches (got, expected): {diffs}' if diffs else ''))
    snap = ta['dsr_snapshot']
    srows = store._load(snap['file'])
    snap_bad = {k: sorted({r[k] for r in srows}) for k, v in snap['expected'].items()
                if {r[k] for r in srows} != {str(v)}}
    rep.add('trials.dsr_snapshot', not snap_bad and snap['expected']['n_cattle_project_trials'] == len(configs),
            f'{snap["file"]}: {snap["expected"]["raw_logged_rows"]}-row / '
            f'{snap["expected"]["trial_rows_including_repeats"]}-trial-row earlier snapshot; DSR trial count '
            f'{snap["expected"]["n_cattle_project_trials"]} equals distinct configurations in the log'
            + (f'; mismatches: {snap_bad}' if snap_bad else ''))
    fr = ta['freeze']
    text = (root / fr['file']).read_text(encoding='utf-8')
    m = re.search(fr['pattern'], text)
    freeze = tuple(int(x) for x in m.groups()) if m else None
    want = tuple(fr['expected'])
    dev_counts = (len(dev), sum(r['kind'] == 'trial' for r in dev), sum(r['kind'] == 'overlay' for r in dev),
                  sum(r['kind'] == 'diagnostic' for r in dev))
    rep.add('trials.freeze_record', freeze == want == dev_counts,
            f'{fr["file"]} records {freeze} (rows, trial, overlay, diagnostic) at freeze; development rows '
            f'of the log give {dev_counts}')
    rep.add('trials.note_statement', norm(ta['paper_text']) in claims['_note_text'],
            f'note states: "{ta["paper_text"]}"')
    return got


def check_missing(claims, store, rep):
    spec = claims['holdout_missing']
    rows = store._load(spec['file'])
    filled = [(r['hypothesis'], r['spec'], r['returns'], r[spec['column']]) for r in rows
              if r[spec['column']].strip() != '']
    zeros = [f for f in filled if re.fullmatch(r'[-+]?0*\.?0*', f[3])]
    detail = (f'original {spec["column"]} blank in all {len(rows)} rows; preserved, never replaced with zero'
              if not filled else f'{len(filled)} rows carry a value the note says is missing'
              + (f'; {len(zeros)} are zero, a missing value reported as zero' if zeros else ''))
    rep.add('holdout.turnover_missing', not filled and norm(spec['paper_text']) in claims['_note_text'], detail)
    recovered = claims.get('holdout_recovered')
    if recovered:
        rerun = store._load(recovered['file'])
        report = store._load(recovered['report'])
        keys = ('hypothesis', 'spec', 'returns')
        original = {tuple(r[k] for k in keys): r for r in rows}
        actual = {tuple(r[k] for k in keys): r for r in rerun}
        valid = len(actual) == len(rerun) == len(rows) and actual.keys() == original.keys()
        for key, row in actual.items():
            value = float(row['turnover'])
            valid = valid and math.isfinite(value) and value >= 0
            baseline = original.get(key, {})
            for col, old in baseline.items():
                if col == 'turnover':
                    continue
                new = row.get(col, '')
                try:
                    equal = math.isclose(float(old), float(new), rel_tol=1e-9, abs_tol=1e-11)
                except ValueError:
                    equal = old == new
                valid = valid and equal
        rep.add('holdout.turnover_recovered', valid,
                f'{len(rerun)} replay rows have finite turnover; original return metrics unchanged within tolerance')
        source_ok = all((store.root / p).is_file() and sha256(store.root / p) == digest
                        for p, digest in report['source_sha256'].items())
        rep.add('reproduction.recorded_run', report['status'] == 'PASS' and source_ok,
                'Saved isolated reproduction report passes and its source hashes match; this verifier does not rerun it')
        return []
    return [{'metric': spec['label'], 'file': spec['file'], 'column': spec['column'], 'rows': len(rows),
             'value': None, 'status': 'MISSING' if not filled else 'PRESENT'}]


def check_pairs(claims, store, rep):
    spec = claims['h2_pair_attribution']
    js = store._load(spec['file'])
    bad = []
    for stock, hedge in spec['hedges'].items():
        pair = js['concentration']['pnl_by_pair'][stock]
        legs = js['concentration']['pnl_by_asset'][stock] + js['concentration']['pnl_by_asset'][hedge]
        alone = js['concentration']['pnl_by_asset'][stock]
        if abs(pair - legs) > 1e-9:
            bad.append(f'{stock}: pair {pair} != stock + {hedge} {legs}')
        if f'{pair * 100:.1f}' == f'{alone * 100:.1f}':
            bad.append(f'{stock}: pair and standalone values are indistinguishable')
        label = f'{fmt_value(pair, {"scale": 100, "dp": 1, "suffix": "%"})} ({stock}/{hedge})'
        if label not in claims['_note_text']:
            bad.append(f'note does not label {label}')
    rep.add('h2.pair_attribution', not bad,
            'TXRH/XLY and TSN/XLP figures equal stock-plus-hedge pair P&L, labelled as pairs, not standalone stocks'
            + (f'; problems: {bad}' if bad else ''))


def check_abs_paths(root, art, rep):
    hits = []
    for rel in art['scan_absolute_paths']:
        path = root / rel
        if path.is_file() and _ABS_PATH.search(path.read_text(encoding='utf-8', errors='replace')):
            hits.append(rel)
    rep.add('portability.absolute_paths', not hits,
            f'{len(art["scan_absolute_paths"])} workflow files free of machine-specific absolute paths'
            if not hits else f'absolute paths in: {hits}')


def check_pdf_text(root, claims, results, rep):
    """Optional: compare displayed values with the PDF text if PyMuPDF is already installed."""
    try:
        import fitz  # noqa: F401  (optional; never installed by this tool)
    except Exception:
        rep.add('paper.pdf_text', True, 'skipped: PyMuPDF not installed (optional); HTML-to-PDF correspondence '
                'rests on the hashed pair and build_note.py', level='advisory')
        return
    doc = fitz.open(str(root / claims['paper_pdf']))
    text = norm(' '.join(page.get_text() for page in doc))
    sizes = [round(s['size'], 1) for page in doc for b in page.get_text('dict')['blocks']
             for line in b.get('lines', []) for s in line['spans'] if s['text'].strip()]
    pages = doc.page_count
    doc.close()
    values = {p for r in results for d in r['displayed'] for p in d.split(' / ')}
    values -= {e['saved_displays'] for r in results for e in r['errata']}
    values |= {e['note_shows'] for r in results for e in r['errata']}
    absent = sorted(v for v in values if not contains_value(text, v))
    rep.add('paper.pdf_text', not absent and min(sizes) >= 11,
            f'PyMuPDF: {pages} pages, minimum text size {min(sizes)} pt; every claimed display value found in PDF text'
            if not absent else f'PDF text lacks displayed values: {absent}')


def headline(store, claims):
    """Saved development and holdout headline rows, labelled by role. Values are fractions."""
    keys = ('ann_return', 'ann_vol', 'sharpe', 'max_drawdown', 'turnover')
    out = []
    for h in claims['headline_rows']:
        row = store.rows(h['file'], h['where'])
        if len(row) != 1:
            raise ClaimError(f'headline {h["label"]}: {len(row)} rows')
        r = row[0]
        vals = {}
        for k in keys:
            col = h.get('columns', {}).get(k, k)
            raw = r.get(col, '')
            vals[k] = None if raw is None or str(raw).strip() == '' else float(raw)
        if h.get('turnover_json'):
            node = store._load(h['turnover_json'][0])
            for key in h['turnover_json'][1:]:
                node = node[key]
            vals['turnover'] = float(node)
        if h['period'] == 'holdout' and claims.get('holdout_recovered'):
            recovered = store.rows(claims['holdout_recovered']['file'], h['where'])
            if len(recovered) != 1:
                raise ClaimError('recovered turnover must match exactly one holdout row')
            vals['turnover'] = float(recovered[0]['turnover'])
        out.append({'label': h['label'], 'role': h['role'], 'period': h['period'], 'costs': h['costs'],
                    'source': h['file'], **vals})
    return out


def _pct(x, dp=2):
    return 'MISSING' if x is None else f'{x * 100:+.{dp}f}%'


def render(rep, heads, decisions, trials, missing):
    lines = ['GQH 2026 cattle submission: artifact-only verification', f'Scope: {SCOPE}', '']
    for period in ('development', 'holdout'):
        lines.append(f'{period.upper()} (saved tables; returns on fixed $1M initial capital)')
        lines.append(f'  {"result":34} {"role":24} {"ann.ret":>8} {"vol":>6} {"Sharpe":>7} {"maxDD":>6} {"turnover":>9}')
        for h in (x for x in heads if x['period'] == period):
            turn = 'MISSING' if h['turnover'] is None else f'{h["turnover"]:.1f}x'
            lines.append(f'  {h["label"]:34} {h["role"]:24} {_pct(h["ann_return"]):>8} '
                         f'{h["ann_vol"] * 100:5.1f}% {h["sharpe"]:+7.2f} {h["max_drawdown"] * 100:5.1f}% {turn:>9}')
        lines.append('')
    lines.append('REGISTERED DECISIONS (unchanged; recomputed only to confirm consistency)')
    for hyp, d in decisions.items():
        conds = ', '.join(f'{c["id"]} {"pass" if c["passed"] else "FAIL"}' for c in d['conditions'])
        lines.append(f'  {hyp} ({d["primary"]}): {d["registered_decision"]}  [{conds}]')
    lines += ['', f'TRIALS: {trials["distinct_trial_configurations"]} distinct configurations '
              f'({trials["distinct_h1_configurations"]} H1 + {trials["distinct_h2_configurations"]} H2); '
              f'log {trials["total_rows"]} rows ({trials["development_rows"]} development, '
              f'{trials["holdout_rows"]} holdout); repeats are not new configurations', '']
    for m in missing:
        lines.append(f'MISSING: {m["metric"]} ({m["file"]}:{m["column"]}) -> {m["status"]}; not inferred')
    lines += ['', 'CHECKS']
    for c in rep.checks:
        lines.append(f'  [{c["status"].upper():4}] {c["id"]}: {c["detail"]}')
    lines += ['', 'NOT PROVEN BY THIS COMMAND'] + [f'  - {x}' for x in NOT_PROVEN]
    lines += ['', f'RESULT: {"FAIL" if rep.failed else "PASS"} ({len(rep.failed)} failed, '
              f'{sum(c["status"] == "warn" for c in rep.checks)} advisory)']
    return '\n'.join(lines)


def verify(root=ROOT):
    """Run every check against `root`; returns (report_dict, text). Reads files only."""
    root = Path(root)
    rep = Report()
    art = json.loads((root / ARTIFACTS).read_text(encoding='utf-8'))
    claims = json.loads((root / CLAIMS).read_text(encoding='utf-8'))
    check_files(root, art, rep)
    html_path = root / claims['paper_html']
    note = Note(html_path.read_text(encoding='utf-8') if html_path.is_file() else '')
    claims['_note_text'] = note.text
    store = Store(root)
    check_paper(root, art, claims, note, rep)
    check_labels(claims, rep)
    results = check_claims(root, claims, note, store, rep)
    heads, decisions, trials, missing = [], {}, {}, []
    for name, fn in (('roles', lambda: check_roles(claims, store, rep)),
                     ('decisions', lambda: decisions.update(check_decisions(claims, store, rep))),
                     ('trials', lambda: trials.update(check_trials(root, claims, store, rep))),
                     ('missing', lambda: missing.extend(check_missing(claims, store, rep))),
                     ('pairs', lambda: check_pairs(claims, store, rep)),
                     ('headline', lambda: heads.extend(headline(store, claims)))):
        try:
            fn()
        except (ClaimError, KeyError, ValueError, OSError) as e:
            rep.add(f'{name}.readable', False, f'could not evaluate: {type(e).__name__}: {e}')
    check_abs_paths(root, art, rep)
    check_pdf_text(root, claims, results, rep)
    report = {
        'tool': 'verify_submission.py', 'scope': SCOPE, 'status': 'FAIL' if rep.failed else 'PASS',
        'checks': rep.checks, 'headline': heads, 'registered_decisions': decisions,
        'trial_accounting': trials, 'missing_metrics': missing, 'claims': results,
        'not_machine_checked': claims.get('not_machine_checked', []), 'not_proven': NOT_PROVEN,
    }
    text = render(rep, heads, decisions, trials or {'distinct_trial_configurations': '?',
                  'distinct_h1_configurations': '?', 'distinct_h2_configurations': '?', 'total_rows': '?',
                  'development_rows': '?', 'holdout_rows': '?'}, missing)
    return report, text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--json', default=DEFAULT_REPORT, help=f'JSON report path (default {DEFAULT_REPORT})')
    ap.add_argument('--no-json', action='store_true', help='print the report only')
    args = ap.parse_args(argv)
    install_guards()
    try:
        report, text = verify(ROOT)
    except (OSError, ValueError, KeyError) as e:
        print(f'verify_submission: cannot run: {type(e).__name__}: {e}', file=sys.stderr)
        return 1
    print(text)
    if not args.no_json:
        out = Path(args.json)
        out = out if out.is_absolute() else ROOT / out
        try:
            out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
            print(f'JSON report: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}')
        except OSError as e:
            print(f'verify_submission: could not write JSON report ({e})', file=sys.stderr)
            return 1
    return 1 if report['status'] == 'FAIL' else 0


if __name__ == '__main__':
    sys.exit(main())
