# Guidance, school examples and follow-up explanations

The reported guidance question was being treated as a request for school names.
Its follow-up about “branches” repeated the list. Distinct centre IDs also shared
an operator name, making the output look duplicated.

## Interpretation and presentation

The model still interprets the complete message and chooses tools. Instructions
now distinguish practical guidance, school options, ordinary definitions and
questions about preceding wording. Guidance uses available general evidence;
ordinary terminology explanations may be conversational. A broad overview does
not request a fee calculation. Successful wording remains model-authored and
subject to the existing factual/citation checks.

`search_rank_compare_schools` accepts `presentation=distinct_names` for general
examples. It groups already filtered/ranked records by names normalised for
case, spacing and punctuation before applying the display limit. The first
ranked centre represents each name with its exact repository spelling and ID.
`total_matches` counts matching centres; `displayed_count` counts shown examples.
Default centre searches, ranking and comparisons keep individual centres.
Distinct-name presentation is rejected for ranking/comparison. This is cosmetic
grouping, not an operator identity resolver or a suitability calculation.

The validator rejects repeated bare school names in bullet lists and requests
bounded repair. Supported addresses can distinguish same-named branches.
This readability check does not prove relevance; evaluation does that separately.

## Combined frontend control

At the user's subsequent request, the browser presents one unchecked option,
“Remember my conversation and preferences”. Explicit combined consent enables
both existing request flags, is remembered on the device, and explains the
different retention periods. Opt-out calls `/api/memory/forget` to clear both.
Existing preference-only opt-in can restore saved preferences without silently
enabling chat; the user must select the new combined option. Backend retention
and the separate APIs below remain independently implemented.

The combined-control change passes the frontend production build and a browser
check for one checkbox, both request flags, device opt-in across reload, clearing
both memories and migration of old preference-only settings. Logs:
`/tmp/kindercompass-combined-memory-build.log` and
`/tmp/kindercompass-combined-memory-browser.log`.

### Original separate controls

The unchecked “Remember this conversation for follow-up questions” option is
not persisted as a browser preference. Successful turns after opt-in enter the
existing backend RAM history: up to six exchanges, with 30-minute idle expiry.
The anonymous UUID accompanies turns when either retention option is enabled.
There is no browser transcript upload or persistent transcript database.

`/api/conversation/forget` clears ephemeral context only.
`/api/memory/preferences/forget` deletes saved preferences while retaining
completed dialogue and invalidating in-flight leases under the session lock,
preventing a pending turn from saving after opt-out. The old
`/api/memory/forget` still clears both. UI preference edits outside chat clear
ephemeral state before changing the client profile to preserve stale-turn
protection. See the [history contract](llm-first-context.md).

## Relevance evaluation

The separate [dataset](../resources/conversation_relevance_evaluation.json)
covers the reported questions, paraphrases, contextual definitions, distinct
examples with/without required Chinese, selected branches and combined guidance
and examples. It does not replace the existing fixed rollout dataset.

```bash
PYTHONPATH=.:SystemCode/src/backend:SystemCode/src/backend/pipeline \
  .venv/bin/python -m SystemCode.src.backend.scripts.evaluate_conversation_relevance \
  --output /tmp/kindercompass-relevance.json
```

Capture uses the configured provider, local authoritative catalogue and synthetic
family inputs; it writes only the requested report and makes read-only provider
calls. Mechanical checks cover replies, tool choices, distinct names and unchanged
preferences. Answer relevance and interpretation require explicit review; exit
zero is not a general quality gate. Completed evidence is in [progress](agents.md).
