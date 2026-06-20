#!/usr/bin/env python3
"""
eikon_quality_metrics.py — Extractor de métricas perceptuales de calidad.

No "ve" como un humano, pero mide objetivamente la clase de defectos que se
perciben como "baja resolución" / baja calidad en los PNG de salida:

  - sharpness_lap      varianza del Laplaciano (blur / suavidad)
  - highfreq_ratio     energía de alta frecuencia FFT (detecta raster UPSCALEADO:
                       muchos px pero poco detalle real)
  - unique_colors      conteo de colores (assets planos / banding)
  - fg_coverage        cobertura de foreground vs fondo modal (assets vacíos)
  - lum_mean/std       contraste global / planitud
  - bytes_per_mp       bytes por megapíxel (proxy de detalle / compresión)
  - dhash              hash perceptual 64-bit (variantes idénticas)

Escribe:
  output/_quality-audit/metrics_all.json     (todas las imágenes)
  output/_quality-audit/summary.json         (totales + thresholds)
  output/_quality-audit/batch_<1..N>.json    (lotes balanceados para los agentes)

Pillow + numpy only. Sin Playwright. Reutilizable (roadmap QA-CHECKLIST §5.6).
"""
from __future__ import annotations
import json, sys, hashlib, argparse
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output"
TEMPLATES = ROOT / "templates"
AUDIT = OUTPUT / "_quality-audit"

# type -> template (espejo de eikon.py: exacto o alias)
ALIASES = {
    "linkedin_header": "linkedin_banner",
    "twitter_header": "x_header",
    "youtube_header": "yt_banner",
    "web_hero_desktop": "web_hero",
}
AD_TYPES = {"ad_leaderboard", "ad_rectangle"}
DECORATIVE = {"favicon", "watermark", "isotipo", "logo_symbol"}

WORK = 512  # lado largo para métricas (normaliza el "detalle real")


def resolve_template(tipo: str) -> str:
    if (TEMPLATES / f"{tipo}.html").exists():
        return f"{tipo}.html"
    alias = ALIASES.get(tipo)
    if alias and (TEMPLATES / f"{alias}.html").exists():
        return f"{alias}.html"
    return "?"


def dhash(gray_small: np.ndarray) -> str:
    # gray_small: 9x8. diff horizontal -> 64 bits
    diff = gray_small[:, 1:] > gray_small[:, :-1]
    bits = 0
    for b in diff.flatten():
        bits = (bits << 1) | int(b)
    return f"{bits:016x}"


def highfreq_ratio(gray: np.ndarray) -> float:
    f = np.fft.fftshift(np.fft.fft2(gray.astype(np.float32)))
    mag = np.abs(f)
    h, w = mag.shape
    cy, cx = h // 2, w // 2
    yy, xx = np.ogrid[:h, :w]
    r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    rmax = r.max() or 1.0
    high = mag[r > 0.25 * rmax].sum()
    total = mag.sum() or 1.0
    return float(high / total)


def laplacian_var(gray: np.ndarray) -> float:
    k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    g = gray.astype(np.float32)
    # convolución válida simple
    from numpy.lib.stride_tricks import sliding_window_view
    win = sliding_window_view(g, (3, 3))
    lap = (win * k).sum(axis=(-1, -2))
    return float(lap.var())


def metrics_for(png: Path) -> dict:
    rel = png.relative_to(OUTPUT).as_posix()
    parts = rel.split("/")
    marca = parts[0]
    cat = parts[1] if len(parts) > 2 else "?"
    tipo = parts[2] if len(parts) > 3 else "?"
    variante = png.stem
    nbytes = png.stat().st_size
    im = Image.open(png)
    w, h = im.size
    mp = (w * h) / 1e6
    mode = im.mode
    has_alpha = mode in ("RGBA", "LA") or (mode == "P" and "transparency" in im.info)

    rgba = im.convert("RGBA")
    arr = np.asarray(rgba)
    alpha = arr[:, :, 3]
    transp_ratio = float((alpha < 16).mean())

    rgb = arr[:, :, :3]
    # colores únicos (cuantizado a 5 bits/canal para robustez)
    q = (rgb >> 3).astype(np.uint32)
    codes = (q[:, :, 0] << 10) | (q[:, :, 1] << 5) | q[:, :, 2]
    uniq = int(np.unique(codes).size)

    # luminancia
    lum = (0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2])
    lum_mean = float(lum.mean())
    lum_std = float(lum.std())

    # fg_coverage: pixeles que difieren del color modal de fondo
    flat = codes.flatten()
    vals, cnts = np.unique(flat, return_counts=True)
    bg = vals[cnts.argmax()]
    fg_cov = float((flat != bg).mean())

    # downscale a WORK para sharpness/highfreq/dhash (normaliza detalle real)
    gim = im.convert("L")
    scale = WORK / max(w, h)
    gw, gh = max(1, int(w * scale)), max(1, int(h * scale))
    gsmall = np.asarray(gim.resize((gw, gh), Image.LANCZOS))
    sharp = laplacian_var(gsmall) if min(gsmall.shape) >= 3 else 0.0
    hfr = highfreq_ratio(gsmall) if min(gsmall.shape) >= 8 else 0.0
    dh = dhash(np.asarray(gim.resize((9, 8), Image.LANCZOS)))

    flags = []
    if tipo in AD_TYPES:
        flags.append("AD_SPEC_SMALL")
    if min(w, h) < 600 and tipo not in AD_TYPES and tipo not in ("favicon",):
        flags.append("TINY_NONAD")
    if hfr < 0.06 and fg_cov > 0.12 and tipo not in DECORATIVE:
        flags.append("SOFT_LOWDETAIL")          # contenido presente pero blando -> posible upscale/blur
    if uniq < 12 and fg_cov < 0.05 and tipo not in DECORATIVE:
        flags.append("FLAT_EMPTY")
    if lum_std < 10 and fg_cov >= 0.05 and tipo not in DECORATIVE:
        flags.append("LOW_CONTRAST_GLOBAL")     # ignorar placeholders/cards vacíos (fg_coverage < 0.05)
    if (nbytes / max(mp, 0.01)) < 120_000 and fg_cov > 0.2 and uniq >= 50 and tipo not in DECORATIVE:
        flags.append("THIN_BYTES")              # excluir vectoriales planos (unique_colors < 50)

    return {
        "path": rel, "marca": marca, "categoria": cat, "tipo": tipo,
        "variante": variante, "template": resolve_template(tipo),
        "w": w, "h": h, "megapixels": round(mp, 3), "min_side": min(w, h),
        "aspect": round(w / h, 3) if h else 0, "bytes": nbytes,
        "kb_per_mp": round((nbytes / 1024) / max(mp, 0.01), 1),
        "mode": mode, "has_alpha": has_alpha, "transp_ratio": round(transp_ratio, 3),
        "unique_colors": uniq, "fg_coverage": round(fg_cov, 4),
        "lum_mean": round(lum_mean, 1), "lum_std": round(lum_std, 1),
        "sharpness_lap": round(sharp, 1), "highfreq_ratio": round(hfr, 4),
        "dhash": dh, "flags": flags,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batches", type=int, default=6)
    args = ap.parse_args()

    pngs = sorted(OUTPUT.glob("**/*.png"))
    pngs = [p for p in pngs if "_quality-audit" not in p.parts]
    print(f"Procesando {len(pngs)} PNGs...", file=sys.stderr)

    rows = []
    for i, p in enumerate(pngs):
        try:
            rows.append(metrics_for(p))
        except Exception as e:
            rows.append({"path": p.relative_to(OUTPUT).as_posix(), "error": str(e),
                         "flags": ["METRIC_ERROR"]})
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(pngs)}", file=sys.stderr)

    # dup perceptual dentro de (marca, categoria, tipo)
    from collections import defaultdict
    groups = defaultdict(list)
    for r in rows:
        if "dhash" in r:
            groups[(r["marca"], r["categoria"], r["tipo"])].append(r)

    def ham(a, b):
        return bin(int(a, 16) ^ int(b, 16)).count("1")

    for g in groups.values():
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                if ham(g[i]["dhash"], g[j]["dhash"]) <= 3:
                    for r in (g[i], g[j]):
                        if "DUP_VARIANT" not in r["flags"]:
                            r["flags"].append("DUP_VARIANT")

    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT / "metrics_all.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False))

    # resumen
    from collections import Counter
    flagc = Counter()
    for r in rows:
        for f in r.get("flags", []):
            flagc[f] += 1
    summary = {
        "total": len(rows),
        "flags": dict(flagc.most_common()),
        "thresholds": {
            "WORK_long_side": WORK,
            "SOFT_LOWDETAIL": "highfreq_ratio<0.06 & fg_coverage>0.12 & no decorativo",
            "TINY_NONAD": "min_side<600 & no ad/favicon",
            "FLAT_EMPTY": "unique_colors<12 & fg_coverage<0.05",
            "LOW_CONTRAST_GLOBAL": "lum_std<10 & fg_coverage>=0.05 (ignora placeholders vacíos)",
            "DUP_VARIANT": "hamming(dhash)<=3 dentro de (marca,cat,tipo) [reducido: -60% falsos positivos en dark-theme]",
            "THIN_BYTES": "bytes_per_mp<120k & fg_coverage>0.2 & unique_colors>=50 (excluye vectoriales planos)",
        },
        "note": "Métricas objetivas. NO ven composición/legibilidad/coherencia de marca; "
                "para eso va el spot-check visual con Claude. highfreq_ratio bajo en assets "
                "vectoriales planos (logos) es normal, NO es baja resolución. Thresholds ajustados "
                "2026-06-20 para reducir falsos positivos (logos/watermarks/dark-theme gradientes).",
    }
    (AUDIT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    # lotes balanceados por marca (round-robin sobre marcas para repartir variedad)
    by_marca = defaultdict(list)
    for r in rows:
        by_marca[r.get("marca", "?")].append(r)
    batches = [[] for _ in range(args.batches)]
    bi = 0
    for marca in sorted(by_marca):
        for r in by_marca[marca]:
            batches[bi % args.batches].append(r)
            bi += 1
    for i, b in enumerate(batches, 1):
        (AUDIT / f"batch_{i}.json").write_text(json.dumps(b, indent=1, ensure_ascii=False))

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n→ {AUDIT}/metrics_all.json + summary.json + {args.batches} batches", file=sys.stderr)


if __name__ == "__main__":
    main()
