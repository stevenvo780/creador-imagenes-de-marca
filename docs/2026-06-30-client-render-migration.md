# Migración del render al navegador (cliente) — Diseño

> Objetivo: quitar el render HTML→PNG con Chromium **server-side** (el único gran
> consumo de CPU en GCP) y moverlo al **navegador del usuario**. El servidor queda
> liviano: planifica, genera el SVG del isotipo, persiste y sirve. Costo GCP ≈ solo
> almacenamiento + tráfico.
>
> Basado en el blueprint `eikon-client-render-blueprint` (8 mapas + auditoría).

## 1. Qué se mueve y qué se queda

**Al navegador (lo caro):**
- Rasterizar HTML→PNG (hoy `eikon_core/render.py` `page.screenshot` con Playwright).
- Aplicar las variables (CSS custom props + `data-*`) a la plantilla.
- Esperar fuentes (`document.fonts.ready`) y capturar.

**Se queda en el servidor (liviano, ya existe):**
- `plan_combinations()` (cartesiano determinista, ~ms).
- **Generación del SVG del isotipo en Python** (`isotype.py`) → se entrega como **data-URI precalculado** en el plan. NO se porta a JS (riesgo de determinismo del `seeded_random` SHA/MD5).
- Ranking/WCAG/dHash **post-upload** sobre el PNG recibido (`ranking.py`).
- Persistencia DB + `StorageBackend` (GCS/local), auth multi-tenant, galería, ZIP.

## 2. Decisión de tecnología de rasterizado

**`modern-screenshot`** (o `html-to-image`), MIT, open-source. Serializa el DOM a un
`<svg><foreignObject>` y lo dibuja en `<canvas>` usando **el propio motor del
navegador** → fidelidad CSS alta (mejor que html2canvas que reimplementa CSS), con
embebido de fuentes y opción `pixelRatio`. Evitamos html2canvas-pro (comercial).

- `device_scale_factor` → se fuerza vía `pixelRatio: spec.device_scale_factor` (2 o 3
  según categoría), NO `window.devicePixelRatio` (que varía por monitor/zoom).
- El isotipo se inyecta como `<img src="data:image/svg+xml;base64,…">` (NO `innerHTML`,
  por XSS).

## 3. Determinismo — postura

Pixel-perfect entre navegadores es **imposible** (anti-aliasing/GPU). **No es un
requisito del producto**: cada usuario genera SUS assets en SU navegador; no hay
comparación cruzada. El dHash de dedup corre **server-side sobre el PNG subido**, así
que la dedup/variety se mantiene. El golden-pixel guard de dev deja de aplicar al path
cliente (se documenta).

## 4. Fuentes

Servir los woff2 de `templates/fonts/` desde `/static/fonts/` (mismo origen). El cliente
precarga con **FontFace API** (`await Promise.all(fonts.map(f=>f.load()))`) antes de
rasterizar; `modern-screenshot` los embebe. Timeout 3s → si falla, procede con fallback
(se registra warning).

## 5. Endpoints (contratos)

**NUEVO** `GET /api/v1/batches/{batch_id}/plan` → render-spec:
```json
{
  "batch_id": 1, "asset_type": "isotipo", "category": "logos",
  "template_name": "isotipo", "viewport": {"w": 800, "h": 800},
  "device_scale_factor": 3,
  "combinations": [
    { "idx": 0, "params": {"isotype_style":"orbital","layout":"symbol_only", …},
      "vars": {"primario":"#…","acento":"#…","texto":"#…","bg":"#…","font_titulo":"…", …},
      "data_attrs": {"data-isotype-style":"orbital","data-layout":"symbol_only", …},
      "isotype_data_uri": "data:image/svg+xml;base64,…",   // server pre-generado
      "texts": {"titulo":"…","subtitulo":"…","etiqueta":"…","numero":"…"} }
  ]
}
```
Reusa `plan_combinations` + `map_marca_to_vars` + `_build_isotype_data_uri` (ya existen
server-side; solo se exponen en vez de renderizar).

**NUEVO** `POST /api/v1/batches/{batch_id}/variations/upload` (multipart):
- body: `{ combo_idx:int, asset_type:str, params:json, image: File(png), layout_warnings?:json }`
- server: valida JWT `tenant_id`; **reconstruye** `output_path =
  tenants/{tenant_id}/{marca}/{category}/{asset_type}/{batch_id}/combo_{idx:03d}.png`
  (NUNCA confía en el cliente); valida magic-bytes PNG; `storage.save()`; INSERT
  variation; idempotente `UNIQUE(batch_id, combo_idx)` (2da vez → 200).
- al recibir todas (`counts.received == expected`) → rankea server-side y marca
  `completed`.

**NUEVO** `GET /api/v1/templates/{name}` → sirve el HTML de la plantilla (mismo origen,
`text/html`), lista blanca de nombres (anti path-traversal). Alternativa: el SPA importa
las plantillas como assets en build.

**Estáticos:** `/static/fonts/*.woff2`.

**Sin cambios:** galería, descargas, wizard/axes/brands/asset-types, auth.

## 6. Módulo de render en el cliente (`frontend/src/render/`)

`renderBatchClientSide(batchId, onProgress)`:
1. `GET …/plan`.
2. Precargar fuentes (FontFace) + fetch plantilla HTML una vez.
3. Por combinación (pool de ~3 web-workers/offscreen para no congelar la UI):
   - montar la plantilla en un `<div>` oculto (tamaño viewport), aplicar `vars` (CSS
     custom props en `:root` del contenedor) + `data_attrs` + `img` del isotipo + textos.
   - `await document.fonts.ready` + doble `rAF`.
   - `domToPng(node, { pixelRatio: device_scale_factor, width, height })`.
   - `POST …/variations/upload` (blob).
   - `onProgress(i+1, total)`.
4. Al terminar, navegar a la galería (que ya sirve los PNG subidos).

`StepBatchProgress` pasa a **progreso local inmediato** (sin polling de 2s).

## 7. Seguridad del demo en vivo (clave)

- **Feature flag** `EIKON_CLIENT_RENDER` (env + flag por request). Con flag OFF, el worker
  server-side actual sigue funcionando → **el demo de hoy no se toca**.
- Migración **aditiva**: nuevos endpoints + módulo cliente conviven con el path viejo.
- Se activa cliente por defecto sólo tras validar el loop completo en local.

## 8. Plan por fases

- **F1 (MVP slice):** isotipo, 1 marca, 4 combos. Endpoints `/plan` + `/upload` +
  `/static/fonts`. Módulo cliente mínimo. Sin ranking (score placeholder). Validar loop
  end-to-end en LOCAL (cliente renderiza → sube → galería muestra). dHash/WCAG luego.
- **F2:** todos los asset_types (banners/cards/og/stationery), fuentes completas,
  ranking server-side post-upload, dedup variety.
- **F3:** pool de workers + progreso, reintentos/checkpoint localStorage, timeout de
  batch (30 min → failed), idempotencia.
- **F4:** flag a default-cliente; el worker server-side queda como fallback opcional;
  bajar recursos de Cloud Run al mínimo (servir-solo) de forma permanente.

## 9. Riesgos (del audit) y mitigaciones
- Fidelidad CSS (mix-blend/backdrop-filter): foreignObject usa el motor del navegador →
  alto; los casos no soportados se simplifican o se pre-rasterizan como textura.
- Atomicidad de subida: idempotencia + timeout server 30 min + checkpoint localStorage.
- Aislamiento multi-tenant: server reconstruye `output_path`; nunca del cliente.
- XSS: isotipo por `<img src=data:…>`, params validados por schema server-side, CSP.
