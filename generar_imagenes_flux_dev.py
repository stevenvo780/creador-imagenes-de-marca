#!/usr/bin/env python3
"""
Generador de imágenes de marca para Agora / Elenxos — FLUX.1-dev (máxima calidad).

Usa FLUX.1-dev (Black Forest Labs) con cuantización NF4 en GPU local.
RTX 5070 Ti 16 GB: transformer NF4 ~6 GB + T5 bf16 ~10 GB via offload.

Uso:
    python generar_imagenes_flux_dev.py                  # genera todas
    python generar_imagenes_flux_dev.py --id linkedin_post_tesis
    python generar_imagenes_flux_dev.py --plataforma Instagram
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

from diffusers import BitsAndBytesConfig, FluxPipeline, FluxTransformer2DModel
from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
PROMPTS_FILE = SCRIPT_DIR / "prompts.json"
OUTPUT_DIR = SCRIPT_DIR / "output_flux_dev"

DEVICE = "cuda:0"
DTYPE = torch.bfloat16

MODEL_ID = "black-forest-labs/FLUX.1-dev"


def load_prompts(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_pipeline() -> FluxPipeline:
    """Carga FLUX.1-dev con transformer cuantizado NF4 (~6 GB VRAM)."""
    print(f"[INFO] Cargando transformer {MODEL_ID} en NF4 (4-bit) …")

    nf4_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=DTYPE,
    )

    transformer = FluxTransformer2DModel.from_pretrained(
        MODEL_ID,
        subfolder="transformer",
        quantization_config=nf4_config,
        torch_dtype=DTYPE,
    )

    print("[INFO] Cargando pipeline completo (T5, CLIP, VAE en bf16) …")
    pipe = FluxPipeline.from_pretrained(
        MODEL_ID,
        transformer=transformer,
        torch_dtype=DTYPE,
    )

    # model_cpu_offload: mueve T5/CLIP/VAE/transformer a GPU uno a uno.
    # Pico VRAM ≈ max(transformer_NF4 ~6 GB, T5_bf16 ~10 GB) ≈ 10 GB.
    pipe.enable_model_cpu_offload(gpu_id=0)

    print("[INFO] Modelo listo — FLUX.1-dev NF4, máxima calidad.\n")
    return pipe


def generar_imagen(
    pipe: FluxPipeline,
    item: dict,
    output_dir: Path,
    steps: int = 50,
    guidance: float = 3.5,
    seed: int | None = None,
) -> Path:
    """Genera una imagen con FLUX.1-dev y la escala al tamaño final."""
    target_w = item["ancho"]
    target_h = item["alto"]

    aspect = target_w / target_h

    # Resoluciones nativas de generación (múltiplo de 16).
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
    print(f"  Steps: {steps} | Guidance: {guidance} | Seq len: 512")

    with torch.inference_mode():
        result = pipe(
            prompt=prompt,
            width=gen_w,
            height=gen_h,
            num_inference_steps=steps,
            guidance_scale=guidance,
            max_sequence_length=512,
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
    parser = argparse.ArgumentParser(description="Generador FLUX.1-dev NF4 — Agora")
    parser.add_argument("--id", help="Generar solo la imagen con este ID")
    parser.add_argument("--plataforma", help="Generar solo imágenes de esta plataforma")
    parser.add_argument("--steps", type=int, default=50, help="Pasos de inferencia (default: 50)")
    parser.add_argument("--guidance", type=float, default=3.5, help="Guidance scale (default: 3.5)")
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
    print(f"  GENERADOR FLUX.1-dev NF4 — {marca['nombre_producto']}")
    print(f"  Marca corporativa: {marca['nombre_corporativo']}")
    print(f"  Tagline: {marca['tagline']}")
    print(f"  GPU: {DEVICE}")
    print(f"  Imágenes a generar: {len(imagenes)}")
    print(f"  Steps: {args.steps} | Guidance: {args.guidance}")
    print(f"  Cuantización: NF4 (4-bit) | Seq len: 512")
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
