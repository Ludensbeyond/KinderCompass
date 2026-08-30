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
