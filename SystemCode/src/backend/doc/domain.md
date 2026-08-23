# `domain/`

`domain/` owns typed, infrastructure-independent contracts shared by the API,
services, repositories, and pipeline.

- `models.py` defines family, programme, evaluation, and API-facing Pydantic
  models.
- `catalogue.py` defines validated school and service catalogue records.
- `__init__.py` marks the package and may expose stable public imports.

Put a model here when it expresses backend business data used across layers.
Keep FastAPI routing, database queries, environment access, and external client
calls out of this folder. Validation should reject invalid authoritative data
close to loading time rather than allowing malformed records into scoring or
evaluation.
