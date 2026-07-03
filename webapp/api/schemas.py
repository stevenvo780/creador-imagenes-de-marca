"""Modelos pydantic de request/response para la API v1."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Claves válidas de paleta que el motor lee (en español).
VALID_PALETTE_KEYS: frozenset[str] = frozenset({"bg", "primario", "acento", "acento_2", "texto"})

# Traducción de claves en inglés a las claves en español que el motor espera.
_EN_TO_ES_PALETTE: dict[str, str] = {
    "primary": "primario",
    "secondary": "acento_2",
    "accent": "acento",
    "accent_2": "acento_2",
    "background": "bg",
    "text": "texto",
}

# Límite de entero compatible con SQLite INTEGER (int64 con signo).
_SQLITE_INT_MAX: int = 2**63 - 1


def _normalize_palette(palette: dict[str, Any]) -> dict[str, Any]:
    """Traduce claves inglés→español y rechaza claves desconocidas.

    Devuelve el dict normalizado. Lanza ValueError con las claves no reconocidas.
    """
    normalized: dict[str, Any] = {}
    unknown: list[str] = []
    for key, value in palette.items():
        if key in VALID_PALETTE_KEYS:
            normalized[key] = value
        elif key in _EN_TO_ES_PALETTE:
            # Traducir inglés → español; la última asignación gana en caso de duplicado.
            normalized[_EN_TO_ES_PALETTE[key]] = value
        else:
            unknown.append(key)
    if unknown:
        valid = sorted(VALID_PALETTE_KEYS | set(_EN_TO_ES_PALETTE.keys()))
        raise ValueError(
            f"claves de paleta desconocidas: {unknown!r}. "
            f"Claves permitidas: {valid}"
        )
    return normalized


class BrandCreate(BaseModel):
    """Payload para crear un brand del tenant."""

    slug: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    palette: dict[str, Any] = Field(default_factory=dict)
    typography: dict[str, Any] = Field(default_factory=dict)
    logo_text: str = ""
    logo_symbol: str = ""
    logo_style: str = ""
    logo_seed: int = 0
    texts: dict[str, Any] = Field(default_factory=dict)

    @field_validator("palette", mode="before")
    @classmethod
    def validate_palette_keys(cls, v: Any) -> Any:
        if not isinstance(v, dict) or not v:
            return v
        return _normalize_palette(v)


class BrandUpdate(BaseModel):
    """Payload de actualización parcial de un brand (campos opcionales)."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    palette: dict[str, Any] | None = None
    typography: dict[str, Any] | None = None
    logo_text: str | None = None
    logo_symbol: str | None = None
    logo_style: str | None = None
    logo_seed: int | None = None
    texts: dict[str, Any] | None = None

    @field_validator("palette", mode="before")
    @classmethod
    def validate_palette_keys(cls, v: Any) -> Any:
        if v is None or not isinstance(v, dict) or not v:
            return v
        return _normalize_palette(v)


class BatchCreate(BaseModel):
    """Payload para encolar un batch combinatorio sobre un brand."""

    brand_id: int = Field(ge=1, le=_SQLITE_INT_MAX)
    asset_types: list[str] = Field(default_factory=lambda: ["isotipo"])
    fixed: dict[str, str] = Field(default_factory=dict)
    permuted: list[str] = Field(default_factory=list)
    count: int = Field(default=4, ge=1, le=64)
    seed_salt: str = Field(default="", max_length=80)
    # "server": render con Chromium en el servidor (histórico).
    # "client": el navegador del usuario renderiza y sube los PNG (sin CPU GCP).
    render_mode: Literal["server", "client"] = Field(default="server")
    # Overrides de contenido variable por pieza: claves como titulo, subtitulo, copy, etc.
    content: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_axis_overlap(self) -> BatchCreate:
        """Rechaza si un eje aparece en fixed Y en permuted al mismo tiempo."""
        overlap = set(self.fixed.keys()) & set(self.permuted)
        if overlap:
            raise ValueError(
                f"ejes no pueden estar en fixed y permuted simultáneamente: {sorted(overlap)!r}"
            )
        return self


class SelectRequest(BaseModel):
    """Marca/desmarca una variación como seleccionada en la galería."""

    variation_id: int
    selected: bool = True


class ZipRequest(BaseModel):
    """Lista de IDs de variaciones a empacar en un ZIP descargable."""

    ids: list[int] = Field(min_length=1, max_length=200)
