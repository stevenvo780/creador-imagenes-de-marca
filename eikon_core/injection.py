from __future__ import annotations


def injection_script(
    vars_dict: dict[str, str],
    variant_name: str = "",
    template_name: str = "",
    data_attrs: dict[str, str] | None = None,
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
        "--font-size-scale": "font_size_scale",
        "--space-scale": "space_scale",
        "--corner-radius": "corner_radius",
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
        value = vars_dict.get(key, "")
        if value:
            lines.append(f"  root.style.setProperty('{css_var}', '{value}');")

    if variant_name:
        lines.append(f"  document.body.dataset.variant = '{variant_name}';")
    if template_name:
        lines.append(f"  document.body.dataset.template = '{template_name}';")

    # Apply custom data attributes (from combination params)
    if data_attrs:
        for attr_name, attr_value in data_attrs.items():
            escaped_value = attr_value.replace("'", "\\'")
            # Convert data-attr-name to camelCase for dataset access
            # data-bg-treatment -> bgTreatment
            attr_key = attr_name.replace("data-", "")
            # Convert hyphens to camelCase
            parts = attr_key.split("-")
            camel_key = parts[0] + "".join(p.capitalize() for p in parts[1:])
            lines.append(f"  document.body.dataset.{camel_key} = '{escaped_value}';")

    for attr, key in attr_map.items():
        value = vars_dict.get(key, "").replace("'", "\\'")
        lines.append(
            f"  document.querySelectorAll('[{attr}]').forEach(el => {{ el.textContent = '{value}'; }});"
        )

    lines.append("  if (window.__eikonVariantRefresh) window.__eikonVariantRefresh();")
    lines.append("})();")
    return "\n".join(lines)


def injection_script_with_isotype(
    vars_dict: dict[str, str],
    isotype_svg: str | None = None,
    variant_name: str = "",
    template_name: str = "",
    data_attrs: dict[str, str] | None = None,
) -> str:
    """JS que inyecta valores de marca + SVG isótipo generado en vivo.

    Args:
        vars_dict: Diccionario de variables de marca
        isotype_svg: SVG string del isótipo generado (base64 data URI)
        variant_name: Nombre de variante para dataset
        template_name: Nombre de template
        data_attrs: Atributos data- adicionales

    Returns:
        Script JS completo con inyección de isótipo
    """
    # Obtener script base sin isótipo
    base_script = injection_script(vars_dict, variant_name, template_name, data_attrs)

    if not isotype_svg:
        return base_script

    # Agregar inyección de isótipo
    lines = base_script.split("\n")
    # Insertar antes del cierre de la IIFE
    insert_idx = len(lines) - 2  # Antes del último "})();"

    isotype_injection = f"""  // Inyectar SVG isótipo generado (en TODOS los contenedores;
  // limpiar primero para reemplazar cualquier SVG placeholder del template
  // — si no, el placeholder y el símbolo inyectado se superponen).
  document.body.dataset.isotypeUri = '{isotype_svg}';
  document.querySelectorAll('[data-isotype-container]').forEach((isotypeContainer) => {{
    isotypeContainer.innerHTML = '';
    const img = document.createElement('img');
    img.src = '{isotype_svg}';
    img.style.width = '100%';
    img.style.height = '100%';
    isotypeContainer.appendChild(img);
  }});"""

    lines.insert(insert_idx, isotype_injection)
    return "\n".join(lines)
