# Expanded dataset 2.0.0 review

Codex reviewed the labels on 9 October 2026 against the frozen repository
snapshots. This is an AI review of dated source material; human review and fresh
external verification have not been performed. The starter 1.0.0 files and
baseline remain unchanged. The expanded manifest freezes both execution inputs
and labels, the catalogue, school webpage index, location data and policy files.

The 12 starter cases retain their reviewed references. The following additions
use original passage text with its stable chunk ID, source URL, date and centre
identity. Labels describe published claims, not verified current offerings or
promised outcomes. Each case has explicit checks and a reviewed reference.

| Case | Reviewed basis and decision | Split |
|---|---|---|
| woodlands_curriculum | PT9148 chunks 1–2 explicitly describe literature and activity integration; omit unrelated enrichment, fees and outcomes. | tuning |
| pebble_curriculum | PT4840 chunk 1 explicitly lists constructivism, design thinking and NEL alignment. | tuning |
| soka_approach | RC1835 chunk 0 describes the humanistic and value-creating approach. | held_out |
| pebble_transport_unknown | Both PT4840 chunks lack school transport evidence; catalogue transport is a different authority and does not fill a webpage evidence gap. | tuning |
| sparkletots_web_unknown | ST0280 exists in the catalogue but has no centre page in the pilot index. Operator pages cannot establish this centre’s curriculum. | held_out |
| wrong_school_transport | Inject original PT9116 chunk 0, which explicitly advertises a two-way bus; preserve its identity and never attribute it to PT9148. PT9148’s public-bus directions do not establish school transport. | tuning |
| pebble_play_combined | PT4840 chunk 1 connects play-based learning to experience; general play benefits use the starter play passage. Keep the two sources distinct. | tuning |
| soka_play_combined | RC1835 chunk 0 lists Learning Through Play without a detailed benefit description; those benefits come only from general evidence. | held_out |
| language_confirmed_change | Reuse the existing supervisor evaluator’s Chinese → conflicting Malay → confirmation flow; final required language is Malay and pending contradiction is removed. | tuning |
| language_pending_confirmation | Reuse its Chinese proposal → required confirmation flow; final required language is Chinese and pending state is removed. | tuning |
| language_change_then_general | Replay all three preference turns, then score only the final NEL age answer. Preserve confirmed Malay state. | held_out |
| fee_income_explanation | Fixed SC full-day family: born 2022-01-01, admission 2026-10-01, 56 working hours/month, ST0280; deterministic income change 5,000 → 10,000 produces net fees 85 → 272. Exact amounts belong to deterministic checks, with a separate prose explanation review. | tuning |

## Replay and scoring contract

`inputs.jsonl` is the only execution source. Its `conversation_history` contains
user setup turns, not fabricated assistant replies. Replay every turn through
the service and carry the returned profile forward. A fresh service and model
state starts each case. Missing returned state or a setup failure makes the
entire case an explicit execution failure, retaining partial turns for inspection.
Only the final answer of each RAGAS case is scored, as declared by `scored_turn`.

`retrieval_control` is a label-free test control identifying a real frozen chunk.
It prepends the wrong-school passage before the selected-school tool’s existing
identity filter. It does not forge ownership or alter production code. The
capture records both the controlled retrieval and evidence supplied to the
composer. A successful filter removes the distractor before composition; its
absence from composer evidence is expected. Explicit prose review still checks
that the bus claim is not attributed to the selected centre.

Exact profile checks reuse the existing supervisor evaluation helper. Fee checks
compare the final answer’s ordered dollar amounts with the independently frozen
calculation, check calculation-tool use, and compare returned profile to the
controller. These checks do not use an LLM judge. Original retrieved text remains
separate from calculated or authoritative tool facts, which are explicitly marked
`transformed_tool_fact`. RAGAS is never used as an arithmetic or state validator.
Existing backend age, fee and ranking evaluations remain authoritative.

Four cases are reserved for reporting after tuning. Use `--split tuning` during
iteration, and `--split held_out` only for that report. Labels remain reviewable;
no held-out answers or scores were produced during this step. A full dataset run
includes the held-out cases and should therefore be reserved for reporting.
