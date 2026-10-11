# Eikón: campañas, conexiones y calendario por empresa

Fecha: **11 de octubre de 2026**, America/Bogota.
Estado: **diseño escrito para revisión; subsistemas nuevos no implementados**.
Amplía la entrega de galería/Codex del 8 de octubre, sin reabrir su implementación.

## Objetivo y alcance

El operador aprobó avanzar desde galería y estudio a un centro de identidad de
producto y publicaciones. Cada empresa utiliza su propio Codex y sus redes.
Humanizar será el primer uso real. El recorrido de aceptación es:

**producto → campaña → pieza y copy → revisión owner → fecha y cuenta → envío → recibo**.

La identidad común Humanizar se aplica como entrega acotada sobre el renderer
existente. Este documento define los nuevos contratos de campañas, conexiones,
calendario, trabajador y panel. Se implementarán por entregas verticales, no como
cinco productos independientes ni como una reescritura de Eikón.

Primera publicación: imagen Facebook en las cuentas actuales verificadas. La
galería sigue privada. Instagram se habilita después de resolver un medio de
entrega autorizado y revisar su formato exacto. Vídeos/reels y TikTok requieren
adaptadores y pruebas posteriores; X conserva la exclusión de gasto. No se añade
facturación, un proveedor de imágenes alternativo ni compra de créditos.

## Decisión arquitectónica

Se conserva FastAPI/React, PostgreSQL y storage privado del servicio existente.
Eikón será la fuente de autorización, calendario y resultados. Un trabajador
duradero en server2 consumirá entregas autorizadas y utilizará los adaptadores
del publicador Humanizar. Vercel conserva el proxy y no ejecuta los envíos diarios.

Se descartan copiar la cola actual a una base común sin tenant y añadir solo un
botón de publicación sobre la galería: ninguna alternativa representa de forma
segura revisión del copy, cuenta de destino, incertidumbre e historial.

La cola SQLite actual de Humanizar se preserva como historial y flujo legado,
con sus timers apagados. Los nuevos envíos utilizarán una outbox separada por
empresa y una autorización explícita de Eikón. No se mezclan otras empresas en
esa cola ni se eliminan IDs antiguos para evadir la deduplicación.

## Identidad y producción

El perfil `texts.brand_family=humanizar` selecciona explícitamente el sistema
común en el flujo existente; no se infiere por slug ni por cuenta. Papel,
carbón, coral, lavanda y Manrope proceden del manual oficial. Un acento secundario
puede distinguir productos. Los logos originales conservan sus bytes y hashes.
Si falta un original o una identidad procedural explícitamente fijada, se
presenta wordmark provisional; no se inventa un símbolo oficial.

Codex recibe proyecto, producto, referencias, dimensiones, finalidad y límites
del contenido mediante los encargos actuales. La bandeja de producción agrupa
encargos por campaña y muestra qué sigue pendiente. Codex genera en su cliente;
MCP importa. Las composiciones usan retículas, márgenes, ajuste de texto y
contraste deterministas. Estos controles ayudan a la revisión, sin certificar
por sí solos fidelidad de logo, calidad semántica o veracidad de afirmaciones.

Las ilustraciones actuales permanecen pendientes: se completan con identidad,
copy y formatos finales, y se revisan. Una conversión PNG→JPEG o una variante
de vídeo crea una nueva pieza con sus bytes, hash y revisión; nunca se sustituye
silenciosamente el archivo aprobado.

## Campañas y revisión completa

Una campaña pertenece a una empresa y proyecto, y agrupa objetivo, producto,
secuencia y variantes por plataforma. Cada variante tiene revisiones inmutables.
El estado de campaña resume sus variantes; no autoriza un envío por sí mismo.

Una `publication_revision` congela:

- empresa, proyecto, marca y versión de identidad;
- medio, SHA256, snapshot de marca y revisión visual vigente;
- caption exacto, enlaces, fuentes, contexto y comprobaciones de derechos;
- conexión, plataforma y **ID remoto de la cuenta**, no únicamente un alias;
- fecha consciente de zona horaria, vencimiento y hash canónico del conjunto.

El owner revisa imagen y texto, destino y fecha, y registra decisión, actor,
fecha, hash y evidencias. Confirma expresamente fidelidad de marca, derechos y
afirmaciones/fuentes sobre esa revisión. Una ruta de validación para contratos
Eikón comprueba esta autorización humana, los checks y sus evidencias sin
convertirla en scores numéricos. No fabrica `calidad_evaluacion` ni
`image_review` para superar el validador antiguo; su ruta legacy sigue intacta.
Cambiar cualquiera de esos campos crea una revisión
nueva que necesita aprobación; la revisión anterior conserva su historial.
No se convierte una aprobación visual en un score editorial inventado.

Los permisos actuales de Codex conservan su alcance: crear encargos y entregar
medios, sin aprobar, gestionar identidad, conectar cuentas o habilitar envíos.
Una aprobación caducada por cambio de marca/proyecto no permite exportación.

## Conexiones y credenciales

Cada conexión pertenece a una empresa y representa plataforma, modo de API,
ID remoto, nombre comprobado, permisos concedidos, expiración y estado operativo.
Una relación explícita indica qué proyectos pueden utilizarla. No se acepta un
tenant ni una cuenta de destino enviados como autoridad por el cliente.

El owner inicia OAuth desde Eikón. State de un solo uso y PKCE cuando el proveedor
lo soporta quedan ligados a su sesión, empresa y conexión; el callback comprueba
identidad y permisos antes de activar. La interfaz muestra consentimiento,
cuenta, alcance, vencimiento y necesidad de MFA o revisión externa.

Las credenciales se cifran con AES-GCM y clave de servicio independiente de la
clave de firma JWT. El material de clave se genera y respalda privadamente; no
se guarda en Git, argumentos CLI, capturas ni recibos. El despliegue autorizado
debe suministrarlo al runtime mediante configuración privada. Los datos públicos
de conexión no devuelven tokens ni ciphertext. Una pérdida de clave bloquea los
envíos; no provoca fallback ni renovación con otra cuenta.

Las credenciales Humanizar existentes se incorporan por el controlador usando
sus referencias privadas actuales, con verificación de identidad y respaldo.
No se piden otra vez permisos ya concedidos dentro de ese alcance. Una empresa
nueva completa su propio consentimiento; no hereda tokens de Humanizar.

El trabajador utiliza una credencial dedicada, acotada por empresa, distinta de
la clave Codex. Solo puede reservar/reportar entregas y resolver la credencial
de una conexión que pertenezca a **su reserva vigente**. La resolución usa HTTPS,
no devuelve otras cuentas y no permite seleccionar otro tenant. Tokens de redes
no aparecen en la galería ni en el navegador del revisor.

## Calendario, reservas e incertidumbre

La aprobación crea una entrega programada para una revisión exacta. Eikón
reserva atómicamente una entrega vencida y autorizada mediante un lease ligado
a empresa, revisión, cuenta y worker. Dos workers no reciben el mismo envío.
Después del preflight y antes del POST, el worker solicita a Eikón una
transición atómica y durable `reservada → intento_iniciado`, ligada a claim,
worker y hash exactos. Solo una respuesta confirmada autoriza ese único intento.
Si la transición tiene timeout, se concilia antes de enviar; no se supone que
falló. La outbox local conserva la misma autorización antes del POST remoto.
Una entrega con intento iniciado nunca se reasigna automáticamente, aunque
venza su lease o desaparezca el worker.

Antes de reservar/despachar se comprueban aprobación actual, SHA descargado,
identidad, conexión, permisos reales, expiración y hash del contrato. Si Eikón
no responde o cambia la autorización antes de iniciar el intento, se bloquea.
No se promete atomicidad entre Eikón y una red externa: una vez iniciado el POST,
revocar autorización requiere conciliar su resultado o retirar la publicación.

La ventana por defecto será de 60 minutos desde la fecha aprobada. Una entrega
fuera de ventana queda vencida y visible, sin publicación tardía automática ni
ráfaga de recuperación. El owner puede crear y aprobar una nueva revisión con
otra fecha. Esta ventana es una decisión operativa para impedir envíos tardíos
automáticos; no atribuye una causa al atraso observado en el incidente anterior.

Estados de entrega: programada, retenida, reservada, intento_iniciado, publicada, fallida,
incierta, vencida y cancelada antes del intento. Cambiar de estado no borra eventos.
Timeout después del POST, pérdida de recibo o caída en vuelo quedan inciertos;
el vencimiento del lease no permite repetir automáticamente un POST ya iniciado.

La deduplicación compara SHA y **destino real normalizado** (plataforma/cuenta)
dentro de la empresa. `api_mode` sirve para verificar permisos, pero no crea un
destino distinto. Si hay IDs dependientes de aplicación/modo, se exige mapping
de equivalencia comprobado; si no puede comprobarse, se retiene la conexión.
Cambiar alias, ID interno, caption o nombre de archivo no
permite repetir la misma pieza. La misma pieza puede ir a cuentas distintas una
vez cada una. Similitud perceptual o copy repetido produce advertencias editoriales;
no se presenta el hash exacto como detector semántico.

El ledger es append-only: reserva, inicio, publicado, fallido, incierto,
conciliación, cancelación y retirada registran actor, fecha, revisión, intento,
cuenta y evidencia. Los reportes del worker son idempotentes por intento/evento.
Una retirada conserva el recibo original y la guardia, y registra confirmación
posterior. Los cuatro borrados del 11 se importarán como eventos históricos, no
como permiso para republicar. Antes del primer claim nuevo se importa
idempotentemente **todo el historial de intentos y recibos legacy**, con SHA y
destino comprobados: publicados conservados, retirados, fallidos, inciertos y
en vuelo. Un corte de migración verificado bloquea envíos hasta acreditar la
guardia histórica completa. Los ocho envíos antiguos repetidos siguen retenidos
y no se convierten en nuevas autorizaciones.

## Datos y límites de autorización

| Entidad | Relación y contrato |
|---|---|
| Campaña | tenant/proyecto/producto, objetivo y resumen de variantes |
| Revisión de publicación | inmutable; medio, identidad, copy, destino, fecha y hash |
| Revisión editorial | append-only; owner, decisión, hash y comprobaciones |
| Conexión social | tenant, identidad remota, permisos y metadatos de credencial cifrada |
| Entrega | tenant, revisión aprobada, fecha, estado efectivo y lease |
| Intento/evento | append-only; entrega, worker, claim, recibo y resultado/conciliación |

Toda consulta, FK y unicidad que relacione estas entidades incluye tenant. El
owner prepara y revisa sus campañas y conexiones en la primera entrega. No se
atribuye permiso de edición a miembros ni se añaden nuevos roles en esta entrega.
Los grants de worker se emiten expresamente y no se heredan de claves legacy ni
de las seis concesiones Codex actuales. Los endpoints de worker rechazan ese
material de autenticación aunque el mismo usuario sea propietario de una marca.

## Interfaz y operación

La entrada muestra empresa activa y proyecto, seguido de pendientes para crear,
revisar, programar y resolver. Desde un producto se accede a identidad, galería,
campañas y calendario. Una vista de campaña reúne piezas, captions, variantes,
estado de aprobación y fechas. Revisar no exige recorrer pantallas inconexas.

Calendario y panel muestran cuenta real, horario/zona, retenciones, último
resultado y enlace remoto comprobado. Diferencian pendiente, autorizado,
programado y publicado. Un HTTP 200 de salud o un ACK del worker no se muestra
como publicación. El owner puede cancelar antes del intento, reconectar,
conciliar o solicitar una retirada confirmada. Métricas de alcance se añaden
solo cuando exista permiso y evidencia; el recibo y enlace son la base inicial.

## Verificación y despliegue

Se reutilizan los guards de media, hash, review, preflight Meta, claims SQLite
y resultados conservadores. La autorización editorial humana nueva tiene una
ruta explícita y pruebas propias; la evaluación y los scores legacy no se
debilitan ni se inventan. Pruebas SQLite y PostgreSQL cubren aislamiento,
reservas concurrentes y eventos idempotentes. Las pruebas de integración cubren:

1. Tenant ajeno para proyecto, medio, conexión, revisión, entrega y credencial.
2. Medio aprobado con identidad cambiada; archivo reemplazado o copy editado.
3. Alias distintos con el mismo destino, retiradas y replanificación.
4. Dos workers, lease vencido, caída en vuelo y timeout tras aceptación remota.
5. OAuth state repetido/ajeno, callback incorrecto, permisos insuficientes y token vencido.
6. Falla de red/servicio y ausencia de stock: bloqueo visible sin logo como fallback.
7. Fecha vencida/ambigua y ventana de 60 minutos; ningún envío tardío automático.
8. GUI real de crear/revisar/programar/resultado en desktop y móvil.

Primero se prueba sin llamadas de publicación y con dobles de red. La aceptación
real exige una pieza final revisada por el owner, una reserva y un envío por
cuenta autorizada, con recibo y lectura posterior. Cada prueba registra SHA de
código y pieza, cuenta, fecha, contrato y resultado; sin tokens en evidencia.

El despliegue reutiliza servicio/proxy/worker existentes, con respaldo privado de
configuración y datos. Los nuevos timers empiezan deshabilitados. El calendario
antiguo permanece apagado; su reactivación no forma parte de la migración. No se
retrocede a una revisión que ignore grants nuevos o lea credenciales sin sus guards.

## Orden de las entregas y cierre

1. Familia/estado de identidad en el estudio existente y comprobación visual.
2. Campaña, variantes y revisión completa, antes de cualquier envío nuevo.
3. Conexión Humanizar/Facebook, lease y trabajador separado con pruebas de fallo.
4. Calendario/panel y recorrido real comprobado; otras empresas con sus propias cuentas.
5. Instagram con medio exacto autorizado; después vídeos/reels y TikTok según elegibilidad.

La meta no se declara completa por una galería, una instalación, un health o un
ACK. Debe existir el recorrido real revisado y publicado, estados visibles,
historial preservado y aislamiento probado. Los canales bloqueados externamente
se reportan como tales, con el paso humano concreto pendiente; no se registran
como capacidades operativas.
