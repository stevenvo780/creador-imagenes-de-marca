from __future__ import annotations

import sys
from pathlib import Path

_TEMPLATE_ALIASES: dict[str, tuple[str, ...]] = {
    "linkedin_header": ("linkedin_banner",),
    "twitter_header": ("x_header",),
    "youtube_header": ("yt_banner",),
    "web_hero_desktop": ("web_hero",),
}


def resolve_template(type_spec_name: str, templates_dir: Path) -> Path | None:
    """Encuentra el archivo de plantilla HTML para un tipo de asset."""
    exact = templates_dir / f"{type_spec_name}.html"
    if exact.exists():
        return exact

    candidates = _TEMPLATE_ALIASES.get(type_spec_name, ())
    for alias in candidates:
        candidate = templates_dir / f"{alias}.html"
        if candidate.exists():
            return candidate

    existing = sorted(p.name for p in templates_dir.glob("*.html"))
    print(
        f"  ⚠ Template no encontrado para '{type_spec_name}'. "
        f"Templates disponibles ({len(existing)}): {', '.join(existing[:12])}{'…' if len(existing) > 12 else ''}",
        file=sys.stderr,
    )
    return None
