# Offline evaluation checks. Provider capture/scoring is explicitly run by a contributor.
.PHONY: eval-check
PYTHON ?= .venv/bin/python

eval-check:
	PYTHONPATH=.:docs/examples/ragas:SystemCode/src/backend:SystemCode/src/backend/pipeline $(PYTHON) -m unittest discover -s docs/examples/ragas -p 'test_*.py' -q
	$(PYTHON) docs/examples/ragas/smoke.py --validate-only
