---
date: 2026-06-29
phase: "Fase 0 — Terreno limpio + gates duros + hardening del motor"
status: done
scope: limpieza, linters/type/format duros, CI real, determinismo de render, seams de testabilidad
---

# Auditoría Fase 0 — Hardening

## Scope

Dejar el motor Eikón en **terreno limpio con gates duros** antes de construir el producto:
limpieza de cruft, linters/type-check/format estrictos, CI real (sin bypass), fix de
determinismo de render, y refactor de seams de testabilidad — **sin regresión visual**.

## Evidence

| Gate | Comando | Resultado |
|---|---|---|
| Lint | `.venv/bin/ruff check .` | **All checks passed!** (0 errores; ruleset E/W/F/I/UP/B/C90/SIM/RUF/PERF/PIE/TID, McCabe 12) |
| Format | `.venv/bin/ruff format --check .` | 44/44 formateados |
| Types | `.venv/bin/mypy eikon_core webapp` | **Success: no issues** (strict en eikon_core/webapp) |
| Tests | `make test / test-variations / test-taxonomy / test-webapp` | **167 / 83 / 10 / 16** ✓ (276 total) |
| Determinismo | render kosmos ×3 → pixel-hash | **idéntico** en las 3 corridas (antes: `lockup_horizontal/v1_color` flaky) |
| No-regresión | golden pixel-hash vs pre-0B (kosmos+iris) | solo `v1_color` cambió (estabilización del race; 15px AA), resto idéntico |
| Cleanup | `du` / `git status` | 3 venvs (~10.4 GB) y 6 templates muertos eliminados |

## Findings

| Sev | Hallazgo | Evidencia | Remediación |
|---|---|---|---|
| resolved | Race de fuentes en el primer screenshot → render no determinista | v1_color variaba entre corridas | `fonts.ready` + reflow + doble rAF + settle en `render.py`; verificado 3× idéntico |
| resolved | `OUTPUT_DIR` global + hack de metaclass | `eikon.py`/`constants.py` | `eikon_core/paths.py` (RenderPaths, listo para tenant-scoping) + `__getattr__` |
| resolved | Errores Playwright por string-match | `render.py` | `eikon_core/errors.py` (excepciones tipadas) |
| resolved | CI con `\|\| true` (validadores informativos) | `eikon-gates.yml` | CI reescrito: gates reales + job render-qa separado |
| resolved | Sin linters/type/format | — | ruff+mypy+format+pre-commit + cobertura |
| minor | PNG **byte**-no-determinista (píxeles sí deterministas) | sha256 de archivo varía, pixel-hash no | Aceptado MVP; normalizar encoding PNG en fase posterior si se requiere reproducibilidad byte-exacta |
| note | Cobertura piso 46% (actual ~48%); objetivo 80% | `pyproject [tool.coverage]` | Ratchet al añadir tests sintéticos (Fase 1/3) |
| note | Runner casero (276 checks) no migrado a pytest idiomático; cobertura subestima checks por subprocess | `make test` vs `pytest` | Migración diferida a Fase 3 (junto a E2E) |
| note | `webapp/app.py` C901 suprimido (registro de rutas FastAPI) | per-file-ignore | Aceptable; se revisará al partir el router en Fase 1 |

## Autocrítica (complejidad y valor)

- **¿Sumó valor o fue plomería?** El fix de determinismo es **producto, no plomería**: sin él, "re-renderiza la variación que elegiste" daría resultados distintos — rompe la promesa de "elegir las mejores". Justificado.
- **Complejidad añadida:** mínima y con propósito (`paths.py`, `errors.py` son pequeños y habilitan tenant-scoping y manejo de fallos de Fase 1). No hay over-engineering.
- **Deuda honesta declarada:** cobertura aún baja y tests caseros sin migrar — explícito arriba, no se afirma "tests duros completos". Se cierra en Fase 3.

## Sign-off

- Auditor: Opus (orquestador) + verificación adversarial (renders + gates ejecutados, no auto-reportes).
- Estado: **done** — base lista para Fase 1 (producto). 0 críticos, 0 majors abiertos.
