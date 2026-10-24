# Step 8 regression workflow verification

Completed 9 October 2026. The [regression workflow](regression-workflow.md)
provides commands for offline checks, split selection, actual capture,
validation, explicit provider scoring, review, bundling and comparison. It
records 20 tuning cases (13 evidence/seven behaviour) and four held-out cases
(three evidence/one behaviour), plus the unchanged 12-case starter option.

`make eval-check` passes 29 offline tests and the synthetic format-only smoke
check. Seven new tests verify case-ID comparison independent of report order,
score changes, undefined outcomes, individual behaviour/completeness regressions,
fallback changes, preservation of failed executions and pending reviews,
frozen split export/bundling, and the actual comparison CLI's JSON/Markdown
outputs and incompatible-input rejection. Changed dataset, evidence, split,
case count, judge, scoring versions and scorer hash are rejected. Different
answer origins never produce pooled metric deltas. Split bundling verifies the
full frozen cases hash and exact selected labels; modified split references
are rejected.

A direct split-selection CLI run exports exactly 20 tuning labels to `/tmp`.
The historical private Step 6 bundle passes archive integrity but comparison
exits 2 because it predates supporting-snapshot hashes. No report is produced;
the workflow requires a fresh baseline with current metadata rather than
claiming compatibility. Synthetic tests verify the successful comparison path
using hash-verified temporary bundles. No new provider capture, judge scoring,
expanded baseline, human calibration or release gate is claimed.

All production backend files remain unchanged. The routine Make target exercises
the existing focused capture and real deterministic conversation checks; no
provider operations run in automated testing. Raw messages, score fixtures,
review exports and bundles remain temporary or privately ignored. Step 8 is
complete against its documentation/comparison criteria; a contributor can now
run the explicit provider workflow and inspect a compatible comparison report.
