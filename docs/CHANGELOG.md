# Changelog — Eikón

Todos los cambios relevantes al motor de generación de assets de marca.
Formato: [Semantic Versioning](https://semver.org/lang/es/) ligero.

## v1.2 — 2026-06-20 · Cierre operativo y documental

### Added
- `scripts/eikon_aggregate_wcag.py` — consolida reportes WCAG por marca
  en `output/_contraste-report.json` agregado, sin dependencias externas.
- `scripts/eikon_count.py` — conteo de PNGs/manifests/WCAG/galerías y
  `_STATUS.md` maestro en raíz.
- `docs/OUTPUT-NO-VERSIONADOS.md` — política de qué se versiona y qué no.
- `docs/QA-CHECKLIST.md` — checklist mecánico + visual para futuras corridas.
- `INSTRUCCIONES-EIKON.md` — guía operativa vigente.
- `CHANGELOG.md` (este archivo).
- 9 galerías por marca que faltaban (pinakotheke, pinakotheke-estructuras-preontologicas, pinakotheke-hinton, pinakotheke-paideia, pinakotheke-techne, prizma, prizma-hermes, prizma-logos, steven-vallejo).
- `_gallery_aggregated.html` regenerada con las 34 marcas.

### Changed
- `README.md` — reescrito mínimo: refleja motor canónico `eikon.py`,
  flags reales, output actual 34 marcas / 1302 PNG, scripts nuevos.
- `ESTADO-ENTREGA.md` — estado operativo real (no "NO ejecutado"),
  motor `eikon.py`, Kosmos piloto aprobado.
- `INSTRUCCIONES-GENERADOR-V2.md` — anotada como LEGACY al inicio,
  apunta a `INSTRUCCIONES-EIKON.md`.
- `output/_contraste-report.json` — regenerado desde reportes por marca.

### Verified
- 34 marcas con `_manifest.json`, `_contraste-report.json`.
- 1302 PNGs totales.
- 34/34 galerías por marca + 1 agregada.
- `python3 -m py_compile` OK en todos los .py del motor + scripts + tests.
- `python3 tests/test_eikon_checks.py` → 55 ✓ / 0 ✗.

## v1.1 — 2026-06-19 · Estabilización del motor

### Added
- Cache por hash estable (`compute_hash`, `load_cache`, `save_cache`).
- `_manifest.json` por marca con metadata completa.
- `--resume` (alias `--solo-cambios`) para re-render incremental.
- `--clean` opt-in para limpiar `output/<marca>/` antes de renderizar.
- `--only-marcas` para subset por coma.
- `--skip-contraste` para omitir validación WCAG.
- Detección de foreground multi-región (centro → cuadrantes → full) en
  `contrast_validator.py`.
- `min_fg_ratio` configurable (default 0.005) para reducir falsos
  "no foreground" en logos y banners minimalistas.
- 11 tests sintéticos en `tests/test_eikon_checks.py` (templates, WCAG
  luminance, foreground detection, hash, manifest, dry-run, contraste
  configurable, text limits, per-brand report, post-validación).
- Post-validación: re-marca como `generated` los assets donde el PNG
  existe pero el render había reportado error espurio
  (race condition de `Page.captureScreenshot`).

### Changed
- Flags CLI consolidadas: `--marca`, `--all`, `--only-marcas`, `--solo`,
  `--dry-run`, `--resume`, `--parallel`, `--skip-contraste`, `--clean`.
- `apply_text_limits` con truncado por palabra/punto.
- `_TEMPLATE_ALIASES` para resolver nombres legacy (linkedin_header → linkedin_banner, etc.).
- Text limits portados desde `_legacy/render.py` (Fase 2).

### Fixed
- Race conditions de `Page.captureScreenshot` con retry simple.
- Cálculo WCAG usa coeficientes BT.709 (no NTSC) — corrige luminancia
  en grises medios.
- `favicon`, `isotipo`, `watermark`, `logo_symbol` excluidos de WCAG
  (decorativos por diseño).

## v1.0 — 2026-06-19 · Motor canónico consolidado

### Added
- `eikon.py` — generador canónico único que reemplaza 12 scripts legacy.
- `contrast_validator.py` — validador WCAG AA con luminancia BT.709.
- `gallery.py` — galerías HTML individuales + agregada con thumbnails
  base64 inline.
- `MASTER-TAXONOMIA.md` — spec de categorías, tipos, variantes.
- `BRIEF-AGENCIA.md` — brief creativo Cloud Atlas / Prizma.
- `marcas/<slug>.json` para 38 marcas (4 agora-* + 34 no-agora).
- `templates/<plantilla>.html` para ~20 tipos de assets.
- Render Playwright Hi-Res con `deviceScaleFactor` dinámico
  (3× logos/print, 2× social/web).
- `_legacy/` con scripts históricos (`generar_agencia.py`,
  `generar_agencia_v2.py`, `render.py`, etc.) preservados pero no usados.

### Notas

- El motor `eikon.py` reemplaza `generar_agencia_v2.py` (anteriormente
  referenciado como "Eikon v2"). El nombre interno del motor en código
  sigue siendo `eikon-v1.2` (ENGINE_VERSION).
- "Cauce" fue retirado del namespace antes de v1.0; todo lo nuevo usa
  `pinakotheke`/`prizma`.