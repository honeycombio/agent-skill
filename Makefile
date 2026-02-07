.PHONY: test test-structural test-scenarios test-scenarios-full test-plugin-only test-single test-all test-report install

test: test-structural

test-structural:
	python -m pytest tests/structural/ -v

# Default: compare plugin vs MCP-only on core scenario subset
test-scenarios:
	python -m pytest tests/scenarios/test_scenarios.py::test_scenario_core -v -s

# Full: compare plugin vs MCP-only on ALL scenarios
test-scenarios-full:
	python -m pytest tests/scenarios/test_scenarios.py::test_scenario -v -s

# Plugin-only (no baseline comparison) — quick local validation
test-plugin-only:
	python -m pytest tests/scenarios/test_scenarios.py::test_scenario_plugin_only -v -s -k "not comparison"

test-single:
	python -m pytest tests/scenarios/test_scenarios.py -v -s -k "$(ID)"

# Generate HTML comparison report from saved output
test-report:
	python -m tests.scenarios.report

test-all: test-structural test-scenarios

install:
	pip install -r tests/requirements.txt
