# Eikón: proyectos y galería privada de Codex — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Una empresa conecta su Codex, organiza proyectos y marcas e importa una imagen real a su galería privada para revisión humana, con aislamiento comprobado entre empresas.

**Architecture:** Extender FastAPI y React sin sustituir el renderer ni sus tablas. Añadir proyectos, encargos, assets inmutables y revisiones; MCP stdio transmite los bytes generados en el cliente. El calendario y el publicador quedan para planes posteriores que usarán los hashes y aprobaciones de esta entrega.

**Tech Stack:** Python/FastAPI/Pydantic/Pillow, SQLite y Postgres, storage local/GCS, React/TypeScript/Vite, MCP Python por stdio. Usar las dependencias existentes; no añadir proveedores de imágenes pagados.

**Spec:** `docs/superpowers/specs/2026-10-08-eikon-codex-publicaciones-design.md`, aprobada por el usuario el 8 de octubre de 2026. Base: `74454f9bd82ee5f48002f2ba5a3ce3e750bde002`. Checkout: `/datos/workspaces/personal/eikon-codex-publicaciones`, rama `codex/eikon-codex-publicaciones`.

## Global Constraints

- Cada empresa conecta **su propio Codex y sus propias redes**.
- Todas las entidades incorporan `tenant_id`; procede de la autenticación, nunca del cuerpo de la petición.
- Los assets nuevos se almacenan bajo el prefijo de empresa utilizando `get_storage()`.
- PNG/JPEG: máximo 20 MiB y 40 millones de píxeles; dimensiones válidas: 256–8192 píxeles por eje y coincidencia con el encargo.
- Originales y hashes inmutables; cambios de archivo, texto o identidad requieren nueva revisión.
- Las nuevas piezas no tendrán enlaces públicos permanentes.
- El administrador/revisor es el usuario autenticado con el rol `owner` que ya existe en `users`; las API keys no aprueban ni administran claves.
- Las claves antiguas conservan las rutas anteriores, pero no heredan permisos nuevos.
- Los logotipos oficiales se conservan como archivos originales. Ningún upload exitoso ni score implica aprobación.
- No modificar `ad_leaderboard.html`, `letterhead.html` ni `stat_card.html`.
- Conservar los temporizadores y la cola actual de Humanizar; este plan no habilita un nuevo publicador.
- No almacenar datos privados de clientes, claves, respaldos o conversaciones completas en Git.
- Producción requiere Postgres y almacenamiento persistente privado. No crear recursos externos ni cambiar el proyecto de alojamiento para resolver una falta de acceso.

## Review Focus

1. Dos importaciones simultáneas con la misma clave: una sola pieza, sin sobrescribir el original (tarea 4).
2. Identidad modificada entre encargo y upload/revisión: conflicto explícito y conservación de las versiones (tareas 3 y 5).
3. Imagen con extensión válida pero bytes truncados, orientados por EXIF o demasiados píxeles: validación real antes de persistir (tarea 4).
4. Sesión humana con cookies y Authorization juntos, o clave revocada: ninguna elevación accidental ni aprobación mediante una clave (tarea 2).
5. Fallo de GCS/BD tras recibir bytes y una miniatura privada cacheada: no asset aparentemente listo, no exposición entre sesiones (tareas 4, 5 y 7).

## Estructura y contratos compartidos

Crear módulos enfocados:

| Archivo | Responsabilidad |
|---|---|
| `webapp/project_storage.py`, `webapp/api/projects.py` | CRUD y autorización de proyectos. |
| `webapp/migrations.py` | Migraciones aditivas, versionadas e idempotentes por dialecto. |
| `webapp/api/permissions.py` | Scopes de API key y sesión owner. |
| `webapp/brand_briefs.py`, `webapp/api/generation_briefs.py` | Snapshot/versiones de marca y encargos. |
| `webapp/media_validation.py` | Decodificación y límites de imágenes. |
| `webapp/media_storage.py` | Assets, idempotencia y estados de persistencia. |
| `webapp/api/media.py`, `webapp/api/media_reviews.py` | Importación, consulta, descarga y revisión. |
| `mcp_server/media_tools.py` | Herramientas nuevas y upload multipart por HTTPS. |
| `frontend/src/api/media.ts` | Contratos de proyectos, encargos y assets. |
| `frontend/src/pages/ProjectsPage.tsx`, `frontend/src/pages/Media/` | Organización y revisión en la galería. |
| `scripts/import_brand_inventory.py` | Resumen y aplicación privada del inventario. |
| `webapp/tests/media_helpers.py` | Clientes aislados, imágenes sintéticas y helpers de pruebas. |

Modificar únicamente las uniones necesarias en `webapp/app.py`, `webapp/db.py`, `webapp/storage.py`, `webapp/api/deps.py`, `webapp/api/auth_api.py`, `webapp/api/brands.py`, `webapp/api/schemas.py`, `webapp/api/serializers.py`, `mcp_server/server.py`, `frontend/src/App.tsx`, `frontend/src/components/AppShell.tsx` y la galería existente. No reorganizar el motor.

Respuestas JSON nuevas: recurso individual directo; listas `{items, next_cursor}`; errores con `detail` en español y sin datos de otro tenant. IDs enteros positivos dentro del rango de la BD. Scopes exactos: `projects:read`, `projects:write`, `brands:read`, `briefs:write`, `media:read`, `media:write`.

Tipos públicos: `Project{id,slug,name,description,archived}`, `GenerationBrief{id,project_id,brand_id,brand_version,width,height,prompt,status,expires_at,references}`, `MediaAsset{id,project_id,brand_id,brief_id,source,sha256,mime,width,height,byte_size,status,download_url,thumbnail_url,created_at}`. No devolver claves de storage internas ni secretos. Estados: `pending_review`, `approved`, `rejected`, `archived`; durante persistencia `ingesting` no aparece en listas de piezas listas.

Los helpers de pruebas de la tarea 1 expondrán `MediaClients(a, b, db_path, output_root)`, `project(client, slug) -> dict`, `brand(client, project_id, slug) -> dict`, `brief(client, brand_id, width=512, height=512) -> dict`, `image_bytes(width=512, height=512, color='teal') -> bytes` y `upload(client, brief_id, key, data) -> Response`. Todos usan rutas públicas y datos sintéticos; `brief` se empieza a usar cuando la tarea 3 implementa su ruta.

## Task 1: proyectos y migración sin pérdida de marcas

**Files:** Crear `webapp/project_storage.py`, `webapp/migrations.py`, `webapp/api/projects.py`, `webapp/tests/media_helpers.py`, `webapp/tests/test_projects.py`. Modificar `webapp/db.py`, `webapp/app.py`, `webapp/api/schemas.py`, `.gitignore` solo para excluir el entorno local si hace falta.

**Interfaces:** `create_project(db_url, tenant_id, slug, name, description='') -> dict`; `get_project(db_url, tenant_id, project_id) -> dict | None`; `list_projects(db_url, tenant_id, limit=50, cursor=None) -> list[dict]`; `update_project(db_url, tenant_id, project_id, changes: dict) -> dict | None`; `migrate_projects(db_url) -> None`. `/api/v1/projects`, `PATCH /api/v1/projects/{id}`, `POST /api/v1/projects/{id}/archive`.

- [ ] Crear un entorno privado reproducible en `.venv`; instalar requerimientos existentes y registrar la línea base sin corregir fallos ajenos para obtener un verde.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt -r webapp/requirements-webapp.txt -r mcp_server/requirements.txt
.venv/bin/python -m pytest webapp/tests/test_brands.py webapp/tests/test_api.py webapp/tests/test_storage_backend.py tests/test_api_key_auth.py tests/test_multitenant_isolation.py
```

- [ ] Crear `media_helpers.py` con dos `TestClient` distintos contra una sola app y BD temporal; registrar `alpha` y `beta` mediante `/auth/register`, sin arrancar el worker. Usar `Settings(data_root=tmp_path, sqlite_path=tmp_path/'eikon.db', jwt_secret=secrets.token_urlsafe(48))`, `create_app(settings, output_root=tmp_path/'output')`. El helper `project` hace POST con `{slug,name:slug,description:''}` y exige 201. Los helpers `brand` y `brief` usan las rutas y contratos de tareas 3/4. `upload` envía multipart con campos `brief_id`, `source='codex'`, `provenance='{"tool":"image_gen","model":"declared-by-client"}'` y `Idempotency-Key`.

```python
def image_bytes(width=512, height=512, color='teal'):
    stream = io.BytesIO()
    Image.new('RGB', (width, height), color).save(stream, format='PNG')
    return stream.getvalue()

def test_project_is_private(media_clients):
    p = project(media_clients.a, 'campaign')
    assert media_clients.b.get(f'/api/v1/projects/{p["id"]}').status_code == 404
    assert media_clients.b.patch(f'/api/v1/projects/{p["id"]}',
        json={'name': 'Changed'}).status_code == 404
    assert media_clients.b.get('/api/v1/projects').json()['items'] == []
```

- [ ] Ejecutar `pytest webapp/tests/test_projects.py -q`: debe fallar por ruta ausente, no por fixture/import roto.
- [ ] Implementar SQL con `WHERE tenant_id = ? AND id = ?`, unicidad `(tenant_id,slug)`, paginación 1–100 y archivo lógico. Crear `schema_migrations`; añadir columnas mediante introspección segura SQLite/Postgres, sin ejecutar SQL de un input externo. Asignar cada marca existente al proyecto General propio; no borrar ni alterar sus logos/IDs.

```sql
CREATE TABLE IF NOT EXISTS projects (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 tenant_id INTEGER NOT NULL REFERENCES tenants(id),
 slug TEXT NOT NULL, name TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '', archived INTEGER NOT NULL DEFAULT 0,
 created_at INTEGER NOT NULL, UNIQUE(tenant_id, slug)
);
```

- [ ] Probar migración sobre BD con marcas existentes, dos ejecuciones seguidas y ambos dialectos; una transacción fallida no marca la migración como completada. Usar Postgres efímero de pruebas si Docker está disponible; si no, registrar la prueba de Postgres pendiente y no desplegar migración como validada.
- [ ] Ejecutar pruebas nuevas y línea base relevante; commit `feat: añadir proyectos privados y migración de marcas`.

## Task 2: scopes y administración humana de claves

**Files:** Crear `webapp/api/permissions.py`, `webapp/tests/test_media_permissions.py`. Modificar `webapp/api/deps.py`, `webapp/api/auth_api.py`, `webapp/storage.py`, `webapp/migrations.py` y la protección de rutas nuevas de proyectos.

**Interfaces:** `require_scope(user: dict, scope: str) -> None`, `require_owner_session(user: dict) -> None`; principal añade `auth_method: 'session'|'api_key'`, `api_key_id: int | None`, `scopes: frozenset[str]`. `create_scoped_api_key(db_url, tenant_id, name, scopes, expires_at) -> tuple[str,dict]`. La resolución de API keys devuelve metadatos vigentes sin revelar el hash. Claves nuevas: 30 días por defecto, máximo 365; revocables.

- [ ] Escribir pruebas con sesión owner, key con solo `media:write`, key legacy y key expirada. Probar prioridad de cookie y Bearer explícitamente: operaciones humanas requieren sesión válida y `role=='owner'`; el rol no viene del token/cuerpo.

```python
def test_key_cannot_mint_keys(media_clients):
    r = media_clients.a.post('/api/v1/auth/api-keys', json={
        'name': 'codex', 'scopes': ['media:write'], 'expires_in_days': 30})
    assert r.status_code == 201
    agent = TestClient(media_clients.a.app)
    agent.headers['Authorization'] = f'Bearer {r.json()["key"]}'
    assert agent.post('/api/v1/auth/api-keys', json={}).status_code == 403
    assert agent.get('/api/v1/projects').status_code == 403
    assert media_clients.a.delete(f'/api/v1/auth/api-keys/{r.json()["id"]}').status_code == 204
    assert agent.get('/api/v1/media').status_code == 401
```

- [ ] Ejecutar test y comprobar fallo funcional. Implementar scopes como lista JSON validada contra la lista cerrada; rechazar desconocidos, no aceptar `tenant_id`; no guardar el valor de la key. Owner session puede usar rutas nuevas y administrar claves; API keys no pueden crear/listar/revocar otras claves ni revisar assets.

```python
def require_owner_session(user):
    if user['auth_method'] != 'session' or user['role'] != 'owner':
        raise HTTPException(status_code=403, detail='Se requiere sesión de propietario')
```

- [ ] Probar también que una key legacy sigue listando marcas por su ruta anterior y falla en rutas nuevas; que una cookie inválida no se sustituye silenciosamente por otro principal; que una cookie válida de A con Bearer B nunca procesa recursos de B bajo A.
- [ ] Ejecutar tests de autenticación existentes y nuevos; documentar el cambio intencional de administración de claves; commit `feat: limitar claves MCP por permisos y propietario`.

## Task 3: identidad versionada, encargos e inventario privado

**Files:** Crear `webapp/brand_briefs.py`, `webapp/api/generation_briefs.py`, `scripts/import_brand_inventory.py`, `webapp/tests/test_generation_briefs.py`, `webapp/tests/test_brand_inventory.py`. Modificar marcas, schemas, serializadores, migraciones y registro de routers en `webapp/app.py`.

**Interfaces:** `snapshot_brand(db_url, tenant_id, brand_id) -> dict`; `create_generation_brief(db_url, tenant_id, brand_id, prompt, width, height, expires_at) -> dict`; `get_generation_brief(db_url, tenant_id, brief_id) -> dict | None`. GET `/api/v1/brands/{id}/brief`, POST/GET `/api/v1/generation-briefs`. Snapshot incluye proyecto, identidad serializada canónicamente, versión monotónica y hashes/referencias de logos. Una referencia privada se descarga con sesión o scope; no se lee una ruta arbitraria enviada por un cliente.

- [ ] Fijar los helpers `brand` (POST `/brands` con `project_id`) y `brief` (POST con `brand_id,prompt='Pieza de prueba',width,height,expires_in_hours=24`). Escribir:

```python
def test_brief_cannot_use_other_company_brand(media_clients):
    p = project(media_clients.a, 'alpha-campaign')
    b = brand(media_clients.a, p['id'], 'alpha-brand')
    r = media_clients.b.post('/api/v1/generation-briefs', json={
        'brand_id': b['id'], 'prompt': 'Private', 'width': 512, 'height': 512})
    assert r.status_code == 404
    first = brief(media_clients.a, b['id'])
    media_clients.a.put(f'/api/v1/brands/{b["id"]}', json={'name': 'New name'})
    second = brief(media_clients.a, b['id'])
    assert second['brand_version'] > first['brand_version']
```

- [ ] Ejecutar prueba; implementar asociar marca/proyecto con comprobación de empresa, versionar todo cambio de identidad, almacenar snapshot inmutable y vencimiento; bloquear encargos de proyectos archivados. Mantener el contrato de marcas antiguas asignándolas a General cuando no se envía proyecto.

```python
snapshot_json = json.dumps(identity, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
snapshot_hash = hashlib.sha256(snapshot_json.encode('utf-8')).hexdigest()
```

- [ ] Añadir importador con `--base-url`, `--project-id`, `--dry-run` por defecto y `--apply` explícito. Lee la key de variable privada, no de argumento/log. Usa nombres `nombre_producto`, `nombre_corporativo`, `paleta`, `tipografia`, `logo_asset` del inventario; traduce al schema API vigente. Respeta slugs reservados con prefijo de proyecto para importaciones nuevas; conserva mapeo de origen sin modificar fixtures protegidos.
- [ ] Implementar subida autenticada del logo original hacia storage por empresa, saneamiento SVG/data URI existente, sin paths del servidor. Dry-run genera resumen: crear, omitir idéntica, conflicto de identidad, referencia ausente. En conflicto no aplica reemplazo. Repetir `--apply` no duplica ni reasigna marcas; prueba dos tenants con mismo slug y originales de logo cuyo hash permanece igual.

Contrato de logo nuevo: POST multipart `/api/v1/brands/{id}/reference-logo` con scope `media:write` y marca propia; máximo 5 MiB, PNG/JPEG decodificado o SVG saneado por el código existente. Guarda bytes originales en storage, versión y SHA-256; no recibe `logo_asset` como path externo. GET `/api/v1/brands/{id}/reference-logo` requiere sesión o `brands:read`, devuelve bytes y `Cache-Control: private, no-store`. La referencia del snapshot usa esa ruta y el hash. El importador transmite el archivo desde su máquina mediante estos endpoints.
- [ ] Tests de encargos, inventario y regresión de marcas; commit `feat: crear encargos Codex e importar identidad por proyecto`.

## Task 4: importación de imágenes inmutables

**Files:** Crear `webapp/media_validation.py`, `webapp/media_storage.py`, `webapp/api/media.py`, `webapp/tests/test_media_ingest.py`, `webapp/tests/test_media_concurrency.py`. Modificar migraciones y app.

**Interfaces:** `validate_image(content: bytes, expected_width: int, expected_height: int) -> dict` devuelve `sha256,mime,width,height,byte_size,thumbnail_bytes`; `import_media(db_url, storage, tenant_id, brief_id, idempotency_key, content, source, provenance) -> dict`; `get_media(db_url, tenant_id, media_id) -> dict | None`; `list_media(db_url, tenant_id, filters, limit=50, cursor=None) -> list[dict]`. POST multipart `/api/v1/media`, GET lista y detalle. El helper `upload` conserva el contrato indicado al inicio.

- [ ] Escribir tests de idempotencia, hash correcto, estado pendiente y contenido conflictivo.

```python
def test_upload_does_not_overwrite(media_clients):
    p = project(media_clients.a, 'campaign')
    b = brand(media_clients.a, p['id'], 'brand')
    job = brief(media_clients.a, b['id'])
    first = upload(media_clients.a, job['id'], 'same-key', image_bytes())
    assert first.status_code == 201
    again = upload(media_clients.a, job['id'], 'same-key', image_bytes())
    assert again.status_code == 200
    assert again.json()['id'] == first.json()['id']
    conflict = upload(media_clients.a, job['id'], 'same-key', image_bytes(color='red'))
    assert conflict.status_code == 409
    assert first.json()['status'] == 'pending_review'
```

- [ ] Ejecutar y confirmar fallo. Implementar lectura acotada de multipart en bloques, máximo 20 MiB antes de copiar todo a memoria, JSON de procedencia acotado a 16 KiB, MIME real, `Image.verify()` y segunda apertura/`load()`. Tratar warnings de bombas como errores; comprobar dimensiones antes de decodificar, EXIF y orientación. Original queda intacto y miniatura se normaliza; referencias vencidas o identidad cambiada dan 409.

```python
with Image.open(io.BytesIO(content)) as image:
    if image.format not in {'PNG', 'JPEG'}:
        raise ValueError('Formato de imagen no admitido')
    width, height = image.size
    if width * height > 40_000_000 or not all(256 <= v <= 8192 for v in (width, height)):
        raise ValueError('Dimensiones fuera de los límites')
    if (width, height) != (expected_width, expected_height):
        raise ValueError('Dimensiones diferentes del encargo')
    image.verify()
```

- [ ] Persistir con reserva única `(tenant_id,idempotency_key)`, hash y estado `ingesting`; storage usa clave derivada de empresa/ID/hash, nunca nombre de upload. Finalizar `pending_review` solo después de original+miniatura guardados. Reintento de reserva en curso devuelve 409 con causa recuperable, sin sobrescritura; recuperación completa una reserva propia coherente o la marca fallida y limpia objetos. Registrar fallos sin bytes/token.
- [ ] Prueba de carrera con dos conexiones a la BD y barrera, fallo de storage antes de la miniatura, fallo del commit final, archivo PNG truncado, exceso de bytes/píxeles, EXIF rotado y MIME fingido. Comprobar que no aparece una pieza lista incompleta y que no cambia un original previo.
- [ ] Tests de ingest y storage; commit `feat: importar imágenes Codex con validación e idempotencia`.

## Task 5: descargas privadas y revisión de versiones

**Files:** Crear `webapp/api/media_reviews.py`, `webapp/tests/test_media_reviews.py`, `webapp/tests/test_media_downloads.py`. Modificar API/storage de media, migraciones, serializadores y app; conservar los downloads de variaciones existentes.

**Interfaces:** `review_media(db_url, tenant_id, media_id, user_id, decision, expected_sha256, expected_brand_version, reason) -> dict`; `promote_variation(db_url, storage, tenant_id, variation_id) -> dict`. GET `/media/{id}/download`, GET `/media/{id}/thumbnail`, POST `/media/{id}/reviews`, POST `/media/from-variation`. Asset origin guarda `variation_id` y copia inmutable; no reutiliza score como revisión.

- [ ] Escribir una prueba de descarga sin sesión, con sesión ajena y con key de importación sin lectura; otra prueba intenta aprobación por API key.

```python
def test_private_download_and_review(media_clients):
    p = project(media_clients.a, 'campaign')
    b = brand(media_clients.a, p['id'], 'brand')
    job = brief(media_clients.a, b['id'])
    asset = upload(media_clients.a, job['id'], 'one', image_bytes()).json()
    anonymous = TestClient(media_clients.a.app)
    assert anonymous.get(asset['download_url']).status_code == 401
    assert media_clients.b.get(asset['thumbnail_url']).status_code == 404
    response = media_clients.a.post(f'/api/v1/media/{asset["id"]}/reviews', json={
        'decision': 'approved', 'expected_sha256': asset['sha256'],
        'expected_brand_version': job['brand_version'], 'reason': 'Logo y texto revisados'})
    assert response.status_code == 201
    assert media_clients.a.get(f'/api/v1/media/{asset["id"]}').json()['status'] == 'approved'
```

- [ ] Ejecutar prueba y fallar funcionalmente. Implementar `Cache-Control: private, no-store`, content-type real, `X-Content-Type-Options: nosniff`, nombres de descarga saneados y ningún redirect a bucket público. Obtener archivo mediante storage scoped; no `url_for()` para assets nuevos.
- [ ] Revisiones append-only en transacción, comparación de hash/versiones y rol owner desde BD. Rechazo exige motivo. Identidad cambiante y asset archivado dan conflicto; rechazo/aprobación posteriores conservan historial. La revocación de aprobación por cambio de identidad impide que se presente como vigente.

```sql
SELECT * FROM media_assets WHERE tenant_id = ? AND id = ?;
INSERT INTO asset_reviews(tenant_id, media_id, sha256, brand_version,
 decision, reason, reviewer_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
```

- [ ] Probar variación legacy seleccionada/score positivo: copia aparece pendiente; verificar igualdad de hash del original. Probar downgrade de owner antes de revisión, lectura cruzada, caché tras logout y mock GCS sin URL pública. Auditar configuración real del bucket antes de afirmar privacidad de objetos antiguos; no cambiar permisos globales sin conocer qué aplicaciones comparten bucket.
- [ ] Tests de revisión, descargas, aislamiento y regresión legacy; commit `feat: revisar assets inmutables y servir galería privada`.

## Task 6: herramientas MCP de encargos e importación

**Files:** Crear `mcp_server/media_tools.py`, `mcp_server/tests/test_media_tools.py`. Modificar `mcp_server/server.py`, `mcp_server/README.md`, `mcp_server/QUICKSTART.md`.

**Interfaces:** Async `eikon_list_projects()`, `eikon_create_project(name: str, slug: str, description: str='')`, `eikon_get_brand_brief(brand_id: int)`, `eikon_create_generation_brief(brand_id: int, prompt: str, width: int, height: int)`, `eikon_import_image(brief_id: int, file_path: str, idempotency_key: str, provenance: dict | None=None)`, `eikon_list_media(project_id: int | None=None, brand_id: int | None=None, status: str | None=None)`. Todas devuelven `dict` con `success` y recurso/error seguro; los wrappers MCP serializan JSON y se registran tanto en FastMCP como en fallback.

- [ ] Escribir tests con `httpx.MockTransport` para multipart y errores; cliente HTTP se inyecta en `MediaTools(base_url, api_key, client)` y las funciones públicas usan esa unidad. No enviar la key a destinos indicados por el usuario ni seguir redirects de uploads autenticados.

```python
@pytest.mark.asyncio
async def test_import_sends_bytes_not_server_path(tmp_path):
    path = tmp_path / 'image.png'
    path.write_bytes(image_bytes())
    def handle(request):
        assert request.url.path == '/api/v1/media'
        assert b'image/png' in request.content
        assert image_bytes() in request.content
        assert str(path).encode() not in request.content
        return httpx.Response(201, json={'id': 9, 'status': 'pending_review'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        tools = MediaTools('https://example.invalid', 'test-key', client)
        result = await tools.import_image(1, str(path), 'key-one', {})
    assert result['success'] is True
```

- [ ] Ejecutar test y comprobar fallo. Si no hay `pytest-asyncio` entre dependencias existentes, usar test síncrono con `asyncio.run()` para esta prueba; no añadir un plugin para un solo caso.
- [ ] Implementar archivo cliente permitido y de tamaño acotado, basename fijo de upload, multipart y headers Bearer; no revelar Authorization ni cuerpos sensibles al construir error. HTTP 401/403/409/413/422 produce causa recuperable, no éxito vacío. Key obtenida del entorno privado del cliente y base URL HTTPS configurada; HTTP solo para localhost de desarrollo.

```python
response = await self.client.post(
    f'{self.base_url}/api/v1/media',
    headers={'Authorization': f'Bearer {self.api_key}', 'Idempotency-Key': key},
    data={'brief_id': str(brief_id), 'source': 'codex', 'provenance': json.dumps(provenance)},
    files={'file': ('image.png', content, 'image/png')},
    follow_redirects=False,
)
```

- [ ] Probar listado real de tools en sesión MCP stdio y una llamada autenticada contra servidor local con tenant sintético; no basta importar el módulo. Verificar revocación con una segunda llamada. Documentar: obtener kit → generar con herramienta del cliente → importar → revisión humana; nunca prometer que MCP genera por sí mismo ni pedir una key de API de imágenes.
- [ ] Ejecutar pruebas MCP y registrar recibo sin secretos; commit `feat: conectar Codex a encargos y galería por MCP`.

## Task 7: proyectos, galería y revisión en React

**Files:** Crear `frontend/src/api/media.ts`, `frontend/src/pages/ProjectsPage.tsx`, `frontend/src/pages/Media/MediaCard.tsx`, `frontend/src/pages/Media/MediaDetail.tsx`, `frontend/src/pages/Media/ApiKeysPanel.tsx`. Modificar `App.tsx`, `AppShell.tsx`, galería y editor de marcas; estilos en un archivo de Media propio.

**Interfaces:** Tipos descritos en contratos compartidos; `listProjects()`, `createProject(payload)`, `listMedia(filters)`, `getMedia(id)`, `reviewMedia(id,payload)`, `createCodexKey(payload)`. Fetch con credentials include. No localStorage de key; respuesta secret mostrada una sola vez y borrada al cerrar panel o salir.

- [ ] Preparar un servidor local con dos empresas sintéticas. Escribir comprobaciones de interacción Playwright para crear proyecto, filtrar marca/origen/estado, abrir imagen y rechazar/aprobar; pruebas hacen assertions de DOM y requests, no snapshots que repliquen JSX.

```python
page.get_by_role('link', name='Proyectos', exact=True).click()
page.get_by_role('button', name='Nuevo proyecto', exact=True).click()
page.get_by_label('Nombre del proyecto').fill('Campaña local')
page.get_by_role('button', name='Guardar', exact=True).click()
expect(page.get_by_text('Campaña local', exact=True)).to_be_visible()
page.get_by_role('link', name='Galería', exact=True).click()
expect(page.get_by_text('Pendiente de revisión', exact=True).first).to_be_visible()
```

- [ ] Confirmar fallo funcional en UI actual. Implementar páginas y acceso por rol usando sesión existente; conservar tarjetas legacy con etiquetas de origen y promoción a revisión. Estados vacíos, errores de sesión, rechazo con motivo, conflicto de versión y carga tienen mensajes y acciones claros. Owner ve aprobar; un agente no recibe acceso humano desde la UI.

```typescript
export type MediaStatus = 'pending_review' | 'approved' | 'rejected' | 'archived';
export const mediaLabels: Record<MediaStatus, string> = {
  pending_review: 'Pendiente de revisión', approved: 'Aprobado',
  rejected: 'Rechazado', archived: 'Archivado',
};
```

- [ ] Usar miniaturas con cookie y rutas autenticadas. Al logout cancelar fetches y limpiar estado; no conservar una imagen blob de A al entrar como B. Probar teclado, foco del diálogo, errores 401/409, escritorio 1440×900 y móvil 390×844.
- [ ] `npm ci` y `npm run build` desde frontend; ejecutar recorrido real de Estudio cliente y upload para comprobar regresión, diferenciándolo del batch server. Inspeccionar píxeles de capturas y guardar artefactos fuera de Git privado cuando tengan datos reales.
- [ ] Commit `feat: organizar proyectos y revisar imágenes en galería`.

## Task 8: imagen real de Codex, privacidad de producción y cierre

**Files:** Crear `docs/QA-GALERIA-CODEX.md`, `docs/DEPLOY-GALERIA-CODEX.md`. Modificar README/CLAUDE/AGENTS solo donde cambia el comportamiento. Evidencia privada en una carpeta externa al repo; no fixtures con marca/contactos de clientes.

**Interfaces:** Consume todos los contratos anteriores. Produce recibo de prueba con empresa autorizada, IDs de proyecto/encargo/asset/revisión, hashes, SHA de release, resultado de autenticación/MCP/UI y comprobación de descarga anónima, sin tokens.

- [ ] Ejecutar suite nueva completa y regresiones relevantes. Ejecutar lint/types del alcance; comparar con la línea base y declarar fallos previos separadamente. Probar migraciones SQLite y Postgres, storage local y contrato GCS; ninguna omisión se etiqueta como PASS.

```bash
.venv/bin/python -m pytest webapp/tests tests mcp_server/tests
.venv/bin/python -m ruff check webapp/project_storage.py webapp/migrations.py webapp/brand_briefs.py webapp/media_validation.py webapp/media_storage.py webapp/api/projects.py webapp/api/permissions.py webapp/api/generation_briefs.py webapp/api/media.py webapp/api/media_reviews.py mcp_server/media_tools.py
.venv/bin/python -m mypy webapp/project_storage.py webapp/brand_briefs.py webapp/media_validation.py webapp/media_storage.py
git diff --check
gitleaks git --redact --no-banner
```

- [ ] Conectar la empresa del propietario mediante sesión autorizada; usar el resumen de inventario para organizar sus marcas sin sustituir identidades en conflicto. Humanizar Systems/News usan el kit vigente. Comprobar la identidad de la cuenta antes de emitir su key scoped.
- [ ] Realizar una llamada MCP autenticada desde el cliente Codex; obtener un encargo y referencias. Generar una imagen con `image_gen` integrado, incorporar el logo oficial exacto, inspeccionar los píxeles e importarla mediante MCP. Registrar hash y comprobar la imagen en la galería. Una sesión local aislada MCP aporta prueba del protocolo; solo afirmar «conectado en Codex» si la llamada se hizo desde la conexión real del cliente. Si falta reconexión humana del MCP, dejar esa prueba explícitamente pendiente.
- [ ] Revisar la pieza con sesión owner. Probar que otro tenant y usuario anónimo no descargan original/miniatura ni acceden al encargo. Generar una segunda pieza de prueba para el otro tenant y comprobar aislamiento simétrico.
- [ ] Inspeccionar acceso real a Cloud Run, DB, bucket y configuración del proxy Vercel. Preparar copia privada recuperable de configuración y DB; nunca imprimir sus valores. Ensayar migración y rollback en copia aislada. Si falta acceso o el bucket comparte objetos públicos con otra app, documentar el bloqueo y solicitar únicamente ese acceso/decisión antes de tocar permisos compartidos.
- [ ] Desplegar la versión probada en el proyecto existente mediante su flujo verificado, sin activar servicios pagados ni crear proyectos nuevos. Comprobar frontend, rutas profundas, cookies Secure same-origin, upload multipart a través del proxy y una descarga privada real. Registrar SHA/digest y repetir una prueba funcional acotada en el despliegue. Si producción no puede actualizarse, entregar la versión local/preview validada y el motivo exacto; no declarar despliegue completo.
- [ ] Confirmar que temporizadores/cola de Humanizar no cambiaron. Preparar la revisión de rama con riesgos y evidencia; adjuntar cualquier PR creada al chat. No fusionar trabajo ajeno ni commits de los checkouts sucios.
- [ ] Commit `docs: documentar pruebas y despliegue de galería Codex` y entregar resultado comprobado, limitaciones externas y siguiente entrega de conexiones sociales.

## Matriz de cobertura y ejecución

| Requisito del diseño | Tareas |
|---|---|
| Empresas/proyectos y conservación de datos anteriores | 1, 3 |
| Claves revocables, roles y scopes | 2, 6, 7 |
| Inventario y logos oficiales/versionados | 3, 8 |
| Imagen real, validación, hash y reintentos | 4, 6, 8 |
| Revisión humana, rechazo e historia inmutable | 5, 7, 8 |
| Galería privada e aislamiento simétrico | 1–5, 7, 8 |
| UI real y regresión de renderizado cliente | 7, 8 |
| Evidencia de servicio, migración y despliegue | 1, 8 |
| Conservación de publicador y contratos para próximas fases | Restricciones globales, 8; conexiones/calendario/trabajador tienen planes separados. |

Revisión propia: firmas y campos compartidos cotejados; cada riesgo del Review Focus tiene prueba asignada. Las tareas producen entregables comprobables y siguen el orden de sus dependencias. La implementación permanece pendiente de la revisión del plan y selección del método de ejecución por el usuario.
