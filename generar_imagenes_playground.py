#!/usr/bin/env python3
"""
Generador de imágenes de marca para Agora / Elenxos — Playground v2.5 (máxima calidad).

Playground v2.5-1024px-aesthetic: mismo UNet que SDXL pero entrenado
específicamente para calidad estética superior. Gana consistentemente en
preferencia humana vs SDXL, DALL-E 3 y Midjourney v5.2.

Sin restricciones de acceso. Modelo cargado directo en GPU para
aprovechar toda la VRAM (≈14 GB de 16 GB en RTX 5070 Ti).

Uso:
    python generar_imagenes_playground.py                  # genera todas
    python generar_imagenes_playground.py --id linkedin_post_tesis
    python generar_imagenes_playground.py --plataforma Instagram
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch

# Desactivar backends problemáticos en Blackwell (RTX 5070 Ti, CC 12.0)
torch.backends.cuda.enable_flash_sdp(False)
torch.backends.cuda.enable_mem_efficient_sdp(False)
torch.backends.cudnn.enabled = False

from diffusers import DiffusionPipeline, EDMDPMSolverMultistepScheduler
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
PROMPTS_FILE = SCRIPT_DIR / "prompts.json"
OUTPUT_DIR = SCRIPT_DIR / "output_playground"

DEVICE = "cuda:0"
DTYPE = torch.bfloat16

MODEL_ID = "playgroundai/playground-v2.5-1024px-aesthetic"


def load_prompts(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_pipeline() -> DiffusionPipeline:
    """Carga Playground v2.5 directo en GPU — sin offload, máxima VRAM."""
    print(f"[INFO] Cargando {MODEL_ID} en {DEVICE} ({DTYPE}) …")
    print("[INFO] Sin CPU offload → máximo uso de VRAM para calidad.\n")

    pipe = DiffusionPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=DTYPE,
        variant="fp16",  # Descarga los pesos fp16 (más ligeros)
    )

    # Scheduler recomendado para Playground v2.5
    pipe.scheduler = EDMDPMSolverMultistepScheduler()

    # Cargar directo en GPU sin offload: ~14 GB, cabe en 16 GB.
    pipe = pipe.to(DEVICE)

    # Optimización de atención
    pipe.enable_attention_slicing(1)

    print("[INFO] Modelo listo — Playground v2.5, cargado en GPU.\n")
    return pipe


def generar_imagen(
    pipe: DiffusionPipeline,
    item: dict,
    output_dir: Path,
    steps: int = 50,
    guidance: float = 3.0,
    seed: int | None = None,
) -> Path:
    """Genera una imagen con Playground v2.5 y la escala al tamaño final."""
    target_w = item["ancho"]
    target_h = item["alto"]

    aspect = target_w / target_h

    # Resoluciones de generación nativas (SDXL base).
    if aspect >= 2.5:
        gen_w, gen_h = 1536, 640
    elif aspect >= 1.5:
        gen_w, gen_h = 1344, 768
    elif aspect <= 0.6:
        gen_w, gen_h = 768, 1344
    else:
        gen_w, gen_h = 1024, 1024

    prompt = item["prompt"]
    # Playground v2.5 responde bien a negative prompts estéticos
    negative = (
        "ugly, blurry, low quality, distorted, deformed, disfigured, "
        "bad anatomy, watermark, text artifacts, oversaturated, "
        "amateur, poorly rendered"
    )

    generator = None
    if seed is not None:
        generator = torch.Generator(device=DEVICE).manual_seed(seed)

    print(f"  Generando a {gen_w}×{gen_h} → reescalar a {target_w}×{target_h}")
    print(f"  Steps: {steps} | Guidance: {guidance}")

    with torch.inference_mode():
        result = pipe(
            prompt=prompt,
            negative_prompt=negative,
            width=gen_w,
            height=gen_h,
            num_inference_steps=steps,
            guidance_scale=guidance,
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
    parser = argparse.ArgumentParser(description="Generador Playground v2.5 — Agora")
    parser.add_argument("--id", help="Generar solo la imagen con este ID")
    parser.add_argument("--plataforma", help="Generar solo imágenes de esta plataforma")
    parser.add_argument("--steps", type=int, default=50, help="Pasos de inferencia (default: 50)")
    parser.add_argument("--guidance", type=float, default=3.0, help="Guidance scale (default: 3.0)")
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
    print(f"  GENERADOR Playground v2.5 — {marca['nombre_producto']}")
    print(f"  Marca corporativa: {marca['nombre_corporativo']}")
    print(f"  Tagline: {marca['tagline']}")
    print(f"  GPU: {DEVICE} (directo, sin offload)")
    print(f"  Imágenes a generar: {len(imagenes)}")
    print(f"  Steps: {args.steps} | Guidance: {args.guidance}")
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
