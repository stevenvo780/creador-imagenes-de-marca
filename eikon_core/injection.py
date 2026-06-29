from __future__ import annotations


def injection_script(
    vars_dict: dict[str, str], variant_name: str = "", template_name: str = ""
) -> str:
    """JS que inyecta los valores de marca en vivo dentro del template renderizado."""
    css_map = {
        "--primario": "primario",
        "--acento": "acento",
        "--acento-2": "acento_2",
        "--texto": "texto",
        "--bg": "bg",
        "--font-titulo": "font_titulo",
        "--font-cuerpo": "font_cuerpo",
    }
    attr_map = {
        "data-logo-simbolo": "logo_simbolo",
        "data-logo-texto": "logo_texto",
        "data-titulo": "titulo",
        "data-subtitulo": "subtitulo",
        "data-copy": "copy",
        "data-url": "url",
        "data-etiqueta": "etiqueta",
        "data-numero": "numero",
        "data-etiqueta-2": "etiqueta_2",
        "data-numero-2": "numero_2",
    }

    lines = ["(() => {", "  const root = document.documentElement;"]
    for css_var, key in css_map.items():
        lines.append(f"  root.style.setProperty('{css_var}', '{vars_dict.get(key, '')}');")

    if variant_name:
        lines.append(f"  document.body.dataset.variant = '{variant_name}';")
    if template_name:
        lines.append(f"  document.body.dataset.template = '{template_name}';")

    for attr, key in attr_map.items():
        value = vars_dict.get(key, "").replace("'", "\\'")
        lines.append(
            f"  document.querySelectorAll('[{attr}]').forEach(el => {{ el.textContent = '{value}'; }});"
        )

    lines.append("  if (window.__eikonVariantRefresh) window.__eikonVariantRefresh();")
    lines.append("})();")
    return "\n".join(lines)
