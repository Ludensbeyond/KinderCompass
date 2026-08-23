# `repositories/`

`repositories/` is the authoritative data-access boundary. It turns stored or
curated data into domain objects for the rest of the backend.

- `school_repository.py` loads and resolves school records and stable school
  IDs, including Neo4j-backed catalogue access.
- `policy_repository.py` selects dated subsidy policy data from
  `resources/policy/`.

Call repositories from services or backend pipeline code, never from the
browser. Keep provider-specific queries and loading details here while
returning domain contracts to callers. Do not accept browser-supplied school
facts as authoritative; reload them by stable ID.
