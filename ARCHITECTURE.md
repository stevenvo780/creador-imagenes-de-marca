# ARCHITECTURE.md — Arquitectura profunda de Eikón

> Sistema modular determinista de generación de assets de marca.  
> 2 fases: IDENTIDAD (logo fijo) → ESTUDIO (batch recurrente).

---

## 1. Módulos principales + responsabilidades

```
┌─────────────────────────────────────────────────────────────────┐
│                     Eikón (Arquitectura)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           Frontend (React SPA + Vite)                    │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │  │
│  │  │ BrandIdentityPage.tsx │  │ AssetStudioPage.tsx   │  │ GalleryPage.tsx  │  │  │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │  │
│  │         │ HTTP           │ HTTP            │ HTTP       │  │
│  └─────────┼─────────────────┼────────────────┼──────────┘  │
│            │                 │                │              │
│  ┌─────────▼─────────────────▼────────────────▼──────────┐  │
│  │        FastAPI (webapp/)                              │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │ API v1 Routers                                  │  │  │
│  │  │ ├── auth_api.py (register, login, logout)      │  │  │
│  │  │ ├── brands.py (CRUD, logo options, identity)   │  │  │
│  │  │ ├── batches.py (async batch jobs)              │  │  │
│  │  │ ├── client_render.py (plan, upload PNG)        │  │  │
│  │  │ ├── downloads.py (PNG scoped by tenant)        │  │  │
│  │  │ └── gallery.py (list assets with URLs)         │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │ Services                                        │  │  │
│  │  │ ├── security.py (JWT httpOnly, TTL 30d)        │  │  │
│  │  │ ├── db.py (SQLite ↔ Postgres dual)             │  │  │
│  │  │ ├── storage.py (CRUD DB: users/brands/batches) │  │  │
│  │  │ └── jobs/worker.py (WorkerPool: async render)  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │ Storage Backend (abstraction)                   │  │  │
│  │  │ ├── local.py (dev: output/ disk)               │  │  │
│  │  │ └── gcs.py (prod: Google Cloud Storage)        │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └────────────┬───────────────────────────────────────────┘  │
│               │                                               │
│  ┌────────────▼───────────────────────────────────────────┐  │
│  │        eikon_core/ (Motor determinista Python)        │  │
│  │                                                         │  │
│  │  ┌─ brand.py                                          │  │
│  │  │  └─ load_json(marca_path) → BrandData             │  │
│  │  │     (colores HSL, tipografía, textos)             │  │
│  │  │                                                    │  │
│  │  ├─ taxonomy.py                                       │  │
│  │  │  └─ CLOUD_ATLAS_TAXONOMIA / PRIZMA_TAXONOMIA     │  │
│  │  │     (CARGADO DE config/taxonomy.json)             │  │
│  │  │  └─ TypeSpec (type → variants)                    │  │
│  │  │  └─ VariantSpec (variant_id → label)              │  │
│  │  │                                                    │  │
│  │  ├─ mapping.py                                        │  │
│  │  │  └─ map_marca_to_vars(marca_data)                 │  │
│  │  │     → CSS vars dict (HSL, opacidad)               │  │
│  │  │  └─ Validar contraste WCAG (BT.709 luminancia)    │  │
│  │  │                                                    │  │
│  │  ├─ isotype.py + isotypes/pack_*.py                  │  │
│  │  │  └─ generate_isotype(seed, style, brand_color)    │  │
│  │  │     → SVG inline (procedural)                      │  │
│  │  │  └─ Packs: Brand Form, Geo, Sym, Fractales, etc   │  │
│  │  │                                                    │  │
│  │  ├─ injection.py                                      │  │
│  │  │  └─ injection_script(isotipo, logo_data_uri)       │  │
│  │  │     → JS que inyecta en el DOM de la template     │  │
│  │  │                                                    │  │
│  │  ├─ render.py (ORCHESTRATOR PRINCIPAL)               │  │
│  │  │  └─ render_asset(                                 │  │
│  │  │       brand_id, asset_type, content_override)     │  │
│  │  │  ├─ 1. Load marca JSON                            │  │
│  │  │  ├─ 2. Generar isotipo (seed/asset)               │  │
│  │  │  ├─ 3. Resolver template HTML                     │  │
│  │  │  ├─ 4. Inyectar vars + isotipo                    │  │
│  │  │  ├─ 5. Validar layout (DOM inspection)            │  │
│  │  │  ├─ 6. Renderizar con Playwright (server-side)    │  │
│  │  │  └─ 7. Escribir PNG + metadata                    │  │
│  │  │                                                    │  │
│  │  ├─ combinatorial/                                   │  │
│  │  │  ├─ planner.py → plan_combinations()              │  │
│  │  │  │  └─ Enumera: categorías × tipos × variantes    │  │
│  │  │  │  └─ Determinístico (sin aleatoriedad)          │  │
│  │  │  └─ ranking.py → rank_by_diversity()              │  │
│  │  │     └─ Selecciona N mejores (HSL distance)        │  │
│  │  │                                                    │  │
│  │  ├─ layout.py (VALIDADOR DOM)                        │  │
│  │  │  └─ inspect_layout_dom()                          │  │
│  │  │     → texto mínimo, overflow, duplicación         │  │
│  │  │  └─ aggregate_layout_status() → pass/warn/fail    │  │
│  │  │                                                    │  │
│  │  ├─ manifest.py                                      │  │
│  │  │  └─ write_manifest(assets_data)                   │  │
│  │  │     → _manifest.json por marca                    │  │
│  │  │     (hash, status, layout_status, warnings)       │  │
│  │  │                                                    │  │
│  │  ├─ templates.py                                     │  │
│  │  │  └─ resolve_template(asset_type) → HTML file      │  │
│  │  │  └─ Soporta aliases legacy (linkedin_banner)      │  │
│  │  │                                                    │  │
│  │  ├─ validation.py                                    │  │
│  │  │  └─ validate_taxonomy() → schema check            │  │
│  │  │                                                    │  │
│  │  ├─ constants.py                                     │  │
│  │  │  └─ MARCAS_DIR, TEMPLATES_DIR, OUTPUT_DIR, ...   │  │
│  │  │                                                    │  │
│  │  ├─ cache.py                                         │  │
│  │  │  └─ compute_hash(asset_spec)                      │  │
│  │  │  └─ load_cache() / save_cache()                   │  │
│  │  │                                                    │  │
│  │  └─ errors.py                                        │  │
│  │     └─ EikonScreenshotError, EikonValidationError    │  │
│  │                                                         │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐   │
│  │          MCP Server (mcp_server/server.py)           │   │
│  │  FastMCP + httpx async client                        │   │
│  │  ├─ eikon_list_brands()                             │   │
│  │  ├─ eikon_create_brand()                            │   │
│  │  ├─ eikon_set_identity()                            │   │
│  │  ├─ eikon_generate_asset() (→ batch_id)             │   │
│  │  ├─ eikon_generate_and_get() (polling end-to-end)   │   │
│  │  └─ eikon_gallery()                                 │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Flujo de datos: IDENTIDAD (Fase 1)

```
┌────────────────────────────────────────────────────────────────┐
│  Fase 1: IDENTIDAD (Usuario elige logo UNA VEZ)               │
└────────────────────────────────────────────────────────────────┘

        Frontend (BrandIdentityPage.tsx)
           │
           │ POST /api/v1/brands/{id}/set-identity
           ▼
    ┌──────────────────┐
    │ Option A         │    Option B
    │ logo_style +     │    │
    │ logo_seed        │    │ logo_asset (path)
    └──────────┬───────┘    │
               │            ▼
               │     render.py._load_logo_asset_data_uri()
               │     ├─ Resolve path (anti path-traversal)
               │     ├─ Sanitize SVG (reject scripts, xlink)
               │     └─ Encode as data:image/svg+xml;base64,...
               │
               │ Ambas opciones:
               ▼
    ┌─────────────────────────────────┐
    │ render_asset() en render.py     │
    │ (orchestrator principal)        │
    │                                 │
    │ 1. Load marca JSON              │
    │ 2. Generate/load isotipo        │
    │    └─ isotype.generate_isotype()│
    │       (procedural SVG)          │
    │    O data URI (logo_asset)      │
    │ 3. Resolve template (isotipo.html)
    │ 4. Inyectar vars + isotipo      │
    │    └─ injection_script()        │
    │ 5. Validate layout              │
    │ 6. Screenshot Playwright        │
    │ 7. Save PNG + metadata          │
    └─────────────────────────────────┘
               │
               ▼
    Storage backend
    └─ output/<marca>/logos/isotipo_v1_color.png
```

**Estado persistente**: la elección de logo_style/seed O logo_asset se guarda en la tabla `brands.logo_seed` / `brands.logo_asset` (DB).

---

## 3. Flujo de datos: ESTUDIO (Fase 2, Batch)

```
┌────────────────────────────────────────────────────────────────┐
│  Fase 2: ESTUDIO (Generación recurrente de assets)            │
│  Backend + Frontend (dúo: client-side rendering)              │
└────────────────────────────────────────────────────────────────┘

Frontend (AssetStudioPage.tsx)
  │
  ├─ GET /api/v1/batches/{batch_id}/plan
  │  │
  │  └─ Webapp (client_render.py.get_batch_plan())
  │     ├─ Load marca (identity ya fija)
  │     ├─ Fetch combinatorial spec (axes.json)
  │     ├─ plan_combinations() → render-specs
  │     │  (sin renderizar todavía)
  │     └─ Retorna:
  │        {
  │          "combinations": [
  │            {
  │              "category": "logos",
  │              "asset_type": "isotipo",
  │              "variant": "v1_color",
  │              "template": "isotipo.html",
  │              "isotype_svg_uri": "data:image/svg+xml;base64,...",
  │              "vars": {"--primary": "hsl(...)"}
  │            }, ...
  │          ]
  │        }
  │
  └─ Frontend lo RECIBE
     │
     ├─ Para cada combination:
     │  │
     │  └─ Load template HTML (templates/isotipo.html)
     │     │
     │     ├─ Inyectar isotipo_svg_uri (data URI) → <img src=data:...>
     │     ├─ Inyectar CSS vars (--primary, --secondary, ...)
     │     ├─ Inyectar contenido (textos de override)
     │     │
     │     └─ RASTERIZAR HTML→PNG (navegador, modern-screenshot)
     │        └─ screenshot.png
     │
     └─ POST /api/v1/batches/{batch_id}/variations/upload
        (Frontend envía PNG al servidor)
        │
        └─ Webapp (client_render.py.upload_variation())
           ├─ Recibe PNG + asset_id
           ├─ Valida (hash, size, tenant_id scope)
           ├─ Guarda en storage backend
           │  (local: output/ O GCS: bucket)
           │
           └─ Retorna: {"success": true, "asset_id": ...}

Resultado:
  ├─ PNG guardado en storage
  ├─ Batch status → "completed"
  └─ Gallery muestra assets con URLs descargables
```

**Clave**: El client-render es NAVEGADOR + `modern-screenshot`, NO Playwright. Más rápido, cero CPU servidor.

---

## 4. Worker Pool (server-side render alternativo)

Para renders asincronos que no necesitan navegador:

```
┌────────────────────────────────────────────────────────────┐
│  WorkerPool (jobs/worker.py) — Render asincrónico         │
│  (Alternativa a client-render, menos usado)               │
└────────────────────────────────────────────────────────────┘

1. POST /batches
   └─ Webapp enqueues batch (status='pending')
   
2. WorkerPool.poll_loop() (runs in lifespan)
   │
   └─ Fetch batches where status='pending'
      │
      └─ Para cada batch:
         │
         └─ eikon_runner.render_batch()
            │
            ├─ Para cada asset_spec:
            │  │
            │  └─ render_asset() [MISMO DEL PASO 1]
            │     ├─ Load marca + identity
            │     ├─ Generar/cargar isotipo
            │     ├─ Inyectar vars + isotipo
            │     ├─ Playwright screenshot
            │     └─ Save PNG
            │
            └─ Actualizar batch (status='completed')
            
3. Webapp retorna batch status
   └─ Frontend poll GET /batches/{id} hasta 'completed'
   
4. GET /download/{asset_id}
   └─ Descargar PNG (scoped por tenant)
```

**Nota**: Raro usar WorkerPool en producción (client-render es más eficiente). Principalmente para testing o renders off-peak.

---

## 5. Modelo de datos (DB)

```sql
-- Multi-tenant schema (SQLite / Postgres dual)

CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at INTEGER
);

CREATE TABLE brands (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  slug TEXT,
  -- Identidad fija (Fase 1)
  logo_style TEXT,       -- "pack_brand_form", ...
  logo_seed INTEGER,     -- seed determinístico
  logo_asset TEXT,       -- path a SVG/PNG pre-existente
  -- Colores + tipografía
  palette TEXT,          -- JSON {"primario": "hsl(...)", ...}
  typography TEXT,       -- JSON
  created_at INTEGER
);

CREATE TABLE batches (
  id INTEGER PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  brand_id INTEGER NOT NULL,
  status TEXT,           -- 'pending'|'processing'|'completed'|'failed'
  asset_types TEXT,      -- JSON ["isotipo", "business_card", ...]
  content_overrides TEXT,-- JSON {text_marca: "...", ...}
  created_at INTEGER,
  started_at INTEGER,
  finished_at INTEGER
);

CREATE TABLE variations (
  id INTEGER PRIMARY KEY,
  batch_id INTEGER NOT NULL,
  asset_type TEXT,
  variant_id TEXT,       -- "v1_color", "v2_mono", ...
  png_path TEXT,         -- "assets/batch_{id}/asset_{i}.png"
  hash TEXT,             -- SHA256
  layout_status TEXT,    -- 'pass'|'warning'|'fail'
  wcag_aa BOOLEAN,
  wcag_aaa BOOLEAN,
  created_at INTEGER
);

-- Scoped por tenant_id en TODAS las queries (IDOR prevention)
```

---

## 6. Taxonomía: Estructura JSON

```json
{
  "schema_version": 1,
  "families": {
    "cloud_atlas": {
      "categories": {
        "logos": {
          "device_scale": 3,
          "types": [
            {
              "name": "isotipo",
              "width": 800,
              "height": 800,
              "template": "isotipo.html",
              "variants": [
                {"id": "v1_color", "label": "Color"},
                {"id": "v2_mono", "label": "Mono"},
                {"id": "v3_inverse", "label": "Inverse"}
              ]
            },
            ...
          ]
        },
        "cards": { ... },
        "social": { ... }
      }
    },
    "prizma": { ... }
  }
}
```

**Carga**: `taxonomy.py._from_taxonomy_json()` parses `config/taxonomy.json`.  
**Fallback**: Si JSON inválido, usa `_legacy_python_taxonomia()` dict.

---

## 7. Inyección de isotipo: Flujo de seguridad

```
render.py._load_logo_asset_data_uri(path_str)
  │
  ├─ 1. Validar path contra traversal
  │   └─ Rechaza: "..", paths absolutos /...
  │
  ├─ 2. Resolver a archivo real
  │   └─ Candidatos: repo root, marcas/, parent
  │
  ├─ 3. Para SVG: SANITIZAR
  │   ├─ Rechaza: <script> tags
  │   ├─ Rechaza: event handlers (onclick, onload, ...)
  │   ├─ Rechaza: xlink:href no-data (SSRF)
  │   └─ ✓ Permite: data:image URIs, <defs>, <style>
  │
  ├─ 4. Validar tamaño
  │   └─ MAX: 5 MB
  │
  ├─ 5. Encode as data URI
  │   └─ "data:image/svg+xml;base64,PHN2ZyAuLi8+"
  │
  └─ 6. Inyectar EN TEMPLATE VÍA IMAGEN
      └─ <img src="data:image/svg+xml;base64,..." />
         (SEGURO: img tag, no innerHTML)

Resultado: No hay XSS, no hay SSRF.
```

---

## 8. Multiplicidad de variaciones (Combinatorial)

```
combinatorial/planner.py.plan_combinations(brand_id, axes_config)
  │
  └─ Enumera:
     ├─ Categoría (logos, cards, social, og)
     ├─ Tipo (isotipo, business_card, ig_post, ...)
     └─ Variante (v1_color, v2_mono, v3_inverse, ...)

Ej. (logos, isotipo, v1_color), (logos, isotipo, v2_mono), ...

combinatorial/ranking.py.rank_by_diversity()
  │
  └─ Para cada (tipo) × count:
     ├─ Genera N combinaciones (distinct seeds)
     ├─ Evalúa por HSL distance (paleta interna)
     ├─ Selecciona TOP N (máxima diversidad)
     └─ Determinístico: same seed → same ranking

Resultado: 238 assets (6 marcas × ~40 assets cada una)
```

---

## 9. Validación: WCAG + Layout

```
POST render_asset()
  │
  ├─ Step 1: Layout DOM validation (pre-screenshot)
  │  │
  │  └─ layout.py.inspect_layout_dom()
  │     ├─ Inyecta JS que inspecciona DOM
  │     ├─ Chequea: texto mínimo, overflow, duplicación
  │     └─ Retorna: layout_status='pass'|'warning'|'fail'
  │
  └─ Step 2: WCAG AA/AAA (post-screenshot)
     │
     └─ contrast_validator.py.validate_contrast()
        ├─ Extrae texto + color (Pillow)
        ├─ Calcula luminancia BT.709
        ├─ Ratio contrast >= 4.5:1 (AA) / 7:1 (AAA)
        └─ Escribe _contraste-report.json

Resultado: _manifest.json con status metadata
```

---

## 10. Flujo CLI (entrypoint alternativo)

```
python3 eikon.py --marca pinakotheke-kosmos
  │
  ├─ cli.py.main() (entry)
  │
  ├─ orchestrator.py.run_generator()
  │  │
  │  ├─ Load brand JSON
  │  ├─ Load taxonomía
  │  ├─ Enumerate assets
  │  │
  │  └─ Para cada asset:
  │     │
  │     └─ render.py.render_asset()
  │        ├─ Generar isotipo (seed)
  │        ├─ Inyectar vars + isotipo
  │        ├─ Playwright screenshot
  │        └─ Escribir PNG + manifest
  │
  ├─ gallery.py.generate_gallery()
  │  └─ HTML de galería
  │
  └─ contrast_validator.py.validate()
     └─ _contraste-report.json

Salida: output/<marca>/
```

---

## 11. Stack de comunicación

```
┌─────────────────────────────┐
│  Frontend (React, ts)       │
└──────────────┬──────────────┘
               │ HTTP(S)
               │ ├─ /api/v1/brands
               │ ├─ /api/v1/batches
               │ ├─ /api/v1/batches/{id}/plan
               │ ├─ /api/v1/templates/{name}
               │ └─ /download/{asset_id}
               ▼
┌─────────────────────────────┐
│  FastAPI (python)           │
│  + WorkerPool               │
└──────────────┬──────────────┘
               │
        ┌──────┴────────┐
        │               │
        ▼               ▼
    DB (SQLite    Storage Backend
     / Postgres)  (local / GCS)
        │               │
        ├───────────────┤
        │               │
        └─────────┬─────┘
                  │
             eikon_core/
             (render.py,
              isotype.py,
              taxonomy.py)
                  │
                  ▼
             Playwright
             (Chromium)
                  │
                  ▼
             PNG output
```

---

## 12. Ejemplo end-to-end: crear isotype de Kosmos

```
1. User crea brand "Kosmos" vía /brands POST
   → brand_id = 5

2. User elige identity vía /brands/5/set-identity POST
   {
     "logo_style": "pack_brand_geo",
     "logo_seed": 123
   }
   → Almacenado en brands.logo_seed

3. User abre Studio, genera batch vía POST /batches
   {
     "brand_id": 5,
     "asset_types": ["isotipo"],
     "content_overrides": {"text_marca": "Kosmos"}
   }
   → batch_id = 42, status='pending'

4. Frontend GET /batches/42/plan
   ← {
       "combinations": [
         {
           "asset_type": "isotipo",
           "variant": "v1_color",
           "isotype_svg_uri": "data:image/svg+xml;base64,...",
           "vars": {"--primary": "hsl(210, 100%, 50%)"}
         },
         {
           "asset_type": "isotipo",
           "variant": "v2_mono",
           "isotype_svg_uri": "...",
           "vars": {"--primary": "hsl(0, 0%, 0%)"}
         }
       ]
     }

5. Frontend renderiza cada combination:
   ├─ Load isotipo.html template
   ├─ Inyectar <img src="data:image/svg+xml...">
   ├─ Inyectar CSS vars (--primary, ...)
   ├─ modern-screenshot() → PNG bytes
   │
   └─ POST /batches/42/variations/upload
      {
        "asset_id": "isotipo_v1_color",
        "png_bytes": <binary>
      }

6. Webapp guarda PNG en storage (output/kosmos/logos/isotipo_v1_color.png)
   ├─ Calcula hash
   ├─ Valida layout (DOM)
   ├─ Valida WCAG AA
   └─ Escribe a _manifest.json

7. Batch status → 'completed'

8. Frontend GET /gallery
   ← [
       {
         "asset_id": "isotipo_v1_color",
         "url": "/download/isotipo_v1_color",
         "wcag_aa": true
       },
       ...
     ]

9. User descarga vía GET /download/isotipo_v1_color
   ← PNG (scoped por tenant_id)
```

---

## 13. Puntos críticos para debugging

| Síntoma | Causa probable | Solución |
|---|---|---|
| PNG vacío/corrupto | Logo mal inyectado | Ver injection.py, validar data URI |
| Texto invisible | Contrast fail o layout issue | Check _contraste-report.json, _manifest.json |
| Asset no renderizado | Template no encontrada | Validar resolve_template(), _TEMPLATE_WHITELIST |
| DB constraint error | tenant_id no incluido | Añadir tenant_id a query |
| GCS 403 Forbidden | Storage backend auth | Verificar credentials env var |
| Playwright timeout | Chromium no arrancó | Ver logs, aumentar TIMEOUT_MS |

---

## 14. Deployment: Imagen multi-stage

```dockerfile
# Stage 1: Node build (SPA)
FROM node:20-slim AS node-build
WORKDIR /app/frontend
COPY frontend/package*.json .
RUN npm ci
COPY frontend/ .
RUN npm run build
# → frontend/dist/

# Stage 2: Python runtime
FROM python:3.12-slim
WORKDIR /app
# Instalar Playwright + Chromium
RUN apt-get update && apt-get install -y \
    libssl-dev libnss3 libgconf-2-4 libxss1 libappindicator1 \
    libindicator7 libu2f-udev libvpx7 libxdamage1 libopenjp2-7 \
    libpango-1.0-0 libpangoft2-1.0-0 fonts-liberation libappindicator3-1 \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 \
    libcups2 libdbus-1-3 libexpat1 libgbm1 libgcc1 libglib2.0-0 \
    libgtk-3-0 libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 \
    ca-certificates fonts-dejavu-core
RUN python -m pip install --no-cache-dir -U pip
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Instalar Playwright binaries
RUN playwright install chromium
# Copiar app + SPA build
COPY . .
COPY --from=node-build /app/frontend/dist ./frontend/dist
# Usuario no-root
RUN useradd -m -u 1000 eikon && chown -R eikon:eikon /app
USER eikon
# Lifespan arranca en puerto 8000
EXPOSE 8000
CMD ["uvicorn", "webapp.app:create_app", "--host", "0.0.0.0", "--port", "8000"]
```

**En Cloud Run**:
- Vars env: `DATABASE_URL`, `GCS_BUCKET`, `EIKON_WEBAPP_SECRET`
- Memory: 2 GB (Playwright + Chromium)
- Timeout: 120s (long-running render)
- Concurrency: 1 (render es single-thread)

---

## Conclusión

Eikón orquesta:
- **Determinismo**: Seed explícito, sin aleatoriedad
- **Multi-tenant**: Scoping por tenant en toda la BD
- **Seguridad**: Path traversal, SSRF, XSS mitigado
- **Modularidad**: eikon_core separado de webapp, frontend desacoplada
- **Escalabilidad**: Storage backend abstracción (local/GCS), worker pool async

Flujo simplificado: **Marca JSON → Isotipo (fijo) → Plantilla HTML → Inyectar vars → Renderizar PNG → Validar WCAG**.
