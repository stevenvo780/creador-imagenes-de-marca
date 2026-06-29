# Eikón — Refactor profundo + producto web multi-tenant (Design Spec)

**Fecha:** 2026-06-29
**Autor:** orquestación Opus + flota (Codex/Gemini/MiniMax)
**Estado:** propuesto — pendiente de aprobación del owner
**Alcance:** un solo proyecto, ejecutado en fases. Cadencia aprobada: **autónomo hasta el final** (una sola aprobación de este spec; luego ejecución por fases sin checkpoints intermedios, con 3 ciclos de auditoría al cierre).

---

## 1. Objetivo

Convertir Eikón (motor Python+Playwright de assets de marca, ya funcional) en un **producto web multi-tenant** donde:

- Cada usuario se registra (JWT) y **posee sus propias marcas** (no los `marcas/*.json` compartidos).
- Un **asistente paso-a-paso** permite elegir **combinatorias algorítmicas** (paleta × tipografía × layout × fondo × densidad × forma × **isotipo SVG procedural**) para generar logos, banners, tarjetas, social, OG, papelería — todo el stack que ya entrega el motor.
- Botones de **"genera N variaciones"** (p.ej. 50 banners): se elige el estilo/ejes, se generan variaciones muestreadas determinísticamente, **rankeadas** (WCAG + layout + diversidad), para elegir las mejores.
- Una **galería ordenada** para previsualizar, seleccionar y **descargar** (single + ZIP). Almacenamiento en **carpeta local** ahora, detrás de una interfaz `StorageBackend` lista para migrar a **GCS**.

El motor semi-determinístico actual debe seguir haciendo **todo lo que ya hace**, con **más variedad** y enriquecimiento combinatorio.

---

## 2. Estado actual (verificado por mapeo)

**Base sólida ya existente:**
- `eikon_core/` (18 módulos): pipeline `cli → orchestrator → brand/mapping/injection → render(Playwright) → manifest`, validación WCAG y layout.
- `eikon.py`: shim/entrypoint (con hack de metaclass para `OUTPUT_DIR`).
- `variations.py`: planner determinístico (SHA-256 → seed) **standalone, no cableado al render**.
- `config/taxonomy.json` (familias `cloud_atlas`/`prizma`) + `config/layouts.json` (35 layouts: id, template, w, h, plataforma).
- `templates/` (52 activos) + `eikon-system.css` (26 tokens de color, 2 de tipografía, **0 de tamaño**) + `eikon-runtime.js` (contrato de inyección por query params + auto-contraste + font-fitting).
- `webapp/`: FastAPI multi-tenant MVP — JWT HS256 (cookie httpOnly), PBKDF2, SQLite (`tenants/users/jobs/assets`), jobs vía subprocess de `eikon.py`, vistas server-side (HTMX).
- `scripts/` validadores (ironman, layout, pixels, taxonomy, count, aggregate-wcag), `tests/` (~51 checks caseros + pocos pytest), `audit/` (metodología 4-severidades reutilizable).

**Carencias / deuda confirmadas:**
- **Marcas no son entidad por-tenant** (son archivos compartidos; cualquier tenant apunta a cualquier slug).
- **Sin wizard combinatorio**; `variations.py` desconectado del render.
- **Cero linters/type-check**; CI con validadores informativos (`ironman ... || true` nunca falla).
- Smells del motor: `OUTPUT_DIR` global (constants.py), pattern-matching por nombre de variante (mapping.py:64-84), errores Playwright por string-match (render.py:102-119), `--parallel` declarado y no implementado, hash de cache sensible a whitespace, contrast_validator import opcional silencioso.
- `bg.add_task(asyncio.run, coro)` (loops anidados); `output/` compartido no tenant-scoped.
- Dead weight: 3 venvs (~10.4 GB, gitignored), templates duplicados (`ig_post` vs `instagram_post`), dead (`ui_component`, `whatsapp_perfil`, `contra_cover`), tokens de tamaño ausentes.
- Sin secretos trackeados (✓); `jwt_secret` con fallback de env seguro (✓, debe **exigirse** en prod).

---

## 3. Decisiones de arquitectura (aprobadas)

| # | Decisión | Elección | Razón |
|---|----------|----------|-------|
| 1 | Frontend | **API JSON + SPA React (Vite+TS)** | UX rica para wizard y selección masiva; servida **same-origin** por FastAPI → la cookie JWT httpOnly funciona sin CORS. |
| 2 | Jobs pesados | **Worker async in-process + SSE** | Cola en SQLite, sin infra extra, suficiente para batches de 50; interfaz lista para migrar a cola real. |
| 3 | Combinatoria | **Paramétrico + isotipos SVG procedurales** | Logos de verdad, no wordmark-en-caja; ataca el "aún es pobre". |
| 4 | Cadencia | **Autónomo hasta el final** | Una aprobación; ejecución por fases + 3 auditorías al cierre. |
| 5 | Marcas legacy (38 JSON) | **Al tenant del owner + fixtures de dev** | Son marcas reales/empresariales (Prizma/Agora) → NO públicas. Seed al tenant owner; siguen como fixtures de test. Starter templates públicos se crean genéricos aparte. |

**Principio datos-vs-config (núcleo del "no quemar"):** (a) *Datos de usuario* (marcas: paleta/tipografía/textos/logo/símbolo, assets generados, batches, selecciones) → **DB + storage por-tenant**, nada quemado, aislado por `tenant_id`. (b) *Capacidad del motor* (taxonomía de tipos, layouts/tamaños, plantillas HTML/CSS, catálogo de ejes combinatorios, heurísticas de ranking) → **config versionada en el repo** (es el producto, no data de usuario), declarativa y data-driven (se elimina el pattern-matching `family=="prizma"`). (c) *Rutas/secretos* → **env/config** (des-quemado en Fase 0-B: DI de `OUTPUT_DIR`, etc.).

Stack adicional: **Vite + React + TypeScript** (SPA, build estático servido por FastAPI). Almacenamiento: interfaz `StorageBackend` con impl `LocalStorage` (carpeta) ahora, `GCSStorage` después.

---

## 4. Arquitectura objetivo

### 4.1 Motor (`eikon_core`) — refactor por seams (sin romper comportamiento)
- **DI de rutas:** `RenderContext`/`Settings` dataclass reemplaza `OUTPUT_DIR`/paths module-level → `output_dir(tenant_id, brand_slug)` tenant-scoped. Elimina el hack de metaclass de `eikon.py`.
- **Brand como dato:** `load_brand(source)` acepta `dict` (DB) **o** path; IO separado de lógica.
- **Combinatorial params data-driven:** `mapping.py` deja de hacer pattern-matching por nombre de variante; cada `AxisOption` aporta overrides de tokens (color/tipo/tamaño/fondo/forma) + texto. `render_asset` recibe `params: dict`.
- **Orquestación dual:** `orchestrator.run_generator` mantiene el modo taxonomía actual **y** un modo "plan de variaciones" (itera `Variation` con seed → params → render).
- **Excepciones estructuradas:** `RenderError`/`LayoutError` en `render.py` (no string-match).
- **`eikon_core/isotype.py` (nuevo):** genera SVG procedural (monogram/lettermark, geometric/grid, abstract, enclosure) con seed determinístico → data URI inyectado. Semilla extraída de `web_icons.generate_svg()` → `eikon_core/svg_generator.py`.
- **Cache:** hash normalizado (insensible a whitespace).

### 4.2 Motor combinatorio (nuevo, sobre `variations.py`)
- **Ejes** (`eikon_core/combinatorial/axes.py`):
  1. **Layout** — composición por tipo (lockup h/v, símbolo, wordmark; banner izq/centro/split/overlay), desde `layouts.json` + variantes nuevas.
  2. **Palette scheme** — mono / duotono / claro / oscuro / acento-invertido / gradiente (mapea `--bg/--texto/--acento`).
  3. **Typography pairing** — pares título/cuerpo desde `config/typography.json` (nuevo). Respeta fuentes de marca.
  4. **Background treatment** — sólido / gradiente / patrón geométrico / grid / orbe / textura.
  5. **Density/scale** — compact / normal / spacious (requiere **nuevos tokens de tamaño/espaciado** en `eikon-system.css`).
  6. **Corner/shape** — sharp / rounded / pill (`--corner-radius`).
  7. **Isotype style** — procedural SVG (varios estilos por seed).
  8. **Accent placement** — posición de acento/decoración.
- **Planner** (`planner.py`): envuelve `variations.py`; el wizard fija unos ejes y permuta otros; "N variaciones" = muestreo determinístico (seed) del subespacio elegido.
- **Ranking** (`ranking.py`): `score = f(WCAG_ratio, layout_status, perceptual_diversity(pHash), heurísticas)`; ordena, dedup near-identical, devuelve top-N.
- **Data model:** `Axis`, `AxisOption`, `CombinationSpec(brand_id, asset_types[], fixed{}, permuted[], count, seed)`, `Variation`(extendido con params+score), `VariationBatch`.

### 4.3 Backend (FastAPI JSON API)
- Routers en `webapp/api/`: `auth`, `brands` (CRUD per-tenant), `wizard` (catálogo de ejes/opciones), `batches` (crear batch N, estado), `assets`/`gallery` (listar/seleccionar), `downloads` (single + ZIP).
- `webapp/jobs/worker.py`: cola SQLite + worker async in-process + **SSE** de progreso; `max_concurrent_jobs`, cancelación, reemplaza `bg.add_task(asyncio.run)`.
- `webapp/storage/`: `base.py` (Protocol `StorageBackend`), `local.py` (carpeta tenant-scoped), `gcs.py` (stub futuro).
- **DB (migración aditiva):** `brands(id, tenant_id, slug, name, palette_json, typography_json, logo_text, logo_symbol, texts_json, created_at)`, `brand_assets`/`variations(id, batch_id, brand_id, axis_params_json, seed, score, output_path, wcag_json, layout_status, selected)`, `batches(id, tenant_id, brand_id, spec_json, status, counts_json, ...)`. Aislamiento por `tenant_id` en toda consulta (tests de aislamiento obligatorios). **Migración de marcas legacy:** un seed idempotente convierte los 38 `marcas/*.json` en filas `brands` del **tenant del owner** (no públicas); los JSON quedan además como fixtures de test del motor. Brand CRUD valida que el `tenant_id` del solicitante sea dueño.
- Seguridad: exigir `EIKON_WEBAPP_SECRET` en prod, rate-limit básico en auth, validación de slugs/paths (ya existe `safe_relative_path`).

### 4.4 Frontend (React SPA)
- `frontend/` (Vite+React+TS): login/register, dashboard, **brand editor**, **wizard paso-a-paso** (marca → ejes → estilos → N), **batch progress** (SSE), **galería** (orden, filtros, selección múltiple, descarga ZIP). Cliente API + hook SSE. Build estático → `webapp` `StaticFiles` (same-origin).
- Design system propio mínimo (tokens accesibles), **contraste AA** en la UI, foco/teclado, estados de carga.

---

## 5. Plan por fases

Cada fase termina con: **bugfix**, **gate verde**, **crítica estructural** (qué mejorar en la siguiente) y **autocrítica de complejidad** (¿se está sumando carga innecesaria?).

### Fase 0 — Terreno limpio + gates duros + hardening del motor
- Borrar 3 venvs/caches/`.playwright-cli`; dedup templates (verificando aliases/taxonomy antes de borrar); consolidar `docs/legacy → docs/_archive`.
- `ruff` (estricto: E/W/F/I/C90/RUF/PERF), `mypy --strict`, `ruff format`/`black`, **coverage gate** (≥70% inicial, subir), `pre-commit`.
- CI real: quitar `|| true`, cablear `validate_pixels`/`validate_layout`/`ironman --fail-on-thresholds`/`validate_taxonomy --strict`.
- Refactor de **seams de testabilidad** del motor (DI paths, excepciones estructuradas, hash normalizado, quitar metaclass, resolver `--parallel`) **sin cambiar output**.
- Type hints completos en `eikon_core`/`scripts`/`webapp`. Migrar runner casero (~51 checks) a **pytest idiomático**.
- **Gate:** CI verde con todos los gates duros; baseline reproducible.

### Fase 1 — Backend product core (en paralelo donde sea seguro)
- Engine: brand-as-dict, combinatorial params, output tenant-scoped, `isotype.py`, `svg_generator.py`, wire `variations.py`.
- Motor combinatorio: ejes + planner + ranking + nuevos tokens de tamaño/espaciado + `config/typography.json`.
- DB migración (brands/variations/batches per-tenant) + CRUD de marcas.
- Worker SSE + storage interface (Local).
- API JSON completa (auth/brands/wizard/batches/gallery/downloads).
- **Tests sintéticos** de cada pieza (unit + integración con Playwright headless mínimo).

### Fase 2 — React SPA
- Wizard, batch+SSE, galería+selección+ZIP, auth; servido same-origin. Design system accesible AA.

### Fase 3 — Pruebas sintéticas → E2E → bugfix
- Suite sintética backend+combinatorial completa. **E2E Playwright** del flujo (register → crear marca → wizard → generar 50 → rankear → galería → descargar). Bugfix por hallazgo.

### Fase 4 — 3 ciclos de auditoría + autocrítica (cierre)
- **Ciclo 1 — Estructural:** arquitectura, acoplamiento, deuda, cohesión de módulos.
- **Ciclo 2 — Producto/UX:** ¿es **usable**? ¿tiene **sentido visual**? ¿cumple **contraste WCAG** (assets y UI)? ¿**suma o resta carga** cognitiva? ¿la combinatoria da variedad real o ruido?
- **Ciclo 3 — Fiabilidad:** cobertura, edge cases, **aislamiento multi-tenant**, seguridad JWT/paths, verificación **adversarial** de findings.
- Cada ciclo: hallazgos con severidad (critical/major/minor/note) + remediación verificable + re-verificación. Cierre sin críticos abiertos.

---

## 6. Orquestación por modelo y cuota (declarado)

Política calidad-primero, repartiendo carga por saldo en vivo (`get_ai_quotas`). **OpenCode (0% saldo) excluido → ruteo al siguiente más capaz, sin bajar calidad.**

| Fase / tipo de trabajo | Modelo(s) | Por qué |
|---|---|---|
| Limpieza mecánica, dedup, config lint, boilerplate | **MiniMax + Gemini** | volumen/paralelizable, barato |
| Seams críticos del motor, combinatoria, isotipo, E2E | **Codex (+ Opus verifica)** | lógica no trivial / lo más difícil |
| Lectura/resumen masivo, UI React, docs | **Gemini** | contexto largo |
| Type hints, CRUD/API, storage, tests de volumen | **MiniMax/Gemini** | codificación acotada |
| Auditoría adversarial, síntesis, decisiones, diseño/UX crítico | **Opus (+ Codex)** | no delegar lo crítico |

Ejecución vía **Workflow** (fan-out + verificación adversarial por hallazgo) declarando el plan modelo→fase antes de cada workflow.

---

## 7. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Refactor del motor rompe output actual | Fase 0 con golden tests de output (hash/manifest) antes de tocar seams; cambios sin alterar PNGs. |
| Explosión combinatoria (coste render) | Muestreo determinístico + ranking + límites por batch; dedup near-identical. |
| Aislamiento multi-tenant defectuoso | Tests de aislamiento por `tenant_id` en cada endpoint; paths tenant-scoped + `safe_relative_path`. |
| Subagentes alucinan código | Verificación adversarial separada del generador; gates duros + tests reales. |
| SSE/worker frágil bajo carga | `max_concurrent_jobs`, timeouts, estados de job atómicos; diseño listo para cola externa. |
| Isotipos SVG feos/ilegibles | Reglas geométricas + validación de contraste/legibilidad en el ranking. |

---

## 8. Definición de "fiable" (criterios de aceptación)

1. CI verde con gates **duros** (ruff + mypy strict + coverage + validadores reales, sin `|| true`).
2. Multi-tenant **aislado** (tests), JWT seguro, marcas **per-tenant** con CRUD.
3. Wizard genera **N variaciones reproducibles**, rankeadas, descargables (single + ZIP).
4. Galería ordenada, selección, descarga.
5. **E2E** pasa el flujo completo en Playwright.
6. **WCAG AA** en assets generados y en la UI.
7. **3 auditorías** cerradas sin críticos abiertos; reportes en `audit/reports/`.
8. El motor sigue generando **todo** lo que generaba (no regresión).

---

## 9. Fuera de alcance (YAGNI por ahora)
- GCS real (solo interfaz + stub), cola externa Redis, OAuth, facturación, multi-idioma de UI, generación por IA de imagen.
