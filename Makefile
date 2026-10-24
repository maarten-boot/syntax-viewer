# syntax-viewer — developer tasks.
#
# The source tree may be shared between machines (e.g. over NFS), and a
# virtualenv only works on the machine and path it was created on. So every
# host gets its own: .venv-<hostname>.

PYTHON ?= python3
HOST   := $(shell hostname -s)
VENV   ?= .venv-$(HOST)
PY     := $(VENV)/bin/python
FILE   ?= tests/fixtures/sqlite-parse.y
N      ?= 600
SHOTS  ?= build/screenshots

.DEFAULT_GOAL := help
.PHONY: help venv run dump test fuzz lint check screenshots clean distclean \
        demo-kukel-ebnf demo-kukel-lark demo-bbcbasic demo-json demo-calc demo-c99 demo-sqlite

help:  ## Show this help
	@grep -hE '^[a-z][a-z0-9-]*:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'
	@echo "  Variables: FILE=$(FILE)  VENV=$(VENV)  N=$(N)  PYTHON=$(PYTHON)"

venv: $(VENV)/.installed  ## Create this host's virtualenv with GUI and dev dependencies

$(VENV)/.installed: pyproject.toml
	@$(PYTHON) -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Python >= 3.11 required")'
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -e '.[gui,dev]'
	@touch $@

run: venv  ## Open FILE in the GUI (make run FILE=path/to/grammar)
	$(PY) -m syntax_viewer $(FILE)

dump: venv  ## Print FILE as text, no GUI
	$(PY) -m syntax_viewer --dump $(FILE)

demo-kukel-ebnf: venv  ## GUI: kukel ISO EBNF (asks about upper-case rules)
	$(PY) -m syntax_viewer tests/fixtures/kukel.ebnf
demo-kukel-lark: venv  ## GUI: kukel Lark grammar
	$(PY) -m syntax_viewer tests/fixtures/kukel.lark
demo-bbcbasic: venv  ## GUI: BBC BASIC ISO EBNF
	$(PY) -m syntax_viewer tests/fixtures/BBCBASIC.ebnf
demo-json: venv  ## GUI: JSON in W3C EBNF
	$(PY) -m syntax_viewer tests/fixtures/json-w3c.ebnf
demo-calc: venv  ## GUI: Bison calculator (actions stripped in original view)
	$(PY) -m syntax_viewer tests/fixtures/calc-bison.y
demo-c99: venv  ## GUI: C99 Yacc grammar
	$(PY) -m syntax_viewer tests/fixtures/c99.y
demo-sqlite: venv  ## GUI: SQLite Lemon grammar
	$(PY) -m syntax_viewer tests/fixtures/sqlite-parse.y

test: venv  ## Run the test suite (GUI tests offscreen)
	QT_QPA_PLATFORM=offscreen $(PY) -m pytest -q

fuzz: venv  ## Mutation-fuzz all readers (N mutations per fixture)
	$(PY) tests/fuzz_readers.py $(N)

lint: venv  ## Static checks (ruff)
	$(PY) -m ruff check src tests tools --select F,E9,B

check: lint test fuzz  ## lint + test + fuzz

screenshots: venv  ## Render GUI screenshots offscreen into SHOTS
	$(PY) tools/screenshots.py $(SHOTS)

clean:  ## Remove build output and caches
	rm -rf build .pytest_cache .ruff_cache src/*.egg-info
	find . -name __pycache__ -type d -prune -not -path "./.venv*" -exec rm -rf {} +

distclean: clean  ## Also remove the virtualenvs of all hosts
	rm -rf .venv .venv-*
