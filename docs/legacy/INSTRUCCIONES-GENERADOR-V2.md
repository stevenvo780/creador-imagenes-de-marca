# Generador Eikon v2 — Instrucciones de Uso

> ## ⚠️ DOCUMENTO LEGACY — NO VIGENTE
>
> Este archivo describe `generar_agencia_v2.py`, que fue **reemplazado**
> por el motor canónico `eikon.py`. Conservado solo como referencia
> histórica de la evolución del proyecto.
>
> **Para instrucciones actuales, ver [`INSTRUCCIONES-EIKON.md`](INSTRUCCIONES-EIKON.md).**
>
> Para entender la migración, ver [`CHANGELOG.md`](CHANGELOG.md) (sección v1.0 → v1.2)
> y [`ESTADO-ENTREGA.md`](ESTADO-ENTREGA.md) (estado operativo tras corrida general).
>
> Si llegaste aquí desde un script o un comando, casi seguramente
> deberías estar corriendo:
> ```bash
> python3 eikon.py --marca <slug>      # en lugar de generar_agencia_v2.py
> python3 eikon.py --all                # batch completo
> ```
>
> ---
>
> ## Cambios Principales (LEGACY — v1.0)

### 1. **Consolidación de Output**
- **Antes:** archivos generados en `output_agencia/` (script actual).
- **Ahora:** ÚNICA carpeta `/workspace/Pinakotheke/eikon/output/` limpia al inicio.
- **Limpieza:** usa `shutil.rmtree()` (Python), NO `rm -rf` (shell).

### 2. **Enumeración Completa de Matriz**
- Lee `MASTER-TAXONOMIA.md` → extrae categorías, tipos, variantes.
- Itera **TODAS** las marcas (EXCEPTO `agora-*` regex).
- Genera lista completa: `[(marca_slug, categoria, tipo, variant_num), ...]`
- Soporta filtros CLI: `--marca`, `--solo`, `--variants`.

### 3. **Renderizado Flexible con Playwright**
- Navega a plantilla `?variant=v{N}_{name}`.
- Inyecta CSS variables + atributos `data-*` del JSON marca.
- Screenshot @2x (device_scale_factor=2) con dimensiones correctas por asset.
- Retry automático 2-3 intentos en caso de timeout.

### 4. **Estructura de Salida**
```
/workspace/Pinakotheke/eikon/output/
├── pinakotheke-kosmos/
│   ├── logos/
│   │   ├── lockup_horizontal-v1.png
│   │   ├── lockup_horizontal-v2.png
│   │   ├── lockup_horizontal-v3.png
│   │   ├── lockup_vertical-v1.png
│   │   └── ...
│   ├── banners/
│   │   ├── linkedin_header-v1.png
│   │   ├── linkedin_header-v2.png
│   │   └── ...
│   ├── cards/
│   │   ├── business_card-v1.png
│   │   └── ...
│   └── ... (todas las categorías)
├── pinakotheke-techne/
│   └── ... (mismo patrón)
├── prizma-hermes/
│   ├── logos/
│   │   └── ...
│   └── ... (todas las categorías)
├── prizma-iris/
│   └── ... (mismo patrón)
└── _contraste-report.json  ← Reporte WCAG AA (después del render)
```

### 5. **Validador de Contrastes (módulo nuevo)**
- **Archivo:** `/workspace/Pinakotheke/eikon/contrast_validator.py`
- **Qué hace:**
  - Recorre TODAS las PNG en `output/`.
  - Mide contraste entre colores dominantes (fondo ≈ esquinas, texto ≈ centro).
  - Calcula luminancia WCAG y ratio contraste.
  - Verifica cumplimiento WCAG AA (ratio >= 4.5:1).
  - Escribe reporte: `output/_contraste-report.json`.
- **Salida:**
  ```json
  {
    "timestamp": "2026-06-19T15:30:00",
    "total_assets": 284,
    "wcag_aa": { "pass": 272, "fail": 12 },
    "wcag_aaa": { "pass": 250, "fail": 34 },
    "failing_assets_aa": [
      {
        "img": "pinakotheke-kosmos/logos/lockup_horizontal-v1.png",
        "contrast_ratio": 3.2,
        "bg_color": "#0b1417",
        "text_color": "#8d7cc0",
        "issue": "Ratio 3.2 < 4.5 (WCAG AA incumple)"
      },
      ...
    ],
    "summary": "272/284 assets cumplen WCAG AA (>= 4.5:1)"
  }
  ```

---

## Cómo Correr

### Preparación
```bash
cd /workspace/Pinakotheke/eikon

# Instala dependencias si falta (Pillow, numpy)
pip install Pillow numpy

# Verifica que existan:
# - templates/*.html (plantillas)
# - marcas/*.json (datos de marca)
# - MASTER-TAXONOMIA.md (especificación)
```

### Ejecuciones

**1. Todas las marcas (Cloud Atlas + Prizma):**
```bash
python generar_agencia_v2.py
```
- Limpia `output/` y `output_agencia/`.
- Enumera ~284 assets (2 líneas × 8 categorías × tipos × variantes).
- Renderiza cada uno con Playwright.
- Al final, corre validador de contrastes.
- Duración estimada: 30-60 minutos (depende de conectividad Playwright).

**2. Solo una marca:**
```bash
python generar_agencia_v2.py --marca pinakotheke-kosmos
```
- Renderiza solo los ~71 assets de Pinakotheke Kósmos.
- Duración: ~15-20 minutos.

**3. Solo categorías específicas:**
```bash
python generar_agencia_v2.py --solo logos --solo banners
```
- Renderiza logos + banners de TODAS las marcas.
- Pueden repetirse `--solo`.

**4. Solo variantes específicas:**
```bash
python generar_agencia_v2.py --marca prizma-hermes --variants 1
```
- Renderiza solo v1 de cada tipo (v2, v3 omitidas).

```bash
python generar_agencia_v2.py --variants 1-2
```
- Renderiza v1 y v2 de todos los tipos.

**5. Sin validación de contrastes:**
```bash
python generar_agencia_v2.py --sin-contraste
```
- Renderiza pero NO ejecuta `contrast_validator.py`.
- Útil para testing rápido.

**6. Combinaciones:**
```bash
python generar_agencia_v2.py --marca pinakotheke-kosmos --solo logos --variants 1-2
```
- Solo Pinakotheke, solo logos, solo v1-v2.

---

## Validador de Contrastes (Standalone)

### Uso directo
```bash
# Valida output/ (ubicación por defecto)
python contrast_validator.py

# Valida carpeta específica
python contrast_validator.py /ruta/a/output
```

### Integración en generar_agencia_v2.py
El generador corre automáticamente el validador al final (salvo `--sin-contraste`).

### Interpretación del Reporte

```json
{
  "wcag_aa": { "pass": 272, "fail": 12 },
  "failing_assets_aa": [
    {
      "img": "pinakotheke-kosmos/logos/lockup_horizontal-v1.png",
      "contrast_ratio": 3.2,
      "issue": "Ratio 3.2 < 4.5 (WCAG AA incumple)"
    }
  ]
}
```

**Significado:**
- **contrast_ratio < 4.5:1** → WCAG AA incumple. Ojo: color de texto demasiado similar al fondo.
- **contrast_ratio 4.5-7.0** → WCAG AA OK, pero no AAA (texto pequeño está seguro, pero grande necesita > 7).
- **contrast_ratio >= 7.0** → WCAG AAA (máximo). Muy seguro.

**Acciones si falla:**
1. Revisar plantilla HTML: ¿colores `--texto` y `--bg` están bien definidos?
2. Revisar JSON marca: ¿paleta es coherente?
3. Ejecutar validador con `--sin-contraste` para revisar PNG visualmente.
4. Ajustar CSS o JSON marca y re-renderizar.

---

## Argumentos CLI — Referencia Completa

| Argumento | Valor | Defecto | Descripción |
|-----------|-------|---------|-------------|
| `--marca` | `<slug>` | todas | Procesa solo una marca (ej: `pinakotheke-kosmos`) |
| `--solo` | `<categoria>` | todas | Procesa solo categorías (repetible: `--solo logos --solo banners`) |
| `--variants` | `<N>` o `<N-M>` | 1..max | Rango de variantes (ej: `1` solo v1, `1-2` v1-v2) |
| `--sin-contraste` | flag | NO | No ejecuta validador de contrastes al final |
| `--help` | flag | — | Muestra ayuda |

---

## Estructura Técnica (Para Desarrolladores)

### `generar_agencia_v2.py`
- **`limpiar_output()`**: limpia `output/` + `output_agencia/` con shutil.
- **`parse_taxonomia()`**: parsea MASTER-TAXONOMIA.md → dict.
- **`enumerate_matrix(args)`**: genera lista de (marca, categoria, tipo, variant_num).
- **`render_asset_full(...)`**: Playwright → screenshot → guarda PNG.
- **`async run(args)`**: loop principal.
- **`parse_args()`**: CLI.
- **`main()`**: entry point.

### `contrast_validator.py`
- **`ContrastValidator` class:**
  - `measure_contrast(img_path)`: analiza 1 PNG.
  - `validate_all()`: procesa todas las PNG.
  - `write_report(report_path)`: genera JSON.
  - Métodos auxiliares: `_calculate_luminance()`, `_calculate_contrast_ratio()`, etc.

### Dependencias
- `playwright` (async browser automation)
- `Pillow` (PIL, procesamiento de PNG)
- `numpy` (cálculos vectoriales de píxeles)
- Python 3.9+

---

## Troubleshooting

### "Plantilla no encontrada: cloud_atlas_lockup_horizontal.html"
- **Causa:** archivo no existe en `templates/`.
- **Solución:** revisar nombre de plantilla en MASTER-TAXONOMIA.md vs `templates/*.html`.

### "Chromium not found" / Playwright timeout
- **Causa:** navegador no disponible o muy lento.
- **Solución:** `pip install -U playwright && playwright install chromium`.

### Contraste FAIL en reporte
- **Causa:** color de texto muy similar al fondo.
- **Solución:** revisar paleta JSON marca; ajustar `--texto` o `--bg` para más contraste.
- **Verificación rápida:** abre PNG en navegador, ¿se lee el texto claramente?

### "Matriz vacía" después de filtros
- **Causa:** `--marca`, `--solo` o `--variants` demasiado restrictivos.
- **Solución:** revisar MASTER-TAXONOMIA.md para nombres exactos de categorías.

### Validador no corre
- **Causa:** `contrast_validator.py` no disponible o importación falla.
- **Solución:** verifica archivo en `eikon/` y dependencias (Pillow, numpy).

---

## Notas Importantes

1. **NO ejecutes batch completo en sandbox frío:** Playwright tarda en inicializar. Primer run = ~10min solo de setup.
2. **NO commites ni pushes:** Script está listo pero sin git commit.
3. **Output ÚNICO:** ya no hay `output_agencia/` disperso; todo en `output/`.
4. **Variantes dinámicas:** nombres se infieren de MASTER-TAXONOMIA.md (ej: `v1_color`, `v2_mono`).
5. **Reintento automático:** si un asset falla, reintentar 2-3 veces antes de pasar.

---

## Próximos Pasos

1. **Verificar plantillas:** asegurar que cada archivo HTML en `templates/` tiene atributo `data-variant="..."`.
2. **Correr pilot:** `python generar_agencia_v2.py --marca pinakotheke-kosmos --solo logos` (rápido).
3. **Revisar output:** abrir PNGs en navegador, ¿se ve correcto?
4. **Validar contrastes:** revisar `output/_contraste-report.json`, ¿hay fallos?
5. **Iterar:** ajustar CSS/JSON según reporte.
6. **Batch completo:** una vez validado el pilot, correr `python generar_agencia_v2.py` (todas las marcas).

---

**Última actualización:** 2026-06-19  
**Autor:** Claude Code (delegación Codex)  
**Motor:** Eikon v2 (Playwright + HTML/CSS + Validación WCAG)
