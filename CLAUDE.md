# CLAUDE.md — Eikón (Generador determinista de assets de marca)

> Repositorio: `/workspace/Pinakotheke/eikon/`  
> Sistema: Pinakotheke / Mouseîon (producto independiente)  
> Modo: Generador DETERMINISTA (cero IA/GPU). Motor Python + FastAPI multi-tenant + React SPA.  
> Producción: Cloud Run GCP (`eikon-633619052458.us-central1.run.app`)

---

## ¿Qué es Eikón?

Eikón es un **generador de assets de marca en 2 fases** para el ecosistema Pinakotheke (Cloud Atlas) y la suite Prizma Enterprise:

1. **IDENTIDAD** (fija): elegir o fijar un logo (procedural vía `logo_style`/`logo_seed`, O pre-existente vía `logo_asset` SVG/PNG)
2. **ESTUDIO** (recurrente): generar batches de assets visuales (logos, cards, social, stationery, og tags) heredando la identidad fija, variando solo contenido (textos, colores HSL)

**No** renderizan con IA, no entrenan. El motor es **combinatorial + procedural** (isotypes SVG precompilados, mapeo marca→CSS vars, Playwright para rasterizar HTML→PNG server-side).

Productos: **34 marcas no-agora** genera **~1300 PNGs** con validación WCAG AA/AAA.

---

## Arquitectura de módulos

### `eikon_core/` — Motor determinista (Python)

| Módulo | Responsabilidad |
|--------|---|
| `brand.py` | Cargar JSON de marca (colores, tipografía, textos) desde `marcas/<slug>.json` |
| `taxonomy.py` | **TAXONOMÍA**: categorías/tipos/variantes. **CARGA de `config/taxonomy.json`** (fallback: Python dict en `_legacy_python_taxonomia`) |
| `mapping.py` | Mapear marca → CSS vars (HSL), validar contraste WCAG, aplicar overrides |
| `isotype.py` + `isotypes/pack_*.py` | Generadores de isotipos procedurales (SVG inline) — formas, packs temáticos (Brand Form, Geo, Sím, Fractales, etc.) |
| `injection.py` | Inyectar el isotipo + datos en la plantilla HTML (bind vars, datos JSON) |
| `render.py` | Orquestador: carga marca, resuelve template, inyecta, **renderiza vía Playwright** (server-side) |
| `combinatorial/planner.py` | Planner determinístico: enumera variaciones (distintos counts) × tipos × variantes |
| `combinatorial/ranking.py` | Ranking: selecciona mejores variaciones por diversidad (HSL distance) |
| `templates.py` | Resuelve path/alias de plantillas HTML desde `templates/` |
| `layout.py` | Validador de layout (DOM): overflow, required text, duplicación (pre-screenshot) |
| `manifest.py` | Escribe metadata por asset: `_manifest.json` (hash, estado, warnings) |
| `validation.py` | Validador de taxonomía |
| `constants.py` | Rutas canónicas (MARCAS_DIR, TEMPLATES_DIR, OUTPUT_DIR, TIMEOUT_MS) |

### `webapp/` — API FastAPI multi-tenant

| Módulo | Responsabilidad |
|--------|---|
| `app.py` | Orquestador: lifespan, routers, auth, static mount (SPA), storage backend. Rutas: `POST/auth/register`, `POST/auth/login`, `POST/auth/logout` (JWT cookie) |
| `security.py` | JWT httpOnly cookie, token creation, TTL 30 días, renovación deslizante |
| `db.py` | Schema SQLite/Postgres (dual: DDL idiomático por BD), users/brands/batches/variations |
| `storage.py` | CRUD: insert/update/get usuario, marca, batch, variaciones. Multi-tenant con `tenant_id` |
| `storage_backend/local.py` | Almacenamiento local en disco (`output/`) |
| `storage_backend/gcs.py` | Almacenamiento Google Cloud Storage (prod) |
| `api/auth_api.py` | Endpoints API-KEY: `POST/GET/DELETE /api/v1/auth/api-keys` (crear/listar/revocar API keys para agentes) |
| `api/brands.py` | Endpoints: `GET/POST /api/v1/brands`, logo options, set identity (logo_style/logo_seed/logo_asset) |
| `api/batches.py` | Endpoints: crear batch (async), status, download resultados |
| `api/variations.py` | Endpoints: plan variaciones (combinatorial), upload PNGs (client-render) |
| `api/client_render.py` | Plan → spec (sin renderizar), upload PNG (workflow cliente). Contiene `_TEMPLATE_WHITELIST` |
| `api/downloads.py` | Descargar PNG por asset_id (secure: scoped por tenant) |
| `api/gallery.py` | Listar assets generados con URLs públicas |
| `jobs/worker.py` | WorkerPool async: poll batches, **renderiza vía Playwright** (server-side), escribe storage |
| `services/eikon_runner.py` | Adapter: wrapper de `eikon_core.render_asset()` para el worker |

### `frontend/` — React SPA (Vite + TypeScript)

| Archivo/Dir | Responsabilidad |
|---|---|
| `src/App.tsx` | Router principal, wizard flujo |
| `src/pages/BrandIdentityPage.tsx` | Fase 1: elegir logo (procedural o asset) |
| `src/pages/AssetStudioPage.tsx` | Fase 2: generar batch, subir PNGs |
| `src/styles/theme.css` | Design tokens oscuro, variables CSS |
| `src/render/clientRender.ts` | **CLIENT-RENDER**: carga template, inyecta datos, rasteriza HTML→PNG con `modern-screenshot` |
| `src/api/` | Calls a `/api/v1/*` |
| `public/templates/` | Templates HTML cachadas localmente (fallback) |

**Crítico**: El ESTUDIO usa **CLIENT-RENDER** (navegador, `modern-screenshot`), NO el server. El server-render (Playwright en `jobs/worker.py`) es para OTRA fase (batch asincrónico).

### `mcp_server/` — Servidor MCP para agentes

FastMCP monolítico (`server.py`):
- **Auth**: API-key Bearer (`EIKON_API_KEY` env var)
- **Tools**: `eikon_list_brands`, `eikon_create_brand`, `eikon_logo_options`, `eikon_set_identity`, `eikon_generate_asset`, **`eikon_generate_and_get`** (end-to-end: batch → poll → download), `eikon_gallery`
- **Polling**: `eikon_generate_and_get` hace polling cada 2-5s hasta `status == 'completed'`

---

## Flujo de 2 pasos: IDENTIDAD → ESTUDIO

### Paso 1: IDENTIDAD (fija, usuario elige UNA VEZ)

Usuario elige cómo fijar el logo de la marca:

**Opción A: Logo procedural** (isotype generado)
```json
{
  "logo_style": "pack_brand_form",  // Ej. pack temático
  "logo_seed": 42                    // Ej. seed determinístico
}
```
→ Eikón genera SVG isotype procedural vía `isotype.generate_isotype(params)`.

**Opción B: Logo pre-existente** (logo_asset)
```json
{
  "logo_asset": "marcas/agora/logo.svg"  // Path relativo o absoluto
}
```
→ Se valida, se carga como data URI base64 (SEGURIDAD: sin scripts, SSRF-safe), se inyecta.

### Paso 2: ESTUDIO (recurrente, generador batch)

Usuario entra contenido variable (textos, colores) × categoría/tipo/variante:

```json
{
  "brand_id": 5,
  "asset_types": ["isotipo", "business_card", "og_general"],
  "content_overrides": {
    "text_marca": "Mi Brand",
    "text_tagline": "Innovar siempre"
  }
}
```

**Combinatoria interna**:
- Planner enumera: categoría (logos/cards/og/social) × tipos (isotipo, business_card, ...) × variantes (v1_color, v2_mono, ...)
- Ranking selecciona N mejores por diversidad (HSL distance entre variaciones)
- Cada combinación se renderiza: template HTML + isotipo (fijo de paso 1) + contenido (variable)

---

## Cómo correr / testear / deployar

### Desarrollo local

```bash
cd /workspace/Pinakotheke/eikon

# 1. Backend (FastAPI + worker)
python3 -m pip install -r requirements.txt
uvicorn webapp.app:app --reload --port 8000

# 2. Frontend (React + Vite)
cd frontend
npm install
npm run dev  # Vite en http://localhost:5173

# 3. Tests
pytest tests/ -v
pytest webapp/tests/ -v --cov=webapp

# 4. Linter / type checker
ruff check . && mypy .

# 5. Motor CLI (generación batch)
python3 eikon.py --marca pinakotheke-kosmos
python3 eikon.py --all --dry-run
```

### Tests críticos (382 tests, ~15% de cobertura de edge cases)

```bash
pytest tests/test_eikon_checks.py -v  # Templates, WCAG, hash, manifest
pytest webapp/tests/test_*.py -v      # DB, storage, auth, combinatoria
```

### Deployment a Cloud Run (GCP)

Ver `/workspace/Pinakotheke/eikon/docs/DEPLOY.md` para detalles.

```bash
# Desde raíz del repo
export PROJECT=mi-proyecto-gcp
export REGION=us-central1
export SERVICE=eikon
bash deploy/cloud-run.sh
```

La imagen es **multi-stage** (Node.js build SPA + Python runtime con Playwright/Chromium).

---

## API REST v1 (endpoints principales)

**Auth** (en `app.py`):
- `POST /auth/register` → crea usuario+tenant, retorna JWT cookie
- `POST /auth/login` → autentica, retorna JWT cookie
- `POST /auth/logout` → limpia cookie

**Auth API-Key** (en `api/auth_api.py`, para agentes):
- `POST /api/v1/auth/api-keys` → crear API key
- `GET /api/v1/auth/api-keys` → listar API keys
- `DELETE /api/v1/auth/api-keys/{key_id}` → revocar API key

**Marcas**:
- `GET /api/v1/brands` → lista marcas del tenant
- `POST /api/v1/brands` → crea marca (color, tipografía)
- `GET /api/v1/brands/{id}/logo-options` → variaciones procedurales
- `POST /api/v1/brands/{id}/set-identity` → fija `logo_style`/`logo_seed` O `logo_asset`

**Batches (ESTUDIO)**:
- `POST /api/v1/batches` → crea batch async (enqueued → worker lo procesa)
- `GET /api/v1/batches/{id}` → status (pending/processing/completed/failed)
- `GET /api/v1/batches/{id}/plan` → combinaciones + render-spec (sin renderizar)
- `POST /api/v1/batches/{id}/variations/upload` → recibe PNG subido (client-render)

**Descargas**:
- `GET /api/v1/download/{asset_id}` → PNG (scoped por tenant)

**Galería**:
- `GET /api/v1/gallery` → lista assets generados con URLs

---

## Capa agéntica / MCP

**Cómo un agente genera assets**:

1. Autenticar vía API-key Bearer
2. `eikon_create_brand(name, palette)` → brand_id
3. `eikon_set_identity(brand_id, logo_style="...", logo_seed=42)` → fija identidad
4. `eikon_generate_and_get(brand_id, asset_type="isotipo", content={...})` → **polling end-to-end**:
   - Crea batch
   - Poll cada 2-5s hasta `status == 'completed'`
   - Descarga PNG
   - Retorna URL o bytes

Ver `mcp_server/server.py` para todas las tools.

---

## Convenciones de código

- **Idioma**: Prosa/docstrings/comentarios en **ES**; identificadores/código en **EN**
- **Determinismo**: el motor NO tiene aleatoriedad; seed es explícito
- **Multi-tenant**: TODA consulta BD scoped por `tenant_id` (prevenir IDOR)
- **Validación de entrada**: contra path traversal (logo_asset), palette keys, asset_types
- **Tipificación**: `TypeSpec`, `VariantSpec`, `CombinationSpec`, `BrandData` (usar tipos!)
- **Errores**: raizar en `eikon_core.errors.EikonScreenshotError` y `webapp/api/schemas.py`

---

## GOTCHAS CRÍTICOS

### 1. **Render: CLIENT vs SERVER**

- **CLIENT-RENDER** (frontend, `src/render/clientRender.ts`): Navegador rasteriza HTML→PNG con `modern-screenshot`
  - **Úsalo para**: ESTUDIO (fase 2, generación interactiva)
  - **Cómo verificar**: abrir DevTools → Network → ver request a `/api/v1/batches/{id}/plan`, luego upload del PNG
  
- **SERVER-RENDER** (worker, `jobs/worker.py`): Playwright en servidor
  - **Úsalo para**: Batch asincrónico (si es necesario renderizar en prod sin navegador)
  - **Para QA local**: replicar el CLIENT-render, NO usar el server (caro)

**⚠️ ERROR COMÚN**: Asumir que el ESTUDIO usa Playwright. Errado. El ESTUDIO es 100% cliente. Solo el worker (batch asincrónico) usa Playwright.

### 2. **Taxonomía: DEBE CARGARSE de `config/taxonomy.json`**

- **De verdad**: `config/taxonomy.json` es la fuente canónica.
- **Fallback**: si el JSON falta o es inválido, `taxonomy.py` carga el dict Python `_legacy_python_taxonomia`.
- **Para cambiar tipos/categorías/variantes**: EDITAR `config/taxonomy.json`, NO el dict Python.
- **Validación**: `validate_taxonomy()` en `eikon_core/validation.py` chequea schema.

```bash
# Validar taxonomía antes de usar
python3 -c "from eikon_core.validation import validate_taxonomy; validate_taxonomy()"
```

### 3. **Inyección del isotipo: SIEMPRE como data URI base64**

❌ **JAMÁS**:
```html
<!-- INSEGURO: innerHTML SVG inline = XSS risk -->
<div id="isotype" dangerouslySetInnerHTML={{__html: svg}} />
```

✅ **SIEMPRE**:
```html
<!-- SEGURO: data URI base64 (SVG sanitizado) -->
<img src="data:image/svg+xml;base64,PHN2ZyAuLi8+" alt="logo">
```

**Por qué**: el SVG contiene texto de marca del usuario → XSS. La inyección en `render.py` (`_load_logo_asset_data_uri`) sanitiza SVG (rechaza `<script>`, event handlers, xlink:href no-data) antes de encoded.

### 4. **Storage: leer vía backend, NUNCA directo**

❌ **JAMÁS**:
```python
with open(f"output/{asset_id}.png", "rb") as f:  # ← rompe en GCS
```

✅ **SIEMPRE**:
```python
storage = get_storage()  # local.LocalStorage | gcs.GCSStorage
png_bytes = storage.open(f"assets/{asset_id}.png", "rb").read()
```

**Por qué**: en prod (Cloud Run), los archivos viven en GCS, no en disco. El backend abstrae la diferencia.

### 5. **Multi-tenant / IDOR: TODO scoped por `tenant_id`**

**Toda consulta MUST incluir tenant scope**:

```python
# ❌ INSEGURO: usuario de tenant A puede leer datos de tenant B
brand = db.get_brand(brand_id)

# ✅ SEGURO
brand = db.get_brand(brand_id, tenant_id=current_user["tenant_id"])
```

`update_batch_status()`, `get_brand()`, `list_variations()` lo EXIGEN como parámetro explícito.

### 6. **Content override se aplica en 2 lugares**

- **Client-side** (`/api/v1/batches/{id}/plan`): `content_overrides` enviado en request
- **Server-side** (worker `render_asset`): `apply_combination_overrides()` aplica el mismo override antes de renderizar

**Si no pasan**, los textos salen vacíos o genéricos. Verificar que las claves de override casen con `TEXT_LIMITS` en `text.py`.

### 7. **Plantillas protegidas (compartidas con Prizma, NO editar)**

```json
// config/taxonomy.json
"protected_templates": [
  "ad_leaderboard.html",
  "letterhead.html",
  "stat_card.html"
]
```

Estas son marcas en común con Prizma Enterprise. Edición requiere coordinación explícita. Si las modificas, verifica que Prizma siga funcionando (testear con `prizma-iris`, `prizma-*` marcas).

### 8. **Secretos: NUNCA en repo**

- `.env.local` → git-ignored ✅
- `mcp_server/CREDENTIALS.local.md` → git-ignored ✅
- Env vars en Cloud Run Secret Manager ✅

Nunca pegues `EIKON_API_KEY`, `EIKON_WEBAPP_SECRET`, `DATABASE_URL` en el código.

### 9. **Logo_asset path traversal: validado estrictamente**

```python
# render.py._resolve_logo_asset()
# Rechaza: ".." en path, rutas absolutas (/...), paths fuera de repo
```

Si pasas `../../../etc/passwd`, se rechaza. Esto es **intencionado**. No intentar bypassear.

---

## Archivos importantes

| Archivo | Rol |
|---------|-----|
| `README.md` | Intro + flags CLI |
| `ARCHITECTURE.md` | Diagrama de módulos + flujo de datos (ver ese archivo) |
| `AGENTS.md` | Comandos run/test/deploy rápidos para agentes |
| `eikon.py` | Shim retrocompatible / entrypoint |
| `config/taxonomy.json` | **Fuente canónica de categorías/tipos/variantes** |
| `config/axes.json` | Config de combinatoria (planner: distintos counts) |
| `docs/MASTER-TAXONOMIA.md` | Spec de taxonomía (expansiva, humano-legible) |
| `docs/DEPLOY.md` | Guía multi-stage Docker + Cloud Run |
| `docs/QA-CHECKLIST.md` | Checklist de QA (manual + automatizado) |
| `webapp/db.py` | Schema dual (SQLite ↔ Postgres) |
| `contrast_validator.py` | Validador WCAG AA/AAA standalone |
| `gallery.py` | Generador HTML de galerías |

---

## Roadmap típico para un nuevo agente/feature

1. **Entender el flujo**: IDENTIDAD (logo_style/seed O logo_asset) → ESTUDIO (batch)
2. **Leer taxonomía**: `config/taxonomy.json` es la verdad
3. **Probar CLI local**: `python3 eikon.py --marca MARCA --dry-run`
4. **Probar API**: crear marca vía endpoint, generar batch
5. **Entender cliente**: cómo el frontend hace client-render (ver `src/render/clientRender.ts`)
6. **Deploy**: si es backend, testear en dev local, luego `bash deploy/cloud-run.sh`

---

## Preguntas frecuentes

**P: ¿Cómo agrego una nueva categoría de asset (ej. stickers)?**
R: Editar `config/taxonomy.json`, agregar tipo bajo `stickers`, crear template `templates/sticker.html`, registrar en `_TEMPLATE_WHITELIST` en `webapp/api/client_render.py`.

**P: ¿Cómo cambio el color de un asset para una marca?**
R: Los colores se mapean automáticamente vía `mapping.py` → marca JSON → CSS vars HSL. NO hardcodear colores en templates.

**P: ¿Cómo testeo el render en local sin que sea lento?**
R: Usa `--marca MARCA` (una sola marca) en lugar de `--all`, o `--solo <categoria>` (una categoría) para filtrar. Opcionalmente, `--dry-run` (enumera sin renderizar PNGs).

**P: ¿Dónde escribo logs?**
R: Usa `logger = logging.getLogger(__name__)` en cada módulo. En prod van a stderr (Cloud Logging).

---

## Stack resumido

| Componente | Tecnología |
|---|---|
| Motor | Python 3.12 + eikon_core/ |
| API | FastAPI + Uvicorn |
| BD | SQLite (dev) / Postgres (prod) |
| Render server | Playwright 1.40 + Chromium |
| Storage | Disco local (dev) / Google Cloud Storage (prod) |
| Frontend | React 18 + Vite 5 + TypeScript |
| Rasterizado cliente | modern-screenshot 4.4.37 |
| MCP | FastMCP (Python) |
| CI/CD | Cloud Build (imagen Docker) |
| Deploy | Cloud Run (us-central1) |

---

## Contacto / Propietario

Sistema de Pinakotheke (Mouseîon). Owner: Steven Vallejo.  
Accesos: `/workspace/_accesos/INDEX.md`.
