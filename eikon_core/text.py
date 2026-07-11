from __future__ import annotations

TEXT_LIMITS: dict[str, dict[str, int]] = {
    "business_card": {"titulo": 38, "subtitulo": 44, "copy": 62, "url": 36},
    "og_general": {"titulo": 58, "subtitulo": 56, "copy": 132, "url": 42},
    "stat_card": {"titulo": 48, "copy": 86, "url": 34},
    "ad_leaderboard": {"titulo": 26, "copy": 58, "url": 32},
    "ad_rectangle": {"titulo": 26, "copy": 58, "url": 32},
    "letterhead": {"titulo": 68, "subtitulo": 62, "copy": 190, "url": 42},
    "lockup_horizontal": {"titulo": 42, "subtitulo": 58},
    "lockup_vertical": {"titulo": 42, "subtitulo": 58},
    "wordmark": {"titulo": 42, "subtitulo": 70},
    "isotipo": {"titulo": 28},
    "watermark": {"titulo": 42},
    "favicon": {"titulo": 20},
    "linkedin_header": {"titulo": 62, "subtitulo": 44, "copy": 90, "url": 42},
    "twitter_header": {"titulo": 52, "copy": 72, "url": 42},
    "youtube_header": {"titulo": 64, "copy": 100, "url": 42},
    "web_hero_desktop": {"titulo": 56, "copy": 92, "url": 42},
}


def shorten_text(text: str, limit: int) -> str:
    """Trunca texto en límites de frase/palabra con elipsis visible."""
    text = " ".join((text or "").split())
    if not limit or len(text) <= limit:
        return text
    cut = text[: limit + 1]
    for sep in (". ", "; ", ": ", ", ", " "):
        pos = cut.rfind(sep)
        if pos >= max(40, int(limit * 0.55)):
            return cut[:pos].rstrip(" .;:,") + "…"
    return cut[:limit].rstrip() + "…"


def apply_text_limits(tipo: str, vars_dict: dict[str, str]) -> dict[str, str]:
    """Aplica límites de texto a título, subtítulo, copy y url."""
    limits = TEXT_LIMITS.get(tipo, {})
    result = dict(vars_dict)
    for campo in ("titulo", "subtitulo", "copy", "url"):
        if campo in limits and campo in result:
            result[campo] = shorten_text(result[campo], limits[campo])
    return result
