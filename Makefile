.PHONY: install test lint format clean

install:
	pip install -e ".[dev]"

test:
	pytest -v

lint:
	flake8 src tests
	mypy src tests

format:
	black src tests

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
