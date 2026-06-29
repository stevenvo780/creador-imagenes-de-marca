from __future__ import annotations

import sys
from typing import Any

_playwright_cache: Any = None


def _get_playwright() -> Any:
    global _playwright_cache
    if _playwright_cache is None:
        try:
            from playwright.async_api import TimeoutError as PWTimeout
            from playwright.async_api import async_playwright as apw

            _playwright_cache = (apw, PWTimeout)
        except ModuleNotFoundError:
            print("✗ Playwright no instalado. Usa: pip install playwright", file=sys.stderr)
            sys.exit(1)
    return _playwright_cache


async_playwright = None
PlaywrightTimeoutError = Exception
