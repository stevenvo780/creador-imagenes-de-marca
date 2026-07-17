# Eikón — Generador determinista de assets de marca

Generador de **assets visuales** para el ecosistema Pinakotheke (Cloud Atlas) y suite Prizma Enterprise.  
**Determinista** (cero IA/GPU), **multi-tenant**, **combinatorial**: 2 fases — IDENTIDAD (logo fijo) → ESTUDIO (batch recurrente).

> Produce **~1300 PNG** sobre **34 marcas** con validación **WCAG AA/AAA**  
> Arquitectura: Python `eikon_core/` + FastAPI `webapp/` + React SPA `frontend/` + MCP `mcp_server/`

## Comencemos

**Para documentación completa, leer (en orden):**
1. **[CLAUDE.md](CLAUDE.md)** — arquitectura, gotchas críticos, capa agéntica (EMPIEZA AQUÍ)
2. **[AGENTS.md](AGENTS.md)** — comandos rápidos, startup, debugging
3. **[ARCHITECTURE.md](ARCHITECTURE.md)** — diagramas de módulos + flujos de datos
4. **Este README** — overview técnico + CLI

---

## ¿Qué es Eikón?

**Generador en 2 fases**:

| Fase | Qué | Ejemplo |
|------|-----|---------|
| **1. IDENTIDAD** (fija) | Usuario elige o carga logo (procedural vía seed OR pre-existente SVG/PNG) | `logo_style="pack_brand_geo", logo_seed=42` |
| **2. ESTUDIO** (recurrente) | Generar batch de assets heredando la identidad fija, variando contenido (textos, colores HSL) | `asset_types=["isotipo", "business_card"], content_overrides={text_marca: "Mi Brand"}` |

**Stack**: Python 3.12 (`eikon_core/`) + FastAPI (`webapp/`) + React+Vite (`frontend/`) + modern-screenshot (client-render) + Playwright (server-render opcional) + SQLite/Postgres + local/GCS storage.

---

## Estructura

- `eikon.py`: shim entrypoint histórico (`python3 eikon.py --marca ...`).
- **`eikon_core/`**: motor determinista — taxonomía, mapping HSL, isotypes procedurales, combinatorial planner, Playwright render, validación WCAG+layout.
- **`webapp/`**: FastAPI multi-tenant — auth JWT cookie, CRUD marcas/batches, WorkerPool async, storage backend (local/GCS).
- **`frontend/`**: React SPA (Vite+TypeScript) — Identity + Studio wizard, **client-render** HTML→PNG via modern-screenshot.
- **`mcp_server/`**: Servidor MCP FastMCP — tools para agentes (eikon_list_brands, eikon_generate_and_get, etc).
- **`config/`**: `taxonomy.json` (FUENTE CANÓNICA), `axes.json` (combinatoria).
- **`templates/`**: HTML plantillas + CSS design tokens + fonts WOFF2.
- **`marcas/`**: JSON de marcas (colores, tipografía, textos).
- **`tests/`**: 382+ tests unitarios (templates, WCAG, combinatoria, DB, storage).

## Uso rápido

```bash
cd /workspace/Pinakotheke/eikon

# Una marca (piloto)
python3 eikon.py --marca pinakotheke-kosmos

# Solo una categoría
python3 eikon.py --marca prizma-iris --solo logos

# Subset explícito
python3 eikon.py --only-marcas pinakotheke-kosmos,prizma-iris

# TODAS las marcas no-agora
python3 eikon.py --all

# Dry-run (enumera sin renderizar)
python3 eikon.py --all --dry-run

# Incremental (re-render solo lo que cambió)
python3 eikon.py --marca pinakotheke-kosmos --resume

# Limpiar output/<marca>/ antes de renderizar (opt-in)
python3 eikon.py --marca pinakotheke-kosmos --clean

# Sin validación WCAG al final
python3 eikon.py --marca pinakotheke-kosmos --skip-contraste

# Workers paralelos (actualmente limitado a 1 por diseño)
python3 eikon.py --all --parallel 1
```

## Flags disponibles

| Flag | Significado |
|---|---|
| `--marca <slug>` | Procesa una sola marca (ej. `pinakotheke-kosmos`). |
| `--all` | Procesa TODAS las marcas excepto `agora-*`. |
| `--only-marcas <s1,s2,...>` | Subset por coma (alternativa a `--all`). |
| `--solo <categoria>` | Filtra una categoría (ej. `logos`, `cards`). |
| `--clean` | Borra `output/<marca>/` antes de renderizar (opt-in). |
| `--dry-run` | Enumera sin escribir PNGs. |
| `--resume` | Usa cache para saltar assets no modificados. |
| `--skip-contraste` | Omite validación WCAG al final. |
| `--parallel <N>` | Workers paralelos (limitado a 1). |
| `--fail-on-layout` | Exit 1 si algún asset tiene `layout_status == "fail"` (ver §Validadores de layout más abajo). |

## Estado actual (2026-06-20)

- **34 marcas no-agora** generadas.
- **1302 PNGs** totales.
- **34/34** `_manifest.json` por marca.
- **34/34** `_contraste-report.json` por marca.
- **34/34** galerías individuales + **1** agregada.
- `_STATUS.md` maestro en raíz con tabla completa.
- `output/_contraste-report.json` agregado regenerable vía
  `scripts/eikon_aggregate_wcag.py`.
- Piloto Kosmos (`pinakotheke-kosmos`) aprobado: 45 assets, 100% AA pass.

## Validadores de layout (en esta rama)

Además del WCAG AA, esta rama suma validadores de layout que cubren
defectos que el contraste **no** detecta (overflow, off-viewport,
required-text vacío). Detalle completo en [`docs/QA-CHECKLIST.md`](docs/QA-CHECKLIST.md) §5
y en [`INSTRUCCIONES-EIKON.md`](INSTRUCCIONES-EIKON.md) §10.

Estado al 2026-06-20:

| Script | Estado | Rol |
|---|---|---|
| `eikon.py` (interno) | **implementado** | DOM layout validator corre antes del screenshot; escribe `layout_status` y `layout_warnings` por asset en `_manifest.json`. Soporta `--fail-on-layout`. |
| `scripts/eikon_validate_layout.py` | **implementado** | Scanner agregado de manifests con `--fail-on-errors`, `--json`, `--only-issues`. |
| `scripts/eikon_pixel_check.py` | **planeado** | Congruencia pixel entre variantes del mismo `(categoría, tipo)` — detecta drift y variantes idénticas. |
| Safe-area checker | **planeado** | bounding boxes vs `SAFE_INSET_PX[layout_id]`. |

`_legacy/audit_render.py` ya implementa el chequeo DOM base (texto
mínimo, overflow, duplicación de copy) pero solo loguea a stdout — es
la base conceptual sobre la que se construyó el validador actual.

## Salida

```
output/
  <slug-marca>/
    logos/            # lockup_horizontal, lockup_vertical, wordmark,
                      # isotipo, favicon, watermark
    cards/            # business_card, stat_card
    og/               # og_general
    stationery/       # letterhead
    banners/          # solo Cloud Atlas: ad_leaderboard, ad_rectangle,
                      # linkedin_header, twitter_header, youtube_header,
                      # web_hero_desktop
    _manifest.json           # metadata de cada asset
    _contraste-report.json   # WCAG AA/AAA por marca
    .cache.json              # cache local (no versionado)
  _gallery_<slug>.html       # galería por marca
  _gallery_aggregated.html   # galería agregada (34 marcas)
  _contraste-report.json     # reporte WCAG global agregado
```

## Scripts auxiliares

| Script | Qué hace |
|---|---|
| `eikon.py` | Motor canónico (entry point principal). Incluye validador DOM de layout por asset (pre-screenshot) y flag `--fail-on-layout`. |
| `contrast_validator.py` | Validador WCAG AA standalone. |
| `gallery.py` | Genera galerías HTML (individual, `--all-marcas`, `--aggregated`). |
| `scripts/eikon_aggregate_wcag.py` | Consolida reportes WCAG por marca en el global. |
| `scripts/eikon_validate_layout.py` | Scanner agregado de `layout_status`/`layout_warnings` en manifests. `--json`, `--fail-on-errors`, `--only-issues`. |
| `scripts/eikon_count.py` | Cuenta outputs y escribe `_STATUS.md` (incluye columna Layout). |
| `scripts/eikon_pixel_check.py` | **(planeado)** Congruencia pixel / drift entre variantes. |
| `tests/test_eikon_checks.py` | 55 checks unitarios (templates, WCAG, hash, manifest, dry-run). |

## Documentación

- [`docs/MASTER-TAXONOMIA.md`](docs/MASTER-TAXONOMIA.md) — spec de categorías, tipos, variantes.
- [`docs/INSTRUCCIONES-EIKON.md`](docs/INSTRUCCIONES-EIKON.md) — guía operativa actual.
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md) — historial del motor (v1.0, v1.1, v1.2).
- [`docs/ESTADO-ENTREGA-2026-06-20.md`](docs/ESTADO-ENTREGA-2026-06-20.md) — estado tras corrida general (snapshot histórico).
- [`docs/OUTPUT-NO-VERSIONADOS.md`](docs/OUTPUT-NO-VERSIONADOS.md) — política de output git-ignored.
- [`docs/QA-CHECKLIST.md`](docs/QA-CHECKLIST.md) — checklist mecánico + visual.
- [`docs/QA-GATES.md`](docs/QA-GATES.md) — gates automatizados.
- [`docs/legacy/`](docs/legacy/) — documentos históricos (brief original, instrucciones del generador legacy).

## Notas

- El motor `eikon.py` reemplaza `generar_agencia_v2.py` (legacy).
- `--all` renderiza solo las 6 marcas core (`pinakotheke-kosmos`, `prizma-iris`,
  `steven-vallejo-filosofo`, `agora`, `pinakotheke`, `prizma`).
  Usar `--all-marcas` para renderizar las 38 marcas registradas (incluye demos).
- Las 32 marcas no-core en `marcas/` quedan registradas como demos para
  validar la taxonomía, pero no se renderizan por defecto.
- `agora-*` se renderiza solo si la marca es `agora` exacto; las demás variantes
  (`agora-st`, `agora-elenxos`, `agora-autologic`) son demos no incluidos.
- Las variantes por tipo están definidas en `_build_taxonomia()` dentro
  de `eikon.py`; los alias legacy (linkedin_header → linkedin_banner) se
  resuelven vía `_TEMPLATE_ALIASES`.
- `requirements.txt`: `playwright`, `Pillow`, `numpy`.
