# INSTRUCCIONES — Eikón (motor vigente)

> Guía operativa actual. Reemplaza `INSTRUCCIONES-GENERADOR-V2.md` (LEGACY).
> Última actualización: 2026-06-20.

## TL;DR

```bash
cd /workspace/Pinakotheke/eikon

# Piloto
python3 eikon.py --marca pinakotheke-kosmos

# Batch completo (todas las marcas no-agora)
python3 eikon.py --all

# Galerías
python3 gallery.py --all-marcas
python3 gallery.py --all-marcas --aggregated

# Snapshot maestro
python3 scripts/eikon_count.py --stdout

# WCAG agregado
python3 scripts/eikon_aggregate_wcag.py

# Tests
python3 tests/test_eikon_checks.py
```

## 1. Preparación

### Dependencias

```bash
pip install -r requirements.txt
playwright install chromium
```

`requirements.txt` declara `playwright`, `Pillow`, `numpy`. Los scripts
`scripts/eikon_aggregate_wcag.py` y `scripts/eikon_count.py` son stdlib
puro y no requieren nada extra.

### Estructura esperada

```
eikon/
├── marcas/<slug>.json          # 38 marcas (4 agora-* + 34 no-agora)
├── templates/<plantilla>.html  # ~20 plantillas
├── eikon.py                    # motor canónico
├── contrast_validator.py
├── gallery.py
├── scripts/
│   ├── eikon_aggregate_wcag.py
│   └── eikon_count.py
├── tests/
│   └── test_eikon_checks.py
└── output/                     # git-ignored
```

## 2. Renderizado

### 2.1 Una marca

```bash
python3 eikon.py --marca pinakotheke-kosmos
```

Resultado:
- `output/pinakotheke-kosmos/<categoría>/<tipo>/<variante>.png` (45 assets).
- `output/pinakotheke-kosmos/_manifest.json` con metadata.
- `output/pinakotheke-kosmos/_contraste-report.json` con WCAG AA/AAA.
- `output/pinakotheke-kosmos/.cache.json` con cache (no versionado).

### 2.2 Solo una categoría

```bash
python3 eikon.py --marca prizma-iris --solo logos
```

Filtra la taxonomía a la categoría indicada (logos, cards, og,
stationery, banners).

### 2.3 Batch completo

```bash
python3 eikon.py --all
```

Procesa TODAS las marcas en `marcas/*.json` excepto `agora-*`. Duración
estimada: 10–15 min para 34 marcas con Playwright + Chromium en entorno
local.

### 2.4 Subset explícito

```bash
python3 eikon.py --only-marcas pinakotheke-kosmos,prizma-iris,prizma-prisma
```

Alternativa a `--all` cuando querés un subset cerrado.

### 2.5 Dry-run

```bash
python3 eikon.py --all --dry-run
```

Enumera la matriz completa sin renderizar ni escribir PNGs. Útil para
validar el alcance antes de una corrida pesada.

### 2.6 Incremental con cache

```bash
python3 eikon.py --marca pinakotheke-kosmos --resume
```

Si nada cambió en marca/template/vars, reusa el PNG del disco. La
primera corrida con `--resume` se comporta como una corrida normal
(genera cache); la segunda es esencialmente gratis.

### 2.7 Limpiar antes de renderizar

```bash
python3 eikon.py --marca pinakotheke-kosmos --clean
```

Borra `output/pinakotheke-kosmos/` antes de empezar. **Opt-in**: no se
borra nada implícitamente. Útil cuando cambian plantillas o paleta.

### 2.8 Sin validación WCAG

```bash
python3 eikon.py --marca pinakotheke-kosmos --skip-contraste
```

Útil para debugging rápido cuando querés revisar los PNGs sin esperar
el validador (que puede tardar 1–2 min sobre 45 assets).

## 3. Validación WCAG

### 3.1 Standalone (post-corrida)

```bash
# Una marca
python3 contrast_validator.py --marca pinakotheke-kosmos

# Global (todas las marcas)
python3 contrast_validator.py
```

Escribe el reporte en `output/<marca>/_contraste-report.json` (per-marca)
o `output/_contraste-report.json` (global legacy).

### 3.2 Consolidador agregado

```bash
python3 scripts/eikon_aggregate_wcag.py
```

Lee los reportes por marca y reescribe `output/_contraste-report.json`
agregado. **Idempotente**: correlo cada vez que cambien reportes per-marca.

Salida ejemplo (stdout):
```
✓ Reporte agregado: /workspace/Pinakotheke/eikon/output/_contraste-report.json
  Marcas: 34  ·  Assets: 1030  ·  AA pass: 930/1030  ·  AAA pass: 791/1030

marca                              assets  AA pass  AA fail  no_fg  AAA pass  AAA fail
----------------------------------  ------  -------  -------  -----  --------  --------
pinakotheke-kosmos                 37      37       0        0      32        5
...
TOTAL                              1030    930      100      87     791       239
```

### 3.3 Interpretación

- `contrast_ratio >= 4.5`: WCAG AA OK.
- `contrast_ratio >= 7.0`: WCAG AA + AAA OK.
- `no_foreground: true`: el validador no detectó texto suficiente
  en el muestreo. **No es fail** — es señal de asset minimalista.

Si un asset reporta `aa_fail` real (ratio < 4.5 con foreground
detectable), revisar:

1. Paleta en `marcas/<slug>.json` → `paleta.texto` vs `paleta.bg`.
2. Variantes: `mono`, `inverse`, `light`, `dark` aplican overrides en
   `map_marca_to_vars()` (ver `eikon.py` §variant-aware overrides).
3. Plantilla en `templates/<plantilla>.html` → vars CSS `--texto`, `--bg`.

## 4. Galerías

### 4.1 Por marca

```bash
python3 gallery.py pinakotheke-kosmos
# o todas:
python3 gallery.py --all-marcas
```

Genera `output/_gallery_<slug>.html` con thumbnails base64 inline.

### 4.2 Agregada

```bash
python3 gallery.py --all-marcas --aggregated
```

Genera `output/_gallery_aggregated.html` con las 34 marcas en una sola
página. Útil para revisión visual completa.

## 5. Snapshot maestro (`_STATUS.md`)

```bash
python3 scripts/eikon_count.py            # escribe _STATUS.md
python3 scripts/eikon_count.py --stdout   # también tabla en consola
```

`_STATUS.md` contiene:
- Resumen global (marcas, PNGs, AA/AAA pass/fail).
- Tabla por marca con PNG, manifest, WCAG, galería.
- Comando de regeneración.

## 6. Tests

```bash
python3 tests/test_eikon_checks.py
```

55 checks en 11 secciones: templates, WCAG luminance, foreground
detection, hash de cache, manifest, dry-run, contraste configurable,
text limits, per-brand report, post-validación.

**No requiere Playwright** — se puede correr en cualquier entorno para
validar el motor matemático.

## 7. Troubleshooting

| Síntoma | Causa | Acción |
|---|---|---|
| `ModuleNotFoundError: playwright` | Playwright no instalado | `pip install playwright && playwright install chromium` |
| `template not found for 'X'` | nombre plantilla ≠ TypeSpec | revisar `templates/*.html` vs nombres en `_build_taxonomia()` |
| `no foreground` masivo | paleta bg/fg muy similar | revisar JSON marca |
| Fail real de contraste | ratio < 4.5 con texto detectable | ajustar paleta en JSON marca |
| Galería sin thumbnails | Pillow no instalado | `pip install Pillow` |
| `_contraste-report.json` global desfasado | olvidaste `eikon_aggregate_wcag.py` | correrlo |
| `_STATUS.md` desactualizado | olvidaste `eikon_count.py` | correrlo |

## 8. Convenciones

- **NO commitear** nada de `output/` (ver [`docs/OUTPUT-NO-VERSIONADOS.md`](docs/OUTPUT-NO-VERSIONADOS.md)).
- **NO deployar** sin OK explícito — esto es local.
- Commits pequeños, mensajes en español, identificadores en inglés.
- Cualquier cambio en `templates/` o `marcas/*.json` debe ir acompañado
  de re-render + revisión visual.

## 9. Próximos pasos sugeridos (futuro)

- Implementar `--parallel > 1` con隔离 de contextos Playwright.
- Forzar WCAG AA como gate en CI (que `--resume` solo skip si AA sigue OK).
- Reporte AAA enforced (no solo reportado).
- Auto-fix de paleta cuando `aa_fail` real se detecta.

---

## 10. Validadores de layout (en esta rama)

> **Estado al 2026-06-20:** **implementados parcialmente**.
> - Per-asset DOM validator (`eikon.py`, `LAYOUT_INSPECTION_JS`): **sí**.
>   Corre antes del screenshot, escribe `layout_status` y `layout_warnings`
>   en `_manifest.json`. Flag `--fail-on-layout` propagado al CLI.
> - Scanner agregado (`scripts/eikon_validate_layout.py`): **sí**.
>   CLI con `--json`, `--fail-on-errors`, `--only-issues`.
> - Snapshot maestro: `scripts/eikon_count.py` ahora lee el validator
>   y agrega la columna **Layout** en `_STATUS.md`.
> - Safe-area y variantes-idénticas (pixel): **planeados**, no commiteados.

### 10.1 Por qué hacen falta

WCAG AA mide **contraste**, no **layout**. Defectos típicos que
escapaban y aparecían recién al abrir la galería:

1. **Texto cortado** — `overflow: hidden` del padre clippea el wordmark
   o un subtítulo.
2. **Off-viewport** — un elemento `[data-required-text]` se posicionó
   fuera del rect visible.
3. **Required text vacío** — la inyección de vars falló y el campo
   obligatorio quedó en blanco.
4. **Safe-area** *(planeado)* — un isotipo o un dato pisa el borde.
5. **Variantes idénticas** *(planeado)* — `v1_color` y `v2_mono`
   son bit-identical.

### 10.2 Lo que el validador cubre hoy

`eikon.py` ejecuta `LAYOUT_INSPECTION_JS` después de la inyección y
antes del screenshot. Selectores:

```text
h1,h2,h3,p,span,a,li,[data-required-text],
.headline,.subhead,.title,.claim,.tagline,.wordmark,.desc,.cta
```

Tipos de warning y severidad (`LAYOUT_WARNING_SEVERITY` en `eikon.py`):

| Tipo | Severidad | Significado |
|---|---|---|
| `empty_required_text` | **fail** | `[data-required-text]` quedó vacío → asset incompleto. |
| `off_viewport` | **fail** | el rect del elemento cae fuera del viewport CSS → invisible. |
| `overflow_x` | warn | `scrollWidth > clientWidth` → desborde horizontal. |
| `overflow_y` | warn | `scrollHeight > clientHeight` → texto cortado vertical. |
| `inspection_error` | warn | el inspector JS falló (no rompe el render). |

`aggregate_layout_status()`:

- 0 warnings → `"pass"`
- algún `"fail"` → `"fail"`
- algún `"warn"` sin fail → `"warn"`
- solo info → `"pass"`

El inspector **nunca rompe el render**: si falla, se registra
`inspection_error` con el detalle y la corrida sigue. El screenshot y
la entrega del asset son independientes de la severidad del layout.

### 10.3 Comandos

```bash
cd /workspace/Pinakotheke/eikon

# 1) Per-asset — integrado al render --------------------------------
python3 eikon.py --all                          # imprime "Layout fails: N" al final
python3 eikon.py --all --fail-on-layout         # exit 1 si N > 0
python3 eikon.py --marca pinakotheke-kosmos --resume --fail-on-layout

# 2) Agregado — scanner de manifests --------------------------------
python3 scripts/eikon_validate_layout.py                    # tabla en consola
python3 scripts/eikon_validate_layout.py --json             # JSON a stdout
python3 scripts/eikon_validate_layout.py --only-issues      # sólo issues
python3 scripts/eikon_validate_layout.py --fail-on-errors    # exit 1 si hay issues
python3 scripts/eikon_validate_layout.py --output-dir output

# 3) Snapshot maestro (incluye columna Layout) --------------------
python3 scripts/eikon_count.py
python3 scripts/eikon_count.py --stdout
```

### 10.4 Campos en `_manifest.json`

Por asset (ya implementados):

```json
{
  "path": "logos/lockup_horizontal/v1_color.png",
  "category": "logos",
  "type": "lockup_horizontal",
  "variant": "v1_color",
  "status": "generated",
  "warnings": [],
  "layout_status": "pass",          // skipped | pass | warn | fail
  "layout_warnings": []             // [{type, selector, detail, ...}]
}
```

`status` (entrega) y `layout_status` (calidad de layout) son
**ortogonales**: un asset puede estar `generated` con `layout_status:
"warn"`. La severidad del layout no reescribe la entrega.

### 10.5 Criterios formales (implementados)

```text
empty_required_text  → fail    # textContent.trim() == "" en [data-required-text]
off_viewport         → fail    # rect.right  < 0  o  rect.bottom < 0
                                 # o rect.left  > viewport.w
                                 # o rect.top   > viewport.h
overflow_x           → warn    # el.scrollWidth  > el.clientWidth  + 1px
overflow_y           → warn    # el.scrollHeight > el.clientHeight + 1px
inspection_error     → warn    # excepción atrapada en page.evaluate
```

### 10.6 Cuándo correrlos (gating)

Regla: **dos gates en serie** antes de cualquier share, deploy del
portal o promoción a galería pública. (El tercer gate — pixel
congruencia — está planeado, ver §10.7.)

| Gate | Comando | Falla si |
|---|---|---|
| **G1 — per-asset** | `python3 eikon.py --all --fail-on-layout` | algún asset tiene `layout_status == "fail"` |
| **G2 — agregado** | `python3 scripts/eikon_validate_layout.py --fail-on-errors` | el scan reporta assets o marcas con `layout_status != "pass"` o `layout_warnings` no vacío |

Si ambos pasan, el batch es presentable. Para desarrollo local de una
sola marca alcanza con G1 sobre esa marca:

```bash
python3 eikon.py --marca pinakotheke-kosmos --clean
python3 eikon.py --marca pinakotheke-kosmos --fail-on-layout
```

### 10.7 Planeado para próximas iteraciones (no commiteado)

| Validador | Criterio | Comando esperado |
|---|---|---|
| **Safe-area checker** | bounding box intersecta `SAFE_INSET_PX[layout_id]` (default 24 px, 0 para full-bleed como `banner_ad`, `youtube_header`). | integrado en `eikon.py` o `python3 layout_safearea.py --all` |
| **Pixel congruence / variantes idénticas** | para cada `(categoría, tipo)`, las variantes declaradas (`v1_color`, `v2_mono`, `v3_inverse`, …) deben diferir perceptiblemente: `dHash(8×8)` Hamming distance > 8 OR pixel congruence < 98%. | `python3 scripts/eikon_pixel_check.py --all --threshold 0.98` |
| **Resumen layout consolidado** | `output/_layout-summary.json` con totales por marca y por tipo de warning, complementario al scanner. | `python3 scripts/eikon_layout_summary.py` |

`_legacy/audit_render.py` ya implementa chequeo DOM base (texto mínimo,
overflow, duplicación de copy) pero solo loguea a stdout — es la base
conceptual sobre la que se construyó el validador actual.

### 10.8 Exclusiones conocidas

Los assets decorativos quedan fuera del chequeador de layout **y** del
WCAG — son piezas que por diseño no llevan texto:

- `logo_watermark`, `favicon_512`, `favicon_192`, `favicon_180`,
  `favicon_32`, `app_icon_1024`, `logo_symbol_color`, `logo_symbol_mono`.

El validador los reporta con `layout_status = "skipped"` en el manifest,
lo cual los deja **fuera del cómputo de `layout_fails`**.

### 10.9 Known Issues / Decisiones de calidad (2026-06-20)

#### Bugs FIXED

1. **ad_leaderboard v2→v3 pixel-idénticas** (16 marcas)
   - Síntoma: promo y cta_driven tenían hash md5 idéntico.
   - Fix: rediseño v3 con layout y luminancia diferenciada.
   - Verificación: `eikon_validate_pixels.py` detecta Hamming distance > 0.

2. **lockup_horizontal v3_inverse no invertía**
   - Síntoma: fondo oscuro → WCAG AA fail en kosmos (ratio 1.16).
   - Fix: fondo claro real; re-validado contra specs de contraste.
   - Verificación: `_contraste-report.json` post-fix ≥ 4.5 en todas marcas.

3. **stat_card v2_comparativa (prizma) bajo contraste**
   - Síntoma: relación observada en galería, ratio < 4.5.
   - Fix: ajuste `--texto` en JSON marca → WCAG AA pass.
   - Verificación: per-marca `_contraste-report.json` reporta AA pass.

#### Mejoras de QA

1. **gallery.py thumbnails landscape/legibles**
   - La percepción de "baja resolución" era CSS galería aplastando panorámicas a 200×25px.
   - Los PNG fuente están todos a resolución correcta.
   - Verificación: visual en `_gallery_aggregated.html`.

2. **Variantes near-dup diferenciadas en luminancia**
   - youtube/linkedin/letterhead reforzadas (no solo color).
   - Reducen falsos positivos en validador pixel.
   - Mejora percepción visual en galerías.

3. **eikon_quality_metrics.py thresholds afinados**
   - THIN_BYTES: excluye vectoriales.
   - DUP_VARIANT: hamming ≤ 3.
   - LOW_CONTRAST: ignora fg < 0.05 (decorativos).
   - Menos ruido, más precisión en reportes agregados.

#### Lecciones de auditoría

- **Leer solo CSS confunde "variables iguales" con "render igual."**
  Siempre verificar con dhash perceptual + visual (galería).
  No asumir igualdad sin bitmap: el validador pixel (md5 por archivo, planeado pHash)
  es la fuente de verdad.

### 10.10 Pendiente concreto de esta rama

- [ ] Implementar safe-area checker y sumarlo a `LAYOUT_INSPECTION_JS`
      (o como script aparte).
- [ ] Commitar `scripts/eikon_pixel_check.py` con `--threshold` y
      default 0.98.
- [ ] Agregar tests en `tests/test_eikon_checks.py` que cubran las tres
      clases nuevas con un caso sintético por clase.
- [ ] Cubrir el inspector en `test_eikon_checks.py` (verificar
      `aggregate_layout_status` con vectores sintéticos).
- [ ] Actualizar `CHANGELOG.md` a v1.3 al cerrar la rama con safe-area
      y pixel-check.