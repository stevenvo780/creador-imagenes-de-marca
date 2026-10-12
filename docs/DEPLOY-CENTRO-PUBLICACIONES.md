# Release del centro de publicaciones

Task10A prepara código y gates locales. **Este documento no acredita despliegue,
OAuth, ejecución diaria, publicación ni timer activo.** Task10B comienza después
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
