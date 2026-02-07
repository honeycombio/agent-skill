.PHONY: test test-structural test-scenarios test-comparison test-single test-all install

test: test-structural

test-structural:
	python -m pytest tests/structural/ -v

test-scenarios:
	python -m pytest tests/scenarios/test_scenarios.py -v -s -k "not comparison"

test-comparison:
	python -m pytest tests/scenarios/test_scenarios.py -v -s -m comparison

test-single:
	python -m pytest tests/scenarios/test_scenarios.py -v -s -k "$(ID)"

test-all: test-structural test-scenarios

install:
	pip install -r tests/requirements.txt
