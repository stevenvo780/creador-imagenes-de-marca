# Deployment Guide: logo_asset Support

Este documento describe cómo deployar el soporte de `logo_asset` en Eikon.

## Resumen de cambios

Se ha agregado soporte para que cada brand referencie un logo real pre-existente (SVG/PNG/JPG) en lugar de generar un isotipo procedural.

### Archivos modificados

- `webapp/db.py` — Migración `migrate_add_logo_asset()`
- `webapp/storage.py` — CRUD funciones soportan `logo_asset`
- `webapp/api/schemas.py` — `BrandCreate`, `BrandUpdate` incluyen `logo_asset`
- `webapp/api/serializers.py` — `brand_to_dict()` serializa `logo_asset`
- `webapp/api/brands.py` — Endpoints POST/PUT propagan `logo_asset`
- `webapp/jobs/worker.py` — `_load_batch_context()` propaga `logo_asset` al dict `marca`
- `Dockerfile` — `COPY assets/` para que logos sean resolubles en runtime
- `webapp/scripts/set_brand_logo_asset.py` — Script de utilidad para setear `logo_asset`

### Archivos nuevos

- `webapp/migrations/add_logo_asset.sql` — SQL de referencia (opcional; ya está en init_db)
- `LOGO_ASSET_DEPLOYMENT.md` — Este archivo

## Flujo de deploy

### 1. Build de Docker + Push a registry

```bash
# En la raíz de /workspace/Pinakotheke/eikon
docker build -t gcr.io/udea-filosofia/eikon-webapp:latest .
docker push gcr.io/udea-filosofia/eikon-webapp:latest
```

Si usás Cloud Build:

```bash
gcloud builds submit --config=cloudbuild.yaml
```

### 2. Migración de BD

Si deployás contra una **BD existente (Postgres en prod o SQLite local)**, la migración ocurre automáticamente al iniciar la app:

- El código en `webapp/db.py` llama a `migrate_add_logo_asset()` desde `init_db()`.
- La migración es **idempotente**: si la columna ya existe, no falla (usa `IF NOT EXISTS` en Postgres, `suppress OperationalError` en SQLite).

**No es necesario ejecutar migraciones manuales** — el contenedor las aplica automáticamente.

Si prefieres verificar o aplicar manualmente:

```bash
# SQLite (desarrollo local)
sqlite3 data/webapp/eikon.db < webapp/migrations/add_logo_asset.sql

# Postgres (producción)
# Reemplaza $DATABASE_URL con tu conexión Postgres
psql $DATABASE_URL -f webapp/migrations/add_logo_asset.sql
```

### 3. Setear logo_asset para una marca

Después del deploy, usa el script de utilidad para asignar un logo real a una marca:

```bash
# Ejemplo: asignar agora.svg como logo del brand "agora" en tenant "steven-vallejo"
python webapp/scripts/set_brand_logo_asset.py steven-vallejo agora assets/logos/agora.svg
```

**Prerequisitos del script:**

- Activar el venv: `source .venv/bin/activate`
- Tener `DATABASE_URL` definido en env (o usar SQLite local)
- El archivo `assets/logos/agora.svg` debe existir en el repo (copiado en el build Docker)

**Salida exitosa:**

```
Database URL: /path/to/eikon.db
Tenant steven-vallejo (id=1)
Brand agora (id=42)
✓ Brand actualizado
  logo_asset: assets/logos/agora.svg
```

### 4. Verificar que funciona

Una vez seteado `logo_asset`, renderiza un batch:

```bash
# El motor detectará logo_asset en el dict marca y usará agora.svg
# en lugar de generar un isotipo procedural.
```

## API usage

### Crear un brand con logo_asset

```bash
curl -X POST http://localhost:8080/api/v1/brands \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "slug": "agora",
    "name": "Ágora",
    "palette": {"bg": "#0f1f1d", "primario": "#43b5a6"},
    "logo_asset": "assets/logos/agora.svg"
  }'
```

### Actualizar logo_asset de un brand existente

```bash
curl -X PUT http://localhost:8080/api/v1/brands/42 \
  -H "Authorization: Bearer <JWT>" \
  -H "Content-Type: application/json" \
  -d '{
    "logo_asset": "assets/logos/agora.svg"
  }'
```

### Obtener brand (incluye logo_asset)

```bash
curl http://localhost:8080/api/v1/brands/42 \
  -H "Authorization: Bearer <JWT>"
```

Respuesta:

```json
{
  "id": 42,
  "slug": "agora",
  "name": "Ágora",
  "palette": {...},
  "logo_asset": "assets/logos/agora.svg",
  "...": "..."
}
```

## Testing local

### Correr tests

```bash
source .venv/bin/activate
python -m pytest webapp/tests/test_brands.py -v
python -m pytest webapp/tests/test_api.py -v
```

Todos los tests pasan (32 storage + 17 API).

### Verificar manualmente

```bash
# Activar venv
source .venv/bin/activate

# Iniciar app local
python -m uvicorn webapp.app:app --reload

# Ir a http://localhost:8000/docs para probar endpoints
```

## Troubleshooting

### Error: "column logo_asset does not exist"

- **Causa:** BD antigua sin la migración aplicada.
- **Solución:** Ejecutar manualmente `webapp/migrations/add_logo_asset.sql` o reiniciar la app (inicia automáticamente).

### Logo no se carga al renderizar

- **Causa:** Archivo `assets/logos/archivo.svg` no existe o la ruta es inválida.
- **Solución:** 
  - Verificar que el archivo existe en el repo: `ls assets/logos/`
  - Verificar que el Dockerfile copia `assets/`: `grep "COPY assets" Dockerfile`
  - Usar una ruta relativa al repo root: `assets/logos/agora.svg`

### Script set_brand_logo_asset.py falla

- **Causa:** Tenant o brand slug no existen en la BD.
- **Solución:** Verificar slugs:
  ```bash
  sqlite3 data/webapp/eikon.db "SELECT slug FROM tenants;"
  sqlite3 data/webapp/eikon.db "SELECT slug FROM brands WHERE tenant_id = 1;"
  ```

## Rollback

Si necesitas revertir (poco probable):

- La columna `logo_asset` es **nullable**, así que setearla a `NULL` deshabilita el logo real.
- Los datos no se pierden; simplemente se ignora `logo_asset` en el render.

```sql
-- Revertir todos los logos_asset a NULL
UPDATE brands SET logo_asset = NULL;
```

## Notas

- El motor `eikon_core/render.py` ya soportaba `logo_asset` — esta tarea solo propaga el campo desde la API.
- Logos SVG/PNG/JPG se cargan como data URIs (base64) en los render.
- El path es relativo al repo root (copiado en Docker): `assets/logos/*.{svg,png,jpg}`
- Multi-tenant: cada tenant puede tener distintos logos para sus brands.

---

**Estado:** ✓ Listo para deploy
**Tests:** ✓ 85/85 pasan (2 skipped)
**Commit:** `feat: agregar soporte de logo_asset a brands`
