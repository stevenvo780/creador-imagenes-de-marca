# Eikón — Motor de generación de assets de marca

Núcleo Hi-Res para producir los assets visuales del ecosistema
Pinakotheke (Cloud Atlas) y Prizma Enterprise.

> Genera **1302 PNG** sobre **34 marcas no-agora** con validación WCAG AA
> por marca y galería HTML agregada.

## Pipeline (5 fases)

1. **Carga de marca** — `marcas/<slug>.json` (colores, tipografía, textos).
2. **Mapeo a taxonomía** — Cloud Atlas (pinakotheke-*) o Prizma (prizma-*).
3. **Render Playwright Hi-Res** — `templates/<plantilla>.html` con datos
   inyectados, `deviceScaleFactor` 3× (logos/print) o 2× (social/web).
4. **Validación WCAG AA** — `contrast_validator.py` mide luminancia BT.709
   y ratio entre texto/fondo local.
5. **CLI robusto** — flags `--marca`, `--all`, `--only-marcas`, `--clean`,
   `--dry-run`, `--resume`, `--skip-contraste`, `--parallel`.

## Estructura actual

- `eikon.py`: shim/entrypoint retrocompatible (`python3 eikon.py ...`).
- `eikon_core/`: motor modular por responsabilidad: taxonomía, mapping,
  layout, render, manifests, CLI.
- `taxonomy.json`: taxonomía v1 serializable; se valida con
  `scripts/eikon_validate_taxonomy.py`.
- `variations.py`: planner determinístico para batches/variaciones.
- `webapp/`: MVP FastAPI opcional multi-tenant con JWT cookie, SQLite local
  y jobs Eikon.
- `audit/`: metodología, plantilla y reportes de auditoría.

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

- [`MASTER-TAXONOMIA.md`](MASTER-TAXONOMIA.md) — spec de categorías, tipos, variantes.
- [`BRIEF-AGENCIA.md`](BRIEF-AGENCIA.md) — brief creativo (subconjunto editorial para Eikón; fuente amplia en `Yo/`).
- [`INSTRUCCIONES-EIKON.md`](INSTRUCCIONES-EIKON.md) — guía operativa actual.
- [`docs/OUTPUT-NO-VERSIONADOS.md`](docs/OUTPUT-NO-VERSIONADOS.md) — política de output git-ignored.
- [`docs/QA-CHECKLIST.md`](docs/QA-CHECKLIST.md) — checklist de QA mecánico + visual.
- [`CHANGELOG.md`](CHANGELOG.md) — historial del motor (v1.0, v1.1, v1.2).
- [`ESTADO-ENTREGA.md`](ESTADO-ENTREGA.md) — estado operativo tras corrida general.
- `INSTRUCCIONES-GENERADOR-V2.md` — LEGACY, apunta al nuevo.

## Notas

- `_legacy/` contiene scripts históricos (`generar_agencia.py`,
  `generar_agencia_v2.py`, `render.py`, etc.). **NO USAR** — son de v0.x.
- El motor `eikon.py` reemplaza `generar_agencia_v2.py`.
- `agora-*` se filtra automáticamente: no se renderiza.
- Las variantes por tipo están definidas en `_build_taxonomia()` dentro
  de `eikon.py`; los alias legacy (linkedin_header → linkedin_banner) se
  resuelven vía `_TEMPLATE_ALIASES`.
- `requirements.txt`: `playwright`, `Pillow`, `numpy`.
