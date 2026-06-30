# Guía de deploy — Eikon en Cloud Run (GCP)

Esta guía cubre cómo buildear la imagen Docker de Eikon y desplegarla en **Cloud Run**,
con Postgres (Neon o Cloud SQL) y Google Cloud Storage como backends de producción.

---

## Arquitectura de la imagen

La imagen es **multi-stage**:

| Stage | Base | Qué hace |
|-------|------|----------|
| `node-build` | `node:20-slim` | Compila la SPA React/Vite → `frontend/dist/` |
| `runtime` | `python:3.12-slim` | Instala deps Python, Playwright/Chromium, copia todo, usuario no-root |

La misma imagen corre en **dev** (SQLite + carpeta local) y en **producción** (Cloud Run con
Postgres y GCS), controlado por variables de entorno:

| Variable | Dev (default) | Producción |
|----------|---------------|------------|
| `DATABASE_URL` | no seteada → SQLite `data/webapp/eikon.db` | `postgresql://user:pass@host/db` |
| `GCS_BUCKET` | no seteada → disco local `output/` | `nombre-del-bucket` |
| `EIKON_WEBAPP_SECRET` | dev-default (solo local) | secret seguro >= 32 chars |
| `EIKON_ENV` | dev | `production` |
| `PORT` | `8080` | `8080` (Cloud Run lo inyecta) |

---

## Modelo de datos — capa dual SQLite ↔ Postgres

El mismo código (`webapp/db.py` + `webapp/storage.py`) habla los dos dialectos.
`init_db()` crea el schema de forma idempotente y, cuando el destino es Postgres,
**traduce el DDL escrito para SQLite** (`webapp/db._schema_for_postgres`):

| SQLite (canónico) | Postgres (traducido) | Por qué |
|-------------------|----------------------|---------|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` | `AUTOINCREMENT` no existe en Postgres; `SERIAL` crea la secuencia `<tabla>_id_seq` que usa `currval` para el last-insert-id |
| `seed INTEGER` | `seed BIGINT` | El `seed` deriva de un hash de 64 bits; el `INTEGER` de Postgres es de 32 bits (overflow) |
| `created_at/started_at/finished_at INTEGER` | `... BIGINT` | Epoch en segundos; se promueven a 64 bits para evitar el límite de 2038 |
| `PRAGMA ...` | (se omite) | Exclusivo de SQLite |

Las FK (`tenant_id`, `brand_id`, `batch_id`) permanecen `INTEGER` para casar con el
PK `SERIAL` (int4). Placeholders `?` se traducen a `%s` en tiempo de ejecución.

No hay que correr migraciones manuales: el primer arranque del contenedor crea el
schema en la BD apuntada por `DATABASE_URL`.

---

## Requisitos previos

1. **Proyecto GCP** creado con facturación habilitada.
2. **APIs habilitadas**:
   ```bash
   gcloud services enable \
     run.googleapis.com \
     cloudbuild.googleapis.com \
     artifactregistry.googleapis.com \
     secretmanager.googleapis.com
   ```
3. **Artifact Registry** — repositorio Docker llamado `eikon`:
   ```bash
   gcloud artifacts repositories create eikon \
     --repository-format=docker \
     --location=us-central1 \
     --project=MI-PROYECTO
   ```
4. **Base de datos Postgres** — se recomienda Neon (serverless) o Cloud SQL.
   El `DATABASE_URL` tiene la forma:
   ```
   postgresql://usuario:contraseña@host:5432/eikon?sslmode=require
   ```
5. **Bucket de GCS** — para almacenar los renders de marcas:
   ```bash
   gcloud storage buckets create gs://eikon-assets-MI-PROYECTO \
     --location=US-CENTRAL1 \
     --project=MI-PROYECTO
   ```
6. **Secreto JWT** — string aleatorio de al menos 32 caracteres:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

---

## Crear los secrets en Secret Manager

```bash
# EIKON_WEBAPP_SECRET
echo -n "EL-SECRET-JWT-GENERADO-ARRIBA" \
  | gcloud secrets create eikon-webapp-secret \
      --replication-policy=automatic \
      --data-file=-

# DATABASE_URL
echo -n "postgresql://user:pass@host:5432/eikon?sslmode=require" \
  | gcloud secrets create eikon-database-url \
      --replication-policy=automatic \
      --data-file=-
```

Para actualizar un secret existente (nueva versión):
```bash
echo -n "NUEVO-VALOR" \
  | gcloud secrets versions add eikon-webapp-secret --data-file=-
```

---

## Autenticar gcloud y Docker

```bash
gcloud auth login
gcloud config set project MI-PROYECTO
gcloud auth configure-docker us-central1-docker.pkg.dev
```

---

## Build y deploy con el script

```bash
# Variables mínimas
export PROJECT=mi-proyecto-gcp
export REGION=us-central1          # donde está el Artifact Registry y correrá el servicio
export SERVICE=eikon
export GCS_BUCKET=eikon-assets-mi-proyecto

# Usar secrets en Secret Manager (recomendado para producción)
export SECRET_STRATEGY=secretmanager
export WEBAPP_SECRET_NAME=eikon-webapp-secret
export DATABASE_URL_SECRET_NAME=eikon-database-url

# Correr desde la raíz del repo
bash deploy/cloud-run.sh
```

El script hace:
1. `gcloud builds submit --tag IMAGE .` — build remoto en Cloud Build (más rápido que local).
2. `gcloud run deploy ...` — despliega el servicio con los parámetros de producción.

Al terminar imprime la URL del servicio y el endpoint `/health`.

---

## Build y deploy manual (alternativa local)

Si tenés Docker instalado localmente y preferís controlar el build:

```bash
IMAGE="us-central1-docker.pkg.dev/MI-PROYECTO/eikon/eikon:latest"

# Build local
docker build -t "$IMAGE" .

# Push a Artifact Registry
docker push "$IMAGE"

# Deploy
gcloud run deploy eikon \
  --project MI-PROYECTO \
  --region us-central1 \
  --image "$IMAGE" \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600s \
  --concurrency 4 \
  --min-instances 1 \
  --set-env-vars "EIKON_ENV=production,GCS_BUCKET=eikon-assets-mi-proyecto" \
  --set-secrets "EIKON_WEBAPP_SECRET=eikon-webapp-secret:latest,DATABASE_URL=eikon-database-url:latest"
```

---

## Probar la imagen localmente (sin Cloud Run)

```bash
# Con SQLite + almacenamiento local (modo dev)
docker run --rm -p 8080:8080 \
  -e EIKON_WEBAPP_SECRET="local-test-secret-de-al-menos-32-chars" \
  eikon-test

# Con Postgres + GCS (simula producción)
docker run --rm -p 8080:8080 \
  -e EIKON_WEBAPP_SECRET="mi-secret-seguro" \
  -e EIKON_ENV=production \
  -e DATABASE_URL="postgresql://user:pass@host:5432/eikon" \
  -e GCS_BUCKET="mi-bucket" \
  eikon-test
```

Verificar que responde:
```bash
curl http://localhost:8080/health
# {"status":"ok","app":"eikon-api","version":"1.0.0"}
```

---

## Configuración de Cloud Run (parámetros clave)

| Parámetro | Valor | Razón |
|-----------|-------|-------|
| `--memory 2Gi` | 2 GB | Chromium (Playwright) necesita al menos 1 GB; 2 GB da margen para renders paralelos |
| `--cpu 2` | 2 vCPUs | Playwright usa CPU intensivamente durante renders |
| `--timeout 600s` | 10 min | Un batch de renders puede tardar varios minutos |
| `--concurrency 4` | 4 requests | Limita la concurrencia para no saturar Chromium |
| `--min-instances 1` | 1 instancia mínima | Chromium tiene cold start lento (~10s); `min-instances 1` lo evita |

---

## Notas de seguridad

- **Nunca** pases `EIKON_WEBAPP_SECRET` o `DATABASE_URL` como env vars directas en producción.
  Usa siempre Secret Manager (`--set-secrets`).
- La cookie JWT usa `httpOnly=True` y `samesite=lax`. En producción, Cloud Run sirve HTTPS
  automáticamente, pero asegurate de setear `EIKON_WEBAPP_COOKIE_SECURE=1` si el servicio
  es accedido exclusivamente por HTTPS.
- El usuario dentro del contenedor es `eikon` (uid 1001, no root).
- Los `--allow-unauthenticated` en Cloud Run son para el servicio web público. Si querés
  restringir el acceso (solo usuarios internos), quitá ese flag y configurá IAP o Cloud Armor.

---

## Validación local sin Docker

La imagen está pensada para Cloud Build / Docker, pero la lógica dual (SQLite vs
Postgres, Local vs GCS) se puede validar sin daemon de Docker:

- **Modo SQLite (dev):** `import webapp.app` sin `DATABASE_URL` selecciona SQLite +
  `LocalStorage`. Smoke completo (register → login → brand → batch de 1 isotipo)
  termina en `completed` y escribe el render en `output/tenants/<id>/...`.
- **Modo Postgres:** levantando un Postgres local (cluster nativo o
  `docker run -d -e POSTGRES_PASSWORD=pw -p 5433:5432 postgres:16`) y exportando
  `DATABASE_URL=postgresql://postgres:pw@localhost:5433/postgres`, el **mismo**
  smoke crea las tablas (`tenants/users/brands/batches/variations`) y persiste la
  variación (el `seed` de 64 bits entra sin overflow gracias a `BIGINT`).
- **Selección de storage:** con `GCS_BUCKET` seteado, `get_storage()` devuelve
  `GCSStorage`; sin él, `LocalStorage` (cubierto por `webapp/tests/test_storage_gcs.py`).

> Nota: para `psycopg` en local instalá la dependencia ya declarada en
> `requirements.txt`: `pip install "psycopg[binary]>=3.1"`.

---

## Checklist final — qué falta para apretar deploy

La imagen y los scripts están listos; para un deploy real sólo faltan los datos del
entorno GCP del owner:

- [ ] **Proyecto GCP** con facturación + APIs habilitadas (`run`, `cloudbuild`,
      `artifactregistry`, `secretmanager`) → exportar `PROJECT`.
- [ ] **Artifact Registry** repo `eikon` en la región elegida (`REGION`).
- [ ] **Connection string Postgres** (`DATABASE_URL`) — Neon o Cloud SQL, con
      `sslmode=require` → guardar en Secret Manager (`eikon-database-url`).
- [ ] **Bucket GCS** creado (`GCS_BUCKET`) + rol `roles/storage.objectAdmin` para
      la service account de Cloud Run.
- [ ] **Secreto JWT** (`EIKON_WEBAPP_SECRET`, >= 32 chars) en Secret Manager
      (`eikon-webapp-secret`).
- [ ] Confirmar `EIKON_ENV=production` y, si todo es HTTPS, `EIKON_WEBAPP_COOKIE_SECURE=1`.

Con esos valores: `bash deploy/cloud-run.sh` (build remoto en Cloud Build + deploy).

---

## Troubleshooting

| Síntoma | Causa probable | Solución |
|---------|---------------|---------|
| Container arranca y se detiene inmediatamente | `EIKON_WEBAPP_SECRET` no seteado o muy corto | Verificar el secret en Secret Manager |
| Error 503 en Cloud Run | Cold start de Chromium > 10s con 0 instancias | Asegurar `--min-instances 1` |
| Renders no aparecen en la galería | `GCS_BUCKET` incorrecto o sin permisos | Dar al SA de Cloud Run el rol `roles/storage.objectAdmin` en el bucket |
| `DATABASE_URL` connection refused | Postgres no accesible desde Cloud Run | Usar Cloud SQL Auth Proxy o Neon con SSL, verificar allowlist de IPs |
| `playwright.errors.Error: browser.close()` | Falta de memoria | Aumentar `--memory` a 4Gi |
