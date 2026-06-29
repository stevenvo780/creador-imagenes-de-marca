"""Modelos pydantic de request/response para la API v1."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BrandCreate(BaseModel):
    """Payload para crear un brand del tenant."""

    slug: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    palette: dict[str, Any] = Field(default_factory=dict)
    typography: dict[str, Any] = Field(default_factory=dict)
    logo_text: str = ""
    logo_symbol: str = ""
    texts: dict[str, Any] = Field(default_factory=dict)


class BrandUpdate(BaseModel):
    """Payload de actualización parcial de un brand (campos opcionales)."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    palette: dict[str, Any] | None = None
    typography: dict[str, Any] | None = None
    logo_text: str | None = None
    logo_symbol: str | None = None
    texts: dict[str, Any] | None = None


class BatchCreate(BaseModel):
    """Payload para encolar un batch combinatorio sobre un brand."""

    brand_id: int
    asset_types: list[str] = Field(default_factory=lambda: ["isotipo"])
    fixed: dict[str, str] = Field(default_factory=dict)
    permuted: list[str] = Field(default_factory=list)
    count: int = Field(default=4, ge=1, le=64)
    seed_salt: str = Field(default="", max_length=80)


class SelectRequest(BaseModel):
    """Marca/desmarca una variación como seleccionada en la galería."""

    variation_id: int
    selected: bool = True


class ZipRequest(BaseModel):
    """Lista de IDs de variaciones a empacar en un ZIP descargable."""

    ids: list[int] = Field(min_length=1, max_length=200)
