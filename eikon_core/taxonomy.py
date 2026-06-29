from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from . import constants as cfg
from .types import TypeSpec, VariantSpec
from .validation import validate_taxonomy

TAXONOMY_JSON_PATH = cfg.ROOT / "taxonomy.json"
_FALLBACK_WARNED = False


def _legacy_python_taxonomia(is_prizma: bool) -> dict[str, list[TypeSpec]]:
    logos = [
        TypeSpec("lockup_horizontal", 1200, 400, (
            VariantSpec("v1_color", "Color"), VariantSpec("v2_mono", "Mono"), VariantSpec("v3_inverse", "Inverse")
        )),
        TypeSpec("lockup_vertical", 800, 800, (
            VariantSpec("v1_color", "Color"), VariantSpec("v2_mono", "Mono"), VariantSpec("v3_inverse", "Inverse")
        )),
        TypeSpec("wordmark", 1000, 300, (
            VariantSpec("v1_dark", "Dark"), VariantSpec("v2_light", "Light")
        )),
        TypeSpec("isotipo", 800, 800, (
            VariantSpec("v1_color", "Color"), VariantSpec("v2_mono", "Mono"), VariantSpec("v3_inverse", "Inverse")
        )),
        TypeSpec("favicon", 512, 512, (
            VariantSpec("v1_32", "32px"), VariantSpec("v2_180", "180px"), VariantSpec("v3_512", "512px")
        )),
        TypeSpec("watermark", 1000, 1000, (
            VariantSpec("v1_light", "Light"), VariantSpec("v2_dark", "Dark")
        )),
    ]

    cards_common = [
        TypeSpec("business_card", 1050, 600, (
            VariantSpec("v1_front", "Front"), VariantSpec("v2_back", "Back")
        ))
    ]

    if is_prizma:
        return {
            "logos": logos,
            "cards": cards_common + [
                TypeSpec("stat_card", 1080, 1080, (
                    VariantSpec("v1_big_data", "BigData"), VariantSpec("v2_comparativa", "Comparative"), VariantSpec("v3_uptime", "Uptime")
                )),
            ],
            "og": [
                TypeSpec("og_general", 1200, 630, (
                    VariantSpec("v1_docs", "Docs"), VariantSpec("v2_enterprise_blog", "Blog"), VariantSpec("v3_tool", "Tool")
                )),
                TypeSpec("og_product", 1200, 630, (
                    VariantSpec("v1_product", "Product"), VariantSpec("v2_product", "Product"), VariantSpec("v3_product", "Product")
                )),
            ],
            "stationery": [
                TypeSpec("letterhead", 2480, 3508, (
                    VariantSpec("v1_corporate", "Corporate"), VariantSpec("v2_invoice", "Invoice")
                )),
            ],
        }
    return {
        "logos": logos,
        "banners": [
            TypeSpec("linkedin_header", 1584, 396, (
                VariantSpec("v1_institucional", "Institucional"),
                VariantSpec("v2_producto", "Producto"),
                VariantSpec("v3_evento", "Evento"),
            )),
            TypeSpec("twitter_header", 1500, 500, (
                VariantSpec("v1_brand", "Brand"),
                VariantSpec("v2_lanzamiento", "Lanzamiento"),
                VariantSpec("v3_comunidad", "Comunidad"),
            )),
            TypeSpec("youtube_header", 2560, 1440, (
                VariantSpec("v1_visual", "Visual"),
                VariantSpec("v2_grid", "Grid"),
                VariantSpec("v3_textual", "Textual"),
            )),
            TypeSpec("web_hero_desktop", 1920, 600, (
                VariantSpec("v1_split", "Split"),
                VariantSpec("v2_central", "Central"),
                VariantSpec("v3_video_fallback", "VideoFallback"),
                VariantSpec("v4_minimal", "Minimal"),
            )),
            TypeSpec("ad_leaderboard", 728, 90, (
                VariantSpec("v1_brand", "Brand"), VariantSpec("v2_promo", "Promo"), VariantSpec("v3_cta_driven", "CTA")
            )),
            TypeSpec("ad_rectangle", 300, 250, (
                VariantSpec("v1_visual", "Visual"), VariantSpec("v2_data", "Data"), VariantSpec("v3_testimonial", "Testimonial")
            )),
        ],
        "cards": cards_common + [
            TypeSpec("stat_card", 1080, 1080, (
                VariantSpec("v1_hero_num", "Hero"), VariantSpec("v2_dual_stat", "Dual"), VariantSpec("v3_graph_abstract", "Graph")
            )),
        ],
        "og": [
            TypeSpec("og_general", 1200, 630, (
                VariantSpec("v1_website", "Website"), VariantSpec("v2_articulo", "Article"), VariantSpec("v3_feature", "Feature")
            )),
        ],
        "stationery": [
            TypeSpec("letterhead", 2480, 3508, (
                VariantSpec("v1_oficial", "Official"), VariantSpec("v2_interno", "Internal")
            )),
        ],
    }


def _from_taxonomy_json(path: Path, is_prizma: bool) -> dict[str, list[TypeSpec]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_taxonomy(data)
    family_key = "prizma" if is_prizma else "cloud_atlas"
    family = data["families"][family_key]
    output: dict[str, list[TypeSpec]] = {}
    for category_name, category in family["categories"].items():
        output[category_name] = [
            TypeSpec(
                str(type_entry["name"]),
                int(type_entry["width"]),
                int(type_entry["height"]),
                tuple(
                    VariantSpec(str(variant["id"]), str(variant["label"]))
                    for variant in type_entry["variants"]
                ),
            )
            for type_entry in category["types"]
        ]
    return output


def _build_taxonomia(is_prizma: bool) -> dict[str, list[TypeSpec]]:
    """Retorna taxonomía histórica; usa taxonomy.json si es válido."""
    global _FALLBACK_WARNED
    env_path = os.environ.get("EIKON_TAXONOMY_JSON")
    path = Path(env_path) if env_path else (TAXONOMY_JSON_PATH if TAXONOMY_JSON_PATH.exists() else None)
    if path is not None:
        try:
            return _from_taxonomy_json(path, is_prizma)
        except Exception as e:  # noqa: BLE001 - fallback defensivo de compatibilidad
            if not _FALLBACK_WARNED:
                print(
                    f"⚠ taxonomy.json inválido ({type(e).__name__}: {e}); fallback a legacy Python.",
                    file=sys.stderr,
                )
                _FALLBACK_WARNED = True
    return _legacy_python_taxonomia(is_prizma)


def taxonomy_to_json_dict() -> dict[str, Any]:
    """Construye un taxonomy.json v1 determinista desde la taxonomía legacy."""
    def convert(types_by_category: dict[str, list[TypeSpec]]) -> dict[str, Any]:
        categories: dict[str, Any] = {}
        for category_name, type_specs in types_by_category.items():
            device_scale = 3 if category_name in ("logos", "stationery") else 2
            categories[category_name] = {
                "label": category_name.replace("_", " ").title(),
                "device_scale": device_scale,
                "types": [
                    {
                        "name": type_spec.name,
                        "width": type_spec.width,
                        "height": type_spec.height,
                        "template": _template_name_for_type(type_spec.name),
                        "protected": _template_name_for_type(type_spec.name) in {
                            "ad_leaderboard.html", "letterhead.html", "stat_card.html",
                        },
                        "variants": [
                            {"id": variant.name, "label": variant.label}
                            for variant in type_spec.variants
                        ],
                    }
                    for type_spec in type_specs
                ],
            }
        return categories

    return {
        "schema_version": 1,
        "version": "1.0.0",
        "engine_compat": cfg.ENGINE_VERSION,
        "generated_from": {
            "legacy": "eikon_core.taxonomy._legacy_python_taxonomia",
            "layouts_file": "layouts.json",
            "master_spec": "MASTER-TAXONOMIA.md",
        },
        "protected_templates": ["ad_leaderboard.html", "letterhead.html", "stat_card.html"],
        "conventions": {
            "variant_id_pattern": r"^v\d+_[a-z0-9_]+$",
            "min_type_dim": 16,
            "max_type_dim": 8192,
            "min_variants_per_type": 1,
            "max_variants_per_type": 12,
        },
        "families": {
            "cloud_atlas": {
                "label": "Cloud Atlas / Pinakotheke",
                "categories": convert(_legacy_python_taxonomia(False)),
            },
            "prizma": {
                "label": "Prizma Enterprise",
                "categories": convert(_legacy_python_taxonomia(True)),
            },
        },
    }


def _template_name_for_type(type_name: str) -> str:
    aliases = {
        "linkedin_header": "linkedin_banner.html",
        "twitter_header": "x_header.html",
        "youtube_header": "yt_banner.html",
        "web_hero_desktop": "web_hero.html",
    }
    return aliases.get(type_name, f"{type_name}.html")


CLOUD_ATLAS_TAXONOMIA = _build_taxonomia(is_prizma=False)
PRIZMA_TAXONOMIA = _build_taxonomia(is_prizma=True)
