"""Routers JSON de la API v1 de Eikon (multi-tenant, scoped por cookie JWT).

Cada router se monta en webapp/app.py vía include_router. Las dependencias
compartidas (current_user, settings) viven en webapp/api/deps.py y leen su
configuración desde request.app.state, fijada por create_app().
"""

from __future__ import annotations

from .auth_api import auth_api_router
from .batches import router as batches_router
from .brands import router as brands_router
from .client_render import router as client_render_router
from .downloads import router as downloads_router
from .gallery import router as gallery_router
from .variations import router as variations_router
from .wizard import router as wizard_router

__all__ = [
    "auth_api_router",
    "batches_router",
    "brands_router",
    "client_render_router",
    "downloads_router",
    "gallery_router",
    "variations_router",
    "wizard_router",
]
