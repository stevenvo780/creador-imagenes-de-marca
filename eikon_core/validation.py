from __future__ import annotations

import re
from typing import Any

CANONICAL_FAMILIES = frozenset({"cloud_atlas", "prizma"})
CANONICAL_CATEGORIES = frozenset({"logos", "banners", "cards", "og", "stationery"})
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_VARIANT_RE = re.compile(r"^v\d+_[a-z0-9_]+$")


def validate_taxonomy(data: Any) -> None:
    """Valida taxonomy.json v1 y levanta ValueError accionable si falla.

    Es deliberadamente estricto en estructura y duplicados, pero no valida
    calidad visual: eso pertenece a los gates layout/pixel/WCAG.
    """
    if not isinstance(data, dict):
        raise ValueError(f"taxonomy.root debe ser dict, got {type(data).__name__}")
    if data.get("schema_version") != 1:
        raise ValueError(f"taxonomy.schema_version debe ser 1, got {data.get('schema_version')!r}")
    if not isinstance(data.get("version"), str) or not data["version"]:
        raise ValueError("taxonomy.version debe ser string no-vacío")
    families = data.get("families")
    if not isinstance(families, dict) or not families:
        raise ValueError("taxonomy.families debe ser dict no-vacío")
    missing = CANONICAL_FAMILIES - set(families)
    if missing:
        raise ValueError(f"taxonomy.families faltan familias canónicas: {sorted(missing)}")

    conventions = data.get("conventions") or {}
    min_dim = int(conventions.get("min_type_dim", 16))
    max_dim = int(conventions.get("max_type_dim", 8192))
    max_variants = int(conventions.get("max_variants_per_type", 12))

    for family_name, family in families.items():
        if not isinstance(family_name, str) or not _NAME_RE.match(family_name):
            raise ValueError(f"family name inválido: {family_name!r}")
        if not isinstance(family, dict):
            raise ValueError(f"taxonomy.families[{family_name!r}] debe ser dict")
        categories = family.get("categories")
        if not isinstance(categories, dict) or not categories:
            raise ValueError(f"taxonomy.families[{family_name!r}].categories debe ser dict no-vacío")
        for category_name, category in categories.items():
            if category_name not in CANONICAL_CATEGORIES:
                raise ValueError(f"categoría no canónica en {family_name!r}: {category_name!r}")
            if not isinstance(category, dict):
                raise ValueError(f"category {family_name}/{category_name} debe ser dict")
            scale = category.get("device_scale")
            if scale is not None and (not isinstance(scale, int) or scale <= 0):
                raise ValueError(f"{family_name}/{category_name}.device_scale debe ser int > 0")
            types = category.get("types")
            if not isinstance(types, list) or not types:
                raise ValueError(f"{family_name}/{category_name}.types debe ser lista no-vacía")
            seen_types: set[str] = set()
            for type_idx, type_entry in enumerate(types):
                where = f"{family_name}/{category_name}.types[{type_idx}]"
                if not isinstance(type_entry, dict):
                    raise ValueError(f"{where} debe ser dict")
                name = type_entry.get("name")
                if not isinstance(name, str) or not _NAME_RE.match(name):
                    raise ValueError(f"{where}.name inválido: {name!r}")
                if name in seen_types:
                    raise ValueError(f"type duplicado en {family_name}/{category_name}: {name!r}")
                seen_types.add(name)
                for key in ("width", "height"):
                    value = type_entry.get(key)
                    if not isinstance(value, int) or not (min_dim <= value <= max_dim):
                        raise ValueError(f"{where}.{key} fuera de rango [{min_dim},{max_dim}]: {value!r}")
                template = type_entry.get("template")
                if template is not None and (not isinstance(template, str) or not template.endswith(".html")):
                    raise ValueError(f"{where}.template debe ser *.html o null: {template!r}")
                variants = type_entry.get("variants")
                if not isinstance(variants, list) or not variants:
                    raise ValueError(f"{where}.variants debe ser lista no-vacía")
                if len(variants) > max_variants:
                    raise ValueError(f"{where}.variants supera máximo {max_variants}")
                seen_variants: set[str] = set()
                for variant_idx, variant in enumerate(variants):
                    vwhere = f"{where}.variants[{variant_idx}]"
                    if not isinstance(variant, dict):
                        raise ValueError(f"{vwhere} debe ser dict")
                    vid = variant.get("id")
                    label = variant.get("label")
                    if not isinstance(vid, str) or not vid:
                        raise ValueError(f"{vwhere}.id debe ser string no-vacío")
                    if vid in seen_variants:
                        raise ValueError(f"variant duplicada en {family_name}/{category_name}/{name}: {vid!r}")
                    seen_variants.add(vid)
                    if not _VARIANT_RE.match(vid):
                        raise ValueError(f"{vwhere}.id no cumple convención vN_slug: {vid!r}")
                    if not isinstance(label, str) or not label:
                        raise ValueError(f"{vwhere}.label debe ser string no-vacío")
