# Isolated scoring environment verification

Step 2 completed on 2026-10-07. This verifies the scoring environment with one
synthetic fixture, without running KinderCompass or measuring agent quality.

| Setting | Verified value |
|---|---|
| Python | 3.12.12 |
| RAGAS | 0.2.15 |
| LangChain | 0.3.30 |
| LangChain Core | 0.3.86 |
| LangChain Community | 0.3.31 |
| LangChain OpenAI | 0.3.35 |
| OpenAI SDK | 2.54.0 |
| pandas | 2.3.3 |
| Judge | OpenAI Chat Completions, `gpt-4o-mini`, temperature 0 |
| Credential | Existing local `OPENAI_API_KEY`; no secret stored in results |

The judge model alias was available to the account and successfully scored the
fixture. The scorer does not export the provider's resolved model snapshot;
the recorded model version is the requested alias, not a claimed immutable
snapshot. No agent model settings were loaded. Azure was not used or verified.
Credential handling follows the [official OpenAI authentication documentation](https://developers.openai.com/api/reference/overview).

The separate environment is `/tmp/kindercompass-ragas-venv`; it was created using
the existing Python 3.12 interpreter, then installed from `requirements.txt`.
The resulting full dependency set is saved in
[requirements.lock.txt](requirements.lock.txt) for reproduction. Production
dependencies were not changed.

Verification results:

- `pip check`: no broken requirements found.
- Imports succeeded: `ChatOpenAI`, `EvaluationDataset`, `evaluate`,
  `LangchainLLMWrapper`, `Faithfulness`, `LLMContextPrecisionWithReference`,
  and `LLMContextRecall`.
- `python docs/examples/ragas/smoke.py --validate-only`: validated one RAGAS
  fixture and zero behaviour cases, using no optional dependencies or model calls.
- Paid check: `smoke.py --judge-model gpt-4o-mini --env-file .env` completed
  all three metrics and verified a one-row CSV export with finite scores.

| Synthetic fixture metric | Exported score |
|---|---|
| Faithfulness | 1.0 |
| Context precision with reference | 0.9999999999 |
| Context recall | 1.0 |

These scores describe only `synthetic_format_fixture`, a fictional preschool
opening-time question with a deliberately supported answer. They do not describe
any starter case or actual agent output. Temporary dataset, capture, CSV and
empty behaviour-review export are stored under
`/tmp/kindercompass-ragas-fixture/`; raw output is not committed.

Initial dependency installation and provider scoring attempts failed inside
the network-restricted sandbox (package-index DNS failure and judge timeout).
Dependency installation and the fixture scoring command succeeded after network
approval. No provider compatibility failure remained. Future runs require
package-index access for installation and provider access for paid scoring.

Use the commands in the [starter guide](README.md#run-scoring) to reproduce the
check with an explicit judge model. Step 3, capturing `nel_age` through the real
conversation agent and inspecting its actual evidence, remains the next step.
