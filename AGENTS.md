# AGENTS.md — Arranque rápido para agentes/modelos

> **Para detalles completos, leer `CLAUDE.md` primero.**

Este archivo es la hoja de trucos para agentes que operan en Eikón. Tiene comandos, paths, y punteros a secciones críticas.

---

## Qué es Eikón (tl;dr)

Generador determinista de **assets de marca** en 2 fases:

1. **IDENTIDAD**: fijar logo (procedural vía seed, O pre-existente SVG/PNG)
2. **ESTUDIO**: generar batch de assets (cards, social, logos, etc.) con identidad fija

**Arquitectura**: `eikon_core/` (Python) + `webapp/` (FastAPI) + `frontend/` (React SPA) + `mcp_server/` (MCP para agentes)

---

## Startup rápido (desarrollo local)

```bash
cd /workspace/Pinakotheke/eikon

# 1. Instalar deps + arrancar backend
pip install -r requirements.txt
uvicorn webapp.app:app --reload --port 8000

# 2. En otra terminal, frontend
cd frontend && npm install && npm run dev
# → http://localhost:5173

# 3. Tests (verificar que todo está OK)
pytest tests/ -v --tb=short
pytest webapp/tests/ -v --tb=short

# 4. Linter
ruff check . && mypy .
```

---

## Comandos clave

### Motor CLI (generador de batch)

```bash
# Una marca (verificación rápida)
python3 eikon.py --marca pinakotheke-kosmos

# Dry-run (sin escribir PNGs)
python3 eikon.py --marca pinakotheke-kosmos --dry-run

# Solo logos (filtrar categoría)
python3 eikon.py --marca prizma-iris --solo logos

# Todas las 6 marcas core
python3 eikon.py --all

# Con validación WCAG al final
python3 eikon.py --marca pinakotheke-kosmos --fail-on-layout
```

### Validación + galería

```bash
# Validar taxonomía
python3 -c "from eikon_core.validation import validate_taxonomy; validate_taxonomy()"

# Generar galerías HTML
python3 gallery.py --all-marcas
python3 gallery.py --all-marcas --aggregated

# Validar layout en outputs
python3 scripts/eikon_validate_layout.py --fail-on-errors

# Contar PNGs + status
python3 scripts/eikon_count.py
```

---

## Estructura de directorios (lo esencial)

```
eikon/
├── CLAUDE.md                     ← Documentación COMPLETA (gotchas, arquitectura)
├── AGENTS.md                     ← Este archivo
├── ARCHITECTURE.md               ← Diagramas + flujos detallados
├── README.md                     ← Intro + flags CLI
│
├── eikon.py                      ← Shim entrypoint
├── eikon_core/                   ← Motor Python (render, taxonomía, isotypes, combinatorial)
├── webapp/                       ← FastAPI: auth, brands, batches, storage backend
├── frontend/                     ← React SPA (Vite + TypeScript)
├── mcp_server/                   ← Servidor MCP para agentes
│
├── config/
│   ├── taxonomy.json             ← 🔴 FUENTE CANÓNICA: categorías/tipos/variantes
│   ├── axes.json                 ← Config de combinatoria (planner)
│   └── layouts.json              ← Layouts (safe-area, device scale)
│
├── templates/                    ← HTML plantillas + CSS + fonts
│   ├── isotipo.html
│   ├── business_card.html
│   ├── eikon-system.css          ← Design tokens globales
│   ├── fonts/                    ← WOFF2
│   └── ...
│
├── marcas/                       ← JSON de marcas (colores, tipografía, textos)
│   ├── pinakotheke.json
│   ├── prizma-iris.json
│   └── ...
│
├── output/                       ← PNGs generados (git-ignored)
│   └── <marca>/
│       ├── logos/
│       ├── cards/
│       ├── _manifest.json        ← Metadata (hash, estado, layout status)
│       └── _contraste-report.json ← WCAG AA/AAA
│
├── docs/
│   ├── MASTER-TAXONOMIA.md       ← Spec expandida (tipos, variantes, dimensiones)
│   ├── DEPLOY.md                 ← Guía: imagen Docker + Cloud Run
│   ├── QA-CHECKLIST.md           ← QA manual + automatizado
│   ├── INSTRUCCIONES-EIKON.md    ← Guía operativa del motor
│   └── ...
│
├── tests/                        ← Tests unitarios (382 tests)
│   ├── test_eikon_checks.py
│   └── ...
│
├── Dockerfile                    ← Multi-stage: Node build + Python runtime
└── requirements.txt              ← Deps: Playwright, Pillow, numpy, psycopg
```

---

## Rutas canónicas (constants.py)

```python
# Importar vía:
from eikon_core.constants import (
    MARCAS_DIR,           # /workspace/Pinakotheke/eikon/marcas/
    TEMPLATES_DIR,        # /workspace/Pinakotheke/eikon/templates/
    OUTPUT_DIR,           # /workspace/Pinakotheke/eikon/output/
    TAXONOMY_JSON_PATH,   # /workspace/Pinakotheke/eikon/config/taxonomy.json
    ROOT,                 # /workspace/Pinakotheke/eikon/
)
```

---

## Gotchas críticos (ver CLAUDE.md §GOTCHAS)

| Gotcha | Qué hacer |
|--------|-----------|
| **Client vs Server render** | Frontend hace CLIENT-render (navegador). Worker hace SERVER-render (Playwright). Para QA local: replicar cliente, NO server. |
| **Taxonomía cargada de JSON** | Editar `config/taxonomy.json`, NO el dict Python en `taxonomy.py`. |
| **Logo como data URI** | SIEMPRE base64 data URI (seguridad). Nunca innerHTML SVG inline. |
| **Storage backend** | Usar `get_storage()` abstracción. Nunca `open()` directo. |
| **Multi-tenant IDOR** | Todas las queries scoped por `tenant_id` explícitamente. |
| **Plantillas protegidas** | No editar `ad_leaderboard.html`, `letterhead.html`, `stat_card.html` sin OK. |
| **Secretos** | NUNCA en repo. Usar env vars / Secret Manager. |

---

## Debugging rápido

```bash
# Ver logs del worker (batch async)
# En dev: stdout. En prod: Cloud Logging.

# Invalidar cache de un asset
rm output/<marca>/.cache.json

# Rerender marca single, sin resume
python3 eikon.py --marca <marca> --clean

# Ver manifest de una marca
cat output/<marca>/_manifest.json | python3 -m json.tool

# Validar CSS vars inyectadas
# Ver el HTML renderizado en DevTools (Network → templates/...)
```

---

## API v1 endpoints (lo esencial)

```bash
# Auth (en app.py)
POST /auth/register        # crea usuario+tenant
POST /auth/login           # JWT cookie
POST /auth/logout          # limpia

# Auth API-Key (en api/auth_api.py, para agentes)
POST /api/v1/auth/api-keys          # crear API key
GET  /api/v1/auth/api-keys          # listar API keys
DELETE /api/v1/auth/api-keys/{id}   # revocar API key

# Marcas
GET  /api/v1/brands          # lista por tenant
POST /api/v1/brands          # crea
POST /api/v1/brands/{id}/set-identity  # fija logo_style/logo_seed O logo_asset

# Batches (async combinatorial render)
POST /api/v1/batches         # crea batch enqueued
GET  /api/v1/batches/{id}    # status

# Client render (alternativa: navigate en navegador)
GET  /api/v1/batches/{id}/plan  # combinaciones + render spec
POST /api/v1/batches/{id}/variations/upload  # recibe PNG subido

# Descargas
GET  /api/v1/download/{asset_id}  # PNG (scoped por tenant)

# Galería
GET  /api/v1/gallery         # assets con URLs
```

---

## Testing

```bash
# Todos los tests
pytest -v

# Solo tests de eikon_core
pytest tests/test_eikon_checks.py -v

# Solo tests de webapp
pytest webapp/tests/ -v --cov=webapp

# Un test específico
pytest tests/test_eikon_checks.py::test_brand_loading -v
```

**Cobertura**: ~15% (focus en edge cases críticos: templates, WCAG, combinatoria, DB, storage).

---

## Deployment

```bash
# Local Docker
docker build -t eikon:latest .
docker run -p 8000:8000 \
  -e DATABASE_URL="sqlite:///data/webapp/eikon.db" \
  -e EIKON_ENV=dev \
  eikon:latest

# Production (Cloud Run)
export PROJECT=mi-proyecto-gcp
export REGION=us-central1
bash deploy/cloud-run.sh

# Verificar health
curl https://eikon-633619052458.us-central1.run.app/health
```

Ver `docs/DEPLOY.md` para detalles (imagen multi-stage, Postgres, GCS, Secret Manager).

---

## MCP (si operás como agente externo)

```python
from mcp.client import ClientSession
# O usa las tools del servidor:
# - eikon_list_brands()
# - eikon_create_brand(name, palette, ...)
# - eikon_generate_and_get(brand_id, asset_type, content)
# Ver mcp_server/server.py para todas.
```

Env: `EIKON_BASE_URL`, `EIKON_API_KEY` (Bearer token).

---

## Pasos típicos: crear asset por agent

1. **Listar marcas**: `eikon_list_brands()` → brand_id
2. **Fijar identidad**: `eikon_set_identity(brand_id, logo_style="pack_brand_form", logo_seed=7)` → fija
3. **Generar batch**: `eikon_generate_asset(brand_id, "isotipo")` → batch_id
4. **Esperar**: poll `eikon_batch_status(batch_id)` hasta `"completed"`
5. **Descargar**: `eikon_gallery(brand_id)` → URLs de assets

O usa **`eikon_generate_and_get()`** que hace todo end-to-end.

---

## Referencias cruzadas

| Necesitas... | Ir a |
|---|---|
| Spec de taxonomía (categorías/tipos/variantes) | `config/taxonomy.json` + `docs/MASTER-TAXONOMIA.md` |
| Guía de isotypes (packs procedurales) | `eikon_core/isotypes/` |
| Validador WCAG | `contrast_validator.py` |
| Flujo completo (diagramas) | `ARCHITECTURE.md` |
| Deploy multi-stage Docker | `docs/DEPLOY.md` |
| QA checklist | `docs/QA-CHECKLIST.md` |
| Marcas JSON (ejemplo) | `marcas/pinakotheke-kosmos.json` |

---

## Preguntas rápidas

**P: ¿Dónde empiezo si quiero añadir un nuevo tipo de asset?**
A: `config/taxonomy.json` (new type) → `templates/new_type.html` (template) → `_TEMPLATE_WHITELIST` en `webapp/api/client_render.py`.

**P: ¿Cómo debuggeo si un PNG sale corrupto?**
A: Ver `_manifest.json` (layout_status, warnings) + contrastar vía `contrast_validator.py` + abrir PNG en editor.

**P: ¿Qué env vars necesito para prod?**
A: `DATABASE_URL`, `GCS_BUCKET`, `EIKON_WEBAPP_SECRET`, `EIKON_ENV=production`, `PORT=8080`.

**P: ¿Cómo cambio colores para una marca?**
A: Editar `marcas/<slug>.json` (palette HSL) → se mapean automáticamente vía `mapping.py`.

---

## Owner / Support

Eikón es parte de Pinakotheke (Steven Vallejo, Mouseîon).  
Accesos: `/workspace/_accesos/INDEX.md`.
