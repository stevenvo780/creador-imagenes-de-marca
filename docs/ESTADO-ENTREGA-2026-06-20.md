# Estado de Entrega — Eikón tras corrida general

**Fecha:** 2026-06-20
**Status:** ✓ FASE OPERATIVA COMPLETA
**Motor:** `eikon.py` (canónico, reemplaza `generar_agencia_v2.py`)

---

## Estado operativo real

| Métrica | Valor |
|---|---|
| Marcas no-agora generadas | **34** |
| PNGs totales (recursivo) | **1302** |
| `_manifest.json` por marca | **34/34** |
| `_contraste-report.json` por marca | **34/34** |
| Reporte WCAG global agregado | sí (`output/_contraste-report.json`) |
| Galerías individuales | **34/34** |
| Galería agregada | sí (`output/_gallery_aggregated.html`) |
| `_STATUS.md` maestro | sí (regenerable vía `scripts/eikon_count.py`) |
| Tests unitarios | **55/55 PASS** (`tests/test_eikon_checks.py`) |
| Piloto Kosmos | APROBADO (45 assets, 100% AA pass, 86% AAA pass) |

### Desglose por familia

| Familia | Marcas | Assets/marca (aprox) | Categorías |
|---|---|---|---|
| Cloud Atlas (pinakotheke-*) | 17 | 45 | logos, cards, og, stationery, banners |
| Prizma (prizma-*) | 9 | 26 | logos, cards, og, stationery |
| Steven Vallejo | 3 | 45 | logos, cards, og, stationery, banners |
| Genéricos (pinakotheke, prizma, steven-vallejo) | 3 | 26–45 | reducido |
| `prizma-hermes`, `prizma-logos` | 2 | 26 | reducido |

> Las marcas "genéricas" y `prizma-hermes`/`prizma-logos` heredan parte
> de la taxonomía reducida (sin banners en algunos casos). El conteo
> exacto por marca está en `_STATUS.md`.

## Motor actual: `eikon.py`

`eikon.py` es el entry point canónico. Reemplaza:

- `generar_agencia.py` (v0, descartado).
- `generar_agencia_v2.py` (v1.0 previo, conservado en `_legacy/`).
- `render.py` y otros scripts históricos en `_legacy/`.

### Capacidades del motor

- Render Playwright Hi-Res con `deviceScaleFactor` dinámico (3× logos/print, 2× social/web).
- Cache por hash estable: `--resume` salta assets sin cambios estructurales.
- Post-validación: re-marca como `generated` assets cuyo PNG existe pero
  el render reportó error espurio (race condition de `Page.captureScreenshot`).
- Detección de foreground multi-región (centro → 4 cuadrantes → full)
  en `contrast_validator.py` para reducir falsos "no foreground".
- Text limits portados desde `_legacy/render.py` (Fase 2).
- `_manifest.json` por marca con metadata de cada asset (path, dimensiones, hash, status, warnings).

### Flags disponibles

| Flag | Uso |
|---|---|
| `--marca <slug>` | Una sola marca. |
| `--all` | Todas las marcas excepto `agora-*`. |
| `--only-marcas <s1,s2,...>` | Subset por coma. |
| `--solo <categoria>` | Filtra una categoría. |
| `--clean` | Borra `output/<marca>/` antes de renderizar (opt-in). |
| `--dry-run` | Enumera sin escribir PNGs. |
| `--resume` | Cache: saltar assets no modificados. |
| `--skip-contraste` | Omite validación WCAG. |
| `--parallel <N>` | Workers paralelos (limitado a 1). |

## Validación WCAG AA

- **Algoritmo:** luminancia BT.709 (sRGB → linear → relative luminance).
- **Threshold AA:** ratio ≥ 4.5:1 (texto normal).
- **Threshold AAA:** ratio ≥ 7.0:1 (texto grande).
- **Excluidos:** watermark, favicon, isotipo, `logo_symbol` (decorativos).
- **Reporte global:** `output/_contraste-report.json` (regenerable).

### Tasa global (corrida actual)

- WCAG AA pass: ~930/1030 (~90%) sobre assets evaluados.
- `no_foreground`: 87 (no cuentan como fail — son assets sin texto detectable en el muestreo).
- WCAG AAA pass: ~791/1030 (~77%).

> La diferencia entre 1302 PNGs y 1030 evaluados se explica por la
> exclusión de assets decorativos (watermark, isotipo, favicon).

## Scripts auxiliares vigentes

- `scripts/eikon_aggregate_wcag.py` — consolida reportes por marca en global.
- `scripts/eikon_count.py` — escribe `_STATUS.md` con tabla maestra.
- `gallery.py` — genera galerías individuales + agregada.
- `contrast_validator.py` — validador WCAG standalone.

## Documentación vigente

| Archivo | Propósito |
|---|---|
| `README.md` | Overview + flags + estado actual. |
| `INSTRUCCIONES-EIKON.md` | Guía operativa detallada. |
| `MASTER-TAXONOMIA.md` | Spec de categorías/tipos/variantes. |
| `BRIEF-AGENCIA.md` | Brief creativo (subconjunto editorial). |
| `CHANGELOG.md` | Historial v1.0 → v1.2. |
| `docs/OUTPUT-NO-VERSIONADOS.md` | Política de output git-ignored. |
| `docs/QA-CHECKLIST.md` | Checklist mecánico + visual. |
| `ESTADO-ENTREGA.md` | Este archivo. |
| `_STATUS.md` | Snapshot regenerable de output. |

## Pendientes residuales

1. **`agora-*` no soportadas**: filtradas por diseño (viven en Agora, no en Eikón).
2. **`--parallel > 1`** no implementado: limitado a 1 worker por seguridad de Playwright.
3. **Validación AAA**: reportada pero no enforced (solo AA es el piso).
4. **Galería agregada pesada** (~5–10 MB con thumbnails base64): aceptable local, no versionada.
5. **87 `no_foreground`** warnings: por diseño (logos minimalistas, watermarks), no son fallos.

## Cómo seguir

- Para regenerar TODO desde cero: ver [`docs/OUTPUT-NO-VERSIONADOS.md`](docs/OUTPUT-NO-VERSIONADOS.md).
- Para QA de una corrida: ver [`docs/QA-CHECKLIST.md`](docs/QA-CHECKLIST.md).
- Para entender el brief: [`BRIEF-AGENCIA.md`](BRIEF-AGENCIA.md).
- Fuente narrativa amplia de Cloud Atlas: vive en `Yo/` (no en eikon).