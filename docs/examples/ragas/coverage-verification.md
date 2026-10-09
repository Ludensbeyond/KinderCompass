# Step 7 coverage verification

Completed 9 October 2026. [Expanded manifest](expanded/manifest.json) freezes a
separate 2.0.0 dataset of 24 cases: 16 evidence cases and eight behaviour cases.
Twenty are tuning cases and four are held out for reporting after tuning.
[Review decisions](expanded/review.md) explain all added references, setup,
provenance, exact checks and final-turn scoring. The starter and its baseline
are preserved for compatible reruns.

## Verification

From the repository root, the complete offline evaluation suite passes:

```bash
PYTHONPATH=.:docs/examples/ragas:SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m unittest discover -s docs/examples/ragas -p 'test_*.py' -q
```

22 tests pass, including five new coverage tests. They verify all frozen dataset
and supporting snapshot hashes, stable school identities, reviewed labels,
label-free inputs, 24 unique IDs, disjoint 20/4 splits, final-turn selection and
16/8 scorer compatibility using a clearly synthetic format fixture.

Actual deterministic service replay verifies the three conversation setups and
returned profile deltas. The authoritative fee engine independently verifies
85 → 272 under the fixed income change; captured controller wording matches
those amounts. These offline runs use controller fallbacks with no model and
are not accepted-agent results. Partial setup failures remain explicit and
prevent scoring an earlier answer as the final turn.

The controlled retrieval test exercises the real frozen retrieval index and
preserves PT9116’s bus-service text and identity; a negative assertion detects
that passage if it enters PT9148’s composer evidence. Existing school identity
filtering remains unchanged. Calculated facts retain an explicit transformed
basis rather than claiming to be original webpage passages.

No provider-backed capture or scoring of the expanded dataset is claimed or
required by Step 7’s dataset/setup completion criteria. Human calibration and
fresh website verification remain pending. Semantic checks about missing
information and incorrect attribution require the explicit pass/fail prose
reviews specified in each case. Coverage-check results in capture metadata do
not substitute for those reviews or determine RAGAS scores.

## Capture the new tuning cases

```bash
PYTHONPATH=.:SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python docs/examples/ragas/capture_dataset.py --staged \
  --dataset-dir docs/examples/ragas/expanded --split tuning \
  --output /tmp/kindercompass-ragas-expanded-tuning.jsonl
```

This command incurs agent-provider charges. It verifies all frozen snapshots
before calling the provider and rejects a different configured school index.
The capture manifest records the selected split, adapter and collector hashes,
exact checks, model configuration and turn failures. Raw captures stay outside
Git. Use `--split held_out` for post-tuning reporting. To score a selected split,
select the matching labelled case subset by the manifest’s frozen case IDs;
`score.py` expects every case in its supplied dataset. No regression comparison
or release gate has been added; Step 8 remains pending.
