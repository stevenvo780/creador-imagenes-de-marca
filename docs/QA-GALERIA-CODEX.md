# QA de galería privada y Codex MCP

Estado verificado al **2026-10-09 UTC**; timestamps de cada recibo abajo: re-review independiente Astra del código `03550de` **Spec APPROVED / Quality APPROVED**; F-I1–F-I4 y T8-M1 resueltos, sin nuevos Critical/Important en el delta. Replay Codex nativo **local** y build/runtime Docker del código actual comprobados por el controlador. **GUI autenticada y release de producción pendientes.** Esta documentación es una entrega con reservas, no el cierre de Task7/Task8.

Código actual: `03550de240b0ce816bcb7513ebc379981ddd1c2a`; baseline documental anterior: `ea9aab7d01bb23b901adafb0a0cdf949c97f062c`. La suite webapp646 corresponde a producto `259101bf741585d73121ead12af9132f610bb928`; el fix `ea9aab7` sólo cambió frontend/QA. La ola `03550de` cambia autorización, rollback, renderer y paginación MCP con cobertura enfocada propia, descrita abajo; no hereda un PASS global de las suites anteriores. Los recibos de Tasks1–7 y del controlador se conservan en el ledger local del workflow o en evidencia privada fuera de Git. Este documento reproduce sus resultados saneados; el escritor de documentación no repitió esas suites ni abrió respaldos, vault o datos reales.

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
| Codex nativo e imagen integrada | Flujo local previo con cinco tools reales y pieza final1024 inspeccionada; recibo17:10:55Z sobre `03550de`: import/listado nativos y replay del mismo asset3 aprobado, hash exacto e historia sin cambios; key POSTreference-logo403 sin alterar snapshot/storage | Destino LOCAL HTTP 8846; conexión Codex a producción pendiente |
| Revisión humana e historia | Tasks5/7 y controlador: aprobación/rechazo, hash/versión/snapshot, owner desde BD, historia inmutable; key-review403, owner-review201 local | Recorrido GUI de revisión y producción pendiente |
| Aislamiento simétrico | Controlador: Alpha→Bravo y Bravo→Alpha, encargo/original/thumbnail404; anónimo401 en ambas. Descargas propias200, bytes/hash idénticos y `no-store` | Objetos nuevos GCS y proxy de producción aún pendientes |
| Frontend y renderer | Task7 final: 35/35 regresiones controladas, tsc/Vite; seam logo exacto PNG/JPEG/SVG y Manrope probados | DOM/rasterizer controlados no prueban modern-screenshot, FontFace nativa, píxeles ni GUI |
| GUI desktop/mobile | Protocolo sintético preparado en loopback 8867 | BLOCKED: Brave impide automatización por otro panel de extensión; último `/auth/me`401. No recorrido autenticado, capturas ni mobile PASS |
| Privacidad/auth de producción | Controlador 15:34Z: revisión vigente sin cambios; IAM del bucket sin allUsers/allAuthenticatedUsers; objeto anterior anónimo403. Login propio 16:24:04Z por proxy HTTPS: /auth/login200 y /auth/me200, owner, cookie Secure/HttpOnly/SameSiteLax | No equivale a prueba de original/thumbnail nuevos, multipart, MCP ni UI de producción |
| Release y preservación Humanizar | Re-review del delta `03550de` aprobada; metadata producción16:58:46Z: eikon-00056-jjs al100%, cero tags, sin nueva key ni release. Controlador≈17:12Z SSHserver2: humanizar-publicaciones.timer y humanizar-publicaciones-plan-daily.timer ambosactive, sin mutación | Gates GUI y funcionales de producción, SHA/digest de release y recibo posterior timers/cola pendientes; ver [runbook](DEPLOY-GALERIA-CODEX.md) |
| Imagen Docker empaquetada | Controlador: build exacto `03550de`, runtime UID1001 sin red, ASGI sintético de proyecto/encargo/upload/descargas/review y Manrope | Imagen local; no digest de Artifact Registry, GUI ni despliegue |

## Comandos y resultados anteriores recibidos

Los recibos de esta sección preceden a `03550de` y conservan el SHA/alcance de Task6/Task7; no son una nueva corrida sobre el código actual. Todos desde `/datos/workspaces/personal/eikon-codex-publicaciones`, salvo build desde `frontend`. El Postgres de pruebas es sintético PG16 por socket, sin red/puertos, con schemas aislados; no es la base real.

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

Secret scanning del controlador: `gitleaks git --redact --no-banner` en historia alcanzable dio **exit 1, un generic-api-key histórico** en ejemplo comentado de `deploy/cloud-run.sh:16`, commit `4e02b32`, ancestro del baseline `74454f9`. Valor no divulgado, sin suppressions. Deltas `74454f9..259101b` y, posteriormente, `4fc7b16..03550de`: **exit 0/cero hallazgos** en sus respectivos recibos. La fase documental verifica su propio delta por separado. `npm ci`/audit Task7 informó **5 vulnerabilidades heredadas del lock: 3 moderate, 2 high**, sin upgrade encubierto; quedan registradas para alcance separado.

## Cobertura enfocada del código 03550de

Recibos del escritor de la ola final, aceptados por la re-review independiente y conservados en `final-fix-report.md`/`final-re-review.md` del ledger local. No se suman subconjuntos ni se reejecutan suites para obtener un total global:

| Comando recibido | Resultado / alcance |
|---|---|
| `.venv/bin/python -m pytest webapp/tests/test_generation_briefs.py -q`, con PG sintético | 78 PASS, SQLite/PG: identidad sólo owner, guards independientes, GET versionado y snapshot/storage intactos tras403 |
| `.venv/bin/python -m pytest mcp_server/tests/test_media_tools.py -q` | 60 PASS: paginación y validación estricta, además de importaciones/errores anteriores |
| `.venv/bin/python -m pytest mcp_server/tests/test_media_pagination.py -o addopts='' -q`, con PG sintético | 4 PASS /9.46s: stdio real alta/fallback × SQLite/PG, 51 proyectos/51 medios y páginas50+1 |
| `.venv/bin/python -m pytest webapp/tests/test_rollback_scoped_keys.py webapp/tests/test_media_permissions.py webapp/tests/test_brand_inventory.py -o addopts='' -q`, con PG sintético | 121 PASS /14.07s: regresiones de autorización/fence/importador; incluye los cuatro casos iniciales de rollback |
| `.venv/bin/python -m pytest webapp/tests/test_rollback_scoped_keys.py -o addopts='' -q`, con PG sintético | 10 PASS /1.88s finales tras ampliar receta/negativo UPDATE-only; resolver/endpoints anteriores reales y carreras PG sintéticas, no worker completo ni tráfico cloud real |
| `node --test qa/media-client.test.mjs`, cwd frontend | 13 PASS /324ms: tres PNG válidos no cuadrados/cuadrado con renderer real y rasterizador controlado; sin prueba visual nativa |
| `./node_modules/.bin/tsc --noEmit`, cwd frontend | PASS; Ruff9 targets y Mypy5 archivos del delta también PASS, nota histórica jinja2 conservada |

La receta literal de rollback tuvo parseo AST y tests con PostgreSQL real sintético y contrato gcloud controlado; los flags se cotejaron con help local. El replay nativo local y la imagen Docker descritos abajo añaden evidencia del código actual, sin convertir los recibos646/129/35 anteriores en una suite global de `03550de`.

## Recibo nativo local saneado

Recibos del controlador, sin tokens, archivos privados ni conversaciones. Generación/composición/aprobación iniciales a16:22:30Z; replay sobre código `03550de` a **17:10:55Z**:

| Campo | Resultado |
|---|---|
| Cliente/cuenta/destino | Codex CLI nativo, cuenta existente, GPT6.1Sol; backend LOCAL 8846 |
| Llamadas reales | Flujo inicial: listprojects/getbrandbrief/creategenerationbrief/import/listmedia. Código035: `eikon_import_image` y `eikon_list_media` completados en CLI real; mismo idempotency replay |
| Pieza final / encargo / revisión | asset **3**, brief **1**, review **2**; IDs exclusivos del preview local |
| Imagen | **1024×1024**, fondo integrado `image_gen`, firmaPNG oficial exacta y Manrope; inspección de píxeles por controlador |
| SHA256 original | `aa58e57f036e6f979616301fd1fed07c346891b7f6c7e4c74451fbb4b44f7255` |
| Lectura propia | Original200 y thumbnail200, ambos `no-store`; original byte a byte idéntico |
| Aislamiento final | Sobre035: encargo/original/thumbnail ajenos404×3 y anónimo401×3; aislamiento simétrico previo conservado |
| Revisión | Revisión inicial owner201, review2 `approved`, `approval_current=true`; replay035 mantiene review2 única e historia sin cambios, original sin mutar |
| Identidad por API key | POSTreference-logo403 sobre035, snapshot y storage intactos |
| Publicación / producción | Ninguna publicación; conexión a producción **no verificada** |

Negativo editorial conservado: borrador 1254×1254 importado nativamente bajo brief 3/media 2 y rechazado por falta de logo/texto; review 1, HTTP201, hash inmutable. La pieza sintética Bravo aporta la otra dirección de aislamiento. Los project/brand IDs y hashes de referencia/fondo del recibo completo permanecen privados bajo custodia del controlador; no se inventan campos faltantes.

## GUI pendiente y reanudación

Recibo Docker actual del controlador: build **PASS** desde `git archive` exacto de `03550de240b0ce816bcb7513ebc379981ddd1c2a`, etiqueta de revisión con ese SHA. Contexto sin archivos privados ignorados. ImageID local **`sha256:a3679e070fc3f01662e4d0f10345fb51d04054ee94e2d72e58be78b91e467e00`**; no representa un digest publicado ni incluye esta actualización documental. El build anterior de `ea9aab7` queda como recibo histórico, sin sustituir el actual.

Runtime035 **PASS** por ASGI directo con SQLite sintético efímero, UID1001 predeterminado y `--network none`, sin navegador ni lifespan/worker: health200/register201/project201/brand201/brief201/upload201/original con SHA exacto/thumbnail200/owner-review201/anónimo401. Manrope coincide con el hash original; `/media`200 prueba fallback SPA, sin probar una ruta de React ni interacción. Los tres negativos del invocador anterior se conservan en su recibo histórico: fixture montado ilegible para UID1001; endpoint incorrecto405; source/header de idempotencia ausentes422. No satisface multipart del proxy o GCS de producción.

Task7 es el único operador GUI; el escritor de Task8 no abre CUA ni sustituye el navegador. Intento 16:21Z sobre `ea9aab7`: login sintético en tab propia en 8867 interrumpido al pulsar Entrar por panel de otra extensión. El reset de viewport también fue bloqueado. Clipboard/descarga/screenshot fallidos en otros pasos no prueban login, cookie ni píxeles de galería. La composición local sí fue guardada por canvas nativo y revisada en su recibo separado.

Después de resolver el panel por el canal permitido, Task7 debe reiniciar/resetear viewport, recargar build y ejecutar desktop 1440×900 / mobile 390×844 con capturas fuera de Git:

1. Crear proyecto; filtrar/paginar marca/proyecto/origen/estado; revisar carga/vacío/error/reintento.
2. Abrir pieza: encargo congelado, textos, colores, tipografía, logo versionado y SHA; original/miniatura autenticados; cambio de identidad bloquea aprobación actual sin sustituir snapshot.
3. Rechazo sin motivo no envía POST; rechazo motivado, aprobación/historial; negativas401/409 y recuperación.
4. Modal con teclado/foco/trap/Escape/restauración; rol member sin revisión ni botón de claves; key mostrada una sola vez y borrada al cerrar/logout.
5. Logout de A durante fetch/rasterización/descarga y entrada de B: sin blobs, clicks, imágenes, referencias ni keys de A. Filtro nuevo no acepta página anterior.
6. Estudio real: modern-screenshot, Manrope cargada por FontFace nativa, logo oficial exacto, POSTupload, inspección PNG; promoción legacy siempre `pending_review`. Verificar además `business_card` v1_front con logo no cuadrado, proporción y píxeles nativos: el renderer controlado no cierra ese gate.
7. Capturas y receipts HTTP saneados, viewport sin overflow y reset final. El test del worker servidor no sustituye el renderer cliente.

## Cierre que falta

El login API propio por proxy de producción quedó verificado a las 16:24:04Z con la credencial original del controlador, sin extracción de sesiones ni secretos divulgados. El intento previo de bridge clipboard fallido se conserva como negativo, pero ya no bloquea esa autenticación. La sesión está custodiada fuera de Git; no hay key nueva ni release por este recibo.

El gate de código de la ola035 quedó aprobado. El controlador valida GUI, conserva backup/preflight actual, aplica sólo inventario autorizado, conecta MCP real al destino desplegado y produce recibo de migración/release/privacidad/proxy. Antes de la **primera emisión de key scoped**, debe confirmar que revisiones viejas y URLs directas/de tags no alcanzan autorización legacy según el runbook; cero tags actuales no sustituye esa comprobación. Producción16:58:46Z sigue eikon-00056-jjs al100%, cero tags, sin key nueva ni release. El controlador prepara una PR draft; no hay URL proporcionada en este recibo. Debe entregar SHA/digest/revisión, IDs reales saneados, hashes, auth/MCP/UI, aislamiento simétrico y preservación de temporizadores/cola. Hasta ese recibo, GUI y producción siguen pendientes.


## Correcciones de integración final F-I1–F-I4

- `reference-logo` POST exige sesión owner vigente tanto en matriz como endpoint. Una key `media:write`, all-scopes o legacy no cambia logo, versión ni almacenamiento; GET versionado conserva `brands:read`. El importador owner sigue autorizado.
- El rollback a `6fe3ad5` requiere el [fence PostgreSQL y protocolo de revocación](DEPLOY-GALERIA-CODEX.md#rollback-seguro-de-autorización-f-i2-absorbe-t8-m1). Audit es sólo lectura por defecto. Arm/disarm son decisiones administrativas globales explícitas, no startup/migración. **No ejecutados en producción**. Las pruebas sintéticas cubren autorización real anterior y emisiones concurrentes; no certifican rollback de todo el worker.
- El renderer cliente inyecta logos con `object-fit: contain` y centrado; QA del módulo real cubre raster horizontal/vertical/cuadrado en slots desfavorables con DOM/rasterizador controlados. La GUI nativa debe inspeccionar el PNG final de `business_card` v1_front (sin contain propio), incluyendo píxeles del logo y FontFace. Ese gate sigue bloqueado por la extensión Brave, pendiente junto con producción.
- MCP expone `cursor` y `limit` opcionales en los listados de proyectos/medios; límite 1–100, cursor entero no negativo. El registro compartido conserva 22 nombres y las seis herramientas nuevas. Regresión stdio real alta/fallback sobre SQLite/PostgreSQL sintéticos usa 51 proyectos/51 medios, dos páginas acotadas sin solapamiento, filtros e aislamiento. No es una conexión Codex al destino desplegado.

Se conservan los límites DeclinedToJudge 1–9 del dictamen: publicador/redes, GUI real, despliegue/proxy/GCS nuevos, inventario privado vigente, dump/worker y escrituras generales de rollback, URLs/ACL legacy, SDKv1/dependencias, provisionamiento/build alternativo y revisión editorial humana. Los recibos anteriores y negativos no se reemplazan por esta corrección enfocada.
