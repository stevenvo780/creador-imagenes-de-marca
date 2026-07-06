"""Server-rendered Jinja2 templates for the webapp UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _fmt_dt(value: int | float | None) -> str:
    if not value:
        return "—"
    import datetime as _dt

    return _dt.datetime.fromtimestamp(int(value)).strftime("%Y-%m-%d %H:%M:%S")


def _fmt_bytes(value: int | float | None) -> str:
    if value is None:
        return "—"
    n = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:,.1f} {unit}"
        n /= 1024
    return f"{n:,.1f} TB"


def _fmt_status(value: str | None) -> str:
    return value or "unknown"


def _pills(value: str | None) -> str:
    m = {
        "queued": "info",
        "running": "warn",
        "completed": "ok",
        "failed": "danger",
        "cancelled": "muted",
    }
    status_class = m.get(value or "", "muted")
    return f'<span class="pill {status_class}"><span class="dot"></span>{value or "—"}</span>'


env.filters["dt"] = _fmt_dt
env.filters["bytes"] = _fmt_bytes
env.filters["status_pill"] = _pills


def render_template(name: str, **context: Any) -> str:
    template = env.get_template(name)
    return template.render(**context)  # type: ignore[no-any-return]


def render(
    request: Request,
    name: str,
    *,
    user: Any | None = None,
    active: str = "",
    show_chrome: bool = True,
    **context: Any,
) -> HTMLResponse:
    context.setdefault("request", request)
    context.setdefault("static_base", "/static")
    context.setdefault("user", user)
    context.setdefault("active", active)
    context.setdefault("show_chrome", show_chrome)
    html = render_template(name, **context)
    return HTMLResponse(html)


def redirect(location: str, status_code: int = 303) -> RedirectResponse:
    return RedirectResponse(location, status_code=status_code)
