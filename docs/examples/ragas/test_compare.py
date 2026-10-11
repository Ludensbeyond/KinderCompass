"""Offline regression checks use synthetic scores, never provider calls."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

from compare import compare, load_bundle, markdown
from select_cases import select_cases
import test_baseline


class ComparisonTests(unittest.TestCase):
    def fixture(self, root):
        helper = test_baseline.BaselineTests()
        helper.fixtures(str(root))
        dataset = json.loads((root / 'dataset.json').read_text())
        dataset['dataset_id'] = 'synthetic'
        (root / 'dataset.json').write_text(json.dumps(dataset))
        capture = json.loads((root / 'manifest.json').read_text())
        capture.update(dataset_files=dataset['files'], supporting_snapshots=[{'path': '/checkout/index.json', 'sha256': 'fixed'}])
        (root / 'manifest.json').write_text(json.dumps(capture))
        scores = json.loads((root / 'scores.report.json').read_text())
        scores.update(versions={'ragas': 'test'})
        scores['sha256']['scorer'] = 'fixed'
        (root / 'scores.report.json').write_text(json.dumps(scores))
        helper.build(root)
        return load_bundle(root / 'baseline.tar.gz')

    def test_same_bundle_and_case_id_order(self):
        with tempfile.TemporaryDirectory() as directory:
            old = self.fixture(Path(directory))
            new = deepcopy(old)
            new['scores']['cases'].reverse()
            result = compare(old, new)
            self.assertEqual(result['summary']['cases'], 2)
            self.assertEqual(result['summary']['review_regressions'], 0)
            self.assertEqual(result['cases'][1]['metrics']['faithfulness']['delta'], 0)
            self.assertIn('+0.0000', markdown(result))
            self.assertFalse(result['release_gate'])

    def test_score_behaviour_fallback_and_undefined_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            old = self.fixture(Path(directory))
            new = deepcopy(old)
            evidence, behaviour = new['scores']['cases']
            evidence['metrics']['faithfulness']['value'] = .5
            evidence['metrics']['context_recall'] = {'status': 'undefined', 'value': None, 'reason': 'Claim-free'}
            evidence['status'] = 'undefined'
            behaviour['agent_status'] = 'agent'
            behaviour['review']['checks'][0].update({'pass': False, 'reason': 'Invented a fact'})
            from score import report_counts
            new['scores']['counts'] = report_counts(new['scores']['cases'], 2)
            report = compare(old, new)
            self.assertEqual(report['cases'][0]['metrics']['faithfulness']['delta'], -.25)
            self.assertIsNone(report['cases'][0]['metrics']['context_recall']['delta'])
            self.assertEqual(report['summary']['review_regressions'], 1)
            self.assertEqual(report['summary']['fallback_changes'], 1)
            self.assertIn('Invented a fact', markdown(report))
            self.assertIn('undefined', markdown(report))

    def test_incompatible_or_unknown_inputs_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            old = self.fixture(Path(directory))
            for section, key, value in [
                ('dataset', 'dataset_version', 'changed'),
                ('dataset', 'files', {'different': {}}),
                ('run', 'evidence_snapshot', {'sha256': 'changed'}),
                ('run', 'supporting_snapshots', [{'path': '/other/index.json', 'sha256': 'changed'}]),
                ('run', 'split', 'held_out'),
                ('run', 'expected_case_ids', ['a']),
                ('scores', 'judge', {'model': 'different'}),
                ('scores', 'versions', {'ragas': 'different'}),
                ('run', 'supporting_snapshots', None),
            ]:
                with self.subTest(key=key):
                    new = deepcopy(old)
                    new[section][key] = value
                    with self.assertRaises(ValueError):
                        compare(old, new)
            new = deepcopy(old)
            new['scores']['sha256']['scorer'] = 'different'
            with self.assertRaisesRegex(ValueError, 'scorer_sha256'):
                compare(old, new)

    def test_changed_origin_does_not_produce_a_score_delta(self):
        with tempfile.TemporaryDirectory() as directory:
            old = self.fixture(Path(directory))
            new = deepcopy(old)
            new['scores']['cases'][0]['agent_status'] = 'fallback'
            report = compare(old, new)
            self.assertIsNone(report['cases'][0]['metrics']['faithfulness']['delta'])
            self.assertTrue(report['cases'][0]['fallback_changed'])

    def test_cli_writes_private_reports_and_rejects_unknown_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            command = [sys.executable, str(Path(__file__).with_name('compare.py')),
                       '--baseline', str(root / 'baseline.tar.gz'),
                       '--candidate', str(root / 'baseline.tar.gz'),
                       '--output', str(root / 'comparison.json')]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads((root / 'comparison.json').read_text())['summary']['cases'], 2)
            self.assertIn('Evaluation comparison', (root / 'comparison.md').read_text())
            legacy = root / 'legacy'
            legacy.mkdir()
            self.fixture(legacy)
            (legacy / 'baseline.tar.gz').rename(legacy / 'previous.tar.gz')
            capture = json.loads((legacy / 'manifest.json').read_text())
            capture.pop('supporting_snapshots')
            (legacy / 'manifest.json').write_text(json.dumps(capture))
            test_baseline.BaselineTests().build(legacy)
            command[command.index('--candidate') + 1] = str(legacy / 'baseline.tar.gz')
            command[-1] = str(root / 'rejected.json')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('establish a new baseline', result.stderr)
            self.assertFalse((root / 'rejected.json').exists())

    def test_failed_execution_can_be_bundled_with_pending_review(self):
        from baseline import sha256
        from score import inspect_runs, apply_reviews, score_results, report_counts, write_reports
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            (root / 'baseline.tar.gz').rename(root / 'original.tar.gz')
            runs = [json.loads(line) for line in (root / 'runs.jsonl').read_text().splitlines()]
            runs[1].update(status='execution_error', response=None, execution_error={'type': 'TimeoutError'})
            (root / 'runs.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in runs))
            reviews = json.loads((root / 'reviews.json').read_text())
            reviews.pop('b')
            (root / 'reviews.json').write_text(json.dumps(reviews))
            capture = json.loads((root / 'manifest.json').read_text())
            capture['capture_sha256'] = sha256((root / 'runs.jsonl').read_bytes())
            capture['results'] = [{'case_id': r['case_id'], 'status': r['status'], 'execution_error': r.get('execution_error')} for r in runs]
            (root / 'manifest.json').write_text(json.dumps(capture))
            cases = [json.loads(line) for line in (root / 'cases.jsonl').read_text().splitlines()]
            entries, mapping = inspect_runs(cases, runs)
            apply_reviews(cases, entries, reviews)
            score_results(cases, entries, mapping, lambda row, metric: .75)
            scores = json.loads((root / 'scores.report.json').read_text())
            scores.update(cases=entries, counts=report_counts(entries, 2))
            scores['sha256'].update(runs=capture['capture_sha256'], reviews=sha256((root / 'reviews.json').read_bytes()))
            write_reports(root / 'scores.csv', scores, cases, mapping)
            test_baseline.BaselineTests().build(root)
            report = compare(load_bundle(root / 'original.tar.gz'), load_bundle(root / 'baseline.tar.gz'))
            self.assertEqual(report['candidate_counts']['expected'], 2)
            self.assertIn('execution_failed', markdown(report))
            self.assertIn('review_pending', markdown(report))

    def test_frozen_split_export_and_bundle(self):
        from baseline import build_bundle, sha256
        from score import inspect_runs, apply_reviews, score_results, report_counts, write_reports
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = Path(__file__).with_name('expanded')
            self.assertEqual(select_cases(source, 'tuning', root / 'selected.jsonl'), 20)
            self.assertEqual(select_cases(source, 'held_out', root / 'held-out.jsonl'), 4)
            old = self.fixture(root)
            dataset = json.loads((root / 'dataset.json').read_text())
            dataset['splits'] = {'tuning': ['a']}
            (root / 'dataset.json').write_text(json.dumps(dataset))
            case = json.loads((root / 'cases.jsonl').read_text().splitlines()[0])
            (root / 'selected.jsonl').write_text(json.dumps(case) + '\n')
            run = json.loads((root / 'runs.jsonl').read_text().splitlines()[0])
            (root / 'selected-runs.jsonl').write_text(json.dumps(run) + '\n')
            reviews = {'a': {'pass': True, 'reason': 'Complete'}}
            (root / 'selected-reviews.json').write_text(json.dumps(reviews))
            capture = old['run']
            capture.update(split='tuning', attempted=1, expected_case_ids=['a'], results=[{'case_id': 'a', 'status': 'agent', 'execution_error': None}], capture_sha256=sha256((root / 'selected-runs.jsonl').read_bytes()))
            (root / 'selected.manifest.json').write_text(json.dumps(capture))
            entries, mapping = inspect_runs([case], [run])
            apply_reviews([case], entries, reviews)
            score_results([case], entries, mapping, lambda row, metric: .75)
            scores = old['scores']
            scores.update(cases=entries, counts=report_counts(entries, 1))
            scores['sha256'].update(cases=sha256((root / 'selected.jsonl').read_bytes()), runs=capture['capture_sha256'], reviews=sha256((root / 'selected-reviews.json').read_bytes()))
            write_reports(root / 'selected.csv', scores, [case], mapping)
            build_bundle(root / 'selected.jsonl', root / 'dataset.json', root / 'selected-runs.jsonl', root / 'selected.manifest.json', root / 'selected.csv', root / 'selected.report.json', root / 'selected-reviews.json', root / 'notes.md', root / 'split.tar.gz')
            bundle = load_bundle(root / 'split.tar.gz')
            self.assertEqual(compare(bundle, bundle)['summary']['cases'], 1)
            (root / 'selected.jsonl').write_text(json.dumps({**case, 'reference': 'Changed'}) + '\n')
            with self.assertRaisesRegex(ValueError, 'frozen split'):
                build_bundle(root / 'selected.jsonl', root / 'dataset.json', root / 'selected-runs.jsonl', root / 'selected.manifest.json', root / 'selected.csv', root / 'selected.report.json', root / 'selected-reviews.json', root / 'notes.md', root / 'bad.tar.gz')


if __name__ == '__main__':
    unittest.main()
