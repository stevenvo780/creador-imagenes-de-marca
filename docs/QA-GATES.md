# QA Gates — Eikon

Este documento fija los gates incrementales para no volver a entregar por intuición.

## Gate 1 — Suite custom histórica

- Comando: `make test`
- Equivalente: `python3 tests/test_eikon_checks.py`
- Criterio: exit code `0`, salida con `Resultado: ... / 0 ✗`.
- Estado actual verificado: `167 ✓ / 0 ✗`.
- Requiere Playwright: no.

## Gate 2 — Variations scaffolding

- Comando: `make test-variations`
- Equivalente: `python3 tests/test_variations.py`
- Criterio: exit code `0`, salida con `0 ✗`.
- Requiere Playwright: no.
- Rol: base pura para la futura UI de variaciones/batches.

## Gate 2b — Taxonomy serializable

- Comando: `make test-taxonomy`
- Validador directo: `make run-taxonomy`
- Criterio: `taxonomy.json` parsea, valida estructura v1, todos los templates referenciados existen y la paridad con la taxonomía legacy no produce fails.
- Requiere Playwright: no.

## Gate 3 — Pytest bridge

- Comando: `pytest tests/test_runner_bridge.py -v --tb=short`
- Atajo: `make qa` si `pytest` está instalado.
- Criterio: el bridge ejecuta el runner histórico como subprocess y falla si ese runner falla.

## Gate 4 — Syntax compile

- Comando: `make py-compile`
- Criterio: todos los módulos activos compilan sin error, incluyendo `eikon_core/`, `scripts/` y el webapp MVP.

## Gate 5 — Validadores de output antes de release

- Layout: `make run-validate`
- Pixel: `make run-pixels`
- Ironman agregado: `make run-ironman`
- Métricas perceptuales: `make run-metrics`
- Conteo/estado: `make run-count`

Estos gates leen `output/`; pueden fallar por estado histórico de assets aunque el código compile.
No sustituyen los gates de motor limpio: sirven para decidir qué corregir antes de publicar.

### Ironman agregado

- Comando exploratorio / Make: `make run-ironman`
- Comando directo: `python3 scripts/eikon_ironman.py --only-issues`
- Comando estricto / release gate: `make run-ironman-strict`
- Comando estricto directo: `python3 scripts/eikon_ironman.py --only-issues --fail-on-thresholds`
- JSON reproducible: `python3 scripts/eikon_ironman.py --json > /tmp/eikon-ironman.json`
- Cubre: layout (`_manifest.json`), pixel (`_pixel-report.json`) y WCAG (`_contraste-report.json`).
- Thresholds por defecto en modo estricto: cero issues/fails/warnings/reportes faltantes. Ajustar con flags `--max-*` cuando haya deuda histórica aceptada y documentada.

## Gate 6 — Webapp MVP core

- Comando: `make test-webapp`
- Criterio: storage SQLite multi-tenant, password hashing, JWT HS256, guards anti path traversal y command builder sin `shell=True` pasan.
- Requiere servidor FastAPI: no.
- Para correr API real: instalar `webapp/requirements-webapp.txt` y usar `uvicorn webapp.app:app`.

## Política

1. Ningún cambio de motor se considera listo si Gate 1 o Gate 4 fallan.
2. Ningún cambio de variaciones se considera listo si Gate 2 falla.
3. Ningún release visual se considera listo si Gate 5 muestra fails reales sin documentar.
4. Los assets generados siguen fuera de git salvo decisión explícita.
