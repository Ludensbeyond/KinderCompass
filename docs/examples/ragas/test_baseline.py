"""Offline baseline integrity and origin-separation checks."""
import csv
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from baseline import build_bundle, sha256, summarize, verify_bundle
from score import METRICS, apply_reviews, inspect_runs, report_counts, score_results, write_reports


class BaselineTests(unittest.TestCase):
    def fixtures(self, directory):
        root = Path(directory)
        cases = [{'case_id': 'a', 'evaluation': 'ragas', 'category': 'general',
                  'user_input': 'Question?', 'reference': 'Fact.'},
                 {'case_id': 'b', 'evaluation': 'behaviour', 'category': 'behaviour',
                  'user_input': 'Invent?', 'checks': ['Declines invention.']}]
        runs = [{'case_id': 'a', 'response': 'Fact.', 'retrieved_contexts': ['Fact.'], 'status': 'agent'},
                {'case_id': 'b', 'response': 'No.', 'retrieved_contexts': [], 'status': 'fallback'}]
        reviews = {'a': {'pass': True, 'reason': 'All facts present.'},
                   'b': {'checks': [{'check': 'Declines invention.', 'pass': True, 'reason': 'Says no.'}]}}
        for name, rows in [('cases.jsonl', cases), ('runs.jsonl', runs)]:
            (root / name).write_text(''.join(json.dumps(r) + '\n' for r in rows))
        (root / 'reviews.json').write_text(json.dumps(reviews))
        dataset = {'dataset_version': 'test', 'files': {'cases.jsonl': {
            'sha256': sha256((root / 'cases.jsonl').read_bytes())}}, 'evidence_snapshot': {'sha256': 'fixed'}}
        manifest = {'dataset_version': 'test', 'evidence_snapshot': dataset['evidence_snapshot'],
                    'capture_sha256': sha256((root / 'runs.jsonl').read_bytes()),
                    'attempted': 2, 'expected_case_ids': ['a', 'b'],
                    'results': [{'case_id': r['case_id'], 'status': r['status'], 'execution_error': None} for r in runs]}
        results, mapping = inspect_runs(cases, runs)
        apply_reviews(cases, results, reviews)
        score_results(cases, results, mapping, lambda row, metric: .75)
        report = {'cases': results, 'counts': report_counts(results, 2), 'judge': {'model': 'test'},
                  'sha256': {'cases': dataset['files']['cases.jsonl']['sha256'],
                             'runs': manifest['capture_sha256'],
                             'reviews': sha256((root / 'reviews.json').read_bytes())}}
        write_reports(root / 'scores.csv', report, cases, mapping)
        for name, obj in [('dataset.json', dataset), ('manifest.json', manifest)]:
            (root / name).write_text(json.dumps(obj))
        (root / 'notes.md').write_text('Reviewed failures and next improvement.\n')
        return root

    def build(self, root):
        return build_bundle(root / 'cases.jsonl', root / 'dataset.json', root / 'runs.jsonl',
                            root / 'manifest.json', root / 'scores.csv', root / 'scores.report.json',
                            root / 'reviews.json', root / 'notes.md', root / 'baseline.tar.gz')

    def test_bundle_preserves_denominator_flags_and_separate_origins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixtures(directory)
            manifest = self.build(root)
            self.assertEqual(verify_bundle(root / 'baseline.tar.gz'), manifest)
            self.assertEqual(manifest['summary']['accepted_agent'], 1)
            self.assertEqual(manifest['summary']['controller_fallback'], 1)
            self.assertEqual(manifest['cases'][0]['metric_flags'], list(METRICS))
            self.assertFalse(manifest['release_gate'])
            self.assertEqual(manifest['summary']['metrics_by_origin']['fallback']['faithfulness']['count'], 0)
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                self.build(root)
            with tarfile.open(root / 'baseline.tar.gz') as archive:
                self.assertEqual(archive.extractfile('captures.jsonl').read(), (root / 'runs.jsonl').read_bytes())

    def test_mismatched_inputs_csv_reviews_and_denominator_are_rejected(self):
        for target in ('runs.jsonl', 'reviews.json', 'scores.csv', 'scores.report.json'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as directory:
                root = self.fixtures(directory)
                path = root / target
                if target.endswith('.jsonl') or target == 'reviews.json':
                    path.write_text(path.read_text() + '\n')
                elif target == 'scores.csv':
                    path.write_text(path.read_text().replace('0.75', '0.50'))
                else:
                    report = json.loads(path.read_text())
                    report['cases'].pop()
                    path.write_text(json.dumps(report))
                with self.assertRaises(ValueError):
                    self.build(root)
                self.assertFalse((root / 'baseline.tar.gz').exists())

    def test_archive_corruption_is_detected_without_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixtures(directory)
            self.build(root)
            with tarfile.open(root / 'baseline.tar.gz') as original, tarfile.open(root / 'corrupt.tar.gz', 'w:gz') as corrupt:
                for member in original.getmembers():
                    content = original.extractfile(member).read()
                    if member.name == 'captures.jsonl':
                        content += b'changed'
                        member.size = len(content)
                    corrupt.addfile(member, io.BytesIO(content))
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                verify_bundle(root / 'corrupt.tar.gz')

    def test_metrics_are_never_pooled_across_fallback_and_agent(self):
        entries = [{'agent_status': origin, 'status': 'scored', 'evaluation': 'ragas',
                    'review': {'pass': True}, 'metrics': {m: {'status': 'scored', 'value': value}
                                                        for m in METRICS}}
                   for origin, value in [('agent', .2), ('fallback', 1)]]
        summary = summarize(entries)
        self.assertEqual(summary['metrics_by_origin']['agent']['faithfulness']['mean'], .2)
        self.assertEqual(summary['metrics_by_origin']['fallback']['faithfulness']['mean'], 1)


if __name__ == '__main__':
    unittest.main()
