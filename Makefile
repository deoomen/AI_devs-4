PYTHON := .venv/bin/python
PYLINT := .venv/bin/pylint
PYTEST := .venv/bin/pytest

.PHONY: lint test test-unit test-integration

lint:
	$(PYLINT) app/

test:
	$(PYTEST) -v

test-unit:
	$(PYTEST) app/tests/unit/ -v

test-integration:
	$(PYTEST) app/tests/integration/ -v
