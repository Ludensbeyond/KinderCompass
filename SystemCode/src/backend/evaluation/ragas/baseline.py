"""Freeze a reviewed capture and score report into a hash-checked local baseline."""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import tarfile

from score import METRICS, apply_reviews, inspect_runs, read_jsonl, report_counts

THRESHOLDS = dict(zip(METRICS, (0.90, 0.80, 0.80)))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def summarize(entries):
    origins = Counter(e['agent_status'] for e in entries)
    metrics = {}
    for origin in ('agent', 'fallback'):
        metrics[origin] = {}
        for metric in METRICS:
            values = [e['metrics'][metric]['value'] for e in entries
                      if e['agent_status'] == origin and
                      e['metrics'].get(metric, {}).get('status') == 'scored']
            metrics[origin][metric] = {'count': len(values),
                                      'mean': sum(values) / len(values) if values else None}
    return {'cases': len(entries), 'accepted_agent': origins['agent'],
            'controller_fallback': origins['fallback'],
            'scored': sum(e['status'] == 'scored' for e in entries),
            'answer_completeness_pass': sum(e['evaluation'] == 'ragas' and
                                           e['review'].get('pass') is True for e in entries),
            'behaviour_pass': sum(e['evaluation'] == 'behaviour' and e['review']['status'] == 'complete' and
                                 all(c['pass'] for c in e['review']['checks']) for e in entries),
            'metrics_by_origin': metrics}


def build_bundle(cases_path, dataset_path, runs_path, run_manifest_path, scores_path,
                 score_report_path, reviews_path, notes_path, output, repeat_dir=None):
    paths = {'cases.jsonl': cases_path, 'dataset.manifest.json': dataset_path,
             'captures.jsonl': runs_path, 'run.manifest.json': run_manifest_path,
             'scores.csv': scores_path, 'scores.report.json': score_report_path,
             'reviews.json': reviews_path, 'review-notes.md': notes_path}
    data = {name: path.read_bytes() for name, path in paths.items()}
    dataset = json.loads(data['dataset.manifest.json'])
    run_manifest = json.loads(data['run.manifest.json'])
    report = json.loads(data['scores.report.json'])
    if sha256(data['cases.jsonl']) != dataset['files']['cases.jsonl']['sha256']:
        split = run_manifest.get('split')
        frozen_path = dataset_path.with_name('cases.jsonl')
        if split not in dataset.get('splits', {}) or sha256(frozen_path.read_bytes()) != dataset['files']['cases.jsonl']['sha256']:
            raise ValueError('Frozen dataset cases hash mismatch')
        selected = set(dataset['splits'][split])
        expected = [case for case in read_jsonl(frozen_path) if case['case_id'] in selected]
        if read_jsonl(cases_path) != expected:
            raise ValueError('Selected cases differ from the frozen split')
    if dataset['dataset_version'] != run_manifest['dataset_version'] or dataset['evidence_snapshot'] != run_manifest['evidence_snapshot']:
        raise ValueError('Capture dataset or evidence snapshot mismatch')
    for name, expected in [('cases.jsonl', report['sha256']['cases']),
                           ('captures.jsonl', report['sha256']['runs']),
                           ('reviews.json', report['sha256']['reviews']),
                           ('captures.jsonl', run_manifest['capture_sha256'])]:
        if sha256(data[name]) != expected:
            raise ValueError(f'Input hash mismatch: {name}')
    cases, runs = read_jsonl(cases_path), read_jsonl(runs_path)
    results, mapping = inspect_runs(cases, runs)
    if len(runs) != len(cases) or set(run_manifest['expected_case_ids']) != set(mapping):
        raise ValueError('Baseline must retain every case including execution failures')
    if run_manifest['attempted'] != len(runs):
        raise ValueError('Capture manifest attempted count mismatch')
    actual_execution = [{'case_id': r['case_id'], 'status': r['status'],
                         'execution_error': r.get('execution_error')} for r in runs]
    if actual_execution != run_manifest['results']:
        raise ValueError('Capture manifest execution results mismatch')
    apply_reviews(cases, results, json.loads(data['reviews.json']))
    entries = report['cases']
    if [e['case_id'] for e in entries] != [c['case_id'] for c in cases]:
        raise ValueError('Score report must retain every dataset case in order')
    for expected, entry in zip(results, entries):
        for key in ('evaluation', 'category', 'agent_status', 'executed', 'review'):
            if expected[key] != entry[key]:
                raise ValueError(f'Score report disagrees with capture/review: {entry["case_id"]} / {key}')
        if expected['status'] != 'ready' and expected['status'] != entry['status']:
            raise ValueError('Score report changed an unscorable execution status')
        if entry['review']['status'] != 'complete' and expected['status'] not in ('execution_failed', 'invalid_capture', 'missing_capture'):
            raise ValueError('Baseline requires completed behaviour and completeness reviews')
    if report_counts(entries, len(runs)) != report['counts']:
        raise ValueError('Score report counts mismatch')
    csv_rows = list(csv.DictReader(io.StringIO(data['scores.csv'].decode())))
    if [r['case_id'] for r in csv_rows] != [e['case_id'] for e in entries]:
        raise ValueError('CSV case IDs mismatch')
    for row, entry in zip(csv_rows, entries):
        if row['status'] != entry['status'] or row['reason'] != (entry['reason'] or ''):
            raise ValueError('CSV outcome mismatch')
        for metric in METRICS:
            value = entry['metrics'].get(metric, {}).get('value')
            if (float(row[metric]) if row[metric] else None) != value:
                raise ValueError('CSV metric mismatch')
    for entry in entries:
        states = set()
        if entry['status'] in ('scored', 'undefined', 'scoring_failed'):
            if set(entry['metrics']) != set(METRICS):
                raise ValueError('Missing metric outcomes')
            for outcome in entry['metrics'].values():
                states.add(outcome['status'])
                if outcome['status'] == 'scored':
                    value = outcome['value']
                    if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                        raise ValueError('Invalid finite score')
                elif outcome['status'] not in ('undefined', 'scoring_failed') or outcome['value'] is not None or not outcome.get('reason'):
                    raise ValueError('Invalid missing metric outcome')
            expected_status = ('scoring_failed' if 'scoring_failed' in states else
                               'undefined' if 'undefined' in states else 'scored')
            if entry['status'] != expected_status:
                raise ValueError('Metric status mismatch')
        elif entry['metrics']:
            raise ValueError('Unscorable case has fabricated metrics')
    if repeat_dir:
        for path in sorted(repeat_dir.iterdir()):
            if path.is_file() and path.suffix in ('.json', '.jsonl', '.csv'):
                data['judge-repeats/' + path.name] = path.read_bytes()
        repeat_cases = read_jsonl(repeat_dir / 'cases.jsonl')
        repeat_runs = read_jsonl(repeat_dir / 'runs.jsonl')
        original_cases = {c['case_id']: c for c in cases}
        for case in repeat_cases:
            if case != original_cases.get(case['case_id']):
                raise ValueError('Repeat labels differ from baseline')
        for run in repeat_runs:
            if run != mapping.get(run['case_id']):
                raise ValueError('Repeat capture differs from baseline')
        for path in repeat_dir.glob('*.report.json'):
            repeated = json.loads(path.read_text())
            if repeated['judge'] != report['judge'] or repeated['versions'] != report['versions']:
                raise ValueError('Repeat judge settings differ from baseline')
            for key, filename in [('cases', 'cases.jsonl'), ('runs', 'runs.jsonl'), ('reviews', 'reviews.json')]:
                if repeated['sha256'][key] != sha256((repeat_dir / filename).read_bytes()):
                    raise ValueError('Repeat input hash mismatch')
    categories = defaultdict(list)
    for entry in entries:
        categories[entry['category']].append(entry)
    per_case = []
    for entry in entries:
        flags = [metric for metric, threshold in THRESHOLDS.items()
                 if entry['metrics'].get(metric, {}).get('status') == 'scored' and
                 entry['metrics'][metric]['value'] < threshold]
        undefined = [m for m, v in entry['metrics'].items() if v['status'] == 'undefined']
        review_pass = (entry['review']['status'] == 'complete' and
                       (entry['review'].get('pass') is True if entry['evaluation'] == 'ragas'
                        else all(c['pass'] for c in entry['review']['checks'])))
        per_case.append({'case_id': entry['case_id'], 'category': entry['category'],
                         'agent_status': entry['agent_status'], 'score_status': entry['status'],
                         'metric_flags': flags, 'undefined_metrics': undefined,
                         'review_pass': review_pass,
                         'requires_review': bool(flags or undefined or not review_pass or
                                                 entry['status'] not in ('scored', 'behaviour_review'))})
    manifest = {'baseline_id': output.name.removesuffix('.tar.gz'),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'dataset_version': dataset['dataset_version'],
                'evidence_snapshot': dataset['evidence_snapshot'],
                'judge': report['judge'], 'counts': report['counts'],
                'summary': summarize(entries),
                'categories': {name: summarize(group) for name, group in sorted(categories.items())},
                'provisional_thresholds': THRESHOLDS, 'release_gate': False,
                'cases': per_case,
                'files': {name: {'sha256': sha256(content), 'bytes': len(content)}
                          for name, content in data.items()}}
    if output.exists():
        raise ValueError('Refusing to overwrite a baseline bundle')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, 'w:gz') as archive:
        for name, content in {**data, 'bundle.manifest.json':
                              (json.dumps(manifest, indent=2) + '\n').encode()}.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    verify_bundle(output)
    return manifest


def verify_bundle(path):
    with tarfile.open(path, 'r:gz') as archive:
        names = archive.getnames()
        if len(set(names)) != len(names):
            raise ValueError('Duplicate archive members')
        manifest = json.load(archive.extractfile('bundle.manifest.json'))
        if set(names) != set(manifest['files']) | {'bundle.manifest.json'}:
            raise ValueError('Archive inventory mismatch')
        for name, expected in manifest['files'].items():
            content = archive.extractfile(name).read()
            if sha256(content) != expected['sha256'] or len(content) != expected['bytes']:
                raise ValueError(f'Archive hash mismatch: {name}')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeat-dir', type=Path, help='Reviewed judge-repeat input and output files')
    parser.add_argument('--verify', type=Path, help='Verify an existing bundle without extraction')
    parser.add_argument('--cases', type=Path, default=Path(__file__).with_name('cases.jsonl'))
    parser.add_argument('--dataset-manifest', type=Path, default=Path(__file__).with_name('manifest.json'))
    for arg in ('runs', 'run-manifest', 'scores', 'score-report', 'reviews', 'notes', 'output'):
        parser.add_argument('--' + arg, type=Path)
    args = parser.parse_args()
    if args.verify:
        manifest = verify_bundle(args.verify)
    else:
        if any(getattr(args, name) is None for name in
               ('runs', 'run_manifest', 'scores', 'score_report', 'reviews', 'notes', 'output')):
            parser.error('Bundle creation requires capture, scores, reviews, notes and output paths')
        manifest = build_bundle(args.cases, args.dataset_manifest, args.runs, args.run_manifest,
                                args.scores, args.score_report, args.reviews, args.notes, args.output, args.repeat_dir)
    print(json.dumps({'baseline_id': manifest['baseline_id'], 'counts': manifest['counts'],
                      'accepted_agent': manifest['summary']['accepted_agent'],
                      'controller_fallback': manifest['summary']['controller_fallback']}))


if __name__ == '__main__':
    main()
