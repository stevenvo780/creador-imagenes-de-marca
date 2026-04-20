#!/usr/bin/env python3
"""
Generador de imágenes de marca para Agora / Elenxos — FLUX.1-schnell.

Usa FLUX.1-schnell (Black Forest Labs) en GPU local (RTX 5070 Ti 16 GB).
Calidad muy superior a SDXL, solo 4 pasos de inferencia.

Uso:
    python generar_imagenes_flux.py                  # genera todas
    python generar_imagenes_flux.py --id linkedin_post_tesis  # genera una sola
    python generar_imagenes_flux.py --plataforma Instagram    # solo Instagram
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch
from diffusers import FluxPipeline
from PIL import Image

# Desactivar backends problemáticos en Blackwell (RTX 5070 Ti, CC 12.0)
torch.backends.cuda.enable_flash_sdp(False)
torch.backends.cuda.enable_mem_efficient_sdp(False)
torch.backends.cudnn.enabled = False

SCRIPT_DIR = Path(__file__).resolve().parent
PROMPTS_FILE = SCRIPT_DIR / "prompts.json"
OUTPUT_DIR = SCRIPT_DIR / "output_flux"

DEVICE = "cuda:0"
DTYPE = torch.bfloat16

# FLUX.1-schnell: 4 pasos, sin guidance, calidad estado del arte
MODEL_ID = "black-forest-labs/FLUX.1-schnell"


def load_prompts(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_pipeline() -> FluxPipeline:
    print(f"[INFO] Cargando modelo {MODEL_ID} ({DTYPE}) …")
    pipe = FluxPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=DTYPE,
    )

    # model_cpu_offload: mueve componentes completos (T5, transformer, VAE)
    # a GPU uno a uno. Pico ~12 GB, cabe en 16 GB de la 5070 Ti.
    pipe.enable_model_cpu_offload(gpu_id=0)

    print("[INFO] Modelo listo.\n")
    return pipe


def generar_imagen(
    pipe: FluxPipeline,
    item: dict,
    output_dir: Path,
    steps: int = 4,
    seed: int | None = None,
) -> Path:
    """Genera una imagen con FLUX y la escala al tamaño final."""
    target_w = item["ancho"]
    target_h = item["alto"]

    aspect = target_w / target_h

    # FLUX genera bien a resoluciones múltiplo de 16 hasta ~1536.
    if aspect >= 2.5:
        gen_w, gen_h = 1536, 640
    elif aspect >= 1.5:
        gen_w, gen_h = 1344, 768
    elif aspect <= 0.6:
        gen_w, gen_h = 768, 1344
    else:
        gen_w, gen_h = 1024, 1024

    prompt = item["prompt"]

    generator = None
    if seed is not None:
        generator = torch.Generator(device="cpu").manual_seed(seed)

    print(f"  Generando a {gen_w}×{gen_h} → reescalar a {target_w}×{target_h}")

    with torch.inference_mode():
        result = pipe(
            prompt=prompt,
            width=gen_w,
            height=gen_h,
            num_inference_steps=steps,
            guidance_scale=0.0,
            max_sequence_length=256,
            generator=generator,
        )

    img: Image.Image = result.images[0]

    if (img.width, img.height) != (target_w, target_h):
        img = img.resize((target_w, target_h), Image.LANCZOS)

    plat_dir = output_dir / item["plataforma"].lower().replace("/", "-")
    plat_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{item['id']}.png"
    out_path = plat_dir / filename
    img.save(out_path, "PNG")

    return out_path


def main():
    parser = argparse.ArgumentParser(description="Generador FLUX.1-schnell — Agora")
    parser.add_argument("--id", help="Generar solo la imagen con este ID")
    parser.add_argument("--plataforma", help="Generar solo imágenes de esta plataforma")
    parser.add_argument("--steps", type=int, default=4, help="Pasos de inferencia (default: 4)")
    parser.add_argument("--seed", type=int, default=42, help="Seed (default: 42)")
    parser.add_argument("--prompts", type=str, default=str(PROMPTS_FILE))
    args = parser.parse_args()

    data = load_prompts(Path(args.prompts))
    marca = data["marca"]
    imagenes = data["imagenes"]

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
    print(f"  GENERADOR FLUX.1-schnell — {marca['nombre_producto']}")
    print(f"  Marca corporativa: {marca['nombre_corporativo']}")
    print(f"  Tagline: {marca['tagline']}")
    print(f"  GPU: {DEVICE}")
    print(f"  Imágenes a generar: {len(imagenes)}")
    print(f"  Steps: {args.steps}")
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
                pipe, item, OUTPUT_DIR,
                steps=args.steps,
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
