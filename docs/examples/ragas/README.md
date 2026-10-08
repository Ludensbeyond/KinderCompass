# A small RAGAS evaluation for KinderCompass

Start with a fixed, manually reviewed set of questions. Run the real agent,
capture the answers and evidence it actually received, then let RAGAS score
those captures. This makes failures easier to understand than starting with a
large automatically generated dataset.

The starter includes 10 evidence questions and two behaviour checks. References
come from the project's curated general-knowledge index, with source IDs and
snapshot dates preserved. Version 1.0.0 is frozen after a Codex review against
that snapshot on 7 October 2026; human review and fresh external website
verification have not been performed. See [manifest.json](manifest.json) for
reviewer information and file hashes, and [review.md](review.md) for per-case
decisions. No school-specific offerings or current fees are invented.

## What to measure

| Metric | What it tells you | Typical failure |
|---|---|---|
| Faithfulness | Are the answer's factual claims supported by retrieved passages? | Invents an outcome or school offering. |
| Context precision with reference | Are useful retrieved passages ranked ahead of irrelevant ones? | Retrieves mostly unrelated material. |
| Context recall | Do the retrieved passages support the facts in the reference answer? | Retrieves NEL but misses EYDF in a comparison. |

These three metrics need an LLM judge but no embedding model. They do not directly
measure how completely the final answer covers the reference. Initially review
that manually; add answer correctness or a suitable rubric later. Answer
relevancy is another option, but its standard implementation also needs
embeddings.

Keep existing deterministic evaluations for exact age, fees, ranking, tool
permissions, citation ownership and preference updates. RAGAS scores cannot
establish those properties. In particular, faithfulness can still be high when
an answer uses evidence from the wrong preschool.

## Capture agent runs

1. Use `inputs.jsonl` for execution. Forward only `user_input` and `setup` to
   the agent; retain `case_id` outside its prompt for capture correlation.
   `cases.jsonl` holds evaluation-only labels: never send references, reference
   contexts, source labels, expected behaviour or checks to the answering agent.
2. Copy `runs.template.jsonl` to `/tmp/kindercompass-ragas-runs.jsonl`.
3. Submit each `user_input` through the normal agent path. Apply every case's
   explicit `setup`: fresh empty profile, no selected schools and no conversation
   history. Never carry state between these independent cases.
4. Fill in `response` with the actual final answer and `retrieved_contexts` with
   an ordered list of the passage texts the answering agent received. Record
   all supplied evidence, including irrelevant passages, rather than only cited
   chunks. If structured tools supply facts, include their actual payloads as
   text too. Do not dump the whole index into this field.

KinderCompass's conversation evaluation reads the final prose from
`agent_response["question"]`; map that value to RAGAS's `response`. Public
citations alone do not contain the full evidence trace, so capture texts at the
retrieval/tool boundary when automating runs. The existing runner in
`SystemCode/src/backend/scripts/evaluate_conversation_supervisor.py` is a useful
integration point, but this starter does not modify or invoke it.

Example capture shape (the response below illustrates the format and is not a
measured agent result):

```json
{
  "case_id": "nel_age",
  "response": "The NEL framework guides preschool education for children aged four to six.",
  "retrieved_contexts": [
    "Singapore's Nurturing Early Learners framework guides preschool education for children aged four to six. It emphasises holistic development, positive relationships, active construction of knowledge, meaningful and authentic learning, quality interactions, and integrated development across learning areas."
  ]
}
```

Write one JSON object per line in the actual capture file. `reference_contexts`
in the labelled dataset are the passages used to write the expected answer;
they must not be substituted for actual retrievals. Missing retrieved evidence
should remain `[]`. Empty or claim-free answers may yield undefined RAGAS
scores; review them separately instead of counting them as passes.

The labelled dataset records `category`, `evidence_scope`, `expected_behaviour`
and `review` for every case. The ten RAGAS cases use general evidence. The
missing-school behaviour case needs no evidence; the invented-claim behaviour
case permits general Montessori evidence. Behaviour cases use their explicit
checks, without RAGAS pass thresholds. Change the dataset version and refresh
manifest hashes when editing questions, setup, labels or the evidence snapshot.

## Run scoring

This example deliberately pins the RAGAS 0.2 API. Use a separate environment
because the production backend uses newer LangChain packages. When upgrading
RAGAS, check its migration documentation before changing the imports.

From the repository root:

```bash
python3.12 -m venv /tmp/kindercompass-ragas-venv
/tmp/kindercompass-ragas-venv/bin/python -m pip install -r docs/examples/ragas/requirements.lock.txt
/tmp/kindercompass-ragas-venv/bin/python -m pip check

# Check capture format without dependencies, credentials or model calls.
python docs/examples/ragas/score.py --runs /tmp/kindercompass-ragas-runs.jsonl --validate-only

# Set OPENAI_API_KEY through your usual secret-management mechanism first.
# Replace YOUR_JUDGE_MODEL with a model available in your evaluation account.
# This command sends captures to the judge and incurs API charges.
/tmp/kindercompass-ragas-venv/bin/python docs/examples/ragas/score.py \
  --runs /tmp/kindercompass-ragas-runs.jsonl \
  --judge-model YOUR_JUDGE_MODEL \
  --output /tmp/kindercompass-ragas.csv
```

The lock file records the verified Python 3.12 environment; `requirements.txt`
retains the intended dependency ranges for future upgrades. See the
[environment verification](environment-verification.md) for tested versions.

Before scoring real captures, verify the scorer with a single synthetic case:

```bash
# Dependency-free format check; writes a clearly labelled temporary fixture.
python docs/examples/ragas/smoke.py --validate-only

# Paid provider check using an explicit judge model and local credentials.
# --env-file is optional when OPENAI_API_KEY is already exported.
/tmp/kindercompass-ragas-venv/bin/python docs/examples/ragas/smoke.py \
  --judge-model gpt-4o-mini --env-file .env
```

The smoke runner reads only `OPENAI_API_KEY` from the optional secret file;
an exported key takes precedence. It creates its own one-case dataset and capture,
validates them, invokes the three scoring metrics and checks that the CSV contains
one fixture row with finite scores between zero and one. Generated files remain
under `/tmp/kindercompass-ragas-fixture/` by default. The fixture uses fictional
content and never calls the KinderCompass agent. Its scores are not a baseline.
Optional LangSmith tracing and RAGAS usage telemetry are disabled for this check.

The scoring example uses an OpenAI judge; configure the wrapper appropriately
if your evaluation account uses Azure or another provider. Judge configuration
is separate from the agent's model configuration.

The CSV contains individual RAGAS scores. The sibling `.behaviour.json` file
contains the two behaviour cases and checks awaiting human review; it does not
claim that those checks passed. Step 2 verified paid fixture scoring only;
no live agent captures have been scored.

## Make the small set effective

Use these 12 cases as a smoke check, then grow to around 20–30 reviewed cases:
add real selected-school questions, unavailable evidence, wrong-school
distractors, and short conversations that change an earlier preference.
Keep school IDs and context snapshots fixed. For multi-turn tests, preserve
the conversation setup and validate final structured state with the existing
conversation evaluator; an isolated last message loses the relevant context.

Start with provisional review flags such as faithfulness below 0.90 and context
precision or recall below 0.80. These are local starting points, not RAGAS
standards or validated release thresholds. Review every failure and every
undefined score; revise reference answers that require unnecessary details.
Require all explicit behaviour checks to pass. Compare changes using the same
cases, evidence snapshot, judge model and metric versions. Repeat borderline
scores because LLM judges can vary even at temperature zero.

After the manual set is reliable, generate additional questions from your
approved documents using RAGAS test-set generation and review them before
adding them to the regression set. Keep a separate held-out set for reporting
results after tuning.

References: [RAGAS 0.2 metric documentation](https://docs.ragas.io/en/v0.2.15/concepts/metrics/available_metrics/),
[evaluation datasets](https://docs.ragas.io/en/v0.2.15/concepts/components/eval_dataset/).
