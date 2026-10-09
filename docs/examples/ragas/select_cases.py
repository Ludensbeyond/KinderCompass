"""Export a frozen labelled split for scoring; never supply these labels to capture."""

import argparse
import json
from pathlib import Path

from baseline import sha256
from score import read_jsonl


def select_cases(directory, split, output):
    manifest = json.loads((directory / 'manifest.json').read_text())
    path = directory / 'cases.jsonl'
    if sha256(path.read_bytes()) != manifest['files']['cases.jsonl']['sha256']:
        raise ValueError('Frozen cases hash mismatch')
    ids = set(manifest['splits'][split])
    cases = [case for case in read_jsonl(path) if case['case_id'] in ids]
    if len(cases) != len(ids):
        raise ValueError('Frozen split case count mismatch')
    if output.resolve().is_relative_to(Path(__file__).resolve().parents[3]):
        raise ValueError('Write generated split files outside the repository')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(''.join(json.dumps(case) + '\n' for case in cases))
    return len(cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-dir', type=Path, required=True)
    parser.add_argument('--split', choices=('tuning', 'held_out'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({'cases': select_cases(args.dataset_dir, args.split, args.output), 'split': args.split}))


if __name__ == '__main__':
    main()
