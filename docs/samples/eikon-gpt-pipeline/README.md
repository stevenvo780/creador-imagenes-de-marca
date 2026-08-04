# Muestra del pipeline en dos capas

- `before-eikon-mockup.png`: salida real del renderer HTML/CSS de Eikón para
  `pinakotheke-kosmos`, `ig_post/v1_square`.
- `after-local-preview.png`: la misma maqueta pasada por el proveedor offline
  determinista. Sirve como evidencia del pipeline y sus gates, pero **no es una
  salida GPT**.
- `after-local-preview.png.json`: trazabilidad (hashes, BrandSpec, provider,
  modelo y quality gates), sin secretos.

Se regenera con:

```bash
python3 scripts/eikon_refinement_sample.py \
  --chromium-executable /usr/bin/google-chrome
```

La muestra GPT real exige una llamada paga a OpenAI y por eso queda reservada a
una ejecución autorizada con `--provider openai --allow-paid-api`.
