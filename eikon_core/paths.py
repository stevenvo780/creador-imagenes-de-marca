"""Render engine path configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import constants as cfg


@dataclass(frozen=True)
class RenderPaths:
    """Configuration for render output and template paths.

    This frozen dataclass allows future tenant-scoping while maintaining
    default behavior identical to before.
    """

    root: Path
    marcas_dir: Path
    templates_dir: Path
    output_dir: Path

    @classmethod
    def default(cls) -> RenderPaths:
        """Create default paths matching current behavior."""
        return cls(
            root=cfg.ROOT,
            marcas_dir=cfg.MARCAS_DIR,
            templates_dir=cfg.TEMPLATES_DIR,
            output_dir=cfg.OUTPUT_DIR,
        )


# Global instance for current render session
_current_paths: RenderPaths | None = None


def get_render_paths() -> RenderPaths:
    """Get the current render paths configuration."""
    global _current_paths
    if _current_paths is None:
        _current_paths = RenderPaths.default()
    return _current_paths


def set_render_paths(paths: RenderPaths) -> None:
    """Set the render paths configuration."""
    global _current_paths
    _current_paths = paths


def reset_render_paths() -> None:
    """Reset to default render paths."""
    global _current_paths
    _current_paths = None


def output_dir_for(slug: str, base_paths: RenderPaths | None = None) -> Path:
    """Get output directory for a marca slug.

    Args:
        slug: Marca slug (e.g., 'pinakotheke-kosmos')
        base_paths: Optional custom RenderPaths; uses default if None

    Returns:
        Path to output directory for this marca
    """
    if base_paths is None:
        base_paths = get_render_paths()
    return base_paths.output_dir / slug
