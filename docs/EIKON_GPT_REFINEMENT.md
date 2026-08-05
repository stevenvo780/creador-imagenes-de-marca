# Eikón: maqueta on-brand → refinado GPT

Eikón mantiene dos capas deliberadamente separadas:

1. El motor HTML/CSS produce la maqueta determinista: composición, contenido,
   tipografía, paleta, logo y formato.
2. Un proveedor de edición refina esa misma imagen sin rediseñarla. El prompt
   fija como invariantes el texto, layout, logo, paleta y jerarquía. El resultado
   debe superar gates locales de estructura y adherencia de color.

La fuente única de marca es `config/brand-library.json`, generada desde los JSON
históricos de `marcas/`:

```bash
python3 scripts/eikon_brand_library.py --write
python3 scripts/eikon_brand_library.py --check
```

## Flujo sin red para CI y muestras

`local-preview` verifica el pipeline completo sin usar GPT, secretos ni créditos.
Es un filtro Pillow determinista y su metadata lo identifica expresamente; no es
una simulación ni una afirmación de calidad GPT.

```bash
python3 scripts/eikon_refine.py \
  --brand pinakotheke-kosmos \
  --asset-type ig_post \
  --input output/pinakotheke-kosmos/social/ig_post \
  --output-dir output/pinakotheke-kosmos/refined/ig_post \
  --provider local-preview
```

## Flujo GPT Image 2 (opt-in y con costo)

La llamada real requiere dos gates simultáneos: `OPENAI_API_KEY` en el entorno y
`--allow-paid-api`. La clave nunca se escribe en manifests ni mensajes de error.

```bash
OPENAI_API_KEY=... python3 scripts/eikon_refine.py \
  --brand pinakotheke-kosmos \
  --asset-type ig_post \
  --input output/pinakotheke-kosmos/social/ig_post \
  --output-dir output/pinakotheke-kosmos/refined/ig_post \
  --provider openai \
  --model gpt-image-2 \
  --quality high \
  --allow-paid-api
```

Cada salida incluye `<archivo>.png.json` con hashes de entrada/salida, digest de
BrandSpec, proveedor/modelo, tamaño enviado, request id si existe y resultados de
los quality gates. Las escrituras son atómicas, no se sobrescribe por defecto y
una respuesta que altera demasiado la composición o deriva de paleta se rechaza.

Una carpeta de resultados se consolida en una biblioteca verificable con:

```bash
python3 scripts/eikon_refinement_library.py output/mi-lote-refinado
```

El archivo `_library.json` enumera cada par maqueta/refinado, proveedor, modelo,
BrandSpec, quality gates y hashes SHA-256. El comando vuelve a calcular los hashes
y falla si falta un archivo o si cualquier asset fue modificado fuera del flujo.

## Escala y seguridad operacional

- Una entrada puede ser un PNG o un directorio; `--glob` y `--max-assets`
  controlan el lote.
- `--dry-run` enumera el plan sin construir proveedor ni tocar la red.
- La ejecución no está conectada al worker de producción: es una acción explícita
  para evitar gasto accidental.
- Errores 429/5xx y de red se reintentan con backoff acotado. Errores de usuario,
  autenticación o moderación no se reintentan.
