.PHONY: test test-structural test-scenarios test-comparison test-single test-all install

test: test-structural

test-structural:
	python -m pytest tests/structural/ -v

test-scenarios:
	python -m pytest tests/scenarios/test_scenarios.py -v

test-comparison:
	python -m pytest tests/scenarios/test_scenarios.py -v --comparison

test-single:
	python -m pytest tests/scenarios/test_scenarios.py -v -k "$(ID)"

test-all: test-structural test-scenarios

install:
	pip install -r tests/requirements.txt
