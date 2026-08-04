from __future__ import annotations

import json

import pytest

from eikon_core.brand_library import BrandLibrary
from eikon_core.brand_spec import BrandSpec, BrandSpecError


def test_library_consolidates_every_registered_brand() -> None:
    library = BrandLibrary.from_sources()
    assert len(library.brands) == 56
    assert library.get("pinakotheke-kosmos").name == "Kósmos"
    assert all(spec.digest for spec in library.list())


def test_catalog_is_deterministic_and_matches_sources(tmp_path) -> None:
    library = BrandLibrary.from_sources()
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    library.write_catalog(first)
    library.write_catalog(second)
    assert first.read_bytes() == second.read_bytes()

    loaded = BrandLibrary.from_catalog(first)
    loaded.assert_matches_sources()


def test_catalog_rejects_tampered_digest(tmp_path) -> None:
    library = BrandLibrary.from_sources()
    path = library.write_catalog(tmp_path / "brands.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["brands"][0]["digest"] = "0" * 64
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(BrandSpecError, match="Digest inválido"):
        BrandLibrary.from_catalog(path)


def test_normalized_spec_revalidates_required_palette() -> None:
    spec = BrandLibrary.from_sources().get("pinakotheke-kosmos").to_dict()
    del spec["palette"]["accent"]
    with pytest.raises(BrandSpecError, match="faltan colores canónicos"):
        BrandSpec.from_dict(spec)
