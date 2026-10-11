"""Exportaciones de signos existentes, sin escribir ni aprobar marcas remotas."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

_SVGS = re.compile(r"<svg\b[^>]*>.*?</svg>", re.DOTALL)


def _self_contained(fragment: str) -> str:
    if re.search(r"<script|<foreignObject|\son\w+=|\{", fragment, re.IGNORECASE):
        raise ValueError("SVG dinámico o activo: requiere revisión explícita")
    result = fragment
    if not re.search(r"\bxmlns=", fragment.split(">", 1)[0]):
        result = fragment.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
        if result == fragment:
            result = fragment.replace("<svg>", '<svg xmlns="http://www.w3.org/2000/svg">', 1)
    ET.fromstring(result)
    return result


def _receipt(fragment: str, svg: str, role: str) -> dict[str, Any]:
    return {
        "svg": svg,
        "source_fragment_sha256": hashlib.sha256(fragment.encode()).hexdigest(),
        "export_sha256": hashlib.sha256(svg.encode()).hexdigest(),
        "role": role,
        "state": "pending_visual_review",
        "production_mutated": False,
    }


def export_cauce(source: str) -> dict[str, Any]:
    candidates = []
    for fragment in _SVGS.findall(source):
        attribute = re.search(r'class=["\']([^"\']+)["\']', fragment.split(">", 1)[0])
        if attribute and "mark" in attribute.group(1).split():
            candidates.append(fragment)
    if len(candidates) != 1:
        raise ValueError("Se requiere exactamente un SVG class=mark")
    fragment = candidates[0]
    return _receipt(fragment, _self_contained(fragment), "existing_product_symbol")


def export_aletheia_glyph(source: str, css: str) -> dict[str, Any]:
    start = re.search(r"\bfunction Wordmark\(\)", source)
    if start is None:
        raise ValueError("No existe el componente Wordmark esperado")
    body = re.split(r"\nfunction\s+\w+\(", source[start.end() :], maxsplit=1)[0]
    candidates = _SVGS.findall(body)
    if len(candidates) != 1:
        raise ValueError("Se requiere exactamente un SVG en Wordmark")
    fragment = candidates[0]
    root = re.search(r":root\s*\{([^}]+)\}", css)
    color = re.search(r"--measure:\s*(#[0-9a-fA-F]{6})\s*;", root.group(1)) if root else None
    if color is None:
        raise ValueError("Token --measure claro no resuelto")
    converted = fragment.replace("strokeWidth=", "stroke-width=").replace(
        "strokeLinecap=", "stroke-linecap="
    )
    converted = converted.replace("var(--measure)", color.group(1))
    if "var(" in converted:
        raise ValueError("SVG conserva tokens sin resolver")
    receipt = _receipt(fragment, _self_contained(converted), "existing_ui_glyph_only")
    receipt.update(full_wordmark=False, resolved_tokens={"--measure": color.group(1)})
    return receipt


def export_aletheia_symbol(source: str, css: str) -> dict[str, Any]:
    """Recupera el cuadro y glifo actuales; rechaza geometrías distintas.

    La escala es la del componente con Tailwind estándar: rem=16, spacing=4,
    border=1. No reconstruye el nombre ni supone una marca nueva.
    """
    glyph = export_aletheia_glyph(source, css)
    start = re.search(r"\bfunction Wordmark\(\)", source)
    assert start is not None  # comprobado por el exportador del glifo
    body = re.split(r"\nfunction\s+\w+\(", source[start.end() :], maxsplit=1)[0]
    fragment = _SVGS.findall(body)[0]
    prefix = body[: body.index(fragment)]
    containers = re.findall(r"<span\b[^>]*className=\"([^\"]+)\"[^>]*>", prefix)
    expected = {
        "flex",
        "h-7",
        "w-7",
        "shrink-0",
        "items-center",
        "justify-center",
        "rounded-[var(--radius-sm)]",
        "border",
    }
    if not containers or set(containers[-1].split()) != expected:
        raise ValueError("Contenedor Aletheia distinto del símbolo revisado")
    container = re.findall(r"<span\b([^>]*)>", prefix)[-1]
    style = re.search(r"style=\{\{([^{}]+)\}\}", container)
    if style is None or not re.fullmatch(
        r"\s*borderColor:\s*'var\(--rule\)'\s*,\s*"
        r"backgroundColor:\s*'var\(--measure-soft\)'\s*,?\s*",
        style.group(1),
    ):
        raise ValueError("Estilo del contenedor Aletheia sin resolver")
    if re.search(r"\bfont-size\s*:|--spacing\s*:", css):
        raise ValueError("Escala CSS modificada: requiere revisar geometría")
    radius = re.findall(r"--radius-sm:\s*([^;]+);", css)
    if radius != ["0.25rem"]:
        raise ValueError("Radio del símbolo Aletheia sin resolver")
    root = re.search(r":root\s*\{([^}]+)\}", css)
    tokens = dict(glyph["resolved_tokens"])
    for token in ("--rule", "--measure-soft"):
        value = re.search(rf"{token}:\s*(#[0-9a-fA-F]{{6}})\s*;", root.group(1)) if root else None
        if value is None:
            raise ValueError(f"Token {token} claro no resuelto")
        tokens[token] = value.group(1)
    tree = ET.fromstring(glyph["svg"])
    if any(
        tree.attrib.get(k) != v
        for k, v in {
            "viewBox": "0 0 16 16",
            "width": "12",
            "height": "12",
            "fill": "none",
        }.items()
    ):
        raise ValueError("Geometría del glifo Aletheia distinta")
    inner = glyph["svg"].replace("<svg ", '<svg x="8" y="8" ', 1)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28" width="28" height="28">'
        '<rect x="0.5" y="0.5" width="27" height="27" rx="3.5" '
        f'fill="{tokens["--measure-soft"]}" stroke="{tokens["--rule"]}" stroke-width="1"/>'
        f"{inner}</svg>"
    )
    result = _receipt(body, _self_contained(svg), "existing_product_symbol")
    result.update(
        full_wordmark=False,
        resolved_tokens=tokens,
        geometry={"outer_px": 28, "glyph_px": 12, "border_px": 1, "radius_px": 4},
        scale_assumptions={"root_rem_px": 16, "tailwind_spacing_px": 4},
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cauce-source", type=Path, required=True)
    parser.add_argument("--aletheia-source", type=Path, required=True)
    parser.add_argument("--aletheia-css", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cauce_text = args.cauce_source.read_text()
    aletheia_text = args.aletheia_source.read_text()
    css_text = args.aletheia_css.read_text()
    items = [
        ("cauce-simbolo-existente.svg", export_cauce(cauce_text), [args.cauce_source]),
        (
            "aletheia-glifo-existente-claro.svg",
            export_aletheia_glyph(aletheia_text, css_text),
            [args.aletheia_source, args.aletheia_css],
        ),
        (
            "aletheia-simbolo-existente-claro.svg",
            export_aletheia_symbol(aletheia_text, css_text),
            [args.aletheia_source, args.aletheia_css],
        ),
    ]
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = []
    for filename, result, sources in items:
        svg = result.pop("svg")
        (args.output / filename).write_text(svg)
        result["file"] = filename
        result["sources"] = [
            {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in sources
        ]
        manifest.append(result)
    (args.output / "provenance.json").write_text(
        json.dumps({"production_mutated": False, "items": manifest}, indent=2)
    )
    print(
        json.dumps(
            {"exports": len(items), "state": "pending_visual_review", "production_mutated": False}
        )
    )


if __name__ == "__main__":
    main()
