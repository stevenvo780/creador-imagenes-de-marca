# QA de galería privada y Codex MCP

Estado verificado al **2026-10-09 UTC**; release final **19:42:39Z** y timers≈19:46Z: código `2ee2ca2349098991e09ac30e919a2aafeb577873` en producción, MCP nativo persistente, privacidad simétrica, aprobación owner y renderer cliente con logo oficial comprobados por el controlador. **Primera entrega desplegada con límites de QA explícitos**: recorridoGUI completo/otros formatos no verificados y descarga del botónGUI no confirmada. No se presenta toda la matriz Task7/Task8 como ejecutada.

Código de la ola revisada: `03550de240b0ce816bcb7513ebc379981ddd1c2a`; release inicial recibido: `1886839961d520689ed19167aa3362cf2ec31ea8`; release final actual: **`2ee2ca2349098991e09ac30e919a2aafeb577873`**, aprobado independientemente y desplegado19:42:39Z. Estudio/móvil tienen evidencia nativa acotada abajo; no se extrapola a toda laGUI. Baseline documental anterior: `ea9aab7d01bb23b901adafb0a0cdf949c97f062c`. La suite webapp646 corresponde a producto `259101bf741585d73121ead12af9132f610bb928`; el fix `ea9aab7` sólo cambió frontend/QA. La ola `03550de` cambia autorización, rollback, renderer y paginación MCP con cobertura enfocada propia, descrita abajo; no hereda un PASS global de las suites anteriores. Los recibos de Tasks1–7 y del controlador se conservan en el ledger local del workflow o en evidencia privada fuera de Git. Este documento reproduce sus resultados saneados; el escritor de documentación no repitió esas suites ni abrió respaldos, vault o datos reales.

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
| Proyectos privados y conservación de marcas | Tasks1/3 sintéticos más importación idempotente de producción: Systems proyecto 4/marca 106 y News proyecto 5/marca 107, identidad v2 | No se importaron las56legacy a Humanizar; conservar identidades/tenants existentes |
| Migración y compatibilidad de datos anteriores | Backup fresco 19:12:22Z PG17 restaurado aislado, init_db dos veces y columnas originales iguales: 4tenants/4users/62brands/6keys del snapshot previo al release | Sin fence live ni migración destructiva; rollback de worker/escrituras generales sigue sin certificación |
| Roles/scopes/caducidad/revocación | Tasks2/6 y producción: key-review403, key-identity403, probe read-only revocado401 | UI key-once, teclado y rol efectivo aún requieren recorrido GUI completo |
| Inventario y logos | Dry-run56legacy saneado conservado; Systems/News propias importadas idempotentemente en producción, v2, logo oficial SHA 31d8d267ea1db2af060c77fe42be2375a4f15102028b7e9a199774c0a28cd343 | Sin reasignación de tenants ni importación masiva de56legacy; negativos anteriores conservados |
| Imagen y validación | Tasks4/6 más MCP producción asset1/brief1 1024×1024, original exacto/no-store/thumb200; Estudio nativo generó business_card PNG2100×1200 con logo original sin warp | Botón DescargarGUI timeout15s, no descargaGUI confirmada; API archivo propio200 prueba lectura separada, otros formatos/textos específicos no verificados |
| MCP SDK real | Task6: cuatro subprocesos stdio reales, SQLite/PG × capa alta/fallback, initialize/list/call, 22 nombres, seis tools nuevas, replay/aislamiento/revocación | SDK v2.3 probado; rama SDK v1 conservada según contrato, sin runtime separado probado |
| Codex nativo e imagen integrada | CLI0.160.1 real cinco tools/dos imports+replay contra producción; conexión persistente eikon listprojects4/5 realPASS, misma cuenta | El chat actual necesita reload para usar la conexión aquí; no se afirma tool ya invocada desde este chat |
| Revisión humana e historia | Ownerapproved asset1/history1/currentv2 a19:22:48Z, screenshotreal; rechazo vacíoalert/sinreview. Approvalcurrent/history/hash conservados tras deployfinal | Otros casos GUI de rol/foco/401409/key-once/logout completos no se afirman ejecutados |
| Aislamiento simétrico | Producción: empresa QA ajena404×3 en ambas direcciones, anónimo401×3; original propio exacto/no-store, thumbnail200; cuatro objetos nuevos GCS HEAD anónimo403 | Preservar piezas/evidencia sintéticas y originales; comprobación posterior al ajuste de Estudio pendiente |
| Frontend y renderer | Recibos históricos porSHA; guardEstudio+suite47frontendPASS, tsc/VitePASS y reviewsindependientes aprobadas. NativeFontFace/modern-screenshotbusiness_card generada, píxeles logo oficial sinwarp, pequeñoenlayout | Sin validación editorial de payloadtextos, otros formatos ni toda la matrizGUI; legacyDBasset-only nohabilitado por límite backendreadonly |
| GUI desktop/mobile | Desktop1440×900 detalle original/snapshot/history y recuperación visibles; mobile390×844final navright363/documentwidth375, linksaccesibles2filas, viewportreset, filtroAprobado y Escape/foco verificados | Timeout15s DescargarPNG y errores intermitentes conexión/thumb/brief históricos conservados; no todo el protocoloGUI ejecutado |
| Privacidad/auth de producción | Proxy HTTPS existente, cookie/login previos Secure/HttpOnly/SameSiteLax; descarga nueva privada y HEAD anónimo403 para cuatro objetos GCS, IAM bucket/servicio sin cambios | No extender esas lecturas a todo el catálogo/ACLlegacy ni a GUI completa |
| Release y preservación Humanizar | Final2ee2ca2/eikon-00058-t9n100%zero tags19:42:39Z; configsalvoimagen/IAM intactos; timers ambosactive≈19:46Z sin mutación de worker/cola/timers | Sin mainmerge; GitHubActions no inició por restricciónadministrativa, no suitefailure; límitesQA listados abajo y [runbook](DEPLOY-GALERIA-CODEX.md) |
| Imagen Docker empaquetada | Buildexactgitarchive final2ee2ca2PASS; OCIindexd98b8d31568ca9b495d3a954aa88f7f9584794c2e560d7eecb1c6a00a9a52a66 / runtimeamd64129219b1b9e9112e047c71ddb0ce1a50ff5b5693cc9666421777a4be9aaf04fc, membershipverificada | ImageIDlocal035 e index188 son recibos previos, separados del releasefinal |

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
| Publicación / producción | Ninguna publicación; este recibo es LOCAL. La conexión posterior de producción tiene recibo separado abajo |

Negativo editorial conservado: borrador 1254×1254 importado nativamente bajo brief 3/media 2 y rechazado por falta de logo/texto; review 1, HTTP201, hash inmutable. La pieza sintética Bravo aporta la otra dirección de aislamiento. Los project/brand IDs y hashes de referencia/fondo del recibo completo permanecen privados bajo custodia del controlador; no se inventan campos faltantes.

## Recibo de producción final autorizado

El controlador ejecutó el release autorizado por el usuario; el escritor documental sólo consume recibos saneados y no accedió a cuentas/archivos privados. Release inicial188/eikon-00057-xjc conservado: index8fc4ec86a95f4a9f69a87eddd189703ea5aea3a33a4347a64287ca1d114778aa/manifestamd64f9aaba26c69434a840d833387927665836e1d2af35befbea424e17f2425ea30d. La tabla siguiente identifica el release final2ee y no mezcla sus digests.

| Campo | Evidencia recibida |
|---|---|
| Código / revisión / tráfico | `2ee2ca2349098991e09ac30e919a2aafeb577873` / `eikon-00058-t9n` /100%, cero tags,19:42:39Z |
| Destino | emergent-enterprises/eikon/us-central1; [proxy Vercel existente](https://eikon-proxy.vercel.app), tres orígenes: health200/projects-mediaSPAbytesexactos delbundlefinal |
| OCI index | `sha256:d98b8d31568ca9b495d3a954aa88f7f9584794c2e560d7eecb1c6a00a9a52a66` |
| Manifest linux/amd64 | `sha256:129219b1b9e9112e047c71ddb0ce1a50ff5b5693cc9666421777a4be9aaf04fc`, membershipdelindexverificada |
| Configuración | Config completa salvo imagen e IAM bucket/servicio sin cambios |
| Backup/migración | Backup fresco 19:12:22Z PG17 restaurado aislado; init_db dos veces/columnas originales iguales, snapshot: 4 tenants / 4 users / 62 brands / 6 keys. Sin fence live/migración destructiva |
| Inventario propio | Systems proyecto 4/marca 106, News proyecto 5/marca 107, identidad v2; importación idempotente. Logo original SHA `31d8d267ea1db2af060c77fe42be2375a4f15102028b7e9a199774c0a28cd343` |
| MCP nativo | CLI 0.160.1 real, cinco tools listprojects/getbrandbrief/createbrief/importimage/listmedia; dos llamadas import reales incluido replay, asset 1/brief 1 conservados |
| Pieza |1024×1024, SHA `aa58e57f036e6f979616301fd1fed07c346891b7f6c7e4c74451fbb4b44f7255`; original por proxy byteexacto/no-store, thumbnail propio200 |
| Aislamiento/API/GCS | Anónimo401×3; empresa QA ajena404×3 en ambas direcciones; cuatro objetos nuevos GCS HEAD anónimo403; key-review403/key-identity403; probe read-only revocado401 |
| Revisión GUI | Owner approved asset 1/history 1/current v2 a las 19:22:48Z, screenshot real; rechazo vacío previo alert/sin review |
| Conexión del chat | MCP global eikon agregado sin secretos en config, otros settings conservados; chat actual requiere reload, sin claim de tool invocada desde este chat |
| Humanizar | Ambos timers existentes active≈19:46Z exit0, sin mutacionesworkers/cola/timers |
| PR/CI | [PR2 draft](https://github.com/stevenvo780/creador-imagenes-de-marca/pull/2), sin main merge. GitHubActions job no iniciado por restricción administrativa; no es fallo de suite |
| Gate antes primera key | Antes key 7, revisionslist name/statusURL: todas revisiones anteriores sin statusURL; tráfico100%00057/cero tags, sin revision/tagURL published en config; los tres orígenes conocidos servicio/proxy sirvieronSPA exacta nueva. Sin eliminarrevisiones |
| GUI móvil final |390×844 navright363/documentwidth375, linksnavaccesibles2filas, viewportreset; detalle/history, Escape/restaurafoco y filtroAprobado verificados. Overflow632 previo corregido, sin claim de toda matriz móvil |

Desktop1440×900: modal original/snapshot/historia actual verificados por screenshotreal. Al abrir hubo errores intermitentes conexión/thumbnail/brief; «Actualizar detalle» recuperó original+encargo+logo+history visibles sin mutación. Se conserva negativo y recuperación observada, sin concluir la causa.

Captura final19:48Z sobre releaseactual: modalasset1 muestra original+encargo+logo+historiaAprobado presentes sinerror; approvalcurrent/history1/hash preservados. No contradice el negativointermitente anterior ni demuestra coberturaGUI completa.

Final2ee R-STUDIO/R-MOBILE aprobado independientemente sinhallazgos, buildexactgitarchivePASS. Guard y conjunto47frontendPASS, npmTS/VitePASS; dos reglasCSSmóvil build/reviewPASS, gitleaks188..2ee exit0/cero. No suma de suites anteriores ni nuevoPASSglobal Python.

Estudio nativo final: HumanizarSystems reference-only sinwarning, Tipo habilitado; business_card clientcreate terminó «Generado», previewvariation3047 y archivo propio200. NativeFontFace/modern-screenshot reales. Layout1050×600 → PNG2100×1200 escala2, SHA `bf4d2ec3132df31a882f40a50e26d82cd8793600f489b6575dbd88b6e4ff43f1`; píxeles del logo oficial sinwarp, pequeñoenlayout. El test v1_front no afirma textos específicos delpayload ni otros formatos. Click «Descargar PNG» produjo timeoutEVENTdownload15s: **descargaGUI no confirmada**; archivo APIpropio200/bytesintactos es evidencia separada. LegacyDBasset-only sigue nohabilitado por límite de backendreadonly.

Mobilefinal390×844: navright363/documentwidth375 frenteoverflow632 anterior, links accesibles endosfilas y viewportreset, capturas guardadas. FiltroAprobado, detalleimagen/snapshot/history y Escape/restaurafoco ya verificados; no toda la matrizdesktop/mobile.

## Evidencia local anterior y alcance GUI restante

Recibo Docker local anterior del controlador: build **PASS** desde `git archive` exacto de `03550de240b0ce816bcb7513ebc379981ddd1c2a`, etiqueta de revisión con ese SHA. Contexto sin archivos privados ignorados. ImageID local **`sha256:a3679e070fc3f01662e4d0f10345fb51d04054ee94e2d72e58be78b91e467e00`**; no representa un digest publicado ni incluye esta actualización documental. El build anterior de `ea9aab7` queda como recibo histórico, sin sustituir el actual.

Runtime035 **PASS** por ASGI directo con SQLite sintético efímero, UID1001 predeterminado y `--network none`, sin navegador ni lifespan/worker: health200/register201/project201/brand201/brief201/upload201/original con SHA exacto/thumbnail200/owner-review201/anónimo401. Manrope coincide con el hash original; `/media`200 prueba fallback SPA, sin probar una ruta de React ni interacción. Los tres negativos del invocador anterior se conservan en su recibo histórico: fixture montado ilegible para UID1001; endpoint incorrecto405; source/header de idempotencia ausentes422. No satisface multipart del proxy o GCS de producción.

GUI bajo control del operador asignado/controlador; el escritor de Task8 no abre CUA. El bloqueo Brave de 16:21Z y el reset fallido quedan como negativos históricos. Brave ya está desbloqueada y la aprobación owner de producción19:22:48Z tiene screenshotreal; Estudiofinal y mobile tienen recibos acotados arriba, sin sustituir todos los recorridos restantes.

El operador completa el protocolo siguiente sobre el build final y desktop1440×900/mobile 390×844, con capturas fuera deGit; sólo las acciones con recibo explícito anterior están verificadas:

1. Crear proyecto; filtrar/paginar marca/proyecto/origen/estado; revisar carga/vacío/error/reintento.
2. Abrir pieza: encargo congelado, textos, colores, tipografía, logo versionado y SHA; original/miniatura autenticados; cambio de identidad bloquea aprobación actual sin sustituir snapshot.
3. Rechazo sin motivo no envía POST; rechazo motivado, aprobación/historial; negativas401/409 y recuperación.
4. Modal con teclado/foco/trap/Escape/restauración; rol member sin revisión ni botón de claves; key mostrada una sola vez y borrada al cerrar/logout.
5. Logout de A durante fetch/rasterización/descarga y entrada de B: sin blobs, clicks, imágenes, referencias ni keys de A. Filtro nuevo no acepta página anterior.
6. Estudio real: modern-screenshot, Manrope cargada por FontFace nativa, logo oficial exacto, POSTupload, inspección PNG; promoción legacy siempre `pending_review`. Verificar además `business_card` v1_front con logo no cuadrado, proporción y píxeles nativos: el renderer controlado no cierra ese gate.
7. Capturas y receipts HTTP saneados, viewport sin overflow y reset final. El test del worker servidor no sustituye el renderer cliente.

## Entrega y límites que permanecen

Releasefinal2ee (el SHA documental posterior no está desplegado)/inventario/MCPproducción/privacidad/aislamiento simétrico/ownerreview y business_card nativa con proporción del logo tienen recibos arriba. El gate antes key7 quedó documentado por metadata completa y SPAexacta de los tresorígenes; sigue obligatorio para releases/keys posteriores. La conexión globalMCP tuvo lectura persistente real, pero este chat requiere reload.

No se declara toda la matrizGUI ejecutada: otros formatos/textos específicos y todos los casos de roles/key-once/logout/401409/foco siguen sin recibo completo. DescargaGUI timeout15s se conserva; la lecturaAPI propia200 no la convierte enPASS. Errores intermitentesconnection/thumb/brief tuvieron recuperación visible sin causa concluida. El negativo móvil632px quedó corregido enreleasefinal, con métrica375px/viewport390 y capturas.

[PR2](https://github.com/stevenvo780/creador-imagenes-de-marca/pull/2) sigue draft sin mainmerge. Actions no inició por restricciónadministrativa: no suitefailure ni CIgreen. Gitleakshistórico/npm5/skipsranking/RUF036/notatyping conservados; sin certificaciónworker/write rollback, SDKv1/ACLlegacy o publicaciónsocial. Entrega desplegada con reservasdocumentadas; sin cerrarTask7/Task8 por una matriz totalmente ejecutada inexistente.

## Correcciones de integración final F-I1–F-I4

- `reference-logo` POST exige sesión owner vigente tanto en matriz como endpoint. Una key `media:write`, all-scopes o legacy no cambia logo, versión ni almacenamiento; GET versionado conserva `brands:read`. El importador owner sigue autorizado.
- El rollback a `6fe3ad5` requiere el [fence PostgreSQL y protocolo de revocación](DEPLOY-GALERIA-CODEX.md#rollback-seguro-de-autorización-f-i2-absorbe-t8-m1). Audit es sólo lectura por defecto. Arm/disarm son decisiones administrativas globales explícitas, no startup/migración. **No ejecutados en producción**. Las pruebas sintéticas cubren autorización real anterior y emisiones concurrentes; no certifican rollback de todo el worker.
- El renderer cliente inyecta logos con `object-fit: contain` y centrado; QA del módulo real cubre raster horizontal/vertical/cuadrado en slots desfavorables con DOM/rasterizador controlados. El gate PNG de `business_card` v1_front (sin contain propio), píxeles del logo y FontFace tuvo prueba nativa en el releasefinal; no se extrapola a otrosformatos o toda la matrizGUI.
- MCP expone `cursor` y `limit` opcionales en los listados de proyectos/medios; límite 1–100, cursor entero no negativo. El registro compartido conserva 22 nombres y las seis herramientas nuevas. Regresión stdio real alta/fallback sobre SQLite/PostgreSQL sintéticos usa 51 proyectos/51 medios, dos páginas acotadas sin solapamiento, filtros e aislamiento. Esa regresión sintética no es una conexión Codex al destino desplegado; el reciboCLI de producción se documenta aparte.

Los límites DeclinedToJudge1–9 del dictamen035 se conservan como alcance histórico del reviewer. Los recibos reales posteriores del controlador cubren release188 y final2ee/inventario/MCP/privacidad/revisión/Estudio indicados arriba; no amplían esa revisión sintética ni certifican GUI restante, rollback general de worker/escrituras, URLs/ACLlegacy históricas, SDKv1/dependencias, provisionamiento alternativo o decisión de publicación. Publicador/redes siguen fuera de esta entrega y los negativos anteriores se conservan.
