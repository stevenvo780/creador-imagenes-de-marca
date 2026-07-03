"""Router de render del cliente: plan, subida de variaciones, templates, fuentes.

Endpoints de la migración cliente-render:
- GET  /api/v1/batches/{batch_id}/plan → render-spec (combinaciones + SVG isotipo)
- POST /api/v1/batches/{batch_id}/variations/upload → recibe PNG subido
- GET  /api/v1/templates/{name} → sirve HTML de plantilla
- /static/fonts/ → servir woff2 desde templates/fonts/

Scoped por tenant multi-tenant. NO renderiza nada (cero Playwright server-side).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from eikon_core.brand import load_json
from eikon_core.combinatorial import CombinationSpec, plan_combinations
from eikon_core.constants import MARCAS_DIR
from eikon_core.mapping import apply_combination_overrides, map_marca_to_vars
from eikon_core.render import (
    _build_isotype_data_uri,
    _extract_data_attrs_from_combination,
)
from eikon_core.taxonomy import CLOUD_ATLAS_TAXONOMIA, PRIZMA_TAXONOMIA, get_category_for_asset_type
from webapp.db import get_last_insert_id
from webapp.storage import (
    connect,
    get_batch,
    get_brand,
)

from .deps import current_user, get_axes_config, get_settings, get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["client-render"])

# Lista blanca de templates válidos (anti path-traversal)
_TEMPLATE_WHITELIST = {
    "isotipo",
    "logo_symbol_color",
    "ad_leaderboard",
    "ad_rectangle",
    "banner_ad",
    "business_card",
    "email_header",
    "favicon",
    "fb_cover",
    "ig_carousel",
    "ig_post",
    "ig_story",
    "og_image",
    "stat_card",
}


@router.get("/batches/{batch_id}/plan")
async def get_batch_plan(  # noqa: C901
    batch_id: int,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Devuelve el render-spec (plan) para un batch.

    Incluye todas las combinaciones con:
    - idx, params (axis_params)
    - vars (CSS custom props)
    - data_attrs (data-* attributes a inyectar)
    - isotype_data_uri (SVG precomputado server-side, base64 data URI)
    - texts (títulos, subtítulos, etc.)

    Plus metadatos del batch:
    - template_name, viewport (w, h), device_scale_factor, category

    El cliente usa esto para renderizar sin tocar el servidor.
    """
    settings = get_settings(request)
    axes_config = get_axes_config(request)
    db = settings.db_url
    tenant_id = user["tenant_id"]

    # Valida batch pertenencia al tenant
    batch = get_batch(db, tenant_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")

    # Deserializa el spec
    spec_dict = json.loads(batch.get("spec_json", "{}"))
    if not spec_dict:
        raise HTTPException(status_code=400, detail="batch spec vacio")

    brand_id = int(batch.get("brand_id", 0))
    brand = get_brand(db, tenant_id, brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="brand not found")

    # Marca: si hay JSON legacy en marcas/{slug}.json lo usamos; si no (marcas
    # creadas por API), construimos la marca desde la PALETA de la DB — igual que
    # el worker. SIN esto, map_marca_to_vars caía a la paleta default donde
    # primario==bg → los símbolos de línea salían invisibles (negros).
    brand_slug = brand.get("slug", "")
    marca_path = MARCAS_DIR / f"{brand_slug}.json"
    if marca_path.exists():
        marca = load_json(marca_path)
    else:
        marca = {
            "slug": str(brand.get("slug", "")),
            "nombre_producto": str(brand.get("name", "")),
            "paleta": json.loads(str(brand.get("palette_json", "{}"))),
            "tipografia": json.loads(str(brand.get("typography_json", "{}"))),
            "logo_texto": str(brand.get("logo_text", "")),
            "logo_simbolo": str(brand.get("logo_symbol", "")),
            "textos": json.loads(str(brand.get("texts_json", "{}"))),
        }

    # Reconstruye el spec como CombinationSpec (para plan_combinations)
    combo_spec = CombinationSpec(
        brand=spec_dict.get("brand", brand_slug),
        asset_types=spec_dict.get("asset_types", ["isotipo"]),
        fixed=spec_dict.get("fixed", {}),
        permuted=spec_dict.get("permuted", []),
        count=spec_dict.get("count", 1),
        seed_salt=spec_dict.get("seed_salt", ""),
    )

    # Convierte AxesConfig a dict[str, list[str]] para plan_combinations
    axes_dict = {name: axis.option_names() for name, axis in axes_config.axes.items()}

    # Planifica combinaciones (determinístico, sin renderizar)
    try:
        plan = plan_combinations(combo_spec, axes_dict)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Extrae asset_type, category y viewport del primer asset_type (asumiendo homogéneo)
    asset_type = combo_spec.asset_types[0] if combo_spec.asset_types else "isotipo"
    category = get_category_for_asset_type(asset_type)
    if category is None:
        raise HTTPException(status_code=400, detail=f"asset_type desconocido: {asset_type}")

    # Busca el type_spec en el catálogo de taxonomía
    is_prizma = "prizma" in marca.get("familia", "").lower()
    taxonomia = PRIZMA_TAXONOMIA if is_prizma else CLOUD_ATLAS_TAXONOMIA
    type_spec = None
    if category in taxonomia:
        for ts in taxonomia[category]:
            if ts.name == asset_type:
                type_spec = ts
                break

    if type_spec is None:
        raise HTTPException(status_code=400, detail=f"asset_type desconocido: {asset_type}")

    device_scale_factor = type_spec.get_device_scale_factor(category)
    viewport = {
        "w": type_spec.width,
        "h": type_spec.height,
    }

    # Cargar overrides de contenido desde el spec (si existen)
    content_overrides = {}
    if spec_dict:
        content_overrides = spec_dict.get("content", {})

    # Construye combinaciones enrichidas
    combinations_list = []
    for combo in plan:
        idx = combo.idx
        params = combo.params
        seed_hex = hex(combo.seed)[2:].zfill(16)  # seed como hex para _build_isotype_data_uri

        # Vars CSS: marca base + combination overrides
        vars_dict = map_marca_to_vars(marca, asset_type)
        vars_dict = apply_combination_overrides(vars_dict, params)

        # Data attrs a inyectar (layout, isotype_style, data-variant, etc.)
        data_attrs = _extract_data_attrs_from_combination(params, asset_type)

        # SVG isotipo precomputado (server-side, determinístico)
        # Si brand tiene logo_style fijo, usar ese; si no, usar el del params
        if brand.get("logo_style"):
            isotype_style = str(brand["logo_style"])
            isotype_seed = hex(int(brand.get("logo_seed", 0)))[2:].zfill(16)
        else:
            isotype_style = params.get("isotype_style", "orbital")
            isotype_seed = seed_hex

        isotype_data_uri = _build_isotype_data_uri(
            isotype_style, isotype_seed, marca, vars_dict
        )

        # Textos de la marca, aplicando content overrides
        texts_obj = {
            "titulo": content_overrides.get("titulo") or vars_dict.get("titulo", ""),
            "subtitulo": content_overrides.get("subtitulo") or vars_dict.get("subtitulo", ""),
            "etiqueta": content_overrides.get("etiqueta") or vars_dict.get("etiqueta", ""),
            "numero": content_overrides.get("numero") or vars_dict.get("numero", ""),
            "copy": content_overrides.get("copy") or vars_dict.get("copy", ""),
        }

        combinations_list.append({
            "idx": idx,
            "params": params,
            "vars": vars_dict,
            "data_attrs": data_attrs,
            "isotype_data_uri": isotype_data_uri,
            "texts": texts_obj,
        })

    return {
        "batch_id": batch_id,
        "asset_type": asset_type,
        "category": category,
        "template_name": asset_type,  # p.ej. "isotipo", "business_card"
        "viewport": viewport,
        "device_scale_factor": device_scale_factor,
        "combinations": combinations_list,
    }


@router.post("/batches/{batch_id}/variations/upload")
async def upload_variation(
    batch_id: int,
    request: Request,
    combo_idx: int = Form(...),
    asset_type: str = Form(...),
    params: str = Form(...),
    image: UploadFile = File(...),
    layout_warnings: str | None = Form(None),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    """Recibe una variación renderizada por el cliente (PNG + metadatos).

    Campos:
    - combo_idx: índice de la combinación (0-based)
    - asset_type: tipo de asset (isotipo, business_card, etc.)
    - params: JSON string de axis_params (validado server-side)
    - image: UploadFile PNG
    - layout_warnings: (opcional) JSON string de warnings de layout

    Validaciones:
    - JWT + batch pertenencia al tenant
    - Magia PNG (\\x89PNG)
    - Reconstruye output_path internamente (nunca del cliente)

    Idempotente: si (batch_id, combo_idx) ya existe → 200 con la existente.
    Si received == expected → status 'completed', listo para ranking.
    """
    settings = get_settings(request)
    storage = get_storage(request)
    db = settings.db_url
    tenant_id = user["tenant_id"]

    # Valida batch pertenencia
    batch = get_batch(db, tenant_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")

    brand_id = int(batch.get("brand_id", 0))
    brand = get_brand(db, tenant_id, brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="brand not found")

    # Parsea params JSON
    try:
        axis_params = json.loads(params)
        if not isinstance(axis_params, dict):
            raise ValueError("params no es un dict")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"params JSON inválido: {e}") from e

    # Lee el PNG
    png_bytes = await image.read()
    if not png_bytes.startswith(b"\x89PNG"):
        raise HTTPException(status_code=400, detail="magic bytes PNG inválido")

    # Obtén categoria del asset_type (para armar la ruta)
    category = get_category_for_asset_type(asset_type)
    brand_slug = brand.get("slug", "")

    # Reconstruye la clave RELATIVA al tenant (NUNCA del cliente). storage.save
    # agrega el prefijo tenants/{tenant_id}/ por sí mismo, así que NO va aquí.
    # Formato: {marca}/{category}/{asset_type}/{batch_id}/combo_{idx:03d}.png
    relative_path = (
        f"{brand_slug}/{category}/{asset_type}/{batch_id}/combo_{combo_idx:03d}.png"
    )

    # Guarda el PNG. output_path = lo que devuelve save() (ruta abs local o URI
    # gs://), que es lo que la descarga sabe invertir con storage.relative_key().
    try:
        stored_path = storage.save(tenant_id, relative_path, png_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"path inválido: {e}") from e
    except Exception as e:
        logger.exception(f"Error al guardar PNG {relative_path}: {e}")
        raise HTTPException(status_code=500, detail="storage error") from e

    # Parsea layout_warnings si viene
    layout_warnings_obj = {}
    if layout_warnings:
        try:
            layout_warnings_obj = json.loads(layout_warnings)
        except json.JSONDecodeError:
            logger.warning(f"layout_warnings JSON inválido: {layout_warnings}")

    # Crea/actúa idempotentemente la variation
    # score placeholder en F1 (será rankead post-upload en F2+)
    var_id = None
    existing = False
    with connect(db) as con:
        # Intenta insertar
        existing_row = con.execute(
            "SELECT id FROM variations WHERE batch_id = ? AND axis_params_json = ?",
            (batch_id, json.dumps(axis_params, sort_keys=True)),
        ).fetchone()

        if existing_row:
            # Ya existe: devuelve la existente
            existing = True
            var_id = existing_row["id"]
        else:
            # Nueva: crea la variation
            now_ts = int(time.time())
            con.execute(
                """INSERT INTO variations
                   (batch_id, tenant_id, brand_id, axis_params_json, seed, score,
                    output_path, wcag_json, layout_status, selected, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
                (
                    batch_id,
                    tenant_id,
                    brand_id,
                    json.dumps(axis_params, sort_keys=True),
                    None,  # seed será asignado por el worker si lo necesita
                    0.5,  # score placeholder
                    stored_path,
                    json.dumps(layout_warnings_obj) if layout_warnings_obj else None,
                    None,  # layout_status será computado server-side si aplica
                    now_ts,
                ),
            )
            # DB-agnóstico (SQLite last_insert_rowid / Postgres currval del seq).
            var_id = get_last_insert_id(db, con, "variations")

        # Actualiza counts del batch (recibidas). `expected` se deriva del count
        # del spec si no estaba seteado (el create valida count<=combos distintos,
        # así que el plan produce exactamente `count` combos).
        counts_dict = json.loads(batch.get("counts_json", "{}"))
        received = counts_dict.get("received", 0) + (0 if existing else 1)
        spec_json = json.loads(batch.get("spec_json", "{}"))
        expected = counts_dict.get("expected") or int(spec_json.get("count", 1) or 1)
        counts_dict["received"] = received
        counts_dict["expected"] = expected

        con.execute(
            "UPDATE batches SET counts_json = ? WHERE id = ?",
            (json.dumps(counts_dict, sort_keys=True), batch_id),
        )

        # Si received == expected, marca como completed
        if received >= expected and expected > 0:
            now_ts = int(time.time())
            con.execute(
                "UPDATE batches SET status = ?, finished_at = ? WHERE id = ?",
                ("completed", now_ts, batch_id),
            )

    return {
        "variation_id": var_id,
        "combo_idx": combo_idx,
        "output_path": relative_path,
        "idempotent": existing,
    }


@router.get("/templates/{name}")
async def get_template(
    name: str,
    request: Request,
    user: dict[str, Any] = Depends(current_user),
) -> FileResponse:
    """Sirve el HTML de una plantilla por nombre (con lista blanca anti path-traversal).

    Valida JWT del usuario.
    """
    # Lista blanca
    if name not in _TEMPLATE_WHITELIST:
        raise HTTPException(status_code=404, detail=f"template desconocido: {name}")

    template_path = Path(__file__).resolve().parent.parent.parent / "templates" / f"{name}.html"
    if not template_path.is_file():
        raise HTTPException(status_code=404, detail=f"template no existe: {name}")

    return FileResponse(str(template_path), media_type="text/html")
