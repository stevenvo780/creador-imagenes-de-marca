# Eikón MCP: encargos y galería privada

Este servidor local por **stdio** conecta el cliente MCP de cada empresa con su
API Eikón. El cliente obtiene el kit de marca, crea un encargo, genera la imagen
con su propia herramienta de imágenes y entrega los bytes a Eikón. El upload
queda en `pending_review`; un owner autenticado revisa logo, textos e identidad.
MCP no ejecuta remotamente la herramienta integrada `image_gen` ni necesita una
clave de API de imágenes. La conexión efectiva desde Codex debe comprobarse en
ese cliente; una sesión SDK sintética sólo verifica el transporte y la API.

## Instalación y configuración privada

Python 3.10+ y backend Eikón compatible con proyectos, encargos y medios:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r mcp_server/requirements.txt
```

Configure en el entorno privado del proceso `EIKON_BASE_URL` y `EIKON_API_KEY`.
La base debe ser un origen HTTPS sin usuario, password, query, fragmento ni ruta.
Se permite HTTP para `localhost`, `127.0.0.1` o `::1` en desarrollo local. El
servidor no sigue redirecciones autenticadas de las herramientas nuevas.

El owner obtiene la clave en la administración autenticada de Eikón
(`POST /api/v1/auth/api-keys`), elige scopes explícitos y conserva la clave fuera
de Git y de conversaciones. Cada empresa usa su propia clave y conexión.
La clave se entrega una sola vez; revocación y caducidad se comprueban en cada
request. Las claves heredadas NULL conservan sus rutas antiguas y no acceden a
proyectos, encargos ni medios nuevos.

Configure su host MCP con el Python del entorno virtual, el script absoluto
`/ruta/al/repositorio/mcp_server/server.py` y las dos variables privadas. También
se puede arrancar desde la raíz del checkout:

```bash
.venv/bin/python -m mcp_server.server
```

No se abre un puerto MCP. No copie sesiones, cookies o `auth.json` entre cuentas.
La comprobación de disponibilidad exige `list_tools` y una llamada autenticada;
importar el módulo o invocar una función Python no prueba la conexión del host.

## Herramientas nuevas

Todas devuelven JSON con `success` y el recurso o un error seguro.

| Herramienta | Parámetros | Scope | Recurso |
|---|---|---|---|
| `eikon_list_projects` | ninguno | `projects:read` | `projects` (`items`, `next_cursor`) |
| `eikon_create_project` | `name`, `slug`, `description=''` | `projects:write` | `project` |
| `eikon_get_brand_brief` | `brand_id: int` | `brands:read` | `brand_brief` |
| `eikon_create_generation_brief` | `brand_id`, `prompt`, `width`, `height` | `briefs:write` | `brief` |
| `eikon_import_image` | `brief_id`, `file_path`, `idempotency_key`, `provenance={}` | `media:write` | `media` |
| `eikon_list_media` | `project_id?`, `brand_id?`, `status?` | `media:read` | `media` (`items`, `next_cursor`) |

`file_path` señala un archivo explícito en el **equipo donde se ejecuta el
proceso MCP**. No es una ruta en el servidor HTTP ni una URL descargable.
El proceso lee un archivo regular PNG/JPEG (sin symlink final), verifica su
formato real y sube bytes multipart con un basename fijo `image.png` o
`image.jpg`. No envía la ruta ni el nombre original. Límite: 20 MiB, 40 millones
de píxeles, 256–8192 por eje. La API además exige coincidencia con el encargo y
su snapshot vigente. `provenance` es un objeto JSON acotado declarado por el
cliente; no certifica por sí mismo el proveedor o modelo usado.

Una misma clave de idempotencia y el mismo contenido recuperan el recurso
original. Si cambia archivo, encargo o provenance, use una clave nueva; un
conflicto HTTP 409 exige revisar el encargo o la identidad, nunca autoaprobar.
Las referencias originales de logo del kit se conservan; utilice sus recursos
autenticados sin reemplazarlos por una recreación generativa.

`eikon_list_media` devuelve estado efectivo, historial y URLs relativas de
descarga/thumbnail autenticadas. No son enlaces públicos permanentes. Un
estado `approved` sólo cuenta cuando `approval_current` sigue vigente. La API
no permite a ninguna API key revisar medios, administrar claves ni escribir
identidad. Estos actos requieren sesión owner.

## Flujo del cliente

1. Liste proyectos y obtenga `eikon_get_brand_brief` de la marca autorizada.
2. Cree un encargo con prompt y dimensiones mediante `eikon_create_generation_brief`.
3. Genere y revise visualmente en su cliente, incorporando el logo original.
4. Importe el archivo con `eikon_import_image`, una clave estable y provenance.
5. Consulte `eikon_list_media`; el owner revisa la pieza en Eikón antes de usarla.

## Compatibilidad anterior

Se conservan `eikon_list_brands`, `eikon_create_brand`, `eikon_logo_options`,
`eikon_set_identity`, `eikon_list_asset_types`, `eikon_generate_asset`,
`eikon_generate_and_get` y `eikon_gallery`, junto con sus ocho aliases históricos
con sufijo `_tool`. Estas herramientas conservan el motor determinista previo.
Los permisos efectivos los decide la API: una herramienta visible no concede
permiso para cambiar identidad. Hay 14 nombres canónicos y 8 aliases.

La capa alta admite FastMCP SDK v1 y MCPServer SDK v2. El registro de herramientas
se comparte con el fallback low-level. Para probarlo se puede establecer
`EIKON_MCP_LOWLEVEL=1`; no cambia la clave ni sus permisos.

## Errores y verificación

Los errores nuevos no contienen token, cuerpo remoto, traceback o ruta privada.
`error_code` indica la causa; `http_status` aparece en fallos HTTP:

| HTTP | `error_code` | Acción |
|---|---|---|
| 401 | `unauthorized` | Owner comprueba revocación/caducidad y la clave configurada |
| 403 | `forbidden` | Owner revisa scopes; no aumenta permisos automáticamente |
| 404 | `not_found` | Compruebe empresa/recurso |
| 409 | `conflict` | Revise identidad, encargo e idempotencia |
| 413 | `too_large` | Reduzca la imagen |
| 422 | `invalid_request` | Corrija parámetros/dimensiones |
| 3xx | `redirect_refused` | Revise la base HTTPS configurada |

Desde la raíz, con dependencias de desarrollo instaladas:

```bash
.venv/bin/python -m pytest mcp_server/tests tests/test_mcp_generate_and_get.py
.venv/bin/python -m pytest --collect-only
.venv/bin/ruff check mcp_server/server.py mcp_server/media_tools.py mcp_server/tests
.venv/bin/mypy --follow-imports=silent mcp_server/server.py mcp_server/media_tools.py
```

`test_media_stdio.py` usa subprocess real, `ClientSession`, HTTP local sin
worker, SQLite aislada y Postgres de prueba cuando se define
`EIKON_TEST_POSTGRES_URL`. Verifica las seis herramientas, bytes/hash,
idempotencia, tenant extranjero, descargas privadas, caducidad, revocación y
restricciones de identidad/revisiones/administración. Sin esa variable, los
casos Postgres quedan explícitamente omitidos.

Fuentes oficiales de compatibilidad: [migración SDK MCP v1→v2](https://py.sdk.modelcontextprotocol.io/migration/),
[servidor low-level](https://py.sdk.modelcontextprotocol.io/advanced/low-level-server/),
[HTTPX](https://www.python-httpx.org/),
[pytest-asyncio para las pruebas async anteriores](https://pytest-asyncio.readthedocs.io/en/stable/).
