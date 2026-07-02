# Output no versionado — Política de regenerable

> Estado: 2026-06-20 · Aplicado a partir de la corrida general de 34 marcas.

## Resumen ejecutivo

- `output/` está **git-ignored** (PNGs, `_manifest.json`, `_contraste-report.json`, `_gallery_*.html`, `.cache.json`).
- `marcas/`, `templates/`, `eikon.py`, `contrast_validator.py`, `gallery.py`, `scripts/` **sí se versionan**.
- Cualquier cosa en `output/` se puede **regenerar de cero** ejecutando `eikon.py` + `gallery.py` + los scripts de `scripts/`.

## ¿Qué hay en `output/` y por qué no se versiona?

| Contenido | Tamaño típico | Por qué fuera de git |
|---|---|---|
| `*.png` por marca | ~600 KB c/u × 1302 = ~780 MB | Binarios regenerables, inflan el repo |
| `output/<marca>/_manifest.json` | ~50 KB c/u | Metadata derivada del render |
| `output/<marca>/_contraste-report.json` | ~5 KB c/u | Reporte derivado de PNGs |
| `output/<marca>/.cache.json` | <5 KB c/u | Cache local de hashes; caduca |
| `output/_gallery_*.html` | 100–500 KB c/u | HTML con thumbnails base64; regenerable |
| `output/_contraste-report.json` (agregado) | ~50 KB | Lo regenera `scripts/eikon_aggregate_wcag.py` |

## ¿Qué sí se versiona?

- `marcas/<slug>.json` — fuente de verdad por marca.
- `templates/<plantilla>.html` — fuente de verdad visual.
- `eikon.py` — motor canónico.
- `contrast_validator.py` — validador WCAG AA.
- `gallery.py` — generador de galerías.
- `scripts/eikon_aggregate_wcag.py`, `scripts/eikon_count.py` — cierres documentales.
- `docs/MASTER-TAXONOMIA.md`, `docs/legacy/BRIEF-AGENCIA.md` — specs y brief.
- `tests/test_eikon_checks.py` — tests de regresión.
- `requirements.txt` — deps declaradas.
- `_STATUS.md` — snapshot regenerable (ver abajo).

### Sobre `_STATUS.md`

`_STATUS.md` lo escribe `scripts/eikon_count.py` desde `output/`. Es
**regenerable**. Si lo commiteas, será sobreescrito en la próxima corrida.
Recomendación: versionarlo solo como snapshot puntual (ej: al cierre de
fase). La fuente de verdad operativa es siempre el output + scripts.

## Cómo regenerar todo desde cero

Orden recomendado:

```bash
cd /workspace/Pinakotheke/eikon

# 1. Renderizar TODAS las marcas (excluye agora-* automáticamente)
python3 eikon.py --all

# 2. Generar reportes WCAG por marca (ya los escribe eikon.py al final,
#    pero si querés re-ejecutar contraste standalone):
python3 contrast_validator.py        # global
python3 contrast_validator.py --marca pinakotheke-kosmos

# 3. Consolidar reporte agregado
python3 scripts/eikon_aggregate_wcag.py

# 4. Galerías individuales + agregada
python3 gallery.py --all-marcas
python3 gallery.py --all-marcas --aggregated

# 5. Snapshot maestro
python3 scripts/eikon_count.py            # escribe _STATUS.md
python3 scripts/eikon_count.py --stdout   # también tabla en consola
```

## Cómo regenerar UNA sola marca (incremental con cache)

```bash
# Limpieza opt-in de un subset (no global)
python3 eikon.py --marca pinakotheke-kosmos --clean

# Sin limpieza: usa cache, salta assets no modificados
python3 eikon.py --marca pinakotheke-kosmos --resume
```

`--resume` es la forma normal de trabajo: cada asset tiene un hash estable
(engine + slug + categoría + tipo + variante + vars + template). Si nada
cambió, el asset se reusa del disco sin re-renderizar.

## ¿Qué pasa con `.cache.json`?

`output/<marca>/.cache.json` es el **estado de cache por marca**. NO se
versiona. Si lo borrás, `eikon.py` re-renderiza todo la próxima vez (es
el comportamiento esperado de un "fresh run").

## Cómo verificar reproducibilidad

```bash
# Forzar re-render completo de una marca:
rm -rf output/<marca>/
python3 eikon.py --marca <marca>

# Comparar contra una corrida previa (otra máquina, otra branch):
diff -q output/<marca>/_manifest.json /tmp/expected_output/<marca>/_manifest.json
```

Si los manifests son idénticos pero los PNGs difieren a nivel de bytes,
eso es esperable: Playwright + Chromium pueden introducir pequeñas
variaciones de compresión. La metadata (dimensiones, hash de inputs,
status) sí debe ser estable.

## Excepciones y overrides

- `--clean` borra `output/<marca>/` antes de renderizar. Útil cuando
  cambian plantillas o marcas. **No** borra otras marcas ni `output/_gallery_*`.
- `output/_legacy/` (si existe) NO debe regenerarse: es histórico.
- `_gallery_aggregated.html` se regenera siempre desde 0; si cambia el
  set de marcas, regenerar con `gallery.py --all-marcas --aggregated`.

## Política para CI / futuros colaboradores

1. **No commitear nada de `output/`** salvo snapshot explícito de `_STATUS.md`.
2. Cualquier persona con Playwright + Chromium puede regenerar 34 marcas
   en ~10–15 min con `python3 eikon.py --all`.
3. Los tests (`python3 tests/test_eikon_checks.py`) son **independientes**
   de Playwright: se pueden correr en cualquier entorno para validar el
   motor matemático y la lógica de templates/cache/manifest.