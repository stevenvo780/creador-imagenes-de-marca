from __future__ import annotations

import re
from pathlib import Path

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,80}$")
CATEGORY_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
PROTECTED_BRAND_SLUGS = frozenset({"prizma", "prizma-pistis"})


def validate_slug(slug: str) -> str:
    if not isinstance(slug, str) or not SLUG_RE.match(slug):
        raise ValueError(f"slug inválido: {slug!r}")
    return slug


def validate_category(category: str | None) -> str | None:
    if category is None or category == "":
        return None
    if not CATEGORY_RE.match(category):
        raise ValueError(f"category inválida: {category!r}")
    return category


def safe_relative_path(root: Path, candidate: Path) -> Path:
    root = root.resolve()
    candidate = candidate.resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("path traversal detectado")
    return candidate
