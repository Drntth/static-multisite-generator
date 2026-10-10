PY := .venv/bin/python
# Python 3.11+ is required (tomllib); override with e.g. make venv PYTHON=python3.13
PYTHON ?= python3.12

.PHONY: venv build check test lint serve preview clean

venv:
	@$(PYTHON) -c 'import sys; sys.exit(sys.version_info < (3, 11))' \
		|| { echo "Python 3.11+ required, $(PYTHON) is older; use make venv PYTHON=python3.12"; exit 1; }
	$(PYTHON) -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt

build:
	$(PY) scripts/build.py

check:
	$(PY) scripts/check_links.py

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check scripts tests && .venv/bin/ruff format --check scripts tests

serve:
	$(PY) scripts/serve.py

# README image: home pages of every site side by side (needs Google Chrome and ImageMagick).
preview: build
	scripts/preview.sh

clean:
	rm -rf dist .cache
