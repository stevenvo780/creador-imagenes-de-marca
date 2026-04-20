# Creador de imágenes de marca — Agora / Elenxos

Repo auxiliar para producir renders sociales y piezas base del media kit en GPU local.

Referencia canonica de marca:

- `../symploque/assets/README.md`
- `../symploque/assets/elenxos_social_media/manual_de_marca.md`
- `../symploque/05-redes-sociales/media-kit-estructura.md`

## Hardware requerido

- GPU principal: RTX 5070 Ti (16 GB VRAM) — genera las imágenes
- CPU: Ryzen 9 9950X3D
- RAM: 128 GB

## Imágenes que genera

| Plataforma | Tipo | Tamaño | ID |
|---|---|---|---|
| LinkedIn | Post tesis | 1200×627 | `linkedin_post_tesis` |
| LinkedIn | Post diferenciador | 1200×627 | `linkedin_post_diferenciador` |
| LinkedIn | Post madurez | 1200×627 | `linkedin_post_madurez` |
| LinkedIn | Banner perfil | 1584×396 | `linkedin_banner` |
| Instagram | Post cuadrado | 1080×1080 | `ig_post_tesis` |
| Instagram | Carrusel slide 1 | 1080×1080 | `ig_carrusel_problema_1` |
| Instagram | Carrusel slide 3 | 1080×1080 | `ig_carrusel_problema_3` |
| Instagram | Story | 1080×1920 | `ig_story_teaser` |
| Instagram | Reel cover | 1080×1920 | `ig_reel_cover` |
| X/Twitter | Post principal | 1200×675 | `x_post_principal` |
| X/Twitter | Imagen hilo | 1200×675 | `x_post_hilo` |
| YouTube | Thumbnail | 1280×720 | `yt_thumbnail` |
| YouTube | Banner canal | 2560×1440 | `yt_banner` |
| WhatsApp | Avatar | 640×640 | `whatsapp_perfil` |
| Web | Open Graph | 1200×630 | `og_general` |

## Uso

```bash
# Instalar dependencias
python3 -m pip install -r requirements.txt

# O usar el entorno virtual local
./venv/bin/python -m pip install -r requirements.txt

# Generar todas las imágenes con SDXL
python3 generar_imagenes.py

# Generar todas las imágenes con FLUX.1-schnell
python3 generar_imagenes_flux.py

# Generar solo una imagen específica
python3 generar_imagenes.py --id linkedin_post_tesis

# Generar solo para una plataforma
python3 generar_imagenes_flux.py --plataforma Instagram

# Ajustar calidad en SDXL
python3 generar_imagenes.py --steps 50 --guidance 8.0
```

## Salida

Las imágenes se guardan en `output/` y, si usas FLUX, en `output_flux/`, organizadas por plataforma:

```
output/
  linkedin/
  instagram/
  x/
  youtube/
  whatsapp/
  web/
```

## Personalización

Editar `prompts.json` para:
- Cambiar prompts individuales
- Ajustar la paleta de colores sugerida
- Agregar nuevas imágenes

## Estado práctico

- `output/` contiene trabajo real, pero no debe asumirse como media kit final cerrado
- el objetivo no es inventar otra marca, sino servir a la capa canonica documentada en `symploque`
- si cambias el sistema visual oficial, regenera el pack completo para evitar mezclas entre variantes viejas y nuevas
