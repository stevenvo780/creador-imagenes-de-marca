"""Contrato canónico de marca para render determinista y refinado con IA.

Los JSON históricos de ``marcas/`` usan nombres en español y admiten campos
opcionales. Este módulo los normaliza a una representación única, estable y
serializable. La capa de IA consume exclusivamente este contrato: nunca arma
prompts leyendo campos ad-hoc directamente del JSON fuente.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, ClassVar

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,80}$")


class BrandSpecError(ValueError):
    """El documento de marca no puede convertirse al contrato canónico."""


def _text(value: Any, *, fallback: str = "") -> str:
    return str(value).strip() if value is not None else fallback


def _string_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): str(item).strip()
        for key, item in value.items()
        if item is not None and str(item).strip()
    }


def _nested_string_map(value: Any) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, dict[str, str]] = {}
    for key, item in value.items():
        normalized = _string_map(item)
        if normalized:
            result[str(key)] = normalized
    return result


@dataclass(frozen=True)
class BrandSpec:
    """Brand spec única que comparten Eikón y sus proveedores de refinado."""

    SCHEMA_VERSION: ClassVar[str] = "1.0"
    REQUIRED_PALETTE_KEYS: ClassVar[tuple[str, ...]] = (
        "background",
        "primary",
        "accent",
        "accent_secondary",
        "text",
    )

    slug: str
    name: str
    corporate_name: str
    tagline: str
    tone: str
    symbol: str
    family: str
    front: str
    urls: dict[str, str]
    palette: dict[str, str]
    typography: dict[str, str]
    gradients: dict[str, str]
    identity: dict[str, str | int | None]
    assets: dict[str, dict[str, str]]

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> BrandSpec:
        """Normaliza un JSON histórico de ``marcas/`` y valida invariantes."""
        if not isinstance(raw, dict):
            raise BrandSpecError("La marca debe ser un objeto JSON")

        slug = _text(raw.get("slug"))
        if not SLUG_RE.fullmatch(slug):
            raise BrandSpecError(f"slug inválido: {slug!r}")

        name = _text(raw.get("nombre_producto") or raw.get("name"))
        if not name:
            raise BrandSpecError(f"{slug}: nombre de producto requerido")

        source_palette = _string_map(raw.get("paleta") or raw.get("palette"))
        palette = {
            "background": source_palette.get("bg", source_palette.get("background", "")),
            "primary": source_palette.get("primario", source_palette.get("primary", "")),
            "accent": source_palette.get("acento", source_palette.get("accent", "")),
            "accent_secondary": source_palette.get(
                "acento_2", source_palette.get("secondary", "")
            ),
            "accent_tertiary": source_palette.get("acento_3", ""),
            "text": source_palette.get("texto", source_palette.get("text", "")),
            "text_muted": source_palette.get("texto_muted", ""),
            "surface": source_palette.get("surface", ""),
        }
        missing_palette = [key for key in cls.REQUIRED_PALETTE_KEYS if not palette.get(key)]
        if missing_palette:
            raise BrandSpecError(f"{slug}: faltan colores canónicos: {missing_palette}")
        invalid_colors = [
            f"{key}={value!r}"
            for key, value in palette.items()
            if value and not HEX_COLOR_RE.fullmatch(value)
        ]
        if invalid_colors:
            raise BrandSpecError(f"{slug}: colores hex inválidos: {', '.join(invalid_colors)}")
        palette = {key: value.lower() for key, value in palette.items() if value}

        source_typography = _string_map(raw.get("tipografia") or raw.get("typography"))
        typography = {
            "display": source_typography.get("titulos", source_typography.get("display", "Inter")),
            "body": source_typography.get("cuerpo", source_typography.get("body", "Inter")),
        }

        urls = {
            key: value
            for key, value in {
                "primary": _text(raw.get("url")),
                "english": _text(raw.get("url_en")),
                "product": _text(raw.get("url_producto")),
                "corporate": _text(raw.get("url_corporativa")),
            }.items()
            if value
        }
        family = "prizma" if "prizma" in slug.lower() else "cloud_atlas"
        identity: dict[str, str | int | None] = {
            "logo_text": _text(raw.get("logo_texto"), fallback=name),
            "logo_symbol": _text(raw.get("logo_simbolo") or raw.get("simbolo")),
            "logo_style": _text(raw.get("logo_style")),
            "logo_seed": int(raw.get("logo_seed") or 0),
            "logo_asset": _text(raw.get("logo_asset")) or None,
        }

        return cls(
            slug=slug,
            name=name,
            corporate_name=_text(raw.get("nombre_corporativo"), fallback=name),
            tagline=_text(raw.get("tagline")),
            tone=_text(raw.get("tono")),
            symbol=_text(raw.get("simbolo") or raw.get("logo_simbolo")),
            family=family,
            front=_text(raw.get("frente") or raw.get("suite")),
            urls=urls,
            palette=palette,
            typography=typography,
            gradients={
                key: value
                for key, value in {
                    "hero": _text(raw.get("gradiente_hero")),
                    "background": _text(raw.get("gradiente_bg")),
                }.items()
                if value
            },
            identity=identity,
            assets=_nested_string_map(raw.get("textos") or raw.get("assets")),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BrandSpec:
        """Carga una spec ya normalizada desde la biblioteca consolidada."""
        if data.get("schema_version") != cls.SCHEMA_VERSION:
            raise BrandSpecError(
                f"schema_version incompatible: {data.get('schema_version')!r}; "
                f"esperado {cls.SCHEMA_VERSION!r}"
            )
        spec = cls(
            slug=_text(data.get("slug")),
            name=_text(data.get("name")),
            corporate_name=_text(data.get("corporate_name")),
            tagline=_text(data.get("tagline")),
            tone=_text(data.get("tone")),
            symbol=_text(data.get("symbol")),
            family=_text(data.get("family")),
            front=_text(data.get("front")),
            urls=_string_map(data.get("urls")),
            palette=_string_map(data.get("palette")),
            typography=_string_map(data.get("typography")),
            gradients=_string_map(data.get("gradients")),
            identity={
                str(key): value
                for key, value in dict(data.get("identity") or {}).items()
                if isinstance(value, str | int) or value is None
            },
            assets=_nested_string_map(data.get("assets")),
        )
        if not SLUG_RE.fullmatch(spec.slug):
            raise BrandSpecError(f"slug inválido: {spec.slug!r}")
        if not spec.name:
            raise BrandSpecError(f"{spec.slug}: nombre de producto requerido")
        missing_palette = [
            key for key in cls.REQUIRED_PALETTE_KEYS if not spec.palette.get(key)
        ]
        if missing_palette:
            raise BrandSpecError(
                f"{spec.slug}: faltan colores canónicos: {missing_palette}"
            )
        invalid_colors = [
            f"{key}={value!r}"
            for key, value in spec.palette.items()
            if not HEX_COLOR_RE.fullmatch(value)
        ]
        if invalid_colors:
            raise BrandSpecError(
                f"{spec.slug}: colores hex inválidos: {', '.join(invalid_colors)}"
            )
        return spec

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "slug": self.slug,
            "name": self.name,
            "corporate_name": self.corporate_name,
            "tagline": self.tagline,
            "tone": self.tone,
            "symbol": self.symbol,
            "family": self.family,
            "front": self.front,
            "urls": dict(sorted(self.urls.items())),
            "palette": dict(sorted(self.palette.items())),
            "typography": dict(sorted(self.typography.items())),
            "gradients": dict(sorted(self.gradients.items())),
            "identity": dict(sorted(self.identity.items())),
            "assets": {
                key: dict(sorted(value.items())) for key, value in sorted(self.assets.items())
            },
        }

    @property
    def digest(self) -> str:
        payload = json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def prompt_context(self, asset_type: str) -> dict[str, Any]:
        """Contexto mínimo, estricto y estable para el prompt de refinado."""
        return {
            "schema_version": self.SCHEMA_VERSION,
            "brand": self.name,
            "corporate_name": self.corporate_name,
            "tone": self.tone,
            "palette": self.palette,
            "typography": self.typography,
            "identity": self.identity,
            "asset_type": asset_type,
            "exact_content": self.assets.get(asset_type, {}),
        }
