#!/usr/bin/env python3
"""
Sincroniza assets de Eikon hacia Yo/docs/06-contenido/publicaciones.

Hace dos cosas:
1. Crea un catalogo de productos con 3 imagenes por cada marca/proyecto Eikon.
2. Rellena los posts narrativos actuales hasta llegar a minimo 3 imagenes.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
MARCAS = ROOT / "marcas"
PUBLICACIONES = Path("/workspace/Yo/docs/06-contenido/publicaciones")
LINKEDIN_POSTS = PUBLICACIONES / "linkedin"
PRODUCTOS = PUBLICACIONES / "productos"

PRODUCT_IMAGE_SET = [
    ("01-linkedin-post.png", "linkedin/linkedin_post.png"),
    ("02-open-graph.png", "web/og_general.png"),
    ("03-instagram-post.png", "instagram/ig_post.png"),
]

POST_SUPPLEMENT_SET = [
    ("eikon-supp-01-linkedin-post.png", "linkedin/linkedin_post.png"),
    ("eikon-supp-02-open-graph.png", "web/og_general.png"),
    ("eikon-supp-03-instagram-post.png", "instagram/ig_post.png"),
]

POST_TO_MARCA = {
    "bloque-1-agora/01-agora-la-plataforma": "agora",
    "bloque-1-agora/02-agora-st-lenguaje-logica-ejecutable": "agora-st",
    "bloque-1-agora/03-agora-autologic-texto-a-logica": "agora-autologic",
    "bloque-1-agora/04-agora-logiceducation": "agora-elenxos",
    "bloque-1-agora/05-agora-ultimate-terminal": "pinakotheke-techne",
    "bloque-1-agora/06-agora-mcp-delegate-agents": "agora",
    "bloque-2-suites/07-prizma-sinergia-pos": "prizma",
    "bloque-2-suites/08-prizma-graf-tienda-online": "prizma-talos",
    "bloque-2-suites/09-prizma-fiar-credito-comercios": "prizma-pistis",
    "bloque-2-suites/10-prizma-emw-whatsapp-pymes": "prizma-hermes",
    "bloque-2-suites/11-prizma-cristina-cms": "pinakotheke-aporia",
    "bloque-2-suites/12-prizma-symploque-crm": "prizma",
    "bloque-2-suites/13-pinakotheke-helenikos-griego": "pinakotheke-paideia",
    "bloque-3-publico/14-agora-estructuras-preontologicas": "pinakotheke-estructuras-preontologicas",
    "bloque-3-publico/15-agora-animacion-edi-shock": "pinakotheke-estructuras-preontologicas",
    "bloque-3-publico/16-agora-campo-abm": "pinakotheke-kosmos",
    "bloque-3-publico/17-agora-seir": "pinakotheke-kosmos",
    "bloque-3-publico/18-agora-fenomenologia-urbana": "pinakotheke-kosmos",
    "bloque-3-publico/19-agora-complejidad-algoritmos": "pinakotheke-hinton",
    "bloque-3-publico/20-agora-redes-neuronales-filosofia": "pinakotheke-hinton",
    "bloque-3-publico/21-personal-jarvis-ia-local": "pinakotheke-daimon",
    "bloque-3-publico/22-personal-kratos-jarvis-v2": "pinakotheke-techne",
    "bloque-3-publico/23-marca-cafeteria-del-caos": "pinakotheke-agon",
    "bloque-3-publico/24-marca-abstraccion-blog": "pinakotheke-schole",
    "bloque-3-publico/25-marca-sitios-personales": "steven-vallejo",
    "bloque-4-carrera/26-carrera-2014-infraestructura-it": "steven-vallejo-informatico",
    "bloque-4-carrera/27-carrera-2015-gamedev": "steven-vallejo-informatico",
    "bloque-4-carrera/28-carrera-2016-iqpixels-gestion": "steven-vallejo",
    "bloque-4-carrera/29-carrera-2018-sena-sipaem": "steven-vallejo",
    "bloque-4-carrera/30-carrera-2019-ins-kambban-zenit": "steven-vallejo-informatico",
    "bloque-4-carrera/31-carrera-2021-finca-directa-rpa": "steven-vallejo-informatico",
    "bloque-4-carrera/32-carrera-2023-soy-digital-indotel": "steven-vallejo-informatico",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def group_for_slug(slug: str) -> str:
    if slug.startswith("agora"):
        return "agora-elenxos"
    if slug.startswith("pinakotheke"):
        return "pinakotheke"
    if slug.startswith("prizma"):
        return "prizma"
    if slug.startswith("steven"):
        return "steven-vallejo"
    return "otros"


def copy_asset(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def image_count(post_dir: Path) -> int:
    img_dir = post_dir / "imagenes"
    return len([p for p in img_dir.glob("*") if p.is_file()]) if img_dir.exists() else 0


def sync_product_catalog() -> list[dict]:
    rows: list[dict] = []
    for marca_file in sorted(MARCAS.glob("*.json")):
        slug = marca_file.stem
        marca = load_json(marca_file)
        group = group_for_slug(slug)
        target = PRODUCTOS / group / slug
        image_dir = target / "imagenes"

        for out_name, source_rel in PRODUCT_IMAGE_SET:
            copy_asset(OUTPUT / slug / source_rel, image_dir / out_name)

        readme = [
            f"# {marca.get('nombre_producto', slug)}",
            "",
            f"- Marca Eikon: `{slug}`",
            f"- Ecosistema: {marca.get('nombre_corporativo') or group}",
            f"- URL: {marca.get('url_producto') or marca.get('url') or marca.get('url_corporativa') or 'pendiente'}",
            f"- Tagline: {marca.get('tagline') or 'pendiente'}",
            "",
            "## Imagenes listas",
            "",
            "| Uso | Archivo |",
            "|---|---|",
            "| LinkedIn / paisaje | `imagenes/01-linkedin-post.png` |",
            "| Open Graph / web | `imagenes/02-open-graph.png` |",
            "| Instagram / cuadrado | `imagenes/03-instagram-post.png` |",
            "",
        ]
        (target / "README.md").write_text("\n".join(readme), encoding="utf-8")

        rows.append(
            {
                "slug": slug,
                "group": group,
                "name": marca.get("nombre_producto", slug),
                "url": marca.get("url_producto") or marca.get("url") or marca.get("url_corporativa") or "",
            }
        )
    return rows


def write_product_index(rows: list[dict]) -> None:
    lines = [
        "# Catalogo de productos para publicar",
        "",
        "Generado desde Eikon. Cada producto tiene minimo 3 imagenes listas:",
        "",
        "- `01-linkedin-post.png`",
        "- `02-open-graph.png`",
        "- `03-instagram-post.png`",
        "",
        f"Total productos: {len(rows)}",
        "",
    ]
    for group in sorted({row["group"] for row in rows}):
        lines += [f"## {group}", "", "| Producto | Marca | URL | Imagenes |", "|---|---|---|---|"]
        for row in [r for r in rows if r["group"] == group]:
            rel = f"{row['group']}/{row['slug']}"
            url = row["url"] or "pendiente"
            lines.append(f"| {row['name']} | `{row['slug']}` | {url} | [{rel}]({rel}/) |")
        lines.append("")
    (PRODUCTOS / "INDICE.md").write_text("\n".join(lines), encoding="utf-8")


def supplement_story_posts() -> list[tuple[str, int]]:
    results: list[tuple[str, int]] = []
    for rel, marca_slug in POST_TO_MARCA.items():
        post_dir = LINKEDIN_POSTS / rel
        if not post_dir.exists():
            raise FileNotFoundError(post_dir)

        img_dir = post_dir / "imagenes"
        img_dir.mkdir(parents=True, exist_ok=True)

        for out_name, source_rel in POST_SUPPLEMENT_SET:
            if image_count(post_dir) >= 3:
                break
            target = img_dir / out_name
            if target.exists():
                continue
            copy_asset(OUTPUT / marca_slug / source_rel, target)

        results.append((rel, image_count(post_dir)))
    return results


def main() -> None:
    rows = sync_product_catalog()
    write_product_index(rows)
    story_counts = supplement_story_posts()

    below = [(rel, count) for rel, count in story_counts if count < 3]
    print(f"Productos sincronizados: {len(rows)}")
    print(f"Posts narrativos revisados: {len(story_counts)}")
    print(f"Posts bajo 3 imagenes: {len(below)}")
    for rel, count in below:
        print(f"  {rel}: {count}")


if __name__ == "__main__":
    main()
