"""Compare verified private evaluation bundles by case ID; never call a provider."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import tarfile

from baseline import THRESHOLDS, verify_bundle
from score import METRICS, report_counts


def load_bundle(path):
    manifest = verify_bundle(path)
    with tarfile.open(path, 'r:gz') as archive:
        data = {name: json.load(archive.extractfile(name)) for name in
                ('dataset.manifest.json', 'run.manifest.json', 'scores.report.json')}
    return {'bundle': manifest, 'dataset': data['dataset.manifest.json'],
            'run': data['run.manifest.json'], 'scores': data['scores.report.json']}


def compatibility(run):
    dataset, capture, scores = run['dataset'], run['run'], run['scores']
    # Missing metadata is not evidence that two runs used the same inputs.
    required = {'dataset_id': dataset.get('dataset_id'),
                'dataset_version': dataset.get('dataset_version'),
                'dataset_files': dataset.get('files'),
                'evidence_snapshot': capture.get('evidence_snapshot'),
                'supporting_snapshots': capture.get('supporting_snapshots'),
                'judge': scores.get('judge'), 'judge_versions': scores.get('versions'),
                'scorer_sha256': scores.get('sha256', {}).get('scorer')}
    if any(value is None or value == {} or value == [] for value in required.values()):
        raise ValueError('Missing compatibility metadata; establish a new baseline with current capture tooling')
    if dataset['dataset_version'] != capture['dataset_version'] or dataset['files'] != capture['dataset_files']:
        raise ValueError('Capture does not match its frozen dataset')
    if dataset['evidence_snapshot'] != capture['evidence_snapshot']:
        raise ValueError('Capture does not match its frozen evidence')
    # Paths depend on the checkout location; hash and basename identify each snapshot.
    snapshots = {}
    for snapshot in capture['supporting_snapshots']:
        name = Path(snapshot['path']).name
        if name in snapshots or not snapshot.get('sha256'):
            raise ValueError('Ambiguous or missing supporting snapshot hash')
        snapshots[name] = snapshot['sha256']
    required['supporting_snapshots'] = snapshots
    for snapshot in dataset.get('supporting_snapshots', []):
        if snapshots.get(Path(snapshot['path']).name) != snapshot['sha256']:
            raise ValueError('Capture does not match frozen supporting evidence')
    required['split'] = capture.get('split', 'all')
    required['execution_schema'] = capture.get('execution_schema', 'single_turn_v1')
    required['case_ids'] = sorted(capture['expected_case_ids'])
    entries = scores['cases']
    ids = [entry['case_id'] for entry in entries]
    if len(ids) != len(set(ids)) or sorted(ids) != required['case_ids']:
        raise ValueError('Comparison must retain every expected case exactly once')
    if report_counts(entries, capture['attempted']) != scores['counts']:
        raise ValueError('Score report denominator mismatch')
    return required


def review_checks(entry):
    review = entry['review']
    if review['status'] != 'complete':
        return {}
    if entry['evaluation'] == 'ragas':
        return {'Answer completeness': {'pass': review['pass'], 'reason': review['reason']}}
    return {check['check']: check for check in review['checks']}


def issues(entry):
    problems = []
    if entry['status'] not in ('scored', 'behaviour_review'):
        problems.append({'type': entry['status'], 'reason': entry.get('reason')})
    if entry['review']['status'] != 'complete':
        problems.append({'type': 'review_pending', 'reason': 'Explicit review is incomplete'})
    for name, check in review_checks(entry).items():
        if not check['pass']:
            problems.append({'type': 'review_failed', 'check': name, 'reason': check['reason']})
    for name, outcome in entry['metrics'].items():
        if outcome['status'] != 'scored':
            problems.append({'type': outcome['status'], 'metric': name, 'reason': outcome.get('reason')})
        elif outcome['value'] < THRESHOLDS[name]:
            problems.append({'type': 'provisional_metric_flag', 'metric': name,
                             'reason': f"{outcome['value']:.4f} < {THRESHOLDS[name]:.2f}"})
    return problems


def compare(baseline, candidate):
    old_key, new_key = compatibility(baseline), compatibility(candidate)
    differences = [key for key in old_key if old_key[key] != new_key[key]]
    if differences:
        raise ValueError('Incompatible ' + ', '.join(differences) + '; establish a new baseline')
    old_entries = {e['case_id']: e for e in baseline['scores']['cases']}
    rows = []
    for new in candidate['scores']['cases']:
        old = old_entries[new['case_id']]
        metrics = {}
        for name in METRICS:
            before, after = old['metrics'].get(name, {}), new['metrics'].get(name, {})
            comparable = (before.get('status') == after.get('status') == 'scored' and
                          old['agent_status'] == new['agent_status'])
            metrics[name] = {'baseline': before, 'candidate': after,
                             'delta': after['value'] - before['value'] if comparable else None,
                             'reason': None if comparable else 'Missing finite scores or changed answer origin'}
        before_checks, after_checks = review_checks(old), review_checks(new)
        regressions = [{'check': name, 'reason': after_checks.get(name, {}).get('reason', 'Review pending')}
                       for name, check in before_checks.items()
                       if check['pass'] and after_checks.get(name, {}).get('pass') is not True]
        rows.append({'case_id': new['case_id'], 'category': new['category'],
                     'baseline_status': old['status'], 'candidate_status': new['status'],
                     'baseline_origin': old['agent_status'], 'candidate_origin': new['agent_status'],
                     'fallback_changed': (old['agent_status'] == 'fallback') != (new['agent_status'] == 'fallback'),
                     'metrics': metrics, 'review_regressions': regressions,
                     'baseline_issues': issues(old), 'unresolved_issues': issues(new)})
    return {'created_at': datetime.now(timezone.utc).isoformat(), 'compatible': True,
            'release_gate': False, 'compatibility': old_key,
            'baseline_id': baseline['bundle']['baseline_id'],
            'candidate_id': candidate['bundle']['baseline_id'],
            'baseline_counts': baseline['scores']['counts'], 'candidate_counts': candidate['scores']['counts'],
            'agent_settings': {'baseline': baseline['run'].get('model_settings'),
                               'candidate': candidate['run'].get('model_settings')},
            'git_revisions': {'baseline': baseline['run'].get('git_revision'),
                              'candidate': candidate['run'].get('git_revision')},
            'summary': {'cases': len(rows),
                        'review_regressions': sum(bool(r['review_regressions']) for r in rows),
                        'fallback_changes': sum(r['fallback_changed'] for r in rows),
                        'unresolved_cases': sum(bool(r['unresolved_issues']) for r in rows)},
            'cases': rows}


def markdown(report):
    lines = ['# Evaluation comparison', '',
             f"Baseline: {report['baseline_id']}; candidate: {report['candidate_id']}.", '',
             f"Compatible inputs; {report['summary']['cases']} cases. Provisional flags require review; this is not a release gate.", '',
             f"Review regressions: {report['summary']['review_regressions']}; fallback changes: {report['summary']['fallback_changes']}; unresolved cases: {report['summary']['unresolved_cases']}.", '',
             '| Count | Baseline | Candidate |', '|---|---:|---:|',
             *[f"| {name} | {report['baseline_counts'][name]} | {report['candidate_counts'][name]} |"
               for name in report['baseline_counts']], '',
             'Judge: `' + json.dumps(report['compatibility']['judge'], sort_keys=True) + '`.', '',
             'Agent settings (baseline → candidate): `' + json.dumps(report['agent_settings'], sort_keys=True) + '`.', '',
             'Deltas are candidate minus baseline. — means no finite pair with the same answer origin.', '',
             '| Case | Outcome (before → after) | Origin (before → after) | Δ faithfulness | Δ precision | Δ recall |',
             '|---|---|---|---:|---:|---:|']
    for row in report['cases']:
        deltas = ['—' if row['metrics'][m]['delta'] is None else f"{row['metrics'][m]['delta']:+.4f}" for m in METRICS]
        lines.append(f"| {row['case_id']} | {row['baseline_status']} → {row['candidate_status']} | "
                     f"{row['baseline_origin']} → {row['candidate_origin']} | " + ' | '.join(deltas) + ' |')
    lines += ['', '## Review regressions and unresolved failures', '']
    for row in report['cases']:
        for regression in row['review_regressions']:
            lines.append(f"- {row['case_id']}: review regression — {regression['check']}: {regression['reason']}")
        if row['fallback_changed']:
            lines.append(f"- {row['case_id']}: fallback changed ({row['baseline_origin']} → {row['candidate_origin']}).")
        for issue in row['unresolved_issues']:
            lines.append(f"- {row['case_id']}: {issue['type']} {issue.get('metric', issue.get('check', ''))}: {issue['reason']}")
    if not any(r['unresolved_issues'] or r['review_regressions'] or r['fallback_changed'] for r in report['cases']):
        lines.append('No unresolved failures, review regressions or fallback changes.')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='JSON report; Markdown written beside it')
    args = parser.parse_args()
    try:
        report = compare(load_bundle(args.baseline), load_bundle(args.candidate))
    except (ValueError, KeyError, tarfile.TarError) as error:
        parser.exit(2, str(error) + '\n')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    args.output.with_suffix('.md').write_text(markdown(report))
    print(json.dumps(report['summary']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
