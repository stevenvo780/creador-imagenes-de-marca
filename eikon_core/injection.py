from __future__ import annotations

import json

_CSS_MAP = {
    "--primario": "primario",
    "--acento": "acento",
    "--acento-2": "acento_2",
    "--texto": "texto",
    "--bg": "bg",
    "--font-titulo": "font_titulo",
    "--font-cuerpo": "font_cuerpo",
    "--font-size-scale": "font_size_scale",
    "--space-scale": "space_scale",
    "--corner-radius": "corner_radius",
}
_ATTR_MAP = {
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


def _js_payload(obj: dict[str, object]) -> str:
    """Serializa a un literal JS SEGURO.

    Usamos json.dumps (escapa comillas, backslashes, saltos de línea) + neutralizamos
    la secuencia ``</`` para que un valor con ``</script>`` no cierre el <script>.
    Esto evita XSS/inyección de JS: los textos vienen de contenido del usuario y de la
    marca, así que NUNCA se interpolan crudos en el código JS.
    """
    return json.dumps(obj, ensure_ascii=True).replace("</", "<\\/")


def injection_script(
    vars_dict: dict[str, str],
    variant_name: str = "",
    template_name: str = "",
    data_attrs: dict[str, str] | None = None,
    texts_dict: dict[str, str] | None = None,
) -> str:
    """JS que inyecta los valores de marca en vivo dentro del template renderizado.

    Todos los valores (colores, textos, data-attrs) se emiten como un blob JSON y se
    leen desde JS — nada se interpola crudo, así que valores con comillas / ``</script>``
    / saltos de línea no pueden romper el script ni inyectar código.
    """
    css = {css_var: vars_dict[key] for css_var, key in _CSS_MAP.items() if vars_dict.get(key)}
    texts: dict[str, str] = {}
    for attr, key in _ATTR_MAP.items():
        if texts_dict and key in texts_dict:
            texts[attr] = texts_dict[key] if texts_dict.get(key) is not None else vars_dict.get(key, "")
        else:
            texts[attr] = vars_dict.get(key, "")

    payload = _js_payload(
        {
            "css": css,
            "texts": texts,
            "dataAttrs": dict(data_attrs or {}),
            "variant": variant_name,
            "template": template_name,
        }
    )
    return (
        "(() => {\n"
        f"  const __e = {payload};\n"
        "  const root = document.documentElement;\n"
        "  for (const [k, v] of Object.entries(__e.css)) root.style.setProperty(k, v);\n"
        "  if (__e.variant) document.body.dataset.variant = __e.variant;\n"
        "  if (__e.template) document.body.dataset.template = __e.template;\n"
        "  for (const [k, v] of Object.entries(__e.dataAttrs)) document.body.setAttribute(k, v);\n"
        "  for (const [attr, val] of Object.entries(__e.texts)) {\n"
        "    document.querySelectorAll('[' + attr + ']').forEach((el) => { el.textContent = val; });\n"
        "  }\n"
        "  if (window.__eikonVariantRefresh) window.__eikonVariantRefresh();\n"
        "})();"
    )


def injection_script_with_isotype(
    vars_dict: dict[str, str],
    isotype_svg: str | None = None,
    variant_name: str = "",
    template_name: str = "",
    data_attrs: dict[str, str] | None = None,
    texts_dict: dict[str, str] | None = None,
) -> str:
    """JS que inyecta valores de marca + SVG isótipo generado en vivo.

    El SVG (data URI o markup SVG) también se pasa por JSON — nunca crudo. Limpia
    el contenedor ([data-isotype-container]) antes de inyectar para reemplazar
    cualquier placeholder del template.
    """
    base_script = injection_script(vars_dict, variant_name, template_name, data_attrs, texts_dict)
    if not isotype_svg:
        return base_script

    svg_literal = _js_payload({"svg": isotype_svg})
    # SEGURIDAD: inyectamos el isotipo SIEMPRE como <img src="data:image/svg+xml;base64,…">.
    # El SVG dentro de un <img> es una imagen estática (no ejecuta scripts) y el data-uri
    # va por JSON (sin interpolación) → sin XSS. NO usar innerHTML con SVG inline (SVG en el
    # DOM sí ejecutaría <script>/handlers, y el SVG lleva texto de marca del usuario).
    isotype_injection = (
        "(() => {\n"
        f"  const __i = {svg_literal};\n"
        "  document.body.dataset.isotypeUri = __i.svg;\n"
        "  document.querySelectorAll('[data-isotype-container]').forEach((c) => {\n"
        "    c.innerHTML = '';\n"
        "    const img = document.createElement('img');\n"
        "    img.src = __i.svg;\n"
        "    img.style.width = '100%';\n"
        "    img.style.height = '100%';\n"
        "    img.style.objectFit = 'contain';\n"
        "    c.appendChild(img);\n"
        "  });\n"
        "})();"
    )
    # Dos IIFE independientes: primero marca/textos, luego el isótipo.
    return base_script + "\n" + isotype_injection
