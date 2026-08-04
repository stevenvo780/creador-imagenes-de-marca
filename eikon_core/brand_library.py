"""Biblioteca consolidada y verificable de BrandSpec de Eikón."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .brand import load_json
from .brand_spec import BrandSpec, BrandSpecError
from .constants import MARCAS_DIR, ROOT

BRAND_LIBRARY_PATH = ROOT / "config" / "brand-library.json"


@dataclass(frozen=True)
class BrandLibrary:
    """Índice inmutable por slug; rechaza duplicados y drift de digests."""

    brands: dict[str, BrandSpec]

    @classmethod
    def from_sources(cls, marcas_dir: Path = MARCAS_DIR) -> BrandLibrary:
        brands: dict[str, BrandSpec] = {}
        errors: list[str] = []
        for path in sorted(marcas_dir.glob("*.json")):
            try:
                spec = BrandSpec.from_mapping(load_json(path))
                if spec.slug != path.stem:
                    raise BrandSpecError(
                        f"slug {spec.slug!r} no coincide con filename {path.stem!r}"
                    )
                if spec.slug in brands:
                    raise BrandSpecError(f"slug duplicado: {spec.slug}")
                brands[spec.slug] = spec
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
        if errors:
            raise BrandSpecError("Biblioteca inválida:\n- " + "\n- ".join(errors))
        return cls(brands=brands)

    @classmethod
    def from_catalog(cls, path: Path = BRAND_LIBRARY_PATH) -> BrandLibrary:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema_version") != BrandSpec.SCHEMA_VERSION:
            raise BrandSpecError("schema_version de biblioteca incompatible")
        brands: dict[str, BrandSpec] = {}
        for item in data.get("brands", []):
            spec_data = item.get("spec") if isinstance(item, dict) else None
            if not isinstance(spec_data, dict):
                raise BrandSpecError("Entrada de biblioteca sin spec")
            spec = BrandSpec.from_dict(spec_data)
            expected_digest = str(item.get("digest", ""))
            if expected_digest != spec.digest:
                raise BrandSpecError(f"Digest inválido para {spec.slug}")
            if spec.slug in brands:
                raise BrandSpecError(f"slug duplicado: {spec.slug}")
            brands[spec.slug] = spec
        return cls(brands=brands)

    def get(self, slug: str) -> BrandSpec:
        try:
            return self.brands[slug]
        except KeyError as exc:
            raise KeyError(f"Marca no registrada: {slug}") from exc

    def list(self, *, family: str | None = None) -> list[BrandSpec]:
        values: Iterable[BrandSpec] = self.brands.values()
        if family:
            values = (spec for spec in values if spec.family == family)
        return sorted(values, key=lambda spec: spec.slug)

    def to_catalog(self) -> dict[str, Any]:
        return {
            "schema_version": BrandSpec.SCHEMA_VERSION,
            "brand_count": len(self.brands),
            "brands": [
                {"slug": spec.slug, "digest": spec.digest, "spec": spec.to_dict()}
                for spec in self.list()
            ],
        }

    def write_catalog(self, path: Path = BRAND_LIBRARY_PATH) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_catalog(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path

    def assert_matches_sources(self, marcas_dir: Path = MARCAS_DIR) -> None:
        source = self.from_sources(marcas_dir)
        catalog_digests = {slug: spec.digest for slug, spec in self.brands.items()}
        source_digests = {slug: spec.digest for slug, spec in source.brands.items()}
        if catalog_digests != source_digests:
            missing = sorted(source_digests.keys() - catalog_digests.keys())
            stale = sorted(
                slug
                for slug in source_digests.keys() & catalog_digests.keys()
                if source_digests[slug] != catalog_digests[slug]
            )
            extra = sorted(catalog_digests.keys() - source_digests.keys())
            raise BrandSpecError(
                f"Drift en brand-library: missing={missing}, stale={stale}, extra={extra}"
            )
