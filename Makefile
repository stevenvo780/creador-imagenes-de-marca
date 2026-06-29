SHELL := /bin/bash
PY ?= python3
VENV := .venv/bin

.PHONY: help install install-dev webapp-install test test-variations test-taxonomy test-webapp qa py-compile run-validate run-pixels run-taxonomy run-ironman run-ironman-strict run-metrics run-count run-all-checks clean lint format format-check typecheck cov

help: ## lista targets disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n",$$1,$$2}'

install: ## instala dependencias runtime
	$(PY) -m pip install -r requirements.txt

install-dev: ## instala dependencias dev
	$(PY) -m pip install -r requirements-dev.txt

webapp-install: ## instala dependencias opcionales del webapp MVP
	$(PY) -m pip install -r webapp/requirements-webapp.txt

test: ## corre suite custom existente
	$(PY) tests/test_eikon_checks.py

test-variations: ## corre scaffolding de variaciones
	$(PY) tests/test_variations.py

test-taxonomy: ## corre tests de taxonomy.json + validador
	$(PY) tests/test_taxonomy.py

test-webapp: ## corre tests core del webapp sin servidor
	$(PY) webapp/tests/test_webapp_core.py

qa: test test-variations test-taxonomy test-webapp ## corre suites custom y bridge pytest si pytest existe
	@command -v pytest >/dev/null 2>&1 \
	  && pytest tests/test_runner_bridge.py -v --tb=short \
	  || echo "pytest no instalado — bridge skip"

py-compile: ## compila Python activo para detectar errores de sintaxis
	$(PY) -m py_compile eikon.py contrast_validator.py gallery.py web_icons.py variations.py \
	  eikon_core/__init__.py eikon_core/constants.py eikon_core/types.py eikon_core/text.py \
	  eikon_core/playwright_lazy.py eikon_core/validation.py eikon_core/taxonomy.py \
	  eikon_core/brand.py eikon_core/mapping.py eikon_core/injection.py eikon_core/layout.py \
	  eikon_core/templates.py eikon_core/cache.py eikon_core/manifest.py eikon_core/render.py \
	  eikon_core/orchestrator.py eikon_core/cli.py \
	  webapp/__init__.py webapp/config.py webapp/security.py webapp/storage.py webapp/app.py \
	  webapp/services/__init__.py webapp/services/eikon_runner.py webapp/routers/__init__.py \
	  scripts/eikon_aggregate_wcag.py scripts/eikon_count.py \
	  scripts/eikon_ironman.py scripts/eikon_validate_layout.py scripts/eikon_validate_pixels.py \
	  scripts/eikon_validate_taxonomy.py \
	  tests/test_eikon_checks.py tests/test_variations.py tests/test_taxonomy.py tests/test_runner_bridge.py \
	  webapp/tests/test_webapp_core.py

run-validate: ## valida layout desde manifests actuales
	$(PY) scripts/eikon_validate_layout.py

run-pixels: ## valida pixeles sobre todas las marcas con manifest
	$(PY) scripts/eikon_validate_pixels.py --all

run-taxonomy: ## valida taxonomy.json v1 y drift mecanico
	$(PY) scripts/eikon_validate_taxonomy.py

run-ironman: ## resume layout/pixels/WCAG sin fallar por deuda visual conocida
	$(PY) scripts/eikon_ironman.py --only-issues

run-ironman-strict: ## release gate visual estricto (falla si queda deuda)
	$(PY) scripts/eikon_ironman.py --only-issues --fail-on-thresholds

run-count: ## regenera _STATUS.md desde output/
	$(PY) scripts/eikon_count.py

run-aggregate-wcag: ## agrega WCAG por marca en output/_contraste-report.json
	$(PY) scripts/eikon_aggregate_wcag.py

run-render-core: ## re-renderiza las 6 marcas core (--all usa CORE_MARCAS)
	$(PY) eikon.py --all --skip-contraste

run-render-all: ## re-renderiza TODAS las 38 marcas (incluye demos)
	$(PY) eikon.py --all-marcas --skip-contraste

run-all-checks: py-compile test test-variations test-taxonomy test-webapp run-taxonomy run-validate run-pixels run-ironman run-count run-aggregate-wcag ## suite local completa

clean: ## limpia caches Python/test; no toca output/ ni venvs
	rm -rf .pytest_cache __pycache__ */__pycache__ */*/__pycache__
	find . -name '*.pyc' -delete

lint: ## linting con ruff
	$(VENV)/ruff check .

format: ## formatea código con ruff
	$(VENV)/ruff format .

format-check: ## verifica formato sin modificar
	$(VENV)/ruff format --check .

typecheck: ## type-check con mypy sobre eikon_core + webapp
	$(VENV)/mypy eikon_core webapp

cov: ## corre pytest con coverage report
	$(VENV)/pytest --cov --cov-report=term-missing tests/ webapp/tests/
