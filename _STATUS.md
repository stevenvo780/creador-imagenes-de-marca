# _STATUS — Eikon Output Snapshot

_Generado: 2026-06-29 04:11:42 UTC_  
_Output dir: `/workspace/Pinakotheke/eikon/output`_  
_Source: `scripts/eikon_count.py`_

## Resumen global

| Métrica | Valor |
|---|---|
| Marcas | 6 |
| PNGs totales (recursivo) | 238 |
| Assets en manifests | 238 |
| Assets `generated` (manifest) | 238 |
| Assets `error` (manifest) | 0 |
| Assets WCAG AA pass | 188 |
| Assets WCAG AA fail | 2 |
|   ↳ sin foreground detectable | 2 |
| Assets WCAG AAA pass | 146 |
| Assets WCAG AAA fail | 44 |
| Galería agregada | NO |
| Reporte contraste agregado | sí |

## Tabla por marca

| Marca | PNG | Manifest | AA pass | AA fail | no_fg | AAA pass | AAA fail | Galería | Layout |
|---|---:|---|---:|---:|---:|---:|---:|---|---:|
| `agora` | 45 | 45/45 | 35 | 2 | 2 | 28 | 9 | ✗ | 3 |
| `pinakotheke` | 45 | 45/45 | 37 | 0 | 0 | 31 | 6 | ✗ | 2 |
| `pinakotheke-kosmos` | 45 | 45/45 | 37 | 0 | 0 | 32 | 5 | ✗ | 5 |
| `prizma` | 29 | 29/29 | 21 | 0 | 0 | 11 | 10 | ✗ | ✓ |
| `prizma-iris` | 29 | 29/29 | 21 | 0 | 0 | 12 | 9 | ✗ | ✓ |
| `steven-vallejo-filosofo` | 45 | 45/45 | 37 | 0 | 0 | 32 | 5 | ✗ | 2 |

Leyenda:
- `PNG` = archivos `.png` bajo `output/<marca>/` (recursivo).
- `Manifest` = `generated / total_assets` en `_manifest.json` (o `—` si falta).
- `Galería` = presencia de `output/_gallery_<marca>.html`.
- `no_fg` = assets donde el validador WCAG no detectó foreground (no se cuentan como `AA fail` real).
- `Layout` = assets con `layout_status != "pass"` o `layout_warnings` no vacío (✓ = 0 issues, — = sin manifest). Ver `scripts/eikon_validate_layout.py`.

## Cómo regenerar

Asumiendo cwd = raíz de eikon:

```bash
# 1. Conteo + _STATUS.md (incluye columna Layout)
python3 scripts/eikon_count.py

# 2. Validación de layout por marca (assets con layout_status != pass
#    o layout_warnings no vacío). --fail-on-errors → exit 1 si hay issues.
python3 scripts/eikon_validate_layout.py
python3 scripts/eikon_validate_layout.py --json
python3 scripts/eikon_validate_layout.py --fail-on-errors

# 3. Reporte WCAG agregado en output/_contraste-report.json
python3 scripts/eikon_aggregate_wcag.py

# 4. Galerías individuales + agregada
python3 gallery.py --all-marcas
python3 gallery.py --all-marcas --aggregated

# 5. Re-render completo (cuando hay cambios en motor/plantillas)
python3 eikon.py --all
```

Ver `docs/QA-CHECKLIST.md` para el checklist visual de QA.
