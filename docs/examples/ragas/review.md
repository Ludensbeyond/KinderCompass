# Starter label review — version 1.0.0

Codex reviewed all 12 questions, answers and reference passages on 7 October
2026 against the curated general-knowledge snapshot recorded in
[manifest.json](manifest.json). This is an AI-assisted repository review;
human review has not been performed. Each passage, chunk ID, URL and retrieval
date matches that snapshot exactly. The snapshot contains curated summaries,
not verbatim copies of external pages.

No external review was needed to support these snapshot-based labels: they ask
about general guidance and contain no current fees or school offerings. The
external websites were not reverified. `retrieved_at: 2026-08-14` is inherited
snapshot provenance, not the date of this label review. A future external review
should record its own date and update the version if it changes the labels.

| Case ID | Reviewed facts / intended behaviour | Review decision |
|---|---|---|
| `montessori` | Prepared environment, accessible materials, self-directed hands-on activity, freedom within limits, adult guidance, independence and concentration. | All facts supported by `GENERAL:montessori:0`; no guaranteed outcomes required. |
| `play_based` | Physical, social-emotional, cognitive and language skills; problem-solving, negotiation and creative expression. | Supported by `GENERAL:play-based:0`; does not require worksheet or risk-taking detail. |
| `nel_age` | NEL guides preschool education at ages four to six. | Supported by `GENERAL:nel-framework:0`; developmental principles are unnecessary for this question. |
| `eydf_age` | EYDF guides centre-based care and education from birth to age three. | Supported by `GENERAL:eydf:0`; removed developmental-domain detail unrelated to identifying the framework. |
| `reggio` | Capable learners, many forms of expression, relationships, collaboration, family participation, documentation, ateliers and environment. | Supported by `GENERAL:reggio-emilia:0`; these are main ideas, not school offerings. |
| `spark_limits` | Recognition concerns quality improvement; it cannot establish superiority of every programme or outcome. | Supported by `GENERAL:spark-2:0`; question now names SPARK 2.0 to match the snapshot. The limitation is the curated passage's interpretation. |
| `outdoor` | Exploration, experimentation and revisiting ideas in a safe environment; agency, problem-solving, physical development and reflection. | Supported by `GENERAL:outdoor-learning:0`; benefits are possibilities, not guarantees. |
| `quality_teaching` | Teaching supports well-being, learning and holistic development. | Supported by `GENERAL:quality-teaching:0`; question now identifies the Quality Teaching Tool. Removed tool structure and framework alignment from the answer because it asks for the definition. |
| `compare_frameworks` | EYDF: birth to three, centre-based care/education; NEL: four to six, preschool education. | Both reference passages required; no additional developmental principles required. |
| `compare_pedagogies` | Montessori: prepared environment, self-directed activity, freedom within limits. Reggio: relationships, expression, collaboration, environment. | Both passages required; narrowed question to support for learning and removed secondary details from the comparison. |
| `no_selected_school` | Ask for a school selection/identification; make no unidentified-school offering claim or school-specific citation from general evidence. | No reference evidence needed; all three explicit checks must be reviewed. |
| `request_invented_claim` | Do not endorse an exam guarantee or invent support; explain that the evidence does not establish guaranteed results. | `GENERAL:montessori:0` describes intended development, not an exam guarantee. Added missing source provenance; all three explicit checks must be reviewed. |

All cases run independently with an empty profile, no selected schools and no
conversation history. The first ten require general evidence; the missing-school
case needs clarification without evidence; the invented-claim case permits
general Montessori evidence only. Each case records its category, setup, scope,
expected behaviour and review status in [cases.jsonl](cases.jsonl).

Only [inputs.jsonl](inputs.jsonl) is intended for execution: forward `user_input`
and `setup` and retain `case_id` outside the prompt for capture correlation.
Reference labels and behaviour checks remain in evaluation-only files. The
runtime loads its existing knowledge index; it does not load this dataset.
An automated capture runner must preserve this boundary in step 4. No agent
capture or scoring result is claimed by this review.
