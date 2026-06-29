from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARCAS_DIR = ROOT / "marcas"
TEMPLATES_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT / "output"

ENGINE_VERSION = "eikon-v1.2"
TIMEOUT_MS = 18_000
FONT_TIMEOUT_MS = 2_500
DEFAULT_LOCALE = "es"
MIN_PNG_BYTES = 100
