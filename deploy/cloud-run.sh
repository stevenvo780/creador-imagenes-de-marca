#!/usr/bin/env bash
# deploy/cloud-run.sh — Build y deploy de Eikon en Cloud Run (GCP)
#
# USO:
#   export PROJECT=mi-proyecto-gcp
#   export REGION=us-central1          # opcional, default: us-central1
#   export SERVICE=eikon               # opcional, default: eikon
#   export IMAGE=...                   # opcional, se auto-genera si no se pasa
#
#   # Opción A — Secrets en Secret Manager (recomendado para prod):
#   export WEBAPP_SECRET_NAME=eikon-webapp-secret
#   export DATABASE_URL_SECRET_NAME=eikon-database-url
#   export GCS_BUCKET=nombre-del-bucket
#
#   # Opción B — Env vars directas (solo para pruebas rápidas, NO en prod):
#   export EIKON_WEBAPP_SECRET=mi-secret-seguro-de-32-chars
#   export DATABASE_URL=postgresql://user:pass@host:5432/eikon
#   export GCS_BUCKET=nombre-del-bucket
#
#   bash deploy/cloud-run.sh
#
# PREREQUISITOS:
#   - gcloud CLI autenticado: gcloud auth login && gcloud auth configure-docker
#   - Artifact Registry habilitado con repositorio "eikon" en la región
#   - Cloud Run API habilitada
#   - Cloud Build API habilitada
#   - (Para Secret Manager) secrets creados: gcloud secrets create eikon-webapp-secret ...
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Parámetros (sobreescribibles por env) ─────────────────────────────────────
PROJECT="${PROJECT:-}"
REGION="${REGION:-us-central1}"
SERVICE="${SERVICE:-eikon}"
IMAGE="${IMAGE:-}"

# Estrategia de secretos: "secretmanager" (prod) o "envvar" (pruebas rápidas)
SECRET_STRATEGY="${SECRET_STRATEGY:-secretmanager}"

# Nombres de secrets en Secret Manager
WEBAPP_SECRET_NAME="${WEBAPP_SECRET_NAME:-eikon-webapp-secret}"
DATABASE_URL_SECRET_NAME="${DATABASE_URL_SECRET_NAME:-eikon-database-url}"

# Env vars directas (Opción B — solo para pruebas)
EIKON_WEBAPP_SECRET="${EIKON_WEBAPP_SECRET:-}"
DATABASE_URL="${DATABASE_URL:-}"

# Bucket de GCS (no es un secreto, puede ir como env var directa)
GCS_BUCKET="${GCS_BUCKET:-}"

# ── Validaciones ──────────────────────────────────────────────────────────────
if [[ -z "$PROJECT" ]]; then
  echo "ERROR: define PROJECT=<id-proyecto-gcp> antes de correr este script." >&2
  exit 1
fi

if [[ -z "$IMAGE" ]]; then
  IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/eikon/${SERVICE}:latest"
fi

echo ""
echo "=== EIKON DEPLOY ==="
echo "  Proyecto : $PROJECT"
echo "  Región   : $REGION"
echo "  Servicio : $SERVICE"
echo "  Imagen   : $IMAGE"
echo "  Secretos : $SECRET_STRATEGY"
echo ""

# ── Paso 1: Build y push con Cloud Build ──────────────────────────────────────
# Cloud Build toma el contexto del directorio actual (repo root).
# Alternativa local si preferís controlar el build:
#   docker build -t $IMAGE . && docker push $IMAGE
echo "[1/2] Construyendo imagen con Cloud Build..."
gcloud builds submit \
  --project "$PROJECT" \
  --tag "$IMAGE" \
  .

echo ""
echo "[2/2] Desplegando en Cloud Run..."

# ── Paso 2: Armar flags de env vars y secrets ─────────────────────────────────

# Env vars no sensibles (siempre como --set-env-vars)
ENV_VARS="EIKON_ENV=production"
if [[ -n "$GCS_BUCKET" ]]; then
  ENV_VARS="${ENV_VARS},GCS_BUCKET=${GCS_BUCKET}"
fi

# Flags de secrets / env vars sensibles
SECRET_FLAGS=()

if [[ "$SECRET_STRATEGY" == "secretmanager" ]]; then
  # ── Recomendado para producción ──────────────────────────────────────────
  # Los secretos se montan como env vars desde Secret Manager.
  # Prerequisito: secret manager API habilitada y secrets creados.
  #   gcloud secrets create eikon-webapp-secret --replication-policy=automatic
  #   echo -n "mi-secreto" | gcloud secrets versions add eikon-webapp-secret --data-file=-
  #   gcloud secrets create eikon-database-url --replication-policy=automatic
  #   echo -n "postgresql://user:pass@host:5432/eikon" | gcloud secrets versions add eikon-database-url --data-file=-
  SECRET_FLAGS+=(
    "--set-secrets"
    "EIKON_WEBAPP_SECRET=${WEBAPP_SECRET_NAME}:latest,DATABASE_URL=${DATABASE_URL_SECRET_NAME}:latest"
  )
else
  # ── Opción B: env vars directas (solo pruebas) ───────────────────────────
  if [[ -z "$EIKON_WEBAPP_SECRET" ]]; then
    echo "ERROR: EIKON_WEBAPP_SECRET no definido (obligatorio con SECRET_STRATEGY=envvar)." >&2
    exit 1
  fi
  if [[ -n "$EIKON_WEBAPP_SECRET" ]]; then
    ENV_VARS="${ENV_VARS},EIKON_WEBAPP_SECRET=${EIKON_WEBAPP_SECRET}"
  fi
  if [[ -n "$DATABASE_URL" ]]; then
    ENV_VARS="${ENV_VARS},DATABASE_URL=${DATABASE_URL}"
  fi
fi

# ── Paso 3: gcloud run deploy ─────────────────────────────────────────────────
gcloud run deploy "$SERVICE" \
  --project "$PROJECT" \
  --region "$REGION" \
  --image "$IMAGE" \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --no-cpu-throttling \
  --cpu-boost \
  --timeout 600s \
  --concurrency 4 \
  --min-instances 1 \
  --set-env-vars "$ENV_VARS" \
  "${SECRET_FLAGS[@]}"

# NOTA COSTO: --no-cpu-throttling + --min-instances 1 mantienen el worker de
# background con CPU (necesario para renderizar) y el servicio caliente (sin
# cold-start 503), PERO facturan CPU continuamente. Tras una demo/seed, para
# bajar costo: `gcloud run services update eikon --cpu-throttling --min-instances 0`.

# ── Resultado ─────────────────────────────────────────────────────────────────
echo ""
echo "=== Deploy completado ==="
SERVICE_URL=$(
  gcloud run services describe "$SERVICE" \
    --project "$PROJECT" \
    --region "$REGION" \
    --format="value(status.url)"
)
echo "  URL: ${SERVICE_URL}"
echo "  Health: ${SERVICE_URL}/health"
