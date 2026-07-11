# QA Checklist — Eikon

> Checklist mecánico y visual para validar una corrida de Eikón.
> Aplicar después de `python3 eikon.py --all` (o subset).

## 1. Verificación mecánica (rápida, sin navegador)

```bash
cd /workspace/Pinakotheke/eikon

# 1.1 — Compilación de los scripts (std lint)
python3 -m py_compile scripts/eikon_aggregate_wcag.py scripts/eikon_count.py \
                     eikon.py contrast_validator.py gallery.py \
                     tests/test_eikon_checks.py
# Esperado: sin output, exit 0.

# 1.2 — Tests unitarios del motor (no requiere Playwright)
python3 tests/test_eikon_checks.py
# Esperado: "167 ✓ / 0 ✗" (o más si se agregan tests; incluye sección 16
# para eikon_validate_pixels.py).

# 1.3 — Conteo + _STATUS.md
python3 scripts/eikon_count.py --stdout
# Esperado: tabla con N marcas (≥34), total PNGs = 1302 (si fue corrida completa).
#           Sin filas con `manifest = —` ni `Galería = no` tras regenerar galerías.

# 1.4 — Reporte WCAG agregado
python3 scripts/eikon_aggregate_wcag.py
# Esperado: exit 0, tabla en consola, output/_contraste-report.json actualizado.

# 1.5 — Validador pixel por marca y global (Pillow-only, sin Playwright)
python3 scripts/eikon_validate_pixels.py --marca pinakotheke-kosmos
python3 scripts/eikon_validate_pixels.py --all --fail-on-errors
# Esperado: exit 0 en una corrida sana. Errores típicos que SÍ reporta:
#   - archivo PNG faltante / vacío / corrupto
#   - dimensiones reales ≠ declaradas en _manifest.json
#   - variantes bit-idénticas dentro del mismo (category, type)
# Warnings (no fatales): baja densidad de foreground (assets muy planos).
# Excluye tipos listados en --allow-identical-types (e.g. favicon).
# Escribe output/<marca>/_pixel-report.json por marca.
```

### Criterios de aceptación numéricos

| Métrica | Esperado (corrida completa) | Cómo verificarlo |
|---|---|---|
| Marcas | 34 | `scripts/eikon_count.py --stdout` |
| PNGs totales | 1302 | `scripts/eikon_count.py --stdout` |
| Manifests (`_manifest.json`) | 34 | `find output -name _manifest.json \| wc -l` |
| Reportes WCAG por marca | 34 | `find output -name _contraste-report.json \| wc -l` |
| Reporte WCAG agregado | 1 | `test -f output/_contraste-report.json` |
| Galerías por marca | 34 | `ls output/_gallery_*.html \| grep -v aggregated \| wc -l` |
| Galería agregada | 1 | `test -f output/_gallery_aggregated.html` |
| `_STATUS.md` | existe | `test -f _STATUS.md` |

> Nota: 34 marcas = 22 Cloud Atlas (pinakotheke-*) + 9 Prizma (prizma-*) +
> 3 Steven Vallejo (steven-vallejo-*). Las genéricas (`pinakotheke`,
> `prizma`, `steven-vallejo`) y `prizma-hermes`, `prizma-logos` también
> cuentan como marcas válidas (son artefactos de fase).

## 2. Verificación visual (manual, con navegador)

Abrir `output/_gallery_aggregated.html` y revisar:

- [ ] **Layout no se rompe**: ningún asset se sale del viewport o muestra
      texto desbordado (`overflow: hidden` sospechoso).
- [ ] **Contraste AA visible**: textos principales sobre fondo se leen
      sin esfuerzo en los thumbnails (algunos están reducidos, revisar
      también el PNG a tamaño completo si hay duda).
- [ ] **Paleta correcta**: cada marca usa SUS colores (Kósmos no se ve
      como Prizma, etc.). Muestra de 2–3 marcas por familia.
- [ ] **Wordmark / isotipo legibles**: variantes `v1_color`, `v2_mono`,
      `v3_inverse` se distinguen (no son idénticas con color cambiado).
- [ ] **Sin labels internos**: ningún asset lleva textos tipo "LOGO 01",
      "+LINKEDIN", "PRICING", "MOCKUP". Regla dura del brief.
- [ ] **OG / banners con datos reales**: textos visibles (no placeholders
      genéricos).
- [ ] **Watermark / favicon / isotipo** son **excluidos** de WCAG (no
      cuentan como fail). Esto es por diseño — son decorativos.

### Muestreo mínimo sugerido

| Familia | Marcas a abrir | Categorías a chequear |
|---|---|---|
| Cloud Atlas | pinakotheke-kosmos, pinakotheke-techne | logos, banners, og |
| Prizma | prizma-hermes, prizma-iris, prizma-prisma | logos, cards, og |
| Steven Vallejo | steven-vallejo-filosofo | logos, stationery |

Si el 100% de estos pasa, el resto es razonablemente seguro.

## 3. Verificación WCAG específica

```bash
# Ver reporte consolidado
cat output/_contraste-report.json | python3 -m json.tool | less

# Buscar fallos REALES (no "no_foreground")
python3 -c "
import json
from pathlib import Path
base = Path('output')
real_fails = []
for d in sorted(base.iterdir()):
    if not d.is_dir() or d.name.startswith('_'): continue
    rep = d / '_contraste-report.json'
    if not rep.exists(): continue
    data = json.loads(rep.read_text())
    fails = data.get('failing_assets_aa', [])
    real = [f for f in fails if not f.get('no_foreground')]
    if real:
        real_fails.append((d.name, len(real), real[:3]))
print(f'Marcas con WCAG AA fail real: {len(real_fails)}')
for slug, n, sample in real_fails:
    print(f'  {slug}: {n} fails')
    for s in sample:
        print(f'    - {s.get(\"img\")}: ratio={s.get(\"contrast_ratio\")} issue={s.get(\"issue\")}')"
```

- [ ] Si hay **fails reales** (ratio < 4.5 con foreground detectable):
      revisar JSON de la marca (`marcas/<slug>.json`) y/o la plantilla
      correspondiente en `templates/`. Re-renderizar tras el fix.
- [ ] `no_foreground` NO es fail — es señal de que el validador no
      encontró texto suficiente en el centro/cuadrantes. Suele pasar
      con assets muy decorativos (logos minimalistas, watermarks).

## 4. Verificación de galerías

```bash
# Si falta alguna galería por marca:
python3 gallery.py <slug>            # individual
python3 gallery.py --all-marcas      # todas

# Regenerar agregada tras cambios:
python3 gallery.py --all-marcas --aggregated
```

- [ ] Todas las marcas tienen su `_gallery_<marca>.html`.
- [ ] `_gallery_aggregated.html` lista las 34 marcas.
- [ ] Thumbnail base64 se ve (no aparece el placeholder "sin Pillow").

---

## 5. Validadores de layout (en esta rama)

> **Estado al 2026-06-20:** **implementados parcialmente**.
> - DOM layout validator (overflow, off-viewport, required text vacío):
>   integrado en `eikon.py`, corre por asset **antes** del screenshot.
>   Flag `--fail-on-layout` propagado al CLI.
> - `scripts/eikon_validate_layout.py`: scanner agregado de manifests
>   con `--fail-on-errors`. **Sí commiteado.**
> - `scripts/eikon_validate_pixels.py`: validador pixel ligero (Pillow-only)
>   que detecta variantes bit-idénticas, archivos vacíos / corruptos y
>   dim_mismatch contra `_manifest.json`. **Sí commiteado (Fase 6).**
>   Cobertura actual: md5 por archivo (más estricto que el contrato
>   perceptual pHash; ambos convergen en los casos patológicos).
> - Safe-area (`SAFE_INSET_PX`) y pHash perceptual: **planeados.**

### 5.1 Qué cubren (implementado)

`eikon.py` ejecuta `LAYOUT_INSPECTION_JS` justo después de inyectar vars
y antes del screenshot, sobre estos selectores:

```text
h1,h2,h3,p,span,a,li,[data-required-text],
.headline,.subhead,.title,.claim,.tagline,.wordmark,.desc,.cta
```

Warnings emitidos (tipos y severidad en `eikon.py` `LAYOUT_WARNING_SEVERITY`):

| Tipo | Severidad | Significado |
|---|---|---|
| `empty_required_text` | **fail** | `[data-required-text]` quedó vacío tras la inyección → asset incompleto. |
| `off_viewport` | **fail** | el rect del elemento cae fuera de `{clientWidth, clientHeight}` → invisible. |
| `overflow_x` | warn | `scrollWidth > clientWidth` del elemento → desborde horizontal. |
| `overflow_y` | warn | `scrollHeight > clientHeight` del elemento → texto cortado vertical. |
| `inspection_error` | warn | el inspector JS falló (no pudimos verificar) → no rompe el render, solo loguea. |

Severidades se agregan en `aggregate_layout_status(warnings)`:
- `[]` → `"pass"`
- algún `"fail"` → `"fail"`
- algún `"warn"` sin fail → `"warn"`
- solo info → `"pass"`

### 5.2 Campos escritos en el manifest

Por asset en `output/<marca>/_manifest.json` (ya implementados):

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

### 5.3 Comandos (implementados)

```bash
cd /workspace/Pinakotheke/eikon

# Per-asset: corre dentro del render de eikon.py (siempre activo salvo --skip-contraste)
python3 eikon.py --all                           # imprime "Layout fails: N" al final
python3 eikon.py --all --fail-on-layout          # exit 1 si N > 0

# Por marca puntual (re-render con cache + check)
python3 eikon.py --marca pinakotheke-kosmos --resume --fail-on-layout

# Agregado (post-corrida): scanner de manifests
python3 scripts/eikon_validate_layout.py                       # tabla en consola
python3 scripts/eikon_validate_layout.py --json                # JSON a stdout
python3 scripts/eikon_validate_layout.py --only-issues         # sólo issues
python3 scripts/eikon_validate_layout.py --fail-on-errors       # exit 1 si hay issues
python3 scripts/eikon_validate_layout.py --output-dir output   # default

# Snapshot maestro (incluye columna Layout)
python3 scripts/eikon_count.py                  # regenera _STATUS.md
python3 scripts/eikon_count.py --stdout         # tabla + columna Layout
```

### 5.4 Criterios de aceptación (post-corrida, rama actual)

- [ ] Cada `_manifest.json` incluye `layout_status` y `layout_warnings`
      en **todos** sus assets (no solo en los del WCAG).
- [ ] `eikon.py --all` imprime `Layout fails: 0` (o se documentan las
      excepciones aceptadas en `output/<marca>/_manifest.json`).
- [ ] `python3 scripts/eikon_validate_layout.py` exit 0
      (sin issues de `layout_status != "pass"` ni `layout_warnings`).
- [ ] `python3 scripts/eikon_validate_layout.py --fail-on-errors` exit 0.
- [ ] `_STATUS.md` tiene la columna **Layout** con `✓` en las 34 marcas
      (regenerable vía `scripts/eikon_count.py`).
- [ ] `eikon.py --all --fail-on-layout` exit 0 cuando la corrida previa
      estuvo limpia.

### 5.5 Cuándo correrlos (gating)

| Momento | Comando | Por qué |
|---|---|---|
| **Antes de commitear** cambios en `templates/` o `marcas/` | `python3 eikon.py --marca <slug> --clean && python3 eikon.py --marca <slug> --fail-on-layout` | Atrapa regresiones de layout localmente, sin esperar al batch. |
| **Antes de regenerar galerías** | `python3 scripts/eikon_validate_layout.py --fail-on-errors` | Las galerías exhiben los assets rotos a todo el equipo. |
| **Antes de escalar / compartir** (CI, deploy Vercel del portal, share link) | `python3 eikon.py --all --fail-on-layout && python3 scripts/eikon_validate_layout.py --fail-on-errors` | Dos gates en serie: per-asset (durante render) → agregado (post). |
| **Después de un bump de tipografía** | `python3 eikon.py --only-marcas pinakotheke-kosmos,prizma-iris --fail-on-layout` | Las tipografías nuevas suelen cambiar métricas → overflow recurrente. |
| **Auditoría mensual** | `python3 scripts/eikon_validate_layout.py` y revisar tendencia | Detecta drift acumulado marca por marca. |

### 5.6 Validadores planeados (no commiteados)

Aún pendientes — no aparecen en `scripts/` ni en el motor:

| Validador planeado | Qué cubriría | Comando esperado |
|---|---|---|
| **Safe-area checker** | bounding box de nodos visibles intersecta `SAFE_INSET_PX[layout_id]` (default 24 px, 0 para full-bleed como `banner_ad`, `youtube_header`). | `python3 layout_safearea.py --all` o integrado en `eikon.py` |
| **Pixel congruence / variantes idénticas** | hash perceptual (dHash 8×8, Hamming > 8) o congruencia < 98% entre variantes declaradas del mismo `(categoría, tipo)`. | `python3 scripts/eikon_validate_pixels.py --all` (md5; casos patológicos) |
| **Resumen layout consolidado** | `output/_layout-summary.json` con totales por marca + por tipo de warning. | `python3 scripts/eikon_layout_summary.py` |

`_legacy/audit_render.py` ya implementa el chequeo DOM base (texto
mínimo, overflow, duplicación de copy) pero solo loguea a stdout — no
escribió manifest ni tuvo gate. Es la base conceptual de la Fase 5.

### 5.7 Troubleshooting de validadores

| Síntoma | Causa probable | Acción |
|---|---|---|
| `Chromium not found` al correr `eikon.py` | Playwright sin browser | `playwright install chromium` |
| `Layout fails: N` en consola pero `eikon_validate_layout.py` reporta 0 | validador post-corrida lee manifests viejos | re-renderizar la marca (`--clean`) o confiar en el resultado del render (más reciente). |
| `inspection_error` masivo | cambio en el DOM que rompe `LAYOUT_INSPECTION_JS` | revisar el selector o el cambio en `templates/`; el render no se rompe, solo se marca el warning. |
| `off_viewport` en un asset que se ve bien en galería | el asset se renderiza a otra escala (`deviceScaleFactor`) y los píxeles del inspector están en CSS px | comparar el PNG final; el validador mide el DOM CSS, no el bitmap. |
| `--fail-on-layout` no detiene el render | bug o regresión en `eikon.py main()` | confirmar que la corrida muestra `Layout fails: N` en stdout; si N>0 y exit code es 0, escalar al owner. |
| `_STATUS.md` sin columna Layout | `scripts/eikon_count.py` no encuentra `eikon_validate_layout.py` | verificar que `scripts/eikon_validate_layout.py` está commiteado |

## 5. Verificación de cache y re-run

```bash
# Forzar re-run completo de una marca (sin tocar otras):
python3 eikon.py --marca pinakotheke-kosmos --clean

# Re-run con cache (no debería tocar nada si nada cambió):
python3 eikon.py --marca pinakotheke-kosmos --resume
# Esperado en consola: muchos "↻" (cache hit) y pocos "✓" (generated).
```

- [ ] `--clean` + re-render produce el mismo `_manifest.json` (mismo
      `total_assets`, mismas dimensiones, mismo `engine_version`).
- [ ] `--resume` no regenera nada si la entrada no cambió.

## 6. Cuando aparece un problema

| Síntoma | Causa probable | Acción |
|---|---|---|
| `Chromium not found` | Playwright sin browser | `playwright install chromium` |
| `template not found` | nombre plantilla ≠ TypeSpec | revisar `templates/*.html` vs nombres en `_build_taxonomia` |
| `no foreground` masivo | paleta bg/fg muy parecida | revisar JSON marca → paleta |
| Fail real de contraste | texto sobre fondo de luminancia similar | oscurecer `--texto` o aclarar `--bg` en JSON marca |
| `_STATUS.md` desactualizado | olvidaste correr `eikon_count.py` | correrlo, regenera |
| `_contraste-report.json` global desfasado | olvidaste correr `eikon_aggregate_wcag.py` | correrlo (es idempotente) |
| Galería sin thumbnails | Pillow no instalado o PNG corrupto | `pip install Pillow`, revisar PNG |

## 7. Pre-commit (mental, no-hook)

Antes de commitear cambios en motor/plantillas/marcas:

1. Correr `python3 tests/test_eikon_checks.py` → debe pasar.
2. Si tocaste `templates/`, re-renderizar la marca afectada con
   `python3 eikon.py --marca <slug> --clean` y validar visualmente.
3. Si tocaste `marcas/<slug>.json`, lo mismo.
4. Si tocaste `eikon.py` o `contrast_validator.py`, correr suite
   completa y al menos 1 marca end-to-end.

## 8. Known Issues / Decisiones de calidad (2026-06-20)

### Bugs FIXED

| Bug | Síntoma | Fix aplicado | Verificacion |
|-----|---------|--------------|---------------|
| **ad_leaderboard v2→v3** | promo y cta_driven eran pixel-idénticas en 16 marcas (hash md5 igual) | rediseño: v3 ahora diferenciada en layout y luminancia | validador pixel (`eikon_validate_pixels.py`) detecta Hamming distance > 0 entre variantes |
| **lockup_horizontal v3_inverse** | no invertía (fondo oscuro, WCAG AA fail en kosmos 1.16) | fondo claro real implementado; contraste re-validado | WCAG ratio ≥ 4.5 post-fix en todas las marcas |
| **stat_card v2_comparativa (prizma)** | contraste bajo bajo observación de galería | subida a WCAG AA ≥ 4.5 via ajuste de `--texto` en JSON marca | `_contraste-report.json` per-marca reporta pass AA |

### Mejoras de QA

| Mejora | Cambio | Impacto | Herramienta |
|--------|--------|--------|-------------|
| **gallery.py thumbnails** | landscape/legibles (resolución correcta, no aplastadas) | la percepción de "baja resolución" era CSS galería reduciendo panorámicas a 200×25px, NO los PNG fuente (todos en resolución correcta) | visual en `_gallery_aggregated.html` |
| **Variantes near-dup diferenciadas** | youtube/linkedin/letterhead reforzadas en luminancia, no solo color | reducen falsos positivos de pixel-congruencia; mejora percepción visual en galerias | validador pixel detecta diferencias sutiles |
| **eikon_quality_metrics.py thresholds afinados** | THIN_BYTES excluye vectoriales; DUP_VARIANT hamming ≤ 3; LOW_CONTRAST ignora fg < 0.05 | menos ruido, más precisión en reportes | scanner agregado (`eikon_validate_pixels.py --all`) |

### Decisiones de arquitectura

| Decisión | Criterio | Documentacion |
|----------|----------|-----------------|
| **Leer solo CSS confunde "variables iguales" con "render igual"** | verificar con dhash perceptual + visual (galería); nunca asumir igualdad sin bitmap | validador pixel: md5 por archivo (estricto); planeado: pHash Hamming para casos edge |
| **Excluir decorativos de WCAG (watermark/favicon/isotipo)** | por diseño no llevan texto; reportados con `layout_status="skipped"` en manifest | no cuentan hacia `aa_fail` ni `aaa_fail` en reportes consolidados |
| **Safe-area y pixel congruence planeados, no commiteados** | fase 7 (próximas iteraciones) | visibles en § 5.6 de INSTRUCCIONES-EIKON.md |

---

## 9. Pendientes conocidos / no-bloqueantes

- Watermark / favicon / isotipo: excluidos del check WCAG (decorativos).
- `no_foreground` warnings: no son fallos, son ASSETS sin texto detectable.
- `agora-*`: ignorados por `--all` por diseño (no son parte de Eikón).
- Galerías `_gallery_aggregated.html` pesadas (~5–10 MB con thumbnails base64):
  aceptable para uso local; no versionar.

## 10. Auditorías manuales

Las plantillas y reportes de auditoría viven en `audit/`:

- Plantilla base: `audit/TEMPLATE-phase.md`.
- Metodología: `audit/METHODOLOGY.md`.
- Reportes instanciados: `audit/reports/`.

El reporte final MVP actual es `audit/reports/2026-06-29-final-mvp.md`.
