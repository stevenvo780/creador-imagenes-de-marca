#!/usr/bin/env python3
"""
Renderiza tarjetas de publicacion desde Eikon hacia Yo/docs.

No crea marcas nuevas: carga una marca base, aplica overrides por tarjeta y
usa el motor HTML/CSS de render.py para producir PNGs listos para publicar.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
from pathlib import Path
from typing import Any

import render as brand_render


ROOT = Path(__file__).resolve().parent
DEFAULT_CARDS_FILE = ROOT / "publication_cards.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def deep_update(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base


def build_card_marca(card: dict[str, Any]) -> dict[str, Any]:
    marca = copy.deepcopy(brand_render.load_marca(card["marca"]))
    deep_update(marca, card.get("overrides", {}))

    layout_id = card.get("layout", "linkedin_post")
    textos = marca.setdefault("textos", {}).setdefault(layout_id, {})
    textos.update(card.get("textos", {}))
    return marca


async def render_cards(cards: list[dict[str, Any]], scale: int) -> None:
    layouts = {layout["id"]: layout for layout in brand_render.load_layouts()}

    async with brand_render.async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            for card in cards:
                layout_id = card.get("layout", "linkedin_post")
                if layout_id not in layouts:
                    raise ValueError(f"Layout no encontrado para {card['id']}: {layout_id}")

                marca = build_card_marca(card)
                layout = layouts[layout_id]
                vars_dict = brand_render.build_vars(marca, layout)
                output_path = Path(card["output"])

                print(f"[card] {card['id']} -> {output_path}")
                await brand_render.render_one(
                    browser=browser,
                    marca=marca,
                    layout=layout,
                    output_path=output_path,
                    vars_dict=vars_dict,
                    render_scale=scale,
                )
        finally:
            await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Renderiza tarjetas Eikon para publicaciones.")
    parser.add_argument("--cards-file", default=str(DEFAULT_CARDS_FILE))
    parser.add_argument("--only", action="append", help="ID de tarjeta a renderizar. Repetible.")
    parser.add_argument("--scale", type=int, default=1)
    args = parser.parse_args()

    data = load_json(Path(args.cards_file))
    cards = data.get("cards", [])
    if args.only:
        wanted = set(args.only)
        cards = [card for card in cards if card["id"] in wanted]

    if not cards:
        raise SystemExit("No hay tarjetas para renderizar.")
    if args.scale < 1:
        raise SystemExit("--scale debe ser >= 1")

    asyncio.run(render_cards(cards, args.scale))


if __name__ == "__main__":
    main()
