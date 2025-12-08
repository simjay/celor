.PHONY: help install install-docs test format lint docs view-docs docs-clean clean

.DEFAULT_GOAL := help

help:
	@echo "CeLoR - Available Commands"
	@echo "  [dev]"
	@echo "  make install       - Install package with dev dependencies"	
	@echo "  make test          - Run all tests with coverage"
	@echo "  make format        - Format code with black and isort"
	@echo "  make lint          - Check code style and types"
	@echo "  make clean         - Remove build artifacts"
	@echo ""
	@echo "  [docs]"
	@echo "  make install-docs  - Install documentation dependencies"
	@echo "  make build-docs    - Build documentation"
	@echo "  make view-docs     - Start local documentation server"
	@echo "  make clean-docs    - Clean documentation build artifacts"
	@echo ""

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --cov=celor --cov-report=term-missing --cov-report=html

format:
	isort celor/ tests/
	black celor/ tests/

lint:
	@echo "Checking code style..."
	@black --check celor/ tests/
	@isort --check celor/ tests/
	@echo "Running type checks..."
	@mypy celor/
	@echo "✓ All checks passed"

build-docs:
	$(MAKE) -C docs html

docs: build-docs
	@echo "Alias for build-docs"

install-docs:
	pip install -e ".[dev,docs]"

view-docs: build-docs
	@echo "Starting documentation server at http://localhost:8000"
	@echo "Press Ctrl+C to stop"
	@cd docs/_build/html && python3 -m http.server 8000

clean-docs:
	rm -rf docs/_build/

clean:
	rm -rf build/ dist/ *.egg-info
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/
	rm -rf .coverage htmlcov/
	rm -rf docs/_build/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
