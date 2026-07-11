# Eikón — Auditoría de cierre (mega-final)

- Fecha: 2026-06-29
- Branch: `feat/eikon-refactor-multitenant`
- HEAD: `d35a8ff`
- Working tree: 18 archivos modificados sin commitear + untracked (`.claude/`, `tests/test_multitenant_isolation.py`, `webapp/storage_backend.py`)
- Auditor: subagente de verificación (read-only sobre código de producto; solo escribe este reporte)

## Scope

Batería completa de gates sobre el estado ACTUAL del working tree (committed + cambios sin commitear), más verificación del fix de variedad combinatoria. No se modificó código de producto: este es un cierre de auditoría, las reparaciones quedan para una fase de repair separada.

## Evidencia por gate

| Gate | Comando | Resultado |
|------|---------|-----------|
| Lint | `ruff check .` | PASS — `All checks passed!` (exit 0) |
| Types | `mypy eikon_core webapp` | PASS — `Success: no issues found in 57 source files` (exit 0) |
| Unit/integration | `pytest -q` | PASS — `216 passed, 1 warning in 22.61s` (exit 0) |
| Render guard | `python scripts/eikon_render_guard.py` | **FAIL (exit 1)** — kosmos: 3 PNGs regresión; prizma-iris: 29 pixel-idénticos |
| Frontend build | `cd frontend && npm run build` | PASS — `tsc --noEmit && vite build`, 48 módulos, `built in 721ms` (exit 0) |
| E2E | `pytest e2e/` | **FAIL (exit 1)** — 1 test, ERROR en arranque del server |

### Salidas crudas relevantes

Render guard (2 corridas consecutivas, idéntico → determinista):
```
pinakotheke-kosmos: REGRESSION changed=['banners/ad_leaderboard/v3_cta_driven.png',
  'cards/stat_card/v3_graph_abstract.png', 'stationery/letterhead/v2_interno.png'] missing=[]
prizma-iris: OK 29 assets pixel-identical
```

E2E:
```
RuntimeError: No se encontro el app global esperado en webapp/app.py
e2e/conftest.py:89 (vía _write_test_app_module → sentinel no encontrado)
```

## Verificación del fix de variedad

VERIFICADO (extremo a extremo).

- Lógica: `eikon_core/combinatorial/ranking.py` — `rank()` acepta `permuted_axes` y, cuando un eje permutado aparece en los `params`, usa `_dedup_preserve_axis_variety()` que garantiza ≥1 representante por valor declarado aunque las PNGs sean dHash-idénticas.
- Wiring: `webapp/jobs/worker.py:543-561` construye `batch_permuted_axes` desde `spec.permuted` + `axes_config` y lo pasa a `rank(...)`. El flujo batch → worker → ranking está conectado.
- Prueba empírica: `webapp/tests/test_combinatorial_coverage.py::test_rank_preserves_axis_variety_when_permuted_axes_supplied` — `count=4` permutando `palette_scheme ∈ {brand, mono, light, dark}` con 4 PNGs visualmente idénticas:
  - SIN `permuted_axes` (legacy) → dedup por dHash colapsa a **1**.
  - CON `permuted_axes` → preserva **≥3** variaciones con `palette_scheme` distintos.
- Suite de variedad: 7 tests `permuted/axis_variety` → todos PASS (incluye multi-eje, idempotencia, respeto de `top_n`, fallback legacy con `permuted_axes=None`).

Conclusión: el fix resuelve el bug reportado (isotype procedural no refleja cambios de CSS vars → PNGs idénticas → dedup colapsaba el batch a 1).

## Hallazgos por severidad

### MAJOR — E2E gate rojo (introducido por trabajo sin commitear)
- El cambio sin commitear en `webapp/app.py` envolvió `app = create_app()` en un `try/except` (queda indentado en línea 192: `    app = create_app()`).
- El harness e2e (`e2e/conftest.py:44-46`) lee el source de `webapp/app.py` y busca el sentinel literal `\napp = create_app()\n` para neutralizar la app a nivel de módulo; ya no matchea por la indentación → `RuntimeError` y el server uvicorn no arranca.
- Confirmado que es introducido por el working tree (en HEAD el `app = create_app()` está a nivel de módulo, ver diff).
- Fix (en fase de repair): o (a) restaurar `app = create_app()` a nivel de módulo sin indentación, o (b) actualizar el sentinel en `e2e/conftest.py` para tolerar el `try/except`.

### MAJOR — Render guard gate rojo (PRE-EXISTENTE en HEAD)
- 3 PNGs de `pinakotheke-kosmos` difieren del golden committeado (`tests/golden/pinakotheke-kosmos.pix.json`): `banners/ad_leaderboard/v3_cta_driven.png`, `cards/stat_card/v3_graph_abstract.png`, `stationery/letterhead/v2_interno.png`. `prizma-iris` 29/29 idénticos.
- Caracterización:
  - Determinista: mismas 3 PNGs en corridas repetidas (no flaky).
  - PRE-EXISTENTE: se reproduce con working tree limpio (`git stash` → guard → mismas 3 → `stash pop`). Los cambios sin commitear en `render.py`/`orchestrator.py` solo alteran la RUTA de salida (`batch_subdir`), no el contenido de píxeles del render de taxonomía.
  - Las 3 plantillas afectadas son exactamente las protegidas (`ad_leaderboard`/`stat_card`/`letterhead`); todas usan gradientes/filtros/fonts y NO tienen aleatoriedad explícita (sin `random`/`Date`/`now()`).
  - El golden se committeó en `40e7a08` (mismo día); como solo 3 variantes gradient/font-pesadas de un brand divergen y el otro brand es 100% estable, la causa más probable es rasterización dependiente del entorno (versión de Chromium/fonts/anti-aliasing) — el golden fue tomado en un contenedor distinto al de esta corrida (workflow distribuido multi-proveedor).
- Fix (en fase de repair): re-snapshotear el golden en el entorno canónico de CI (`python scripts/eikon_render_guard.py snapshot`) tras confirmar que el render de las 3 variantes es correcto, o investigar la rasterización sub-pixel de esas 3 combinaciones template+variante.

### Verde / sin hallazgos
- ruff, mypy, pytest (216), frontend build: limpios.
- Aislamiento multi-tenant, ranking/variedad, worker SSE, storage seam: cubiertos por la suite verde.

## Sign-off

**ok = false.** Quedan 2 gates rojos clasificados MAJOR. No hay critical.

Abierto (para fase de repair, no resuelto en esta auditoría):
1. [MAJOR] E2E: restaurar el matcheo del sentinel roto por el `try/except` de `webapp/app.py`.
2. [MAJOR] Render guard: golden de `pinakotheke-kosmos` desincronizado en 3 PNGs (re-snapshot en entorno canónico o investigar rasterización).
