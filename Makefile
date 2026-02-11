.PHONY: test test-structural test-scenarios test-scenarios-full test-plugin-only test-single test-all test-report install

PYTHON ?= .venv/bin/python

test: test-structural

test-structural:
	$(PYTHON) -m pytest tests/structural/ -v

# Default: compare plugin vs MCP-only on core scenario subset
test-scenarios:
	$(PYTHON) -m pytest tests/scenarios/test_scenarios.py::test_scenario_core -v -s

# Full: compare plugin vs MCP-only on ALL scenarios
test-scenarios-full:
	$(PYTHON) -m pytest tests/scenarios/test_scenarios.py::test_scenario -v -s

# Plugin-only (no baseline comparison) — quick local validation
test-plugin-only:
	$(PYTHON) -m pytest tests/scenarios/test_scenarios.py::test_scenario_plugin_only -v -s -k "not comparison"

test-single:
	$(PYTHON) -m pytest tests/scenarios/test_scenarios.py -v -s -k "$(ID)"

# Generate HTML comparison report from saved output
test-report:
	$(PYTHON) -m tests.scenarios.report

test-all: test-structural test-scenarios

install:
	$(PYTHON) -m pip install -r tests/requirements.txt
