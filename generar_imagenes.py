#!/usr/bin/env python3
"""
Generador de imágenes de marca para Agora / Elenxos.

Usa Stable Diffusion XL en GPU local (RTX 5070 Ti 16 GB) para producir
imágenes de alta calidad para todas las redes sociales.

Uso:
    python generar_imagenes.py                  # genera todas
    python generar_imagenes.py --id linkedin_post_tesis  # genera una sola
    python generar_imagenes.py --plataforma Instagram    # genera solo Instagram
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Configuración de CUDA antes de importar torch
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
from diffusers import StableDiffusionXLPipeline, DPMSolverMultistepScheduler
from PIL import Image, ImageDraw

# Desactivar backends problemáticos en Blackwell (RTX 5070 Ti, CC 12.0)
torch.backends.cuda.enable_flash_sdp(False)
torch.backends.cuda.enable_mem_efficient_sdp(False)
torch.backends.cudnn.enabled = False

SCRIPT_DIR = Path(__file__).resolve().parent
PROMPTS_FILE = SCRIPT_DIR / "prompts.json"
OUTPUT_DIR = SCRIPT_DIR / "output"

DEVICE = "cuda:0"
DTYPE = torch.bfloat16

# Modelo SDXL base (se descarga la primera vez, ~6.5 GB)
MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"

# Negative prompt global para mantener coherencia de estilo
NEGATIVE_PROMPT = (
    "text, watermark, logo, words, letters, typography, blurry, low quality, "
    "distorted, cartoon, anime, childish, cluttered, noisy, oversaturated, "
    "photo of people, faces, hands, fingers, stock photo, generic, ugly"
)


def load_prompts(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_pipeline() -> StableDiffusionXLPipeline:
    print(f"[INFO] Cargando modelo {MODEL_ID} en CPU → offload a {DEVICE} ({DTYPE}) …")
    pipe = StableDiffusionXLPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=DTYPE,
        use_safetensors=True,
    )
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)

    # sequential_cpu_offload: mueve cada capa individual a GPU una a una.
    # Más lento pero más seguro en GPUs Blackwell nuevas (CC 12.0).
    pipe.enable_sequential_cpu_offload(gpu_id=0)
    pipe.enable_attention_slicing(slice_size=1)

    print("[INFO] Modelo listo.\n")
    return pipe


def generar_imagen(
    pipe: StableDiffusionXLPipeline,
    item: dict,
    marca: dict,
    output_dir: Path,
    steps: int = 40,
    guidance: float = 7.5,
    seed: int | None = None,
) -> Path:
    """Genera una imagen y la escala al tamaño final requerido."""
    target_w = item["ancho"]
    target_h = item["alto"]

    # SDXL trabaja mejor con resoluciones múltiplo de 64 y cercanas a 1024x1024.
    # Generamos a una resolución base coherente y luego escalamos.
    aspect = target_w / target_h

    if aspect >= 2.5:
        # ultra-wide (banners)
        gen_w, gen_h = 1536, 640
    elif aspect >= 1.5:
        # wide (LinkedIn posts, X posts, OG)
        gen_w, gen_h = 1344, 768
    elif aspect <= 0.6:
        # vertical (stories, reels)
        gen_w, gen_h = 768, 1344
    else:
        # cuadrado o cercano
        gen_w, gen_h = 1024, 1024

    prompt = item["prompt"]

    generator = None
    if seed is not None:
        # Con sequential_cpu_offload, los latents iniciales se generan en CPU
        generator = torch.Generator(device="cpu").manual_seed(seed)

    print(f"  Generando a {gen_w}×{gen_h} → reescalar a {target_w}×{target_h}")

    with torch.inference_mode():
        result = pipe(
            prompt=prompt,
            negative_prompt=NEGATIVE_PROMPT,
            width=gen_w,
            height=gen_h,
            num_inference_steps=steps,
            guidance_scale=guidance,
            generator=generator,
        )

    img: Image.Image = result.images[0]

    # Escalar al tamaño final
    if (img.width, img.height) != (target_w, target_h):
        img = img.resize((target_w, target_h), Image.LANCZOS)

    # Guardar
    plat_dir = output_dir / item["plataforma"].lower().replace("/", "-")
    plat_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{item['id']}.png"
    out_path = plat_dir / filename
    img.save(out_path, "PNG")

    return out_path


def main():
    parser = argparse.ArgumentParser(description="Generador de imágenes de marca Agora")
    parser.add_argument("--id", help="Generar solo la imagen con este ID")
    parser.add_argument("--plataforma", help="Generar solo imágenes de esta plataforma")
    parser.add_argument("--steps", type=int, default=40, help="Pasos de inferencia (default: 40)")
    parser.add_argument("--guidance", type=float, default=7.5, help="Guidance scale (default: 7.5)")
    parser.add_argument("--seed", type=int, default=42, help="Seed para reproducibilidad (default: 42)")
    parser.add_argument("--prompts", type=str, default=str(PROMPTS_FILE), help="Ruta al JSON de prompts")
    args = parser.parse_args()

    data = load_prompts(Path(args.prompts))
    marca = data["marca"]
    imagenes = data["imagenes"]

    # Filtrar
    if args.id:
        imagenes = [i for i in imagenes if i["id"] == args.id]
        if not imagenes:
            print(f"[ERROR] No se encontró imagen con id '{args.id}'")
            sys.exit(1)
    elif args.plataforma:
        imagenes = [i for i in imagenes if i["plataforma"].lower() == args.plataforma.lower()]
        if not imagenes:
            print(f"[ERROR] No se encontraron imágenes para plataforma '{args.plataforma}'")
            sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f"  GENERADOR DE IMÁGENES DE MARCA — {marca['nombre_producto']}")
    print(f"  Marca corporativa: {marca['nombre_corporativo']}")
    print(f"  Tagline: {marca['tagline']}")
    print(f"  GPU: {DEVICE}")
    print(f"  Imágenes a generar: {len(imagenes)}")
    print("=" * 60)
    print()

    pipe = build_pipeline()

    total = len(imagenes)
    exitosas = 0
    fallidas = []

    for idx, item in enumerate(imagenes, 1):
        print(f"[{idx}/{total}] {item['nombre']}")
        t0 = time.time()
        try:
            out = generar_imagen(
                pipe, item, marca, OUTPUT_DIR,
                steps=args.steps,
                guidance=args.guidance,
                seed=args.seed,
            )
            elapsed = time.time() - t0
            print(f"  ✓ Guardada en {out} ({elapsed:.1f}s)\n")
            exitosas += 1
        except Exception as e:
            elapsed = time.time() - t0
            print(f"  ✗ Error: {e} ({elapsed:.1f}s)\n")
            fallidas.append(item["id"])

    print("=" * 60)
    print(f"  Completado: {exitosas}/{total} imágenes generadas")
    if fallidas:
        print(f"  Fallidas: {', '.join(fallidas)}")
    print(f"  Directorio de salida: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
