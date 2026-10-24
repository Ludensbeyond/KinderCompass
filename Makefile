# Offline evaluation checks. Provider capture/scoring is explicitly run by a contributor.
.PHONY: eval-check
PYTHON ?= .venv/bin/python

eval-check:
	PYTHONPATH=.:SystemCode/src/backend/evaluation/ragas:SystemCode/src/backend:SystemCode/src/backend/pipeline $(PYTHON) -m unittest discover -s SystemCode/src/backend/evaluation/ragas -p 'test_*.py' -q
	$(PYTHON) SystemCode/src/backend/evaluation/ragas/smoke.py --validate-only
