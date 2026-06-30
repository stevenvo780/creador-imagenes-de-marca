# =============================================================================
# Eikon — imagen multi-stage para Cloud Run
#
# Stage 1 (node-build): compila la SPA React/Vite → frontend/dist/
# Stage 2 (runtime):    Python 3.12-slim, Playwright/Chromium, FastAPI/uvicorn
#
# Variables de entorno en runtime:
#   EIKON_WEBAPP_SECRET  — secret JWT >= 32 chars (OBLIGATORIO en producción)
#   EIKON_ENV            — "production" activa validaciones de seguridad
#   DATABASE_URL         — Postgres DSN (si vacío usa SQLite en data/webapp/)
#   GCS_BUCKET           — nombre del bucket GCS (si vacío usa almacenamiento local)
#   PORT                 — puerto de escucha uvicorn (Cloud Run inyecta 8080)
# =============================================================================

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — BUILD SPA (Node 20 slim)
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-slim AS node-build

WORKDIR /build

# Instalar deps solo cuando cambia package-lock.json (aprovecha cache de capas)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copiar fuentes y compilar
COPY frontend/ ./
RUN npm run build
# Resultado en /build/dist/ (vite outDir = "dist")


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — RUNTIME (Python 3.12 slim)
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Dependencias del sistema:
#   - libpq5: runtime de libpq (psycopg3 binary lo usa en tiempo de ejecución)
#   - curl:   healthcheck opcional ("curl -f http://localhost:8080/health")
#   - gnupg + ca-certificates: necesarios para apt de Playwright (interno al script)
# playwright install --with-deps maneja el resto de sus propias deps de Chromium.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── Dependencias Python ──────────────────────────────────────────────────────
# Copiar requirements antes del código para maximizar cache de Docker.
COPY requirements.txt webapp/requirements-webapp.txt ./

# Instalar todo en una sola capa:
#   - requirements.txt       → playwright, Pillow, numpy, psycopg[binary]
#   - requirements-webapp.txt → fastapi, uvicorn, pydantic, httpx
#   - google-cloud-storage   → SDK GCS para el backend de almacenamiento en nube
RUN pip install --no-cache-dir \
    -r requirements.txt \
    -r requirements-webapp.txt \
    google-cloud-storage

# ── Playwright + Chromium ────────────────────────────────────────────────────
# Debe correr como root: --with-deps instala paquetes apt del sistema.
# El directorio de instalación por defecto es /root/.cache/ms-playwright;
# se moverá a /home/eikon/.cache más abajo tras crear el usuario.
RUN python -m playwright install --with-deps chromium

# ── Código fuente ─────────────────────────────────────────────────────────────
COPY eikon_core/       ./eikon_core/
COPY webapp/           ./webapp/
COPY templates/        ./templates/
COPY marcas/           ./marcas/
COPY config/           ./config/
COPY eikon.py contrast_validator.py gallery.py web_icons.py variations.py ./
COPY pyproject.toml ./

# SPA compilada en el stage anterior (vite outDir = "dist")
COPY --from=node-build /build/dist ./frontend/dist

# ── Directorios de runtime ────────────────────────────────────────────────────
# data/webapp/ → SQLite (dev/local); output/ → renders locales (dev/local)
# En Cloud Run con GCS estos pueden permanecer vacíos, pero deben existir.
RUN mkdir -p data/webapp output

# ── Usuario no-root ───────────────────────────────────────────────────────────
RUN groupadd --gid 1001 eikon \
    && useradd --uid 1001 --gid eikon --no-create-home --shell /bin/bash eikon \
    # Playwright almacena Chromium en $HOME; reubicar el cache de root al nuevo usuario
    && mkdir -p /home/eikon \
    && mv /root/.cache /home/eikon/.cache 2>/dev/null || true \
    && chown -R eikon:eikon /app /home/eikon

ENV HOME=/home/eikon

USER eikon

# ── Exposición de puerto ──────────────────────────────────────────────────────
# Cloud Run inyecta PORT=8080. EXPOSE es documentativo; el CMD usa ${PORT:-8080}.
EXPOSE 8080

# ── Entrypoint ────────────────────────────────────────────────────────────────
# exec garantiza que uvicorn recibe SIGTERM directamente (shutdown limpio).
CMD ["sh", "-c", "exec uvicorn webapp.app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
