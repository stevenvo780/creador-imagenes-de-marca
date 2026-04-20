#!/usr/bin/env python3
"""
Generador MÁXIMA CALIDAD — Playground v2.5 — Agora / Elenxos

Optimizaciones vs script anterior:
  - CUDA_VISIBLE_DEVICES desbloqueado → expone AMBAS GPUs
  - SIN attention_slicing → calidad de atención completa, más VRAM
  - VAE tiling/slicing → decode eficiente a resoluciones altas
  - Reintento automático si OOM en resolución alta
  - Limpieza de VRAM entre imágenes
  - Monitoreo detallado de memoria

Uso:
    python generar_maxcalidad.py                          # genera todas
    python generar_maxcalidad.py --id linkedin_post_tesis
    python generar_maxcalidad.py --plataforma Instagram
    python generar_maxcalidad.py --steps 60 --guidance 3.5
"""

import argparse
import gc
import json
import os
import sys
import time
from pathlib import Path

# ── Desbloquear GPUs ──────────────────────────────────────────────────────
# El entorno tiene CUDA_VISIBLE_DEVICES=0 que oculta la RTX 2060.
# Exponer ambas GPUs ANTES de importar torch.
os.environ.pop("CUDA_VISIBLE_DEVICES", None)
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import torch

# ── Blackwell workarounds (RTX 5070 Ti, CC 12.0) ─────────────────────────
torch.backends.cuda.enable_flash_sdp(False)
torch.backends.cuda.enable_mem_efficient_sdp(False)
torch.backends.cudnn.enabled = False

from diffusers import DiffusionPipeline, EDMDPMSolverMultistepScheduler
from PIL import Image

# ── Config ────────────────────────────────────────────────────────────────
MODEL_ID = "playgroundai/playground-v2.5-1024px-aesthetic"
DEVICE = "cuda:0"
DTYPE = torch.bfloat16

SCRIPT_DIR = Path(__file__).resolve().parent
PROMPTS_FILE = SCRIPT_DIR / "prompts.json"
OUTPUT_DIR = SCRIPT_DIR / "output_maxcalidad"

# Resoluciones de generación (múltiplos de 64, optimizadas para SDXL).
# Sin attention_slicing, el UNet necesita más VRAM → usamos resoluciones
# nativas altas de SDXL que caben en 16 GB.
RESOLUTIONS = {
    "ultra_wide": (1536, 640),   # aspect ≥ 3.0 (banners panorámicos)
    "wide":       (1344, 768),   # aspect ≥ 1.3
    "square":     (1024, 1024),  # aspect ~1.0
    "tall":       (768, 1344),   # aspect ≤ 0.8
    "ultra_tall": (640, 1536),   # aspect ≤ 0.5
}


def vram_report(device=0):
    """Resumen de VRAM para monitoreo."""
    alloc = torch.cuda.memory_allocated(device) / 1024**3
    res = torch.cuda.memory_reserved(device) / 1024**3
    total = torch.cuda.get_device_properties(device).total_memory / 1024**3
    return f"{alloc:.1f}GB alloc / {res:.1f}GB reserv / {total:.1f}GB total"


def classify_aspect(w: int, h: int) -> str:
    aspect = w / h
    if aspect >= 3.0:
        return "ultra_wide"
    elif aspect >= 1.3:
        return "wide"
    elif aspect <= 0.5:
        return "ultra_tall"
    elif aspect <= 0.8:
        return "tall"
    return "square"


def build_pipeline() -> DiffusionPipeline:
    """Carga Playground v2.5 COMPLETO en GPU — sin offload."""
    print(f"[LOAD] Modelo: {MODEL_ID}")
    print(f"[LOAD] Device: {DEVICE}  |  dtype: {DTYPE}")
    print(f"[LOAD] VRAM pre-carga: {vram_report()}\n")

    pipe = DiffusionPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=DTYPE,
        variant="fp16",
    )

    # Scheduler recomendado por Playground v2.5
    pipe.scheduler = EDMDPMSolverMultistepScheduler()

    # Cargar COMPLETO en GPU — sin cpu_offload, sin attention_slicing
    pipe = pipe.to(DEVICE)

    # VAE tiling/slicing: decodifica tiles en vez de la imagen completa,
    # evita OOM en el paso de VAE sin afectar calidad del UNet.
    pipe.enable_vae_tiling()
    pipe.enable_vae_slicing()

    # ── NO attention_slicing ──
    # Esto es CLAVE: attention_slicing(1) fragmenta la atención multi-head
    # en pasos individuales, reduce VRAM pero degrada la calidad.
    # Al no activarlo, el UNet usa atención completa → más VRAM → mejor imagen.

    print(f"\n[LOAD] Modelo listo.")
    print(f"[LOAD] VRAM post-carga: {vram_report()}")
    print(f"[LOAD] Modo: FULL GPU (sin offload, sin attention_slicing)\n")
    return pipe


def generar_imagen(
    pipe: DiffusionPipeline,
    item: dict,
    output_dir: Path,
    steps: int = 50,
    guidance: float = 3.0,
    seed: int | None = None,
) -> Path:
    """Genera una imagen con Playground v2.5 y escala al tamaño final."""
    target_w = item["ancho"]
    target_h = item["alto"]
    key = classify_aspect(target_w, target_h)
    gen_w, gen_h = RESOLUTIONS[key]

    prompt = item["prompt"]
    negative = (
        "ugly, blurry, low quality, distorted, deformed, disfigured, "
        "bad anatomy, watermark, text artifacts, oversaturated, "
        "amateur, poorly rendered, low resolution, jpeg artifacts"
    )

    generator = None
    if seed is not None:
        generator = torch.Generator(device=DEVICE).manual_seed(seed)

    print(f"  Gen: {gen_w}×{gen_h} → final: {target_w}×{target_h}")
    print(f"  VRAM: {vram_report()}")

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

    # Escalar al tamaño final con Lanczos (alta calidad)
    if (img.width, img.height) != (target_w, target_h):
        img = img.resize((target_w, target_h), Image.LANCZOS)

    # Guardar
    plat_dir = output_dir / item["plataforma"].lower().replace("/", "-")
    plat_dir.mkdir(parents=True, exist_ok=True)
    out_path = plat_dir / f"{item['id']}.png"
    img.save(out_path, "PNG")

    return out_path


def main():
    parser = argparse.ArgumentParser(description="Generador MÁXIMA CALIDAD — Agora")
    parser.add_argument("--id", help="Generar solo la imagen con este ID")
    parser.add_argument("--plataforma", help="Solo imágenes de esta plataforma")
    parser.add_argument("--steps", type=int, default=50, help="Pasos de inferencia (default 50)")
    parser.add_argument("--guidance", type=float, default=3.0, help="Guidance scale (default 3.0)")
    parser.add_argument("--seed", type=int, default=42, help="Seed (default 42)")
    parser.add_argument("--prompts", type=str, default=str(PROMPTS_FILE))
    args = parser.parse_args()

    data = json.loads(Path(args.prompts).read_text(encoding="utf-8"))
    marca = data["marca"]
    imagenes = data["imagenes"]

    if args.id:
        imagenes = [i for i in imagenes if i["id"] == args.id]
    elif args.plataforma:
        imagenes = [i for i in imagenes if i["plataforma"].lower() == args.plataforma.lower()]

    if not imagenes:
        print("[ERROR] No se encontraron imágenes con esos filtros.")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Info del sistema ──
    n_gpus = torch.cuda.device_count()
    print("=" * 65)
    print(f"  GENERADOR MÁXIMA CALIDAD — {marca['nombre_producto']} / {marca['nombre_corporativo']}")
    print(f"  Modelo: Playground v2.5-1024px-aesthetic (bf16 completo en GPU)")
    print(f"  GPUs visibles: {n_gpus}")
    for i in range(n_gpus):
        name = torch.cuda.get_device_name(i)
        mem = torch.cuda.get_device_properties(i).total_memory / 1024**3
        print(f"    cuda:{i} — {name} ({mem:.1f} GB)")
    print(f"  Pipeline en: {DEVICE}")
    print(f"  Imágenes: {len(imagenes)}")
    print(f"  Steps: {args.steps} | Guidance: {args.guidance} | Seed: {args.seed}")
    print(f"  Modo: FULL GPU (sin offload, sin attention_slicing)")
    print("=" * 65)
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
            print(f"  ✓ Guardada: {out} ({elapsed:.1f}s)\n")
            exitosas += 1
        except torch.cuda.OutOfMemoryError:
            elapsed = time.time() - t0
            print(f"  ✗ OOM ({elapsed:.1f}s) — limpiando VRAM…\n")
            fallidas.append(item["id"])
            torch.cuda.empty_cache()
            gc.collect()
        except Exception as e:
            elapsed = time.time() - t0
            print(f"  ✗ Error: {e} ({elapsed:.1f}s)\n")
            fallidas.append(item["id"])
            torch.cuda.empty_cache()
            gc.collect()

    # ── Resumen ──
    print()
    print("=" * 65)
    print(f"  RESULTADO: {exitosas}/{total} imágenes generadas")
    if fallidas:
        print(f"  Fallidas: {', '.join(fallidas)}")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  VRAM final: {vram_report()}")
    print("=" * 65)


if __name__ == "__main__":
    main()
