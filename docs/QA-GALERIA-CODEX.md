# QA de galería privada y Codex MCP

Estado al **2026-10-09 16:24:04 UTC**: código Task7 aprobado en revisión independiente; flujo Codex nativo **local** y pieza final local comprobados por el controlador. **GUI autenticada y release de producción pendientes.** Esta documentación es una entrega con reservas, no el cierre de Task8.

Baseline de esta fase: `ea9aab7d01bb23b901adafb0a0cdf949c97f062c`. La suite Python corresponde a producto `259101bf741585d73121ead12af9132f610bb928`; el fix posterior sólo cambia frontend/QA. Los recibos de Tasks1–7 y del controlador se conservan en el ledger local del workflow o en evidencia privada fuera de Git. Este documento reproduce sus resultados saneados; el escritor de documentación no repitió esas suites ni abrió respaldos, vault o datos reales.

## Comportamiento aceptable

- Cada empresa usa su propio Codex y sus propias redes. `tenant_id` procede de autenticación; ninguna petición del cliente decide la empresa.
- Proyecto → marca y logo oficial versionado → encargo congelado → imagen → importación → `pending_review` → decisión de sesión `owner`. Subir, puntuar o seleccionar una pieza nunca equivale a aprobarla.
- PNG/JPEG: máximo **20 MiB**, **40 millones de píxeles**, **256–8192 por eje**, y dimensiones iguales al encargo. El límite de lectura del upload no demuestra un límite del cuerpo multipart en el proxy.
- El original y su SHA256 son inmutables. Cambiar archivo, texto o identidad exige nueva revisión; el historial es append-only. Una aprobación histórica obsoleta pierde `approval_current` sin borrar la historia.
- Originales y miniaturas nuevos usan `get_storage()` y prefijo de empresa; las URLs de API son relativas y autenticadas, sin enlaces públicos permanentes. Las imágenes en frontend son blobs efímeros revocados al cerrar/cambiar sesión.
- Los seis scopes posibles son `projects:read`, `projects:write`, `brands:read`, `briefs:write`, `media:read`, `media:write`. Las API keys no revisan, administran claves ni escriben identidad. Las antiguas conservan rutas anteriores, sin heredar permisos nuevos.
- Logos oficiales se incorporan desde sus bytes originales. El renderer determinista conserva su flujo cliente; la imagen generada por Codex procede de `image_gen` integrado del cliente y se importa mediante MCP.
- No hay un nuevo publicador, conexión social, calendario ni trabajador de publicación en esta entrega. Temporizadores y cola existentes de Humanizar se conservan. Las plantillas protegidas `ad_leaderboard.html`, `letterhead.html`, `stat_card.html` no cambian.

## Matriz de aceptación

| Requisito | Evidencia comprobada | Límite/gate restante |
|---|---|---|
| Proyectos privados y conservación de marcas | Tasks1/3: CRUD, paginación, backfill General por tenant, aislamiento y migración aditiva en SQLite/PG sintéticos | Importación de inventario real de producción pendiente |
| Migración y compatibilidad de datos anteriores | Controlador: restauración privada PG17 sin red/puertos, `init_db` dos veces, igualdad exacta de columnas originales frente a segunda restauración limpia: 4 tenants, 4 usuarios, 62 marcas, 6 keys; cuatro tablas nuevas de medios vacías | Rollback verificado con código anterior sólo para startup/lecturas; no cubre todo el worker ni escrituras |
| Roles/scopes/caducidad/revocación | Tasks2/6: negativas 401/403, sesión owner, revocación en sesión stdio real; keys legacy sin rutas nuevas | UI key-once, teclado y rol efectivo pendientes de navegador real |
| Inventario y logos | Dry-run corregido de 56 marcas legacy: create 56 / missing 0 / conflict 0 / identical 0 con `--logo-root` del repo. Negativo anterior missing 56 conservado. Systems/News: creación local 1 cada una y repetición identical 1 cada una | No aplicar las 56 a Humanizar ni reasignar tenants; importación propia a producción pendiente |
| Imagen y validación | Tasks4/6: bytes/MIME/hash, límites, idempotencia durable, carreras/recuperación, CRC PNG real rechazado; original exacto y thumbnail normalizado | GCS real y multipart del proxy requieren prueba después del release |
| MCP SDK real | Task6: cuatro subprocesos stdio reales, SQLite/PG × capa alta/fallback, initialize/list/call, 22 nombres, seis tools nuevas, replay/aislamiento/revocación | SDK v2.3 probado; rama SDK v1 conservada según contrato, sin runtime separado probado |
| Codex nativo e imagen integrada | Controlador: CLI real con cuenta/proveedor existentes, cinco tools nuevas ejecutadas en flujo local; pieza final 1024 con logo original+Manrope+fondo `image_gen`, píxeles inspeccionados, import/listado nativos | Destino LOCAL HTTP 8846; conexión Codex a producción pendiente |
| Revisión humana e historia | Tasks5/7 y controlador: aprobación/rechazo, hash/versión/snapshot, owner desde BD, historia inmutable; key-review403, owner-review201 local | Recorrido GUI de revisión y producción pendiente |
| Aislamiento simétrico | Controlador: Alpha→Bravo y Bravo→Alpha, encargo/original/thumbnail404; anónimo401 en ambas. Descargas propias200, bytes/hash idénticos y `no-store` | Objetos nuevos GCS y proxy de producción aún pendientes |
| Frontend y renderer | Task7 final: 35/35 regresiones controladas, tsc/Vite; seam logo exacto PNG/JPEG/SVG y Manrope probados | DOM/rasterizer controlados no prueban modern-screenshot, FontFace nativa, píxeles ni GUI |
| GUI desktop/mobile | Protocolo sintético preparado en loopback 8867 | BLOCKED: Brave impide automatización por otro panel de extensión; último `/auth/me`401. No recorrido autenticado, capturas ni mobile PASS |
| Privacidad/auth de producción | Controlador 15:34Z: revisión vigente sin cambios; IAM del bucket sin allUsers/allAuthenticatedUsers; objeto anterior anónimo403. Login propio 16:24:04Z por proxy HTTPS: /auth/login200 y /auth/me200, owner, cookie Secure/HttpOnly/SameSiteLax | No equivale a prueba de original/thumbnail nuevos, multipart, MCP ni UI de producción |
| Release y preservación Humanizar | Ambas tareas temporizadas existentes activas y sin cambios, verificación SSHserver2 del controlador | Revisión Task8 y rama completa, release y recibo SHA/digest pendientes; ver [runbook](DEPLOY-GALERIA-CODEX.md) |
| Imagen Docker empaquetada | Controlador: build exacto `ea9aab7`, runtime UID1001 sin red, ASGI sintético de proyecto/encargo/upload/descargas/review y Manrope | Imagen local; no digest de Artifact Registry, GUI ni despliegue |

## Comandos y resultados recibidos

Todos desde `/datos/workspaces/personal/eikon-codex-publicaciones`, salvo build desde `frontend`. El Postgres de pruebas es sintético PG16 por socket, sin red/puertos, con schemas aislados; no es la base real.

```bash
EIKON_TEST_POSTGRES_URL='postgresql://postgres@/postgres?host=/tmp/eikon-task1-pg-socket' .venv/bin/python -m pytest -o addopts='' webapp/tests -q
EIKON_TEST_POSTGRES_URL='postgresql://postgres@/postgres?host=/tmp/eikon-task1-pg-socket' .venv/bin/python -m pytest -o addopts='' webapp/tests/test_client_reference_logo.py -q
.venv/bin/python -m pytest tests mcp_server/tests -q
.venv/bin/python -m pytest tests mcp_server/tests --collect-only -q
node --test frontend/qa/task7-fix1.test.mjs frontend/qa/media-client.test.mjs
```

| Corrida | Resultado del recibo | Qué prueba |
|---|---|---|
| Task7 webapp | **646 passed / 91.77s**, sin skips/warnings | Regresiones backend finales, ambos dialectos y storage local/contrato GCS mockeado |
| Task7 logo/font final | **21 passed / 4.28s**: 10 SQLite + 10 PG + 1 font | Cubre dos tests posteriores al total 646; bytes exactos/MIME/hash, tenant+marca, corruptos409, Manrope/paquete/licencia |
| Controlador core/MCP | **129 passed, 2 skipped**, exit 0; colección **131** contrastada | Colección MCP reparada y regresiones core/MCP; no una corrida global777 ni648webapp |
| Task7 frontend final | **35/35 PASS / 526.183ms**, exit 0 | 25 regresiones fix + 10 previas, transporte diferido, cancelación/descargas/filtros y detalle con snapshot/referencia; harness controlado |
| Task7 build final | `npm run build`: **tsc estricto + Vite PASS**, exit 0, 70 módulos/122ms | JS inicial 335.92 kB / gzip 95.45 kB; renderer 4.91 kB / gzip 2.09 kB; no lint script frontend configurado |

Los dos skips core históricos están en `tests/test_ranking_isotype_penalty.py`: faltan assets demo de ranking (líneas63/104 en el recibo reciente). No se generaron demos ni se debilitaron pruebas para convertirlos en PASS. Task6 global anterior:754 passed / 2 skipped, antes del último guard de token, cubierto después con focused 43 y luego fix CRC 38; no se presenta como suite global del HEAD actual.

Calidad recibida del controlador:

```bash
.venv/bin/python -m ruff check webapp/project_storage.py webapp/migrations.py webapp/brand_briefs.py webapp/media_validation.py webapp/media_storage.py webapp/api/projects.py webapp/api/permissions.py webapp/api/generation_briefs.py webapp/api/media.py webapp/api/media_reviews.py webapp/api/auth_api.py webapp/api/client_render.py mcp_server/media_tools.py mcp_server/server.py scripts/import_brand_inventory.py eikon_core/mapping.py
.venv/bin/python -m mypy webapp/project_storage.py webapp/brand_briefs.py webapp/media_validation.py webapp/media_storage.py
```

Ruff **16 targets PASS**; Mypy **4 archivos PASS**, con nota informativa heredada de sección `jinja2` no usada. Los RUF036 históricos de `webapp/db.py`/`webapp/storage.py` siguen fuera del alcance; no hay afirmación de lint global limpio. Formato frontend Task7 y `git diff --check` pasaron en sus recibos.

Secret scanning del controlador: `gitleaks git --redact --no-banner` en historia alcanzable dio **exit 1, un generic-api-key histórico** en ejemplo comentado de `deploy/cloud-run.sh:16`, commit `4e02b32`, ancestro del baseline `74454f9`. Valor no divulgado, sin suppressions. Delta `74454f9..259101b`: **exit 0/cero hallazgos**. La fase documental verifica su propio delta por separado. `npm ci`/audit Task7 informó **5 vulnerabilidades heredadas del lock: 3 moderate, 2 high**, sin upgrade encubierto; quedan registradas para alcance separado.

## Recibo nativo local saneado

Recibos del controlador, sin tokens, archivos privados ni conversaciones:

| Campo | Resultado |
|---|---|
| Cliente/cuenta/destino | Codex CLI nativo, cuenta existente, GPT6.1Sol; backend LOCAL 8846 |
| Llamadas reales | `eikon_list_projects`, `eikon_get_brand_brief`, `eikon_create_generation_brief`, `eikon_import_image`, `eikon_list_media` |
| Pieza final / encargo / revisión | asset **3**, brief **1**, review **2**; IDs exclusivos del preview local |
| Imagen | **1024×1024**, fondo integrado `image_gen`, firmaPNG oficial exacta y Manrope; inspección de píxeles por controlador |
| SHA256 original | `aa58e57f036e6f979616301fd1fed07c346891b7f6c7e4c74451fbb4b44f7255` |
| Lectura propia | Original200 y thumbnail200, ambos `no-store`; original byte a byte idéntico |
| Aislamiento final | Bravo key: brief/original/thumbnail404; anónimo401 |
| Revisión | API key403; sesión owner201, `approved`, `approval_current=true`, historia persistida, original sin mutar |
| Publicación / producción | Ninguna publicación; conexión a producción **no verificada** |

Negativo editorial conservado: borrador 1254×1254 importado nativamente bajo brief 3/media 2 y rechazado por falta de logo/texto; review 1, HTTP201, hash inmutable. La pieza sintética Bravo aporta la otra dirección de aislamiento. Los project/brand IDs y hashes de referencia/fondo del recibo completo permanecen privados bajo custodia del controlador; no se inventan campos faltantes.

## GUI pendiente y reanudación

Recibo Docker del controlador: `git archive ea9aab7d01bb23b901adafb0a0cdf949c97f062c | docker build --label org.opencontainers.image.revision=ea9aab7d01bb23b901adafb0a0cdf949c97f062c --tag eikon-gallery:ea9aab7 -` PASS. Contexto exacto del commit, sin archivos privados ignorados. ImageID local `sha256:0de3c7be576e7b2098f6f7194156be15f2b5977c14b1f158a5d3a780d8fa086a`; no representa el digest publicado ni incluye esta documentación posterior.

Runtime por ASGI directo con SQLite efímero, UID1001 y `--network none`, sin navegador ni lifespan/worker: health200/register201/project201/brand201/brief201/multipart-media201/original con SHA exacto/thumbnail200/owner-review201/anónimo-original401. Manrope en `/static/fonts/Manrope-wght.ttf` coincide con el hash original; `/media`200 prueba fallback SPA, sin probar una ruta de React ni interacción. Tres negativos de invocación se conservaron: fixture montado ilegible para UID1001; endpoint incorrecto405; source/header de idempotencia ausentes422. Corregido sólo el invocador, sin cambios de producto ni assertions debilitadas. No satisface multipart del proxy o GCS de producción.

Task7 es el único operador GUI; el escritor de Task8 no abre CUA ni sustituye el navegador. Intento 16:21Z sobre `ea9aab7`: login sintético en tab propia en 8867 interrumpido al pulsar Entrar por panel de otra extensión. El reset de viewport también fue bloqueado. Clipboard/descarga/screenshot fallidos en otros pasos no prueban login, cookie ni píxeles de galería. La composición local sí fue guardada por canvas nativo y revisada en su recibo separado.

Después de resolver el panel por el canal permitido, Task7 debe reiniciar/resetear viewport, recargar build y ejecutar desktop 1440×900 / mobile 390×844 con capturas fuera de Git:

1. Crear proyecto; filtrar/paginar marca/proyecto/origen/estado; revisar carga/vacío/error/reintento.
2. Abrir pieza: encargo congelado, textos, colores, tipografía, logo versionado y SHA; original/miniatura autenticados; cambio de identidad bloquea aprobación actual sin sustituir snapshot.
3. Rechazo sin motivo no envía POST; rechazo motivado, aprobación/historial; negativas401/409 y recuperación.
4. Modal con teclado/foco/trap/Escape/restauración; rol member sin revisión ni botón de claves; key mostrada una sola vez y borrada al cerrar/logout.
5. Logout de A durante fetch/rasterización/descarga y entrada de B: sin blobs, clicks, imágenes, referencias ni keys de A. Filtro nuevo no acepta página anterior.
6. Estudio real: modern-screenshot, Manrope cargada por FontFace nativa, logo oficial exacto, POSTupload, inspección PNG; promoción legacy siempre `pending_review`.
7. Capturas y receipts HTTP saneados, viewport sin overflow y reset final. El test del worker servidor no sustituye el renderer cliente.

## Cierre que falta

El login API propio por proxy de producción quedó verificado a las 16:24:04Z con la credencial original del controlador, sin extracción de sesiones ni secretos divulgados. El intento previo de bridge clipboard fallido se conserva como negativo, pero ya no bloquea esa autenticación. La sesión está custodiada fuera de Git; no hay key nueva ni release por este recibo.

El controlador completa la revisión independiente de esta fase y de la rama, valida GUI, aplica sólo inventario autorizado en producción, conecta MCP real al destino desplegado y produce recibo de migración/release/privacidad/proxy. Debe entregar SHA/digest/revisión, IDs reales saneados, hashes, auth/MCP/UI, aislamiento simétrico y preservación de temporizadores/cola. Hasta ese recibo, GUI y producción siguen pendientes aunque esta documentación y las suites citadas estén listas.
