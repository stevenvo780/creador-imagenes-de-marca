from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VariantSpec:
    name: str
    label: str


@dataclass(frozen=True)
class TypeSpec:
    name: str
    width: int
    height: int
    variants: tuple[VariantSpec, ...]

    def get_device_scale_factor(self, categoria: str) -> int:
        """deviceScaleFactor ALTO: 3 para logos/print, 2 para social/web/cards."""
        if categoria in ("logos", "stationery", "print"):
            return 3
        return 2

    def get_output_width(self, categoria: str) -> int:
        return self.width * self.get_device_scale_factor(categoria)

    def get_output_height(self, categoria: str) -> int:
        return self.height * self.get_device_scale_factor(categoria)
