# `services/`

`services/` implements application use cases independently of HTTP routing. A
service coordinates domain validation, repositories, pipeline functions, and
external integration boundaries, then returns data that `main.py` can translate
into an API response.

Current services cover preference handling, evaluation, location work,
decision and conversation state, feedback, and chat feedback. Add orchestration
here when it spans multiple domain or infrastructure operations. Keep endpoint
declarations and HTTP exception translation in `main.py`; keep reusable scoring,
eligibility, and distance algorithms in `pipeline/`.

The new-flow `conversation_context_service.py` prepares bounded current state
and repository-resolved school identities without ranking or geocoding.
`conversation_history_service.py` holds explicitly opted-in recent dialogue in
RAM with expiry and one active lease per session. These Step 2 foundations are
separate from the served legacy supervisor and persistent preference memory;
see [their contract and integration constraints](llm-first-context.md).
