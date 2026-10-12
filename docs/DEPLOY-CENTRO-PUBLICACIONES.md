# Release del centro de publicaciones

Task10A prepara código y gates locales. **El despliegue API/SPA está comprobado;
OAuth, ejecución diaria, publicación y timer activo siguen pendientes.** Task10B comienza después
de revisión independiente de Task10A y revisión de la rama completa. La entrega
anterior de galería sigue separada: el WorkerPool de Cloud Run renderiza;
el nuevo publicador consume autorizaciones de Eikón desde server2.

Destino existente: proyecto GCP `emergent-enterprises`, región `us-central1`,
servicio `eikon`, proxy Vercel `eikon-proxy`. Revalidar cuenta y recursos antes
de mutar. El controlador root es el único operador de navegador, herramientas
nativas y selección de la cuenta Humanizar. Una UI de otro tenant y una lectura
nativa de la galería no demuestran identidad GUI ni herramientas de publicaciones.

## Secuencia y puntos de parada

1. Fijar SHA revisado y ejecutar la matriz local descrita en QA. Preservar errores,
   skips y atribución al baseline; no cambiar assertions o scopes para obtener PASS.
   Ningún gate local acredita un proveedor vivo.
2. Guardar backups privados de configuración completa Cloud Run/proxy/server2,
   referencias a secretos, DB, storage y outbox. Registrar IDs y hashes saneados;
   nunca DSN, tokens, tickets, claves ni copias completas en Git o en otro modelo.
3. Restaurar un clon aislado. Ejecutar `init_db` dos veces, verificar esquema,
   tablas antiguas y nuevas, ledger, guards, media SHA, outbox e intentos en vuelo.
   `create_app` ejecuta migraciones antes de servir tráfico: una revisión sin tráfico
   también puede alterar DB. Ensayar rollback de código con datos nuevos conservados.
4. Calificar logging **antes de activar OAuth o emitir URLs de media sensibles**.
   La aplicación, Uvicorn, request logs administrados Cloud Run y proxy Vercel son
   capas distintas. Usar solo marcadores sintéticos, conservar sus recibos y buscar
   en cada capa. Protección de persistencia efectiva debe acreditarse, sin
   desactivar seguridad o logs de servicios ajenos. Una exclusión posterior de sink evita ese destino,
   no demuestra que nunca se recibió la URL. El ruling explícito acepta el
   procesamiento autorizado Google y buffer temporal Log Router; no certifica
   ausencia de ingestión o de toda persistencia temporal. Cero drains o cero resultados Vercel
   no demuestran redacción ni ausencia de retención.
5. Verificar manifiesto efectivo de upload y Docker context; construir imagen API,
   fijar digest y revisar contenido/dependencias. La única excepción al filtro de
   sesiones es `frontend/src/auth/useSession.ts`, fuente pública necesaria. Sesiones,
   credenciales y estado privado siguen excluidos. No almacenar configuración OAuth
   o vault bajo `config/`: Docker copia ese directorio. El manifiesto de Task10A
   prueba inclusión de esa fuente, no un build final de Cloud Build.
6. Actualizar solo la imagen del servicio existente preservando recursos, IAM,
   tráfico/tags y configuración respaldados. Nuevos secrets/mounts se suministran
   privadamente con alcance explícito. **No ejecutar `deploy/cloud-run.sh` como
   actualización de imagen:** también modifica IAM, recursos y variables.
7. Instalar el paquete `publisher_worker` separado en server2 y las units existentes
   `deploy/eikon-publisher.service` / `.timer`, inicialmente disabled/inactive.
   La imagen API no incluye automáticamente worker, MCP ni scripts. Revalidar
   `/usr/bin/ffmpeg`, `/usr/bin/ffprobe`, `/usr/bin/prlimit`, permisos y versiones.
   La lectura previa de server2 encontró ambos binarios de vídeo ausentes; candidato
   oficial Ubuntu ffmpeg disponible no demuestra instalación. Si sigue ausente,
   instalar solo paquete oficial y dependencias necesarias; sin upgrade general.
8. Verificar API/SPA/proxy autenticados, aislamiento de tenant, storage privado y
   GUI desktop/móvil bajo owner Humanizar. `/health` es estático: no prueba DB,
   bucket, vault, stock, cliente ni publicación. Guardar SHA/digest/revisión/proxy.
9. Importar idempotentemente historia Humanizar y conexiones propias comprobadas;
   activar política autorizada y grants dedicados planner/reviewer/worker. Relaciones
   `project_ids[]` permiten una cuenta canónica compartida entre productos propios;
   no crear otra credencial por producto. El vault requiere clave independiente de
   JWT y backup privado. Nunca copiar `auth.json` o cambiar cuenta por un fallo.
10. Reconectar mediante mecanismo soportado del cliente. Documentación oficial
    preparatoria describe `config/mcpServer/reload`; comprobar disponibilidad real.
    `codex exec` con sesión existente y MCP real puede aportar evidencia de cliente,
    sin auth copy ni fallback API pagado. Inventario efectivo de **28 herramientas**,
    tokenload/reconnect y llamada correlacionada son gates; stdio de tests no basta.
11. Ejecutar cadena nativa real y diaria: inbox → bytes exactos/identidad/caption/
    fuentes → razonamiento/evaluación → decisión append-only por MCP → readback
    exacto de revisión/hash → autorización → worker. El cliente reúne hechos y
    procedencia antes de congelar `channel_metadata.context`;
    `source_mode=frozen_metadata_context` no significa cuerpos remotos descargados.
    URLs solas, `vision=true` y contexto no vacío no prueban afirmaciones. Ante fuente
    Graf que lleva a administración, justificar/obtener alternativa autorizada o hold.
12. Aceptar por cuenta canónica y formato según QA: recibo final, visibilidad y
    segunda ejecución con cero POST nuevos. Probar también desconexión con stock
    autorizado, sin fallback y sin evaluar pendientes. TikTok requiere evidencia
    real de proveedor/dominio/review/audit y consentimiento exacto por contenido;
    no importar fixtures como autoridad. X permanece `blocked_by_budget` y **cero
    endpoints facturables**, compras o recargas. Habilitación económica futura
    requiere nueva instrucción directa del operador.
13. Conservar prueba diaria y revisar evidencia antes de habilitar nuevo timer.
    Reconsultar inventario de automations para evitar duplicados; heartbeat oficial
    del chat actual, silencioso sin cambios y notificación solo por resultado o
    intervención. Crear una automation no prueba ejecución. Mantener ambos timers
    legacy disabled/inactive y no alterar publicidad u otros servicios.

## Estado de logging recibido durante Task10A

Root probó la revisión antigua con cuatro rutas sintéticas OAuth/media mediante
Cloud Run y proxy. Recibos privados `task10-log-synthetic-baseline.json` y
`task10-log-synthetic-observed.json` registran **8 entradas con marcador: 4 request
logs Cloud Run y 4 logs stdout del contenedor**. Gate **FAIL**. Cero entradas en
consulta Vercel es **NO CONCLUYENTE**. No hubo secretos reales ni cambio runtime.
Activación sensible queda pendiente hasta una protección real calificada y
revisada. Task10B hará el flujo completo SPA/login/start/callback same-origin
Cloud Run con login normal Humanizar, sin copiar cookies ni añadir CORS. Media
usará Run solo si HTTPS y prefijo de dominio son aceptados realmente. Root
respaldará/revalidará todos los sinks/ancestros y aplicará una exclusión nominada
aditiva en _Default limitada al servicio eikon y callback/media/requestURL o
Referer sensibles; conservará _Required y otros logs. Probará nuevos marcadores
tras latencia de ingestión y positivos de diagnósticos seguros, sin borrar el
baseline. Vercel debe quedar fuera del trayecto sensible soportado, manteniendo
proxy/UI normales; cero query hits no lo acredita. No hay cambio runtime todavía.

## Avance operativo del 12 de octubre

Imagen revisada `a4389e898bb34bed876616afc052fd9499664dae`, OCI
`sha256:9eef3179f126238b288b71da071b86db3e5949459e2e41b99783b9717d420e4e`,
desplegada en `eikon-00061-6lk` con 100 % del tráfico. Runtime salvo imagen e
IAM permanecen iguales al respaldo. La nueva SPA coincide byte por byte en
Cloud Run, dominio público y proxy; sesión API Humanizar owner comprobada en
su origen original. No se transfirió la sesión a otro origen.

La exclusión limitada de _Default ya se aplicó, conservando sus otras
propiedades, _Required y el resto de logs. La prueba sintética de callback/media
y Referer tiene controles positivos y diagnósticos Uvicorn redactados. El
marcador exclusivo de Referer no aparece en las consultas; el resultado negativo
anterior de dos queries ordinarias /health se conserva como prueba confundida,
sin borrar entradas ni ampliar el filtrado a todas las rutas. No se acredita
la ingestión del evento JSON INFO propio ni un flujo real de éxito, revocación,
422/500/timeouts. Estos límites impiden cerrar el gate completo o activar OAuth
y URLs temporales. Worker, grants, modelo nativo y publicaciones reales pendientes.

## Recuperación y rollback

Pausar nuevos despachos mediante autoridad propia y detener únicamente el nuevo
worker/timer cuando proceda; no activar legacy. Antes del POST, falta de autoridad
retiene sin inicio. Tras inicio durable o ACK perdido, nunca reasignar, repetir
POST, continuar upload/finish ni borrar publicación para eludir dedup. Recuperar
mismo intento con credencial de conciliación del mismo grant/cuenta: envelope
`purpose=reconcile_only`, `post_permitted=false`; esa credencial no es un token
criptográficamente limitado a GET. El worker y la outbox conservan el límite.

Facebook feed vídeo recupera únicamente por GET de la misma Page `published_posts`
(limit100), `from.id`, ID canónico de PagePost, `is_published`, permalink y
`created_time` reales, adjunto `media_type=video` / `target.id` igual al ID de carga
durable del mismo intento. No usa `object_id` deprecated, GET page/videos, caption,
URL o ID construido como prueba. Ausencia, ambigüedad, permisos o expansión no
admitidos conservan incertidumbre. La vía documental y los tests no acreditan
respuesta ni vídeo visible en la cuenta real.

La conciliación terminal confirma ID/recibo reales y conserva timestamp original
del proveedor, no hora del reporte. Crossday sin tiempo comprobado retiene solo
el destino afectado; retirada tardía conserva recibo/guard y no añade otra cuota.
Tickets quedan ligados a intento/media/grant/TTL/revocación; no renovar para
reintentar POST. Revocar un ticket no deshace un posible efecto remoto.

Revertir código/tráfico por digest/revisión exactos respaldados, sin asumir100%
ni latest. Conservar DB/storage/outbox nuevos, ledger, guards e intentos; no
restore destructivo sobre escrituras nuevas ni downgrade de esquema. Antes de
reabrir rutas antiguas probar que respetan grants/guards nuevos o mantenerlas
cerradas por un fence propio revisado. Fallo de vault o conexión bloquea, no cambia
cuenta. Registrar negativos y paso exacto pendiente; no cerrar meta por rollback,
instalación, health o ACK.

## Runtime y preflight del 12 de octubre: continuación

Cloud Run quedó en `eikon-00062-jg9`, tráfico 100 %, código
`a5dc64c8e755f59e7c81134d3a9aacdd993ba13d`, imagen fijada por digest
`sha256:386c16a05eaea396863be1e98bd3755c2d46f88e2009c080b97ebd7215c1036c`.
Se preservaron cuenta de servicio, recursos y variables previas. La configuración
OAuth y clave independiente del vault usan dos secretos nominados con versión 1;
un bootstrap privado revisado materializa el archivo OAuth con permisos 0600.
No hay credenciales en la imagen, Git ni este documento.

La corrección del logger fue revisada y las consultas gestionadas mostraron
cero coincidencias del marcador sintético, tres eventos JSON seguros y un
control positivo ordinario. Los casos fueron callback 401, media 409 y Referer
sensible 200. Son pruebas sintéticas acotadas: no acreditan todavía OAuth real,
revocación, descarga real del proveedor ni errores 500/timeouts gestionados.

Humanizar, tenant 17 y owner 4, conserva tres conexiones con sus 17 proyectos.
El 12 de octubre se verificaron otra vez las credenciales existentes mediante
el importador privado revisado, con comprobación real de identidad, scopes,
aplicación y vigencia. Facebook Systems (cuenta 1) y Facebook Humanizar
(cuenta 2) quedaron `active`, versión 2, vencimiento conocido y scopes
`pages_manage_posts`, `pages_read_engagement`, `pages_show_list` y
`public_profile`. Se guardaron cifradas en el vault después del respaldo y de
un dry-run satisfactorio; GET `overview` y `connections` respondieron 200 con
ese estado. No hubo POST de publicación ni modificación de política.
El primer dry-run retuvo Instagram News (cuenta 3) con
`token_expiry_unknown`. Task10E añadió la renovación oficial de Instagram en
`0ae3e79fc5ded17e37007926f68cd44717661a97`, con revisión independiente
aprobada, 43 pruebas nuevas y 1358 aprobadas/618 omitidas en la suite completa.
Las omisiones de PostgreSQL no se cuentan como aceptación. Después de un
respaldo nuevo se verificó la cuenta antigua, se renovó una sola vez mediante
`refresh_access_token` y se verificó la credencial devuelta dentro del importador
con CAS de owner/versión. El vault guarda la conexión `active`, versión 2,
`humanizar.news`, ID `17841434345672986`, vencimiento oficial `1797027639` y
sólo `instagram_business_basic`/`instagram_business_content_publish`.
La evidencia de scopes es `capability_probe`; no se afirma introspección de
Meta. GET `overview` y `connections` respondió 200 después de la renovación,
confirmando las tres conexiones activas y política versión 0 deshabilitada.
No hubo POST de publicación ni cambios en otras conexiones, política o cola.

El navegador solicitado es Brave, perfil Personal. La sesión de Humanizar
está autenticada en `https://eikon.humanizar.cloud/publications`; Meta y X
@HumanizarSystem también tienen sesión y TikTok Developers abre la aplicación
Humanizar Publicaciones. La consulta de overview desde Brave produjo
`ERR_BLOCKED_BY_CLIENT`; el panel muestra error aunque la API respondió 200
en la sesión privada original del operador. Se pidió al usuario resolver el
bloqueo local, sin cambiar protecciones mediante automatización ni transferir
cookies entre navegadores u orígenes. El callback configurado sigue siendo
del origen directo de Cloud Run: la retención segura del query OAuth en el
proxy canónico aún no está acreditada; cero coincidencias de logs no bastan.

Server2 recibió `ffmpeg` y `python3-venv` mediante un cuadro privado de sudo;
la contraseña se utilizó en memoria para SSH y no se guardó ni imprimió.
FFmpeg/ffprobe 8.0.1 están disponibles. Se codificó y comprobó un vídeo
sintético H.264, 1080×1920, yuv420p, un segundo; no se publicó esa prueba.

El preflight detectó que `_save_report` cargaba API/storage/renderer. Task10C,
commit `958e6d471d93161d1dfa42ff3ff7b6af751dc37e`, extrajo literalmente el
normalizador compartido sin cambiar contratos. Revisión independiente aprobada,
cero hallazgos; tres pruebas nuevas aprobadas. Suite focal del implementador:
176 aprobadas y 98 omitidas por falta de Postgres de prueba, que no se cuentan
como éxitos. La API conserva el alias y la dependencia previa db/policies del
arranque del worker permanece.

En server2 se preparó un staging nuevo de ese commit, archivo de fuente SHA256
`cce40c9d4d2180588d029f02a849e3a748f6f82260cd070cc67e002822a2748d`, y un
venv independiente con httpx 0.28.1, Pillow 12.3.0 y Pydantic 2.14.1.
El entrypoint deshabilitado y siete casos de registro real en Outbox con
MockTransport pasaron sin importar API/storage/renderer. El transporte simulado
no acredita ningún POST de proveedor ni una publicación remota.

El corte `humanizar-known-inventory-20261011` se importó en producción tras
un dry-run transaccional y un respaldo nuevo posterior a las conexiones de
Facebook. Manifest SHA256
`8389c03c9d2035634a07b6d15c26fb0546d77be867469807a2f80d236bfad92f`:
22 registros, 14 publicados históricos, 8 retenidos, 4 retiradas y 2 destinos
sin mapping acreditado. El replay produjo el mismo recibo, sin duplicados.
Los hashes de políticas, grants, campañas, revisiones, entregas, conexiones y
vault se mantuvieron iguales antes/después/replay. No se afirma inventario
remoto completo ni autorización editorial por importar esta historia.

Pendientes: OAuth/revisión de TikTok, política y
grants, reconexión del cliente a las herramientas nuevas, evaluación editorial real,
instalación del servicio aislado y pruebas de envío/segunda ejecución diaria.
No hay nuevo servicio o timer activado ni recurrencia nueva acreditada.
TikTok conserva requisitos externos; X conserva la decisión de no gasto.

La conexión MCP nativa actual listó proyectos de Humanizar (tenant 17).
Se amplió únicamente su allowlist local de seis herramientas de galería a
doce, añadiendo bandeja, candidatos, evaluación, preparación y vídeo.
El cliente aún no ha acreditado la recarga de esas herramientas y el launcher
conserva sólo la clave de galería: faltan los grants planner/reviewer dedicados.
Este cambio local no habilita publicación ni sustituye las pruebas reales.

La app de TikTok continúa en borrador. Se prepararon descripción y plataforma
web, pero Save exige icono, categoría, términos, privacidad y URL de servicio;
no se confirmó el guardado. Products/scopes y demo de extremo a extremo
siguen pendientes. No se envió a revisión ni se afirma permiso de publicación
pública. La sesión de Instagram en Brave quedó en la pantalla de carga, sin
prueba nueva de acceso social. X mantiene la restricción expresa de no gasto.
