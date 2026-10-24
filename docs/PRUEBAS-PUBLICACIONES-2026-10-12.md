# Pruebas reales de publicaciones — 12 de octubre de 2026

Tenant Humanizar: 17. Fecha local: America/Bogota. Las publicaciones de prueba
no acreditan todavía una recurrencia diaria activa en todas las redes.

## Estado vigente — 22 de octubre, 03:56 UTC

Cauce, ciclo del 21 de octubre, se publicó automáticamente en Facebook Systems,
Facebook Humanizar e Instagram dentro de su ventana original. Graph confirmó
los tres posts y se descargaron e inspeccionaron las imágenes servidas. Cinco
barridos idle0 completos quedaron entre dos snapshots de cinco tablas iguales.
El detalle, la distinción entre ambos snapshots y los límites figuran al final.
El timer sigue activo y quedan nueve ciclos Meta existentes para el 22–30 de
octubre: 27 entregas retenidas por frecuencia y sin inicio. La cobertura global
de cinco cuentas y 17 productos permanece **incompleta y bloqueada**. Brave
continúa ausente y se conservan las intervenciones ya solicitadas de X/TikTok.

Las tablas y estados fechados que siguen conservan su valor histórico. El timer
apagado y la primera prueba de Instagram pendiente corresponden al 12 de octubre;
no describen el estado vigente.

## Resultado comprobado por destino — corte histórico del 12 de octubre

| Destino | Prueba de imagen | Vía | Recurrencia nueva |
|---|---|---|---|
| Facebook Humanizar Systems | Publicada y visible | Worker canónico en server2 | Pendiente de activación |
| Facebook Humanizar | Publicada y visible | Worker canónico en server2 | Pendiente de activación |
| X @HumanizarSystem | Publicada y visible | Brave, sin gasto API | Seguimiento diario configurado; ejecución recurrente pendiente |
| TikTok @humanizar.systems, cuenta confirmada por el operador | Studio retiró «Contenido en revisión» y muestra «Todo el mundo» | Brave / TikTok Studio Fotos | Seguimiento diario configurado; ejecución recurrente pendiente; API bloqueada |
| Instagram @humanizar.news | PNG retenido antes del inicio; JPEG cerrado de forma auditada como failed_before_dispatch, sin envío a Meta | Worker canónico en server2 | Corrección desplegada; primera prueba real y activación pendientes |

Publicaciones comprobadas:

- [Facebook Humanizar Systems](https://www.facebook.com/61588505694024/posts/122127487857283523/).
- [Facebook Humanizar](https://www.facebook.com/100093808513344/posts/1009851405485134/).
- [X Humanizar Systems](https://x.com/HumanizarSystem/status/2109828177581506744).
- [Prueba de TikTok según el enlace de Studio](https://www.tiktok.com/@humanizar.systems/video/7695975112142638357).
  TikTok asignó el ID en la cuenta original `@user3217463593302`. Studio confirmó
  después el cambio a `@humanizar.systems` en los enlaces de ambas publicaciones
  y mostró el avatar oficial actualizado. Brave bloqueó el readback del perfil
  con ERR_BLOCKED_BY_CLIENT; el detalle nuevo devuelve HTTP 403.
  La comprobación visual definitiva del nombre, avatar y biografía sigue pendiente.
  No se cuenta el detalle con imagen todavía sin cargar como prueba visual final.

## Contenido y trazabilidad

Pieza Sinergia POS: logo existente conservado, ilustración de mostrador y texto
«Tu mostrador, en orden». La evaluación editorial nativa comprobó imagen real,
referencia oficial, texto y fuente comercial antes de autorizar el contenido.
El caption describe caja, inventario y cierre de turno, y enlaza humanizar.tech.
No afirma resultados numéricos ni certificaciones.

El JPEG 1080×1350 tiene SHA256
`aabe5e697b0a5a690bf2d0470b9c5af83ef832107267c0e471dc6b80398532b4`.
TikTok se envió una sola vez con marca propia, etiqueta de generación por IA,
sin ubicación y sin añadir música. Studio mantuvo la primera prueba anterior;
no se borraron publicaciones para eludir deduplicación.

## Worker y ausencia de duplicados

El servicio aislado está instalado en server2. El timer nuevo y los dos timers
legacy permanecen deshabilitados e inactivos. El marcador actual permite los
barridos controlados; su presencia no acredita recurrencia activa.

El primer barrido publicó las dos fotos de Facebook y retuvo el PNG de
Instagram por formato no admitido. El segundo barrido procesó cero entregas
nuevas: el outbox mantuvo exactamente las dos filas de fases de Facebook.
Se verificaron los dos posts en Brave además de sus IDs y recibos del proveedor.

Tras cerrar el intento antiguo de Instagram con su grant original, se renovó
la política a versión 2 por 30 días, conservando los 17 proyectos y tres
conexiones. Vigencia hasta el 11 de noviembre de 2026 a las 22:32:11 de Bogotá.
Grants separados: planner 4, reviewer 5 y worker 6; los tres grants anteriores
quedaron revocados. Los tokens permanecen privados y fuera de Git.

Se instaló el grant worker 6 en server2 conservando propietario root y modo
0640. Dos barridos correlacionados por InvocationID terminaron `idle`,
`processed=0`; las fases se mantuvieron en 2. Un tercer barrido comprobó el
control sin intervención desde SSH y también procesó cero entregas.
El permiso NOPASSWD/NOSETENV de `server` admite exclusivamente iniciar el
servicio 17 y activar/desactivar su timer. El intento de `sudo -n id -u`
fue rechazado: no se concedió sudo general sin contraseña.

## Fallo de Instagram y reparación desplegada

Delivery 3 quedó retenido antes de `started_at`: el formato era PNG. Se importó
un JPEG nuevo y se obtuvo una evaluación editorial nativa nueva para delivery 4.
El worker confirmó el inicio de delivery 4, pero no obtuvo la capacidad de
entrega antes de entrar a `dispatching`.

La revisión anterior `eikon-00066-gmp` carecía de las dos variables
`EIKON_PUBLICATION_MEDIA_DELIVERY_ENABLED` y `EIKON_PUBLICATION_MEDIA_ORIGIN`.
La ruta de emisión valida ese gate antes de crear el ticket. Antes del cierre auditado, el outbox original
mantenía `start_confirmed`, cero filas de fases para ese intento —también se
cuentan fases sin recibo— y ningún remote_id. La primera clasificación
`network_timeout` era demasiado amplia; ocultaba también errores HTTP de API.
La segunda ejecución conservó incertidumbre y no añadió fases de proveedor.

La corrección preventiva añade readiness autenticado antes del inicio y
diagnósticos acotados. La revisión independiente fue aprobada; 367 pruebas de
regresión SQLite/PostgreSQL y 121 del worker final pasaron. Dos observaciones
menores posteriores quedaron corregidas con diez pruebas focales aprobadas.
El logging y la entrega de media tienen además 40 pruebas locales aprobadas.

La recuperación se implementó con cuarentena durable en el outbox, evidencia
del worker original y cierre canónico por el owner. Las pruebas focales finales
pasaron en SQLite/PostgreSQL; 362 pruebas de regresión y la revisión independiente
no encontraron defectos críticos o importantes. La observación sobre evidencia
`published_at_utc` quedó corregida y comprobada con 36 pruebas focales finales.

Se desplegó el código `adb6f4a0a6e88bf00821dc42b5d4b1aab66b8de6` en
`eikon-00067-bmn`, 100 % del tráfico. Imagen fijada:
`sha256:9c52cbaf64865c3e10f39c63250bca0753926a2cc2010aa7f862b8d025863264`.
Sólo cambiaron cuatro archivos API en la imagen; se conservaron SPA, IAM y
configuración de ejecución. Readiness autenticado devuelve 200 con
`ready=false` y `media_delivery_release_gate`, antes de conceder un inicio nuevo.

El owner cerró delivery 4 como `failed_before_dispatch` tras comprobar cero
fases locales de ese intento y cero tickets históricos de API. El replay
idéntico devolvió el mismo resultado; el worker original leyó el estado
terminal y guardó su ACK. No se editó la DB manualmente, no se fabricó un ID
remoto y no hubo POST de publicación de Instagram.
`started_at`, intento y SHA quedaron preservados y siguen consumiendo frecuencia
y presupuesto diario. El JPEG anterior no puede reutilizarse para eludir ese guard.

El siguiente intento de Instagram requiere media nueva y no puede empezar antes
del 13 de octubre de 2026 a las 21:22:23 de Bogotá. La primera prueba real,
la descarga del proveedor y la segunda ejecución sin duplicados siguen pendientes.

El transporte de media debe utilizar el origen directo de Cloud Run después
de calificar HTTPS y logging. No se habilitan URLs sensibles a través del proxy
Vercel sin prueba de retención apropiada.

## Bloqueos externos y alcance

TikTok Developers lista «Humanizar Publicaciones», pero su detalle devuelve
«Something went wrong — Network Error» tanto al operador como al control de
Brave. Publicar por Studio no demuestra OAuth, revisión, audit ni publicación
API. X conserva la decisión de no gasto; su vía probada requiere el cliente
Codex, Brave y la sesión disponible.

La página antigua de Facebook Humanizar conserva su avatar anterior: el acceso
a tareas permite publicar, pero no acredita control total para editar perfil.
La prueba de publicación no significa que ese pendiente de administración haya
quedado resuelto.

## Programación diaria configurada

La automatización local `humanizar-publicaciones-diarias` está ACTIVE y
adjunta a este chat. Despierta a las 21:45 de America/Bogota para preparar la
ventana 22:00–23:00. La próxima ejecución prevista es el 13 de octubre.
La configuración no equivale a una ejecución recurrente ya comprobada.

La política conserva frecuencia de 1440 minutos, una publicación diaria por
destino, ventana de 60 minutos y gasto desactivado. Planner y reviewer deben
comprobar hechos, imagen y pertinencia; el worker sólo consume entregas
aprobadas. X y TikTok usan Brave con la sesión autorizada; esta ruta requiere
el equipo encendido y Codex disponible. La API de TikTok sigue sin acreditarse.

Antes de activar el timer de server2, faltan calificar la entrega de media por
HTTPS directo, publicar la prueba nueva de Instagram, comprobar su recibo y
visibilidad, y repetir el barrido sin añadir POST. Las dos variables de media
siguen ausentes. No se activa el timer por tener el marcador o permisos sudo.

Al cierre de este corte, la app informó 100 % de cuota semanal Codex usada y
`ordinaryUsageAllowed=false`. No se cambió de cuenta. La capacidad editorial
IA de la siguiente ejecución depende de la disponibilidad de esa misma cuenta;
no se cuentan la programación ni el stock histórico como nueva evaluación IA.

La meta permanece abierta hasta comprobar las publicaciones recurrentes de todos
los destinos. Pendientes adicionales: completar la API de TikTok, recargar el
MCP de Desktop (el launcher nativo funcionó con roles separados), comprobar el
perfil final de TikTok y recuperar control total del perfil antiguo de Facebook.

## Continuación del 13 de octubre: siguiente pieza y calendario

Los apartados anteriores conservan el corte del 12 de octubre. El siguiente
contenido es Deméter, con hechos comprobados en humanizar.tech: distribuidoras
de alimentos, pedidos, rutas, inventario y entregas. Se conservó la referencia
vigente de Eikón, marca 110/version 4, sin presentarla como un logo histórico
independiente confirmado. La conversión de PNG a JPEG sólo adaptó el formato;
no redibujó ni modificó la composición o la referencia.

JPEG 1080×1350, 191953 bytes, SHA256
`99836aae9569ed692bc3605de70f2b4c2ad830c979e83693ba5922d08dc1ae80`.
Se importó como media 47, con procedencia de las imágenes 32/16 y brief 46.
El original de galería conserva `pending_review`; la aprobación editorial de
publicaciones tiene un flujo separado y no cambia la revisión owner de galería.

El agente Codex actual inspeccionó los bytes reales, la referencia y los hechos.
Un cliente MCP stdio real del launcher existente preparó contratos y entregó
las imágenes al agente; éste registró evaluaciones 5/6/7 y decisiones elegibles
5/6/7, política 2. El recibo identifica honestamente el agente actual y no inventa
un slug de modelo o una atestación criptográfica del proveedor. El launcher sólo
carga galería/planner/reviewer; no recibe el grant worker. El error de configuración
del conector de Desktop sigue pendiente de recarga y no se contó como éxito.

| Destino | Siguiente pieza | Hora de Bogotá | Estado comprobado |
|---|---|---|---|
| Facebook Systems | Deméter, delivery 5 / revisión 5 | 13 oct, 22:00 | Calendario canónico de Eikón; sin inicio ni POST nuevo |
| Facebook Humanizar | Deméter, delivery 6 / revisión 6 | 13 oct, 22:00 | Calendario canónico de Eikón; sin inicio ni POST nuevo |
| Instagram News | Deméter, delivery 7 / revisión 7 | 13 oct, 22:00 | Calendario canónico; primera publicación API aún pendiente |
| TikTok @humanizar.systems | Deméter, ID 7696012000295488775 | 13 oct, 22:00 | Programada realmente en Studio; fila nueva, fecha futura y distintivo de reloj |
| X @HumanizarSystem | Un borrador Deméter con JPEG y etiqueta IA | Ventana 22:00–23:00 | Lista Scheduled vacía; borrador conservado, programación no confirmada |

El calendario de Eikón conserva `held`, con `daily_quota_reached` y
`frequency_limit` del corte inicial. `started_at` sigue vacío en las tres entregas
nuevas; el claim reevalúa las restricciones en su horario. No se borraron los
guards ni se adelantó el horario. El intento viejo 4 de Instagram sigue cerrado;
el nuevo medio tiene procedencia y evaluación propias y nunca se intentó antes
en estos destinos.

TikTok recibió un solo envío de programación, con marca propia y etiqueta IA,
sin música añadida ni ubicación. Una pestaña nueva de Studio confirmó el ID y
el reloj del 13 de octubre, 22:00. La miniatura de esa fila aún no cargaba en
la captura; no se presenta como comprobación visual final de la publicación.
Su visibilidad pública se verificará después de la hora programada. No repetir
el envío de TikTok desde el seguimiento diario si la fila ya existe.

X conserva el borrador tras conciliar que Scheduled estaba vacío. El intento
de programación no se contó como éxito y no se repitió el botón final. La vía
gratuita de publicación directa en la ventana diaria permanece pendiente.

## Calificación gestionada de logging: 13 de octubre

Se probó el módulo real de logging de la imagen fijada mediante un fixture
sintético sin DB, almacenamiento de producción ni llamadas a redes sociales.
Cloud Run mantuvo `eikon-00067-bmn` al 100 % mientras la revisión sintética
`eikon-logq-20261013` atendía únicamente su tag. Luego se retiró el tag y se
restauró la plantilla API original; la revisión de plantilla sin tráfico quedó
`eikon-00069-fwg`. IAM se conservó. No promover `latest` como atajo.

Se observaron HTTP 200, 422, 500 y timeout gestionado 504. Las respuestas
ordinarias protegidas conservan `private, no-store` y `no-referrer`; el 504
gestionado no se atribuye al middleware de la aplicación. Las consultas de
logging dieron cero coincidencias del marcador sensible, dos controles ordinarios
positivos y seis diagnósticos JSON con campos permitidos. La exclusión acotada
de _Default permaneció intacta; no se ampliaron filtros ni se borraron logs.
Esto acredita retención en los sinks comprobados, no ausencia absoluta de
procesamiento o de buffers de Log Router.

Se conservó un resultado negativo del transporte: la interrupción después de
cabeceras produjo `RemoteProtocolError` local, pero el proxy gestionado entregó
HTTP 200 completo al cliente. El diagnóstico seguro fue `response_interrupted`.
El timeout devolvió 504 al cliente y el handler terminó posteriormente con un
diagnóstico 200 a los seis segundos. No se ocultaron esas diferencias.

Once pruebas aisladas de recuperación del operador de logging pasaron, además
de las pruebas HTTP del módulo empaquetado. Las sondas sintéticas no acreditan
descarga con ticket real, revocación ni publicación Instagram. La activación
controlada de media tiene revisión independiente y diez pruebas de recuperación;
la aceptación completa y el timer siguen sujetos a la prueba real del horario.

La habilitación controlada terminó en `eikon-media-20261013`, 100 % del tráfico,
mismo digest y únicamente las dos variables de entrega añadidas. Candidata y
origen directo dieron readiness autenticado `ready=true`, health 200, rechazo
anónimo y ticket inexistente 404 con las cabeceras previstas. IAM y runtime
restante se conservaron; el tag se retiró y worker/timer siguen apagados. Cero
claims, tickets reales y POST de proveedor en esta operación. El gate de
aceptación completa sigue abierto hasta comprobar descarga, revocación y el
primer envío real de Instagram. No confundir el readiness con ese resultado.

La cuota se consultó otra vez el 13 de octubre a las 05:07 UTC: la app de la
misma cuenta pasó a `ordinaryUsageAllowed=true`, uso semanal 0 %. Se conserva
el resultado anterior del 100 % como histórico; no se cambió de cuenta ni se
compraron créditos para resolverlo.

## Vídeo nativo y lectura posterior: 13 de octubre

Se convirtió la composición existente de Agentes de IA a la medida en un MP4
estático silencioso de seis segundos, H.264/yuv420p, 1080×1920 y 30 fps. El padding
conserva la composición entera y el logo oficial; no se redibujó la identidad ni
se produjo una animación nueva. Original 345720 bytes, SHA256
`d395bd2a9cbd8b09066dd04e2138b32f3f596062f8e86e991d1a0faf5616590c`.
La fuente de imagen 45 conserva su revisión owner pendiente. El cliente MCP real
importó el vídeo privado 1 con brief 47 y creó contratos nuevos para las tres
cuentas; la evaluación de imagen no se heredó al vídeo.

El agente Codex actual inspeccionó frames de 0, 3 y 5,9 segundos, la referencia
original y el contexto de humanizar.tech. Registró razones para los seis checks
y decisiones 8–10 elegibles. El recibo conserva `frames_only_silent`,
`full_video_watched=false`, `client_reported` e identificación limitada del
modelo; no presenta una reproducción completa ni atestación criptográfica.
La variante privada con tono generado, vídeo 2/revisión 11, quedó `hold/ai_held`
por audio no inspeccionado y derechos limitados al fixture. No creó entrega de
publicación y no se subió a ninguna red.

| Revisión | Cuenta | Decisión posterior | Entrega de publicación | Fecha Bogotá |
|---|---|---|---|---|
| 8 | Facebook Systems | 8, elegible | 8, sin inicio | 14 oct, 22:00 |
| 9 | Facebook Humanizar | 9, elegible | 9, sin inicio | 14 oct, 22:00 |
| 10 | Instagram News, reel | 10, elegible | 10, sin inicio | 14 oct, 22:00 |
| 11 | Instagram News, fixture con audio | 11, retenida por IA | Ninguna | Sin despacho |

Cuatro GET MCP independientes posteriores entregaron materiales 20–23 y
confirmaron los mismos contratos/hashes y decisiones 8–11. La revisión
independiente recalculó hashes de snapshots y recibos, sin hallazgos Critical o
Important. Esto cierra el gate de evaluación real de Task5. Task10 sigue abierto:
evaluar, programar y leer decisiones no acredita descarga/revocación de tickets,
publicación visible ni recurrencia del proveedor.

Las entregas 8–10 conservaron `held/frequency_limit` y `started_at=null`;
el horario y la ventana siguen siendo 14 de octubre, 22:00–23:00. Dos arranques
reales del servicio de server2 dieron `idle/processed=0`, salida 0 y timer
disabled/inactive antes del vencimiento. Esas ejecuciones no sustituyen la
segunda ejecución sin POST después de una publicación real. No se borraron
guards ni se adelantó el calendario.

## Colas nativas conciliadas: 13 y 14 de octubre

Este corte reemplaza el estado anterior de X sin borrar la evidencia histórica
del intento no confirmado. X mostró en Scheduled una fila Deméter del 13 de
octubre a las 22:00 y otra del vídeo Agentes del 14 a las 22:00. Cada envío final
se activó una vez; la cola confirmó caption, fecha y miniatura, con duración
0:06 para el vídeo. La subida de vídeo requiere primero el menú Upload del
botón de medios; una espera de filechooser anterior a abrir ese menú no acredita
fallo de permisos. Se usó Brave, etiqueta IA y cero gasto API.

TikTok Studio confirmó ambas filas de @humanizar.systems: Deméter ID
`7696012000295488775`, 13 de octubre, 22:00, y vídeo Agentes ID
`7696024738354695425`, 14 de octubre, 22:00, duración 00:06. La vista previa del
archivo silencioso conserva el logo y la composición completos. Se seleccionó
Todo el mundo, marca propia y etiqueta IA, sin música añadida ni ubicación.
Cada programación tuvo un solo envío final.

| Destino | 13 oct, 22:00 | 14 oct, 22:00 | Límite actual |
|---|---|---|---|
| Facebook Systems | Deméter, calendario Eikón 5 | Agentes, calendario Eikón 8 | Claim/envío en horario aún pendiente |
| Facebook Humanizar | Deméter, calendario Eikón 6 | Agentes, calendario Eikón 9 | Claim/envío en horario aún pendiente |
| Instagram News | Deméter, calendario Eikón 7 | Agentes reel, calendario Eikón 10 | Primer recibo API y media real pendientes |
| TikTok | Programación nativa confirmada | Programación nativa confirmada | Visibilidad después del horario pendiente; API Developers bloqueada |
| X | Programación nativa confirmada | Programación nativa confirmada | Visibilidad después del horario pendiente; API sin créditos |

Las capturas `x-agentes-video-programado.png` y
`tiktok-agentes-video-programado.png` conservan evidencia de la cola en el
directorio de visualizaciones del 13 de octubre. Los diarios y recibos privados
conservan los originales y hashes, fuera de Git. No volver a enviar estas piezas
desde el seguimiento diario: primero conciliar la fila o publicación existente.
La automatización oficial existente mantiene 21:45, este chat, política y roles;
se actualizó con ambas fechas/IDs y la prohibición de publicar el fixture 11.

## Comprobación visual de agenda en móvil: 13 de octubre

La sesión owner humanizar abrió la agenda real en Brave y Actualizar cargó diez
entregas, diecisiete campañas y política 2. Se inspeccionó visualmente la agenda
de escritorio y el viewport móvil 390×844, modo oscuro y claro: el contenido
principal cabe sin desbordamiento horizontal y el menú conserva su scroll propio.
En móvil se abrió el detalle real de entrega 1 con reserva/inicio/recibo, se filtró
Agentes y se abrió la campaña 17 con las cuatro evaluaciones. Esto acredita esas
interacciones y tamaños, sin declarar auditoría completa de accesibilidad,
dispositivos físicos o todas las vistas. La aceptación UI compuesta sigue abierta.

El original exacto de revisión 10 cargó y se inspeccionó visualmente dentro de
la sesión owner: vídeo 1080×1920, duración 6 segundos, readyState 4, pausado y
sin error. El hash mostrado coincide con el evaluado. Es vista previa privada
de galería; no sustituye el ticket temporal para el proveedor. No se afirmó
reproducción completa. Se restauraron tema oscuro y viewport de escritorio.

La agenda conserva un límite de copy observado: el mensaje genérico de nueva
revisión también aparece junto a retenciones temporales de frecuencia, aunque el
claim reevalúa esos guards en horario. No usar ese texto para forzar revisiones
alternativas o borrar historia. El ajuste de copy y la prueba final por formato
siguen pendientes; el timer de servidor permanece deshabilitado.

## Corrección de retenciones y despliegue: 13 de octubre

El límite de copy del corte anterior quedó corregido en
`c50e820c5681fe1b8126f4550aee296e7cc55abe`. Las retenciones compuestas sólo por
frecuencia/cuota explican que los límites se comprobarán antes del envío y que
se conserva la misma pieza. Las retenciones de requisitos, mixtas o sin razón
conservan la indicación de revisión del requisito. Una entrega expirada ya no
muestra simultáneamente la instrucción genérica de retención. No cambia el
claim, la política, los permisos, el ledger ni las acciones de cancelación.

La regresión reprodujo cinco fallos antes del cambio; después pasaron 13 tests
del calendario, la suite frontend completa de 47 tests y el build TypeScript/Vite.
El procedimiento privado de release pasó 17 pruebas aisladas de deriva,
ACK perdido, journals, recuperación sin repetir escritura y sondas de SPA.
La revisión independiente no dejó hallazgos Critical/Important. Estos mocks
no acreditan publicación en proveedores ni restauración real de la base.

Cloud Run sirve `eikon-hold-copy-20261013` con el 100 % del tráfico y digest
`sha256:ba6927495a29fdc346636bf02b9358e184c741d17cd7186e5e0c753b711fd2a5`.
La imagen hereda la base fijada del corte de media y sustituye sólo
`frontend/dist`: hash del backend y Config de imagen iguales, configuración
de ejecución e IAM conservados. El respaldo privado conserva dump de 308062
bytes, SHA256 `b70ffbd76646bf7e312a2817367b8587da250a033ce9e43928ed08609e130005`,
con `restore_verified=false`.

Se creó una única candidata con 0 % del tráfico y se mantuvo la revisión
anterior al 100 %. Dos comprobaciones detuvieron la calificación: metadata de
procedencia añadida por gcloud y comparación de la landing pública con el
index de la SPA. Se corrigió el operador para admitir sólo la pareja observada
`gcloud/570.0.0` y comprobar el index en `/publications`. Los journals y paradas
se conservaron; la reconciliación fue de sólo lectura y no repitió la creación
de la candidata. La promoción usó la revisión nombrada y retiró el tag.

Las sondas reales de candidata y producción confirmaron salud 200, landing
200, SHA256 exacto de `/publications` y del bundle principal, y rechazo 403 al
worker anónimo. La sesión owner humanizar en Brave mostró diez entregas,
las seis retenciones temporales con el texto nuevo y la entrega expirada sin
el párrafo contradictorio. Se inspeccionó el texto en escritorio y viewport
390×844 con temas oscuro/claro; ancho de documento 375 px con scrollbar, sin
desbordamiento del contenido. Tema oscuro y viewport normal restaurados.
Capturas `eikon-retencion-temporal-corregida.png`,
`eikon-retencion-temporal-movil-oscuro.png` y
`eikon-retencion-temporal-movil-claro.png` en el directorio de evidencia del día.

TikTok Developers se comprobó de nuevo en Brave: la lista muestra la app
Humanizar Publicaciones, pero su configuración conserva `Network Error`.
La captura `tiktok-developers-error-actual.png` acredita ese bloqueo actual;
no se solicitaron nuevos permisos ni se repitieron las programaciones nativas.
La automatización oficial existente sigue ACTIVE, mismo chat y horario 21:45,
actualizada con la revisión productiva y los límites pendientes.

La consulta SSH final conserva timer 17 disabled/inactive y servicio inactive.
Este release produjo cero POST de publicación. Descarga/revocación real de
media, primer recibo visible de Instagram, formatos por separado, segundo
barrido posterior sin POST y recurrencia de todos los destinos siguen siendo
gates abiertos de Task10. La corrección UI no habilita el timer ni cierra la meta.

## Restauración real de DB y conservación de guards: 13 de octubre, 07:26 UTC

Se restauró el dump privado del corte anterior en PostgreSQL local aislado:
308062 bytes, SHA256
`b70ffbd76646bf7e312a2817367b8587da250a033ce9e43928ed08609e130005`.
El archivo indica origen PostgreSQL 17.9; el clon utilizó la imagen fijada
`postgres@sha256:2d2b8998d31037bf721cfdf764d76ba74171b4fab3431b7f72c27c56ddbdf9e3`.
Sin red, puertos ni credenciales productivas montadas; sólo recibió el dump de
sólo lectura y una credencial nueva del clon. Se ejecutó `init_db` directamente,
sin crear la aplicación ni iniciar workers o adaptadores.

Las 42 tablas conservaron filas y hashes, definiciones de esquema, secuencias
y estados de entregas tras dos inicializaciones con la imagen productiva
`ba6927495a29fdc346636bf02b9358e184c741d17cd7186e5e0c753b711fd2a5`.
Una inicialización adicional de la imagen anterior
`9c52cbaf64865c3e10f39c63250bca0753926a2cc2010aa7f862b8d025863264`
conservó lo mismo. Este ensayo de rollback cubre esas dos versiones de frontend
con backend idéntico; no acredita un downgrade de esquema o código antiguo.
Los triggers de historial, guardas de medios y revisiones rechazaron UPDATE
con sus errores inmutables antes y después de las inicializaciones.

Hash agregado de datos:
`298a34001dedbc388482e09e1d0ec3dca6adc236d58f42e7f10790772e63caf9`;
hash agregado de esquema/secuencias:
`8f8853aae0fca264bb49f0bdbe53b0be51055caa787f1953b1e545712f5934ff`.
Los recibos y snapshots con hashes por tabla permanecen privados, fuera de Git.
Los once contenedores propios y el directorio de datos del clon quedaron
eliminados, comprobados por nombre y por inventario de su etiqueta.

Se conservan dos intentos fallidos anteriores. El primero arrancó PostgreSQL,
pero su comprobación de disponibilidad omitía usuario/base y la comprobación
de ausencia no admitía el mensaje de Docker en minúsculas. Se concilió la
eliminación y se corrigieron ambas comprobaciones. El segundo restauró el dump,
pero el UID local no podía importar el directorio de publicaciones 0750,
propiedad de 1001:1001. Una prueba real de importación, sin DSN ni mounts,
confirmó la causa y la solución: grupo 1001 sólo para el cliente de aplicación,
manteniendo UID no root y sistema de archivos de sólo lectura. Cada nuevo
intento tuvo prefijo/journal propio, sin borrar negativos ni reintentar el anterior.

El operador pasó 18 tests aislados de cleanup, ownership, timeout/ACK perdido,
inspección ambigua, diferencias de datos/esquema y argumentos de los clientes.
La revisión independiente de las fuentes no dejó Critical/Important pendientes;
esa revisión estática se distingue del recibo real exitoso del tercer intento.

`restore_database_verified=true` acredita sólo esta restauración de DB.
`worker_outbox_restore_verified=false`, `storage_originals_restore_verified=false`
y `compound_runtime_gate_complete=false` se conservan. El recibo original del
backup no se reescribe: su `restore_verified=false` era el estado al tomarlo.
No hubo mutación productiva ni POST a proveedores. Timer 17 disabled/inactive
y servicio inactive comprobados por SSH. La aceptación completa y la meta
continúan pendientes de recuperación de archivos/outbox y pruebas por canal.


## Respaldo privado de server2 y restauración real de outbox: 13 de octubre, 16:28 UTC

La contraseña suministrada mediante la ventana enmascarada se utilizó sólo por
stdin de SSH/sudo para exportar el respaldo autorizado; no se guardó. El corte
real de las 16:19:27 UTC contiene la cola SQLite, fuentes Python desplegadas,
requisitos y cinco archivos fijos de configuración privada. El archivo de
286720 bytes y su manifiesto de 26 entradas permanecen fuera de Git. SHA256:
`92ab2b5fd9002338c1c4d5d57facd5aa85b51ad8d650a09d46433aabf58831b8`.

Bajo el lock original y con servicio/timer detenidos, se copiaron DB y WAL a un
directorio privado. SQLite sólo abrió esa copia: nunca la cola productiva,
ni se copió su SHM. El hash de los archivos originales DB/WAL/SHM permaneció
igual antes/después; la copia pasó integrity_check y tenía cero intentos en
curso. El exportador pasó 26 pruebas aisladas y revisión independiente de fuente.

La restauración de las 16:28:29 UTC extrajo únicamente cola y código a otro
clon privado. Los cinco módulos necesarios coincidieron por SHA256 con el
repositorio. El cliente usó la imagen productiva fijada `ba692749...`, UID no root,
red desactivada y raíz de sólo lectura, sin configuración ni tokens
montados y sin ejecutar clientes de proveedor. Las seis tablas y su esquema quedaron idénticos después
de dos inicializaciones con el código exacto exportado. Las guardas de manifest
pre-dispatch y acknowledgement rechazaron UPDATE y DELETE; la cuarentena
rechazó la reapertura. Dos reservas del mismo intento terminado devolvieron
False, sin añadir intentos ni fases.

Hash agregado de datos de la cola:
`5baea7aa418e71a669071de4c76bb18032ac4b5ff664e5626fbf85ccc9f1d257`;
hash agregado de esquema:
`57ead8f8eb49cd302849b261c42b59e041f103f674046e6820412b3249712d3c`.
El único contenedor y el directorio del clon quedaron eliminados; se verificó
la ausencia por nombre y etiqueta. El operador pasó 16 tests sintéticos de
extracción, errores de cola/guardas y duplicados; la revisión estática aprobó
la fuente antes del intento real. Estos tests se distinguen del recibo real.

`worker_outbox_restore_verified=true` acredita esta cola con su código exacto.
`config_backup_only_verified=true` no acredita arrancar su configuración.
La imagen de comprobación usa Python 3.12; server2 usa Python 3.14.4, cuya venv
no se incluyó en el respaldo ni se reprodujo. El recibo conserva falsos los
gates de venv, storage original y recuperación compuesta. La comprobación del
timer incluida en el recibo se atribuye a la hora de exportación. Una consulta
SSH posterior confirmó timer 17 disabled/inactive y servicio inactive. Esta
operación produjo cero POST de proveedor y no habilita la publicación diaria.


## Respaldo actual de storage y lectura de originales restaurados: 13 de octubre, 16:41 UTC

Se respaldaron los 3009 objetos actuales del almacén usado por la revisión
servida `eikon-hold-copy-20261013`: 1130853543 bytes. Las 3003 copias anteriores
se reutilizaron únicamente después de cotejar tamaño y MD5 con sus metadatos
remotos actuales; los seis objetos nuevos se descargaron por generación fijada.
El inventario paginado completo de nombres, generaciones, metageneraciones,
tamaños y MD5 coincidió antes/después. Cada objeto se guardó con SHA256 propio
en el manifiesto privado; hash del manifiesto:
`12eb81a955870c4b04bcf06428c579d3de87513ab7a75596be453907e2ddbb89`.

La fuente fue la configuración inmutable de la revisión nombrada que recibe
100 % de tráfico sin tag, comprobado antes/después; no la plantilla deseada de
un despliegue pendiente. Su imagen observada
`c024d017ac1010cac1396e9552d239809e41bb192d291f68bacb8ef6569bd5af`
es el único manifiesto Linux/amd64 contenido en el índice OCI fijado
`ba6927495a29fdc346636bf02b9358e184c741d17cd7186e5e0c753b711fd2a5`.
Se comprobó el SHA de los bytes originales del índice y la pertenencia exacta
del hijo; el cliente de restauración usa ese índice. La política IAM consultada
no contenía miembros públicos; no se generaliza esta lectura a todas las ACL.

Se creó otra copia privada de los bytes y se montó de sólo lectura en un
contenedor sin red, credenciales ni configuración productiva. El backend real
LocalStorage de la imagen fijada leyó todos los archivos dos veces y cotejó
cada tamaño/SHA. Se rechazaron traversal, rutas absolutas y expansión de home;
se verificaron permisos, propietario e inventario local sin archivos extra.
Se conservaron los originales exactos previstos: JPEG Deméter SHA256
`99836aae9569ed692bc3605de70f2b4c2ad830c979e83693ba5922d08dc1ae80`
y MP4 silencioso de Agentes SHA256
`d395bd2a9cbd8b09066dd04e2138b32f3f596062f8e86e991d1a0faf5616590c`.
El único contenedor y los datos temporales del clon se eliminaron y verificaron;
el respaldo privado independiente permanece fuera de Git.

El operador pasó 35 tests aislados de metadatos, checksum, paginación, paths,
permisos, fuente de revisión y vínculo OCI. La revisión independiente cerró
un hallazgo sobre la plantilla deseada y aprobó el código antes del intento real.
El primer intento se detuvo antes de journal/backup/descarga porque comparaba
el digest del índice con el digest de plataforma de Cloud Run. Se investigó
la relación por lecturas, se conservaron los negativos y se utilizó un prefijo
nuevo para el intento calificado; no hubo mutación productiva.

`storage_originals_restore_verified=true` acredita el respaldo y la lectura de
bytes en un clon local. `cloud_storage_restore_verified=false` conserva fuera
el ensayo en otro bucket. `database_reference_coherence_verified=false` conserva
fuera la correspondencia de todas las referencias del dump con este corte de
archivos; los cortes DB/storage no se presentan como una instantánea atómica.
El entorno completo de server2 y el gate compuesto también siguen abiertos.
Estas operaciones produjeron cero POST de proveedor. No acreditan descarga
por Meta, revocación de URL, primera publicación Instagram ni ejecución diaria.

La automatización oficial existente se actualizó por la herramienta de la app
y permanece ACTIVE en el mismo chat y horario. Conserva las programaciones
nativas de X/TikTok sin reenvío y añade los tres puntos de recuperación, la
relación OCI verificada y los gates pendientes de runtime/coherencia entre cortes.
La actualización del heartbeat no activa el timer ni acredita publicaciones.

## Recuperación del intérprete y dependencias de server2: 13 de octubre, 17:11 UTC

El exportador de las 17:07:56 UTC conservó 1636 archivos y 115196033 bytes:
Python 3.14.4, biblioteca estándar, venv privado y cierre de bibliotecas dinámicas.
El TAR de 116797440 bytes tiene SHA256
`968b49d4a21c2b24284f8b56f59327c1b624cbb134a2dbe2106c54429d135cec`.
Se verificaron propietarios/permisos, tamaños y hashes antes de exportar; sin
sudo ni cambio del timer. El intento anterior se detuvo por el enlace de
`sitecustomize.py` al archivo del sistema y quedó conservado. El intento nuevo
admite sólo esa pareja exacta de rutas, revisada con negativos específicos.

La prueba real de las 17:11:48 UTC ejecutó el loader y el Python copiados, con
caché del loader desactivada, `PYTHONHOME` restaurado y `-S`. Se cotejaron las
13 dependencias, se ejercitaron Pydantic y el codec JPEG, y se importó el worker
sin ejecutar su main. Las 37 imágenes nativas mapeadas procedieron del runtime
restaurado; ninguna biblioteca del contenedor base sustituyó a las calificadas.

La cola exportada pasó nuevamente dos inicializaciones, las cinco guardas y
dos reservas duplicadas sin nuevos intentos/fases. Conservó los hashes de datos
`5baea7aa418e71a669071de4c76bb18032ac4b5ff664e5626fbf85ccc9f1d257`
y esquema `57ead8f8eb49cd302849b261c42b59e041f103f674046e6820412b3249712d3c`.
Contenedor sin red, rootfs y código/runtime de sólo lectura, usuario no root y
ningún archivo de credenciales montado; limpieza confirmada antes del recibo.

`runtime_venv_restore_verified=true` y `original_python_version_recreated=true`
actualizan las limitaciones de los cortes anteriores. Los hooks de personalización
no se ejecutaron y no se reprodujeron rutas/propietarios del sistema server2.
Las 33 pruebas del exportador y 14 del operador de restauración son comprobaciones
locales de contrato; la ejecución real anterior acredita el runtime. Cero POST.

## Configuración recuperada como bytes privados: 13 de octubre, 17:19 UTC

Los cinco archivos fijos de configuración/token/unidades/sudoers del TAR
calificado se copiaron a otro directorio privado. Dos lecturas comprobaron
tamaños, SHA, propietario local, archivos regulares de un enlace, modo 0600
y directorio 0700. Se eliminó la copia antes de emitir el recibo de las
17:19:55 UTC. El digest del conjunto de hashes es
`1a40cd949f0c6a179b9bc99c1ac80f7a6b206b326b61d5119153e8adaac2d9cb`.

`private_config_bytes_restore_verified=true` acredita bytes recuperables en un
clon privado; no ejecución del contenido, instalación en rutas del sistema,
restauración de UID/GID de server2 ni activación de systemd. Diez casos sintéticos
de rechazo/lectura pasaron; el recibo real conserva esa distinción. Ninguna
contraseña ni token se incluyó en Git, documentación o salida pública. Cero POST.

## Coherencia de referencias DB y storage: 13 de octubre, 17:20 UTC

Se restauró el mismo dump calificado en otro clon PostgreSQL sin red y se
montaron los bytes del respaldo de storage como sólo lectura. Una transacción
`READ ONLY` comprobó 17 versiones de logos, 46 originales de galería, sus
46 miniaturas, dos originales de vídeo y 291 variaciones legacy: 398 objetos
distintos. LocalStorage abrió cada referencia con tenant/clave exactos y
cotejó SHA/tamaño del manifiesto; originales y vídeos también coincidieron con
SHA/tamaño de la DB. El puntero de logo actual debía resolver a su versión.

Las 56 referencias a logos embebidos se limitaron al catálogo explícito
`assets/logos`, con archivo/ancestros sin enlaces, formato de imagen válido
y SHA igual al recurso independiente del repositorio. Código, configuración,
assets desconocidos o modificados y enlaces se rechazaron en pruebas negativas.
La revisión independiente cerró el hallazgo de lectura demasiado amplia antes
de ejecutar. Los 29 casos locales pasaron; no hubo ingests incompletos en este
corte y no se reinterpretan como referencias durables cuando los hay.

El conjunto de referencias dio SHA256
`7480c18d16ee53b18a8b08a03c545b60c77b82d7664843078d1898e568f47505`.
Antes y después se conservaron los mismos hashes de filas/esquema de las
42 tablas de la prueba DB anterior. Todos los contenedores propios y la copia
temporal se eliminaron. `database_reference_coherence_verified=true` actualiza
ese límite anterior; DB/storage siguen siendo cortes distintos, no una
instantánea atómica. No se restauró otro bucket ni se inició un proveedor.

Estos ensayos de recuperación no acreditan primera publicación de Instagram,
descarga/revocación de media por Meta, visibilidad nativa después del horario
ni segundo barrido sin POST. El timer permanece deshabilitado e inactivo.

## Recuperación de claves y conexiones: 13 de octubre, 17:32 UTC

La revisión productiva calificada usa nombres directos de Secret Manager,
versión 1, namespace del proyecto autorizado y ningún mapeo de aliases.
Las lecturas de las dos versiones OAuth/vault desde la cuenta explícita
coincidieron byte por byte con las copias privadas ya guardadas. Se conservaron
copias privadas exclusivas adicionales; ningún secreto apareció en la salida
pública del operador, argv, Git o este documento. La validación rechaza otro namespace, versión,
nombre o mapeo de alias; no infiere recursos por coincidencia de nombres.

Un nuevo clon sin red restauró el mismo dump y montó sólo los materiales
privados necesarios como lectura. El cargador real de Eikón abrió las cinco
configuraciones OAuth; AES-GCM descifró las tres conexiones de tenant 17 usando
AAD de empresa/conexión/key ID. El hash del token exportado de server2 coincidió
con grant worker 6, política 2, sin revocación y vigente en ese corte. La
transacción fue READ ONLY, las 42 tablas conservaron filas/esquema y todos los
contenedores/copia temporal se eliminaron antes del recibo de 17:32:24 UTC.

El primer intento falló antes de crear contenedores por una asunción incorrecta
del operador sobre el formato del catálogo OAuth. Se comprobó el bootstrap
real, se corrigió a lista de 1–5 entradas y se utilizó un prefijo nuevo; negativo
y journal previos conservados. Las 27 pruebas sintéticas pasaron, y la revisión
independiente aprobó el ajuste antes del ensayo real.

`connection_vault_recovery_verified=true` y
`worker_token_matches_restored_grant=true` acreditan recuperación del material
y sus bindings históricos. `provider_authentication_or_publication_verified=false`
conserva el límite: no se invocó ningún cliente oficial ni se probó OAuth remoto.
El gate compuesto y la aceptación diaria por proveedor siguen abiertos; estos
siete recibos parciales no activan el timer ni autorizan reintentos inciertos.

## Rollback de frontend y autoridad de rutas: 13 de octubre, 17:49 UTC

Un octavo ensayo restauró el dump calificado en otro PostgreSQL sin red ni
puertos. Se ejecutó la aplicación real de las imágenes exactas vigente
`sha256:ba6927495a29fdc346636bf02b9358e184c741d17cd7186e5e0c753b711fd2a5`
y anterior de frontend
`sha256:9c52cbaf64865c3e10f39c63250bca0753926a2cc2010aa7f862b8d025863264`.
Ambas conservaron el SHA del backend
`9f62652425de1969d245eb5bf84561908fc7ab1d44158c7d3a475a624646a10a`.
La selección del operador rechaza otros pares, orden inverso, tags o backend
distinto; no autoriza rollback de esquema, otro backend ni otro digest.

Cada imagen pasó la misma matriz de 43 respuestas reales ASGI, con controles
positivos de worker, sesión owner y lectura por scopes. Se rechazaron grants
revocados/expirados, política sustituida, owner degradado, empresa ajena,
HTTP sin TLS, cookie mezclada con bearer y ampliación de scopes hacia autoridad
owner. Un grant worker tampoco abrió rutas legacy, planner o reviewer. Las
mutaciones legacy de marca, identidad, selección, generación y lotes respetaron
los permisos correspondientes. Todas las respuestas tuvieron el status esperado.

Las credenciales fueron fixtures creadas exclusivamente en el clon: secreto
JWT aleatorio, hash temporal de grant 6 y dos API keys con IDs explícitos.
No se cargaron JWT, tokens de redes ni claves de vault productivos. No hubo
`dependency_overrides` ni entrada al lifespan; WorkerPool no arrancó. Los
fixtures se retiraron y se restituyeron grant/owner antes de comparar las
42 tablas, esquema, secuencias y estados con el corte original. Hash de filas
`298a34001dedbc388482e09e1d0ec3dca6adc236d58f42e7f10790772e63caf9`
y de esquema
`8f8853aae0fca264bb49f0bdbe53b0be51055caa787f1953b1e545712f5934ff`
intactos. Las guardas inmutables de history, media guards y revisions volvieron
a rechazar UPDATE en ambas imágenes. Todos los contenedores y el clon se
eliminaron antes del recibo de 17:49:22 UTC. Cero POST a proveedores.

Las 19 pruebas locales calificaron contratos de selección y estructura del
operador; las 86 respuestas ASGI anteriores constituyen el ensayo real. La
revisión independiente de fuentes aprobó ejecutar y cerrar este subgate sólo
para ese par con backend idéntico. `supported_rollback_routes_verified=true`
acredita esa reversión acotada. No se modificó tráfico productivo ni se probó
arranque completo con lifespan; `live_authentication_or_publication_verified=false`
y `compound_runtime_gate_complete=false` conservan el límite de aceptación.
La primera publicación visible de Instagram, descarga/revocación real de media,
segundo barrido sin POST y recurrencia por todos los destinos siguen pendientes.

## Corte de accesos y app TikTok, 13 de octubre, 18:06–18:16 UTC

Brave vuelve a cargar la configuración de la app `Humanizar Publicaciones`
(`7694252858519275528`). El bloqueo anterior `Network Error` dejó de reproducirse
en esta lectura. **Production continúa Draft, sin auditoría ni OAuth TikTok
completados.** En el formulario se prepararon nombre `Eikón`, descripción,
categoría Business, plataforma Web y URL del servicio. Save rechazó la operación
por seis requisitos: icono, Terms, Privacy, verificación de URL, explicación de
revisión y vídeo de demostración. No se acredita persistencia de esos cambios.

En ese mismo borrador se añadieron Login Kit y Content Posting API; no se
generaron claves nuevas, no se otorgó consentimiento OAuth y no se envió la app
a revisión. **Direct Post permanece desactivado** mientras se espera respuesta
del operador a la ampliación concreta `user.info.basic` + `video.publish`. El
scope `video.upload` que añadió automáticamente el formulario no se presenta
como permiso aprobado ni como configuración final. La captura de ese estado se
conservó fuera del repositorio y se mostró al operador.

Las fuentes oficiales de TikTok exigen sitio desarrollado accesible, condiciones
y privacidad visibles, permisos mínimos y una demostración real de Sandbox.
Para publicar por API con visibilidad pública es necesaria auditoría; la vía
sin auditar requiere cuenta privada y `SELF_ONLY`. Se conserva pública la cuenta
de Humanizar y su programación existente en Studio. Ni el borrador de la app ni
la programación nativa acreditan publicación pública por API.

Se revisaron las prácticas reales del código mediante un explorador read-only y
se preparó `EIKON-POLITICAS-BORRADOR-2026-10-13.md`. Revisión independiente técnica
y editorial: PASS como borrador, con tres precisiones incorporadas. No es una
validación jurídica ni una política publicada: faltan responsable/contacto,
conservación y procedimiento de atención de solicitudes. El diseño acotado de
las páginas públicas está presentado, a la espera de aprobación; no se modificó
código de producto ni se desplegaron textos legales.

Lectura actual de Instagram en Brave: sesión `humanizar.news`, controles de
Editar perfil y dos publicaciones anteriores visibles. No hubo nuevo envío ni
se dio por superado el fallo anterior de la API. Lectura autenticada de Eikón:
empresa `humanizar`, 17 campañas, diez entregas, dos recibos Facebook confirmados,
tres conexiones Meta con vigencia visible y TikTok/X sin conectar en Eikón.
Deméter conserva el 13 de octubre a las 22:00 Bogotá y Agentes el día 14 a las
22:00, con motivos de retención que se volverán a comprobar antes del envío.
No se adelantaron horarios, reiniciaron cuotas ni recrearon revisiones.

SSH de las 18:16 UTC confirmó servicio inactivo y timer disabled/inactive.
`sudo -n -l` permite iniciar únicamente el servicio 17 y activar/desactivar su
timer sin contraseña; la lectura de su cursor de journal también funcionó. No
se inició el servicio en esta comprobación. La prueba controlada nocturna puede
utilizar ese inicio autorizado, sin volver a solicitar sudo para reinstalar el
publicador o repetir el respaldo ya terminado. Un inicio futuro debe obtener su
propio InvocationID, resultado y recibos, y no hereda prueba de este acceso.

Este corte añade evidencia de acceso y requisitos de conexión; no nuevos recibos
de publicación. La prueba diaria y el timer siguen pendientes. Consultar
[App Review](https://developers.tiktok.com/docs/en/app-review-guidelines) y
[Content Sharing](https://developers.tiktok.com/docs/en/content-sharing-guidelines)
para los requisitos de proveedor consultados.

## Sondeo del token actual de Instagram, 13 de octubre, 18:43 UTC

Se verificó la credencial que usa la conexión 3, versión 2, de la empresa
Humanizar 17, leyendo su vault actual y la configuración exacta de la revisión
servida `eikon-hold-copy-20261013`. Se conservó la cuenta GCP autorizada y se
comprobaron las referencias de secretos versión 1 contra los respaldos privados.
La base de datos se abrió con `default_transaction_read_only=on`; tenant, owner,
conexión y vault se consultaron por empresa. La comparación antes/después confirmó
que conexión y vault no cambiaron.

El verificador real `OfficialOAuthClient.verify` utilizó Graph `v24.0` con un
transporte que permitía exclusivamente dos GET a `graph.instagram.com`, sin
seguir redirecciones ni renovar tokens. `/me` devolvió HTTP 200 y confirmó
`humanizar.news`, ID `17841434345672986`; `content_publishing_limit` también
devolvió HTTP 200: uso 0, total 100, duración 86400 segundos. Estos valores se
leyeron de la respuesta actual, sin fijar el límite en el sondeo. La evidencia
de scopes conserva la categoría `capability_probe` del cliente: **no es una
introspección completa de permisos ni prueba de publicación**.

El operador se revisó independientemente antes de ejecutar. La revisión detectó
una limpieza interrumpible y una lectura sin límite previo, ambas corregidas;
las 26 pruebas locales de sus guardas y cierres pasaron. Un primer intento se
retuvo antes del verificador por comparar el estado SQL con el texto de la UI
`connected`; se corrigió a `active`, que es el estado persistido por `oauth.py`.
Esa corrección no modificó datos ni permisos productivos y recibió revisión
independiente antes del único nuevo intento.

El recibo privado `instagram-readonly-live-20261013T184340-receipt.json`, modo
0600, conserva únicamente campos seleccionados. Se comprobó la terminación del
proxy propio y la ausencia de su directorio de sockets. Resultado: dos GET,
cero POST a proveedores, sin refresh, sin cambio de política, cola o calendario.
`new_api_publication_verified=false` permanece explícito. La publicación visible
de Instagram, descarga/revocación real de media, segundo barrido sin POST y
recurrencia por todos los destinos siguen pendientes; este sondeo no activa el
timer ni sustituye la prueba controlada de las 22:00 Bogotá.

## Sitio de Eikón verificado por TikTok, 13 de octubre, 19:28 UTC

TikTok Developers confirmó **«Your property has been verified»** para el prefijo
`https://eikon.humanizar.cloud/`; después lo mostró en **Verified properties**
del entorno Production de la app `7694252858519275528`. Se conservó una captura
del resultado. Esta comprobación acredita propiedad del sitio, no autorización
OAuth, aprobación de la aplicación ni publicación mediante API.

El archivo oficial de verificación antes devolvía el HTML de la SPA. Se corrigió
con una imagen derivada del digest productivo `ba692749...`, incorporando sólo
ese TXT de 68 bytes y un PNG RGBA 1024 × 1024 del SVG existente de Eikón. No se
rediseñó el logo ni se reconstruyó la aplicación. El manifiesto completo del
frontend quedó igual al anterior más esos dos archivos; Config, capas heredadas
y hash backend se comprobaron antes del ensayo y del despliegue.

La imagen final es
`us-central1-docker.pkg.dev/emergent-enterprises/eikon/eikon@sha256:5e9a0f6a9449e9f4388713566d5b10310bff0eda1cc7861d85b271bc191af30a`.
Su único descriptor Linux/amd64 se verificó contra los bytes y el digest del
registro: `sha256:c696e6b7c7e7b3b0215173f1ed18368dcfce538eef09a00b03d6d3f97af3a4ed`.
La revisión `eikon-tiktok-url-20261013` ejecuta ese descriptor, con 100 % del
tráfico y sin tags después de la promoción. Se verificaron configuración completa
e IAM del servicio sin cambios, salvo la imagen y el reparto autorizado.

El operador recibió revisión independiente y pasaron sus 13 pruebas sintéticas
de guardas, incluida la deriva de secretos, recursos y cuenta de servicio. En la
imagen real, un contenedor sin red, credenciales ni mounts privados produjo
siete respuestas ASGI: TXT, PNG, SPA y JavaScript con bytes exactos; política,
conexiones y readiness del worker rechazaron acceso anónimo con 401/403. Usó
SQLite y clave sintéticos, sin iniciar lifespan ni worker.

La primera calificación se retuvo al encontrar el descriptor resuelto de Cloud
Run; se verificó su unión exacta al índice y se revisó la corrección. El comando
de promoción se ejecutó; la validación de su resultado se retuvo porque devolvió
una lista JSON en vez del objeto esperado. En ambos casos se reconciliaron las
revisiones existentes mediante lecturas y GET; **no se repitieron las
mutaciones**. La reconciliación final comprobó TXT, PNG, SPA,
JavaScript y negativos anónimos en los tres orígenes públicos existentes: dominio,
Cloud Run y proxy Vercel. No se cambiaron DNS, dominio, facturación, permisos,
base de datos, grants, calendario ni timers.

Recibos privados en `tiktok-static-20261013-live1922`: build, ASGI aislado,
manifiestos del registro, unión index/descriptor, respaldo de servicio/IAM,
journals, calificación y promoción reconciliadas. Logs y recibos permanecen
privados; los directorios temporales de autenticación y construcción se
eliminaron. Las operaciones del ensayo no enviaron POST de publicaciones a
proveedores.

El icono está listo y disponible en `/eikon-app-icon-1024.png`, pero **su carga
en el formulario de TikTok no está confirmada**: el selector de archivos no
respondió a la extensión. La app permanece Draft y Direct Post desactivado.
Siguen pendientes políticas públicas con responsable/contacto confirmados,
callback, demostración del flujo real, consentimiento OAuth y revisión de TikTok.
Las colas nativas de X/TikTok y las ventanas del 13 y 14 de octubre no se
recrearon ni adelantaron. El timer 17 continúa retenido y la meta completa de
publicaciones recurrentes en todas las redes permanece abierta.

## Callback canónico de TikTok: ajuste desplegado, 13 de octubre, 20:08 UTC

Se reprodujo un rechazo interno que impedía iniciar TikTok desde el dominio
habitual: `ConnectionPanel` construye el callback con `window.location.origin`,
pero la configuración anterior sólo permitía el origen de Cloud Run. En la
imagen productiva, una fixture con SQLite, empresas y credenciales sintéticas
ejecutó siete comprobaciones del motor real: rechazo canónico con la lista
anterior, aceptación canónica con la nueva, conservación del callback anterior,
rechazo de dominio externo, HTTP, query añadida y conexión de otra empresa.
El contenedor fue read-only, sin red ni mounts privados y sin ejecutar lifespan;
el ensayo no completó rutas HTTP, cookies, intercambio de tokens ni OAuth real.

La configuración ahora conserva el callback de Cloud Run y añade únicamente
`https://eikon.humanizar.cloud/api/v1/publications/oauth/callback` a TikTok.
Las cinco entradas, identificadores, secretos, modos y demás valores quedaron
iguales al original. Se respaldaron en archivos privados el original, los bytes
de la versión 1 real, la candidata y las políticas/configuración existentes.
La igualdad original/versión 1 se comprobó byte a byte.

El procedimiento tuvo revisión independiente antes de las fases mutantes. La
revisión encontró y se corrigió una guarda incompleta de aliases de secretos:
ahora exige el proyecto `633619052458`, rechaza mappings no vacíos de secretos
en servicio/plantilla/revisión y restringe las versiones al proyecto autorizado.
Pasaron 33 comprobaciones sintéticas, incluidas las negativas del defecto.
El operador final tiene SHA-256
`04596eec11c257ceb944b42662210385f1a2c7c5e8dd343746896eb75bdeb3db`.

Se creó y verificó la versión **2 del mismo secreto**
`eikon-publication-oauth-config-v1`; no se creó otro secreto ni se modificó IAM.
La revisión `eikon-tiktok-callback-20261013` se calificó inicialmente con 0 %
y la anterior al 100 %. Tras comprobarla, se promovió la revisión existente
al 100 % y se retiró su tag. Conserva el índice `5e9a0f6a…` y descriptor
`c696e6b7…` del corte anterior; no se reconstruyó ni cambió la imagen.
La comparación completa del servicio permitió sólo esa versión del secretRef,
nombre de revisión, metadatos de cliente esperados y tráfico autorizado.
Se comprobaron secreto referenciado, revisión Ready, imagen, namespace, ausencia
de aliases y conservación de IAM y demás configuración. Los tres orígenes
públicos sirvieron TXT, PNG, SPA y JavaScript exactos y rechazaron acceso anónimo
al worker y campañas. Recibos/journals privados:
`tiktok-callback-20261013-live2000`. No se repitieron mutaciones.

En TikTok Developers se introdujo la misma URL canónica, pero Save respondió
«Please correct all errors before you save changes». Quedaron cinco requisitos
incompletos: icono, términos, privacidad, explicación y demo. **El guardado del
callback en TikTok sigue sin acreditarse**; app Draft, Direct Post desactivado,
sin consentimiento OAuth, revisión enviada ni publicación API nueva.

SSH volvió a confirmar servicio 17 inactive/dead y timer inactive/disabled.
No se iniciaron envíos ni se alteraron las colas nativas o ventanas del 13/14
de octubre. La prueba real de Instagram/media y segundo barrido sigue pendiente.
La aceptación histórica de recuperación no se extiende a esta nueva combinación
de revisión y configuración; el gate compuesto y la meta completa continúan
abiertos.

Una recarga autenticada del dominio canónico volvió a mostrar Humanizar,
17 campañas, 10 entregas, tres cuentas conectadas y política 2 vigente. Los dos
recibos anteriores de Facebook siguen visibles; esto no acredita un envío nuevo.

## Alta inicial de TikTok: defecto reproducido, 13 de octubre, 20:27 UTC

Una auditoría de sólo lectura encontró un bloqueo distinto del callback canónico:
la UI y `ConnectionInput` exigen un `remote_id` antes de OAuth; `OAuthStartInput`
exige una conexión existente y el motor fija ese ID como identidad esperada.
TikTok devuelve un `open_id`, que el transporte cruza entre token y `user/info`,
y el motor lo compara con el ID predeclarado. Un nombre de usuario no descubre ni
reemplaza ese identificador. Esta comprobación es necesaria para reconexiones,
pero el flujo carece de una modalidad de alta sin identidad previamente conocida.

Se preservó un probe con SQLite temporal, credenciales ficticias y transporte
HTTP simulado. Conexiones y DNS reales quedaron bloqueados. Resultados:

| Caso | Resultado local observado |
|---|---|
| Alta sin `remote_id` | 422 `invalid_connection` |
| Alta con ID vacío | 422 `invalid_destination` |
| Inicio OAuth sin `connection_id` | 422 `invalid_connection` |
| ID inicial `humanizar_systems`; token y perfil coinciden en `open-42` | `held / remote_identity_mismatch`; ID inicial conservado y vault ausente |
| Mismo flujo con `open-42` predeclarado | `active` y vault presente |

Pasaron 12 pruebas focales; siete variantes PostgreSQL se excluyeron expresamente.
Se preservó la salida original, sin repetir esa suite. El probe corto se volvió
a ejecutar sólo para capturar su salida: exit 0. El HEAD se capturó antes y
después de esa repetición, `543be0a8…`; no se había capturado al inicio de la
auditoría. Nueve hashes de fuentes verificaron y los archivos auditados quedaron
sin cambios. Artefactos públicos `0444` en `/tmp/eikon_tiktok_bootstrap_*20261013*`:
probe, recibo con comandos exactos, stdout y manifiestos. Revisión independiente:
PASS de la reproducción; HOLD del alta sin `open_id` conocido. No se modificó
código, esquema, portal OAuth ni autoridad productiva para resolverlo.

En Brave se preparó una explicación de 647 caracteres que diferencia Direct Post
implementado del flujo `video.upload` no implementado, y declara pendientes
activación, demo sandbox y auditoría. El formulario bajó de cinco a cuatro errores:
icono, términos, privacidad y demo. Ese texto permanece preparado; no acredita
Save satisfactorio ni envío de revisión. Direct Post sigue apagado. La guía
[oficial de TikTok](https://developers.tiktok.com/docs/en/content-sharing-guidelines)
exige control y consentimiento del creador por contenido; el acceso de cuenta no
lo sustituye. Sin auditoría, Direct Post tiene restricciones de visibilidad y de
cuentas. Las programaciones nativas existentes no acreditan esa aprobación API.

## Lectura real del planner mediante MCP, 13 de octubre, 20:33 UTC

La herramienta nativa de este chat sigue devolviendo `configuration_error` para
el planner. El launcher privado ya configurado carga los grants propios planner
4 y reviewer 5 de la empresa 17. Un cliente MCP nuevo, con ese launcher de hash
fijado, ejecutó exclusivamente `eikon_get_publication_inbox` y obtuvo una respuesta
satisfactoria. Se comprobaron antes/después la revisión canónica actual y tráfico
100 % sin tags, sin cambios. Recibos privados: `planner-mcp-readonly-20261013T203311Z`.

La lectura confirmó empresa 17, política 2 vigente, 17 campañas y tres destinos
Meta. Para el día local 13 de octubre, cada cuenta informó stock autorizado 0,
déficit 1 y capacidad diaria restante 1. Las revisiones 5/6/7 aparecen entre las
entregas retenidas con `frequency_limit` y `delivery_not_stock`. Este resultado no
demuestra por sí solo si el worker las recupera al vencer la frecuencia. La
revisión posterior del motor y su probe temporal confirmaron que `claim_due`
considera una fila `held` sin inicio y vuelve a comprobar los requisitos; cuando
desaparece la causa temporal, reserva la misma entrega con la misma decisión.
`delivery_not_stock` pertenece a la proyección de inbox y no es una razón del
despacho. No hace falta recrear las revisiones 5/6/7 ni repetir la evaluación IA.

El cliente no reparó la conexión nativa del chat, cambió grants ni despachó
publicaciones. La implementación de inbox usa GET. El cero POST del primer recibo
era una inferencia por alcance, no un contador de egress: se conservó el recibo y
la fuente ejecutada y se añadió `receipt-scope-clarification.json`; la fuente
futura etiqueta explícitamente la inferencia y `provider_egress_measured=false`.

## Recuperación de retenciones y colas nativas, 13 de octubre, 20:45 UTC

En SQLite temporal, una publicación anterior contaba para la frecuencia de
1440 minutos hasta `t0+10`. En `t0` y `t0+9`, `claim_due` no reservó y mantuvo
`frequency_limit`. En el límite exacto `t0+10`, la proyección interna de inbox siguió mostrando
stock 0 y `delivery_not_stock`, pero `claim_due` reservó la MISMA entrega: misma
decisión, `started_at=None` y evaluaciones 1→1. Probe exit 0, sin worker,
`start_attempt` ni red. Pasaron seis regresiones del servidor con conexiones y
DNS bloqueados; seis variantes PostgreSQL se excluyeron. No es una prueba del
despacho productivo, del timer ni de PostgreSQL. La revisión independiente fue
PASS, sin Critical ni Important; su Minor distinguió `_stock_projection` de un
GET HTTP en la frontera y se corrigió aquí. Los 14 artefactos de alta TikTok y
frecuencia se copiaron byte a byte a un directorio privado duradero, con hashes
verificados: `tiktok-bootstrap-and-held-evidence-20261013T204917Z`.

Los eventos duraderos `worker:prestart_hold`, intentos con `started_at`, ventanas
vencidas y guardias de medio no se recuperan por este mecanismo. Un intento
iniciado conserva consumo de frecuencia incluso después de `failed_before_dispatch`.
Las revisiones 5/6/7 podrán reservarse dentro de 22:00–23:00 Bogotá sólo si vence
la frecuencia respecto de todos los timestamps contados y pasan los demás
requisitos. La reserva no sustituye la autorización final de inicio ni acredita
un POST. El servicio productivo continúa pendiente de su prueba controlada.

Lectura de las pestañas existentes de Brave a las 20:45–20:46 UTC:

| Red | Programaciones visibles, sin modificaciones en este corte |
|---|---|
| X, vía gratuita de Brave | Deméter 13 oct 22:00, imagen; Agentes 14 oct 22:00, vídeo de seis segundos |
| TikTok Studio, `@humanizar.systems` | Deméter `7696012000295488775`, 13 oct 22:00; Agentes `7696024738354695425`, 14 oct 22:00 |

Cada cola tiene dos filas visibles; no se recrearon ni adelantaron. Capturas:
`x-scheduled-confirmed-20261013T2046.jpg` y
`tiktok-scheduled-confirmed-20261013T2046.jpg` en el directorio de visualizaciones
de este chat. La programación nativa no es aún prueba del envío al vencer la
hora ni de una recurrencia indefinida. Falta validar las publicaciones reales y
el siguiente barrido sin duplicados antes de declarar todas las redes operativas.

Una lectura por SSH de las unidades productivas a las 20:48 UTC confirmó
`eikon-publisher@17.service` inactivo y `eikon-publisher@17.timer` inactivo y
deshabilitado; no se arrancaron. La agenda autenticada conservó 17 campañas,
10 entregas y tres cuentas. Sus detalles históricos muestran, en hora Bogotá,
los inicios del 12 de octubre: Facebook entrega 1 a las 21:11:13, Facebook
entrega 2 a las 21:11:28 e Instagram entrega 4 a las 21:22:24. Esa última cerró
como `failed_before_dispatch` a las 22:23:30 sin borrar su consumo ni su guardia
de medio. Son eventos históricos de la UI, no evidencia de un envío en este corte.

## Corrección del alta TikTok aprobada, 13 de octubre

El usuario aprobó implementar el alta sin conocer `open_id`. Los commits
`3536c8a` y `c2e80cf` incorporan el formulario y el motor. El nuevo endpoint
`POST /api/v1/publications/oauth/onboarding/start` acepta plataforma, modo,
proyectos y callback; no acepta identidad predeclarada ni crea una conexión
provisional. La tabla aditiva `publication_oauth_onboarding_states` liga el
intento a empresa, owner, sesión, configuración y proyectos durante diez minutos.
El callback consume el intento una sola vez antes del exchange, cruza la
identidad de token y perfil y revalida autoridad, proyectos y caducidad bajo
lock antes de guardar conexión y vault juntos. Una conexión existente conserva
la identidad original y el vault ante un alta duplicada. Las reconexiones siguen
exigiendo el ID original.

| Verificación | Evidencia observada |
|---|---|
| Backend focal, SQLite y PostgreSQL | 202 PASS, sin skips; Ruff y mypy pertinentes PASS |
| Interfaz completa configurada | 71 PASS en nueve archivos; 24 casos focales; TypeScript PASS |
| Suite Python completa, PostgreSQL efímero | 2090 PASS, dos skips, exit 0, 529,15 segundos |
| Build de interfaz | PASS; JavaScript principal `index-jvW_EF4d.js` |
| Revisiones independientes | PASS servidor, interfaz, rango integrado y prerrequisitos de imagen |

Los dos skips corresponden exclusivamente a `tests/test_ranking_isotype_penalty.py`,
por falta del output demo. No son exclusiones de PostgreSQL. El primer intento
de suite completa se conserva: tres FAIL, 1503 PASS, dos skips y 585 errores al
agotarse el tmpfs de 512 MiB del PostgreSQL efímero (`DiskFull` y después
`ConnectionRefused`). Se repitió con un contenedor propio nuevo de 4 GiB; no se
relajaron assertions. Los transportes remotos usan fixtures; estas pruebas no
acreditan un consentimiento ni una publicación ante TikTok.

La receta general de Docker actualizaba dos dependencias sin necesidad del
cambio. Se descartó esa imagen y se heredó el digest productivo `5e9a0f6a…`,
copiando el servidor y frontend revisados. Se incluyeron tres prerrequisitos
versionados que aún faltaban en producción: extracción pura del normalizador
de resultados y método aditivo de renovación de Instagram sin caller productivo
automático. Una revisión nueva comprobó equivalencia por AST de la extracción.
La atestación de root comprobó 258 archivos públicos de runtime contra `c2e80cf`,
frontend contra el build, assets exactos y `pip freeze` idéntico al base. La
configuración de contenedor sólo admite actualizar el label de revisión fuente.
Índice candidato `4c0fb683…`; backend SHA256 `f6dc9e36…`.

El respaldo privado fresco de las 21:10 UTC tiene SHA256
`c5a9cab52fce5442ab90d0b047e4bc92700a46f57f434e1ff266dd778fd5ce41`.
La calificación y promoción se documentan por separado después de sus recibos
reales. El consentimiento OAuth, la configuración del portal TikTok, la
aceptación por canal y la recurrencia completa siguen pendientes.

## Alta TikTok entregada y comprobada en Brave, 13 de octubre, 21:52 UTC

La imagen final se subió una sola vez y el registro confirmó índice local/remoto
idéntico `sha256:4c0fb68338c29f9ea600fa8abb915438be8d67d2d0644ed7cb5cd848ba398deb`
y descriptor Linux amd64
`sha256:1b68d779db1667932ea19873bb5e7a5850a258be31ab707370abed1982624109`.
El clon privado sin red ni puertos restauró el respaldo fresco y ensayó esa
imagen inmutable: 42→43 tablas; dos inicializaciones actuales y una anterior
explícita conservaron filas, esquema y secuencias existentes. Las guardas
rechazaron modificaciones. El callback anterior respondió 403 a un intento nuevo,
sin consumirlo ni iniciar worker/proveedor. El recibo `migration-qualified-v2.json`
liga commit, índice, backend, manifiesto y dump; el recibo preliminar permanece
histórico. Los tres contenedores propios y su volumen de socket se eliminaron.

La revisión `eikon-tiktok-onboarding-20261013` se calificó sin tráfico y después
recibió 100 %. IAM, recursos, referencias a secretos y demás configuración
permanecieron iguales; OAuth conserva la versión 2 del mismo secreto. La
primera promoción terminó como HOLD: el comando de tráfico ejecutó con éxito,
pero su salida JSON no era un objeto y el operador la trataba como observación.
Se concilió por lectura y se confirmó 100 %, sin repetir la mutación. La nueva
corrección separa éxito de mutación de observaciones estrictas. Otra revisión
independiente y 70 pruebas ficticias comprobaron conciliación, rechazo de tráfico
0 %, contratos reales del cliente, limpieza y ausencia de repetición.

El operador final, SHA256
`b72bfbebd9e8be64f9c369ceb85f30f01896a0065db91f3522899c990e80ad85`,
concilió de nuevo sólo por lectura. Después de verificar bindings, gates,
revisión/digest, tráfico, IAM/runtime y HTTP creó `promoted.json` exclusivo.
TXT, PNG, SPA y JavaScript fueron exactos en dominio canónico, Cloud Run y proxy
Vercel; el alta anónima fue rechazada en los tres. `provider_posts:0` describe
las acciones de este operador, no un contador global de proveedores.

Brave mostró temporalmente `ERR_NETWORK_CHANGED`. La sesión y overview del
servidor respondían 200; al volver a la agenda canónica en una pestaña nueva
se recuperó la carga, sin cambiar credenciales ni protecciones. Humanizar
conservó 17 campañas, 10 entregas, tres cuentas Meta y política 2 vigente.
En Cuentas → Añadir cuenta → TikTok se comprobó la desaparición del campo ID
remoto, modo `oauth2` y texto de identificación durante autorización. No se
envió el formulario ni se concedieron permisos remotos. Captura de viewport:
`eikon-tiktok-onboarding-completo-20261013.jpg` en las visualizaciones del chat;
la captura de página completa no respondió y se conservó la alternativa visible.

SSH a las 21:41 UTC volvió a confirmar service 17 inactive/dead, sin InvocationID,
y timer disabled/inactive, sin próxima ejecución. Las ventanas y filas existentes
Deméter 5/6/7 y Agentes 8/9/10 se conservaron; ninguna cola nativa se modificó.
El portal TikTok aún requiere icono, términos, privacidad y demo, además del
guardado/configuración, consentimiento y auditoría pertinentes. El nuevo flujo
de alta está entregado; la conexión TikTok real y la meta de publicaciones
recurrentes en todas las redes permanecen abiertas. Los ocho ensayos históricos
de recuperación no se extienden automáticamente a esta imagen/backend nuevos.

### Continuidad del 15 de octubre y prueba real del inicio OAuth de TikTok

Corte del 13 de octubre, 22:22 UTC. Se consultaron los 17 proyectos y la
bandeja del planner mediante su cliente MCP scoped, sin recargar la conexión
global ni cambiar grants. La herramienta nativa de bandeja seguía devolviendo
`configuration_error`; el cliente stdio configurado devolvió la política 2 y
las tres cuentas Meta. Se preservaron Deméter 5/6/7 y Agentes 8/9/10.

La pieza propia de Xenía media 34 se exportó a JPEG para transporte, sin
recortar ni cambiar su diseño. Encargo 48, media 48, identidad versión 4,
1080×1350, 149238 bytes, SHA256
`cf954028cfee154de0c1cc519ad0de8d70d48a1ee49f25b26d1aaaed1364a325`.
La ilustración sigue siendo de Codex; el logo SVG original se conserva.
La fuente pública `https://humanizar.tech/` respondió 200, con HTML SHA256
`a7860e20b74da1daf8cdb5ec99c756442c7fc0b790ecd8a6079f5ace0d035aa5`.
El texto se limita a CRM para PYME, contactos, oportunidades y actividad,
sin cifras privadas, tecnologías ni promesas universales.

El Codex principal recibió por MCP los contratos, JPEG exacto y render del
logo y evaluó los seis checks. Las evaluaciones y decisiones 12/13/14 fueron
`approve`, correlacionadas con contratos distintos por destino. Estos recibos
son declaraciones del cliente (`client_reported`), no una atestación
criptográfica ni una prueba de publicación. Se crearon las entregas 11/12/13
para Facebook Systems, Facebook Humanizar e Instagram humanizar.news,
respectivamente. Su ventana es 15-oct-2026 22:00–23:00 Bogotá
(`due_at=1792119600`, `expires_at=1792123200`). Las filas quedaron `held` por
`frequency_limit`, sin intento ni `started_at`; corresponde reclamar las mismas
filas cuando se despeje el límite, conservando su horario y sin recrearlas.

Brave confirmó en la cola nativa de X una única nueva pieza de Xenía para
15-oct-2026 22:00, con JPEG y texto alternativo que declara ilustración de IA.
El menú de imágenes requiere elegir «Upload» después de abrir «Add media»;
abrir el menú por sí solo no produce un selector. Los clics semánticos de
programación no cambiaron el estado: se comprobaron pantalla y cola antes
de usar el botón visible. La cola remota confirmó tres elementos, uno por
día 13/14/15, evitando reenviar ante un resultado incierto.

TikTok Studio aceptó un clip propio de seis segundos de la pieza de Xenía,
H.264, yuv420p, 1080×1920, 30 fps, sin audio ni recorte, SHA256
`c9b0dc9b530f983c0077cf0fb1ef311e58246f254f4cf80d630d2e87a0ab37cb`.
Se inspeccionaron fotogramas a 0/3/5,9 segundos; `full_video_watched=false`.
La muestra inicial en Studio indicaba duración cero y no había un elemento
DOM video, por lo que no se afirma reproducción completa. Tras el envío,
la cola confirmó duración 00:06, cuenta `humanizar.systems`, acceso público
y fecha 15-oct 22:00, ID `7696281237262224661`. Antes del envío se comprobaron
etiqueta IA, «Tu marca» activada, marca de terceros desactivada, sin ubicación
seleccionada ni música añadida. Los IDs nativos de Deméter y Agentes quedaron
intactos. Son tres programaciones futuras por red; todavía no prueban una
recurrencia ilimitada ni la visibilidad de las publicaciones cuando sean debidas.

El formulario nuevo de Eikón se envió una vez para iniciar OAuth de TikTok
con los 17 proyectos reales de Humanizar, sin introducir `open_id`. Llegó
al proveedor con `user.info.basic,video.publish` y callback canónico, pero
TikTok devolvió `unauthorized_client`, tipo `client_key`, antes del
consentimiento. La clave pública coincide con la de la app
`7694252858519275528`; se volvió a ocultar y no se mostró el secreto.
No se guardaron tokens ni se creó una conexión. La app permanece Draft,
con Direct Post apagado y cuatro requisitos pendientes: icono, términos,
privacidad y demo. El estado incompleto es una causa probable que se debe
comprobar; el rechazo por sí solo no demuestra una causa específica.

SSH a las 22:22 UTC confirmó service 17 inactive/dead, sin InvocationID,
ExecMainStatus 0, y timer inactive/dead/disabled sin próxima ejecución.
No se inició el worker ni se habilitó el timer. La verificación real de
esta noche, los recibos remotos/media, la revocación y la segunda ejecución
con cero POST siguen pendientes; tampoco se extiende la prueba histórica
de recuperación al backend actual. La meta completa continúa abierta.

Recibo privado: `xenia-continuity-20261013T2225-receipt.json`, SHA256
`45d23ba27532bc291611e3e72c4252d63fb9ffac73e40b88fa04a1856ead46ee`.
Capturas en visualizaciones de este chat:
`x-publicaciones-13-14-15oct-20261013.jpg`,
`tiktok-publicaciones-13-14-15oct-20261013.jpg` y
`tiktok-oauth-client-error-20261013.jpg`.

La vista autenticada de Eikón volvió a cargar tras una única actualización:
17 campañas, 13 entregas, tres cuentas Meta y política 2. La captura
`eikon-envios-15oct-20261013.jpg` muestra las tres filas del 15 de octubre
retenidas por frecuencia, con su horario original. Una revisión independiente
de solo lectura recalculó los hashes de las tres solicitudes y resultados MCP,
confirmó la correlación revisión/decisión 12/13/14 → entrega 11/12/13 y verificó
que `claim_due` reevalúa la misma fila cuando sea debida sin modificar su
ventana. El paso del tiempo por sí solo no ejecuta el worker. Resultado:
PASS de correlación y fechas; HOLD de publicación autónoma y recuperación
del backend actual. Informe local `eikon-xenia-continuity-review-20261013.md`,
SHA256 `e7194b5aadce5950238839130652bf70d1423dec3ea03c2868ba6cb7cdf1418e`.

### Recuperación de DB y arranque de la imagen actual; carga del icono TikTok

Corte del 13 de octubre, 23:08 UTC. Se tomó un respaldo nuevo de la revisión
servida `eikon-tiktok-onboarding-20261013`: índice `4c0fb683…`, hijo AMD64
`1b68d779…` y backend `f6dc9e36…`. Antes y después se comprobaron tráfico
100 % sin tags, configuración e IAM. La configuración de DB se obtuvo de
la revisión inmutable y de la instancia Cloud SQL exacta, no de una plantilla
pendiente. Dump de 318012 bytes, SHA256
`e01a46f0c0ae59446e74be27bf4fe6440a08dee00d3f93e23c274906547ea49d`;
proxy, socket y cliente del dump quedaron eliminados. No se mutó producción.

La restauración final usó una copia privada de ese dump con hash idéntico,
sin volver a consultar la DB productiva. PostgreSQL y su cliente usan el UID
local 1000; los clientes de aplicación usan el usuario real de la imagen,
1001:1001. Esto permite leer sus archivos 0600 sin cambiar sus permisos.
El socket compartido admite únicamente al grupo local; el directorio padre
permanece 0700. El inspector distingue los clientes registrados y comprueba
imagen, usuario, label de propiedad, red desactivada, ausencia de puertos,
rootfs de lectura, capacidades retiradas y prohibición de nuevos privilegios.

Resultado real, exit 0 a las 23:07:56 UTC:

- 43 tablas restauradas, incluida `publication_oauth_onboarding_states`.
- Dos llamadas explícitas a init, además de las inicializaciones habituales
  de la aplicación; filas, esquema, secuencias y estados de entregas intactos.
- Las tres guardas de historia, medios y revisiones rechazaron UPDATE.
- Las 43 respuestas ASGI de autoridad correspondieron a lo esperado, usando
  las dependencias reales y retirando las credenciales ficticias del clon.
- Entrada y salida reales del lifespan: WorkerPool de galería iniciado,
  lectura DB con cero batches pendientes y tareas/executor cerrados al salir.
- Los 10 contenedores registrados y los datos temporales quedaron eliminados.

El proceso de galería no es el publicador social. Este ensayo no verifica
autenticación ante proveedores, una publicación, coherencia con GCS ni rollback
al backend anterior. Los ocho ensayos históricos se conservan con su alcance;
`compound_runtime_gate_complete=false` y `publication_acceptance=false` siguen
siendo obligatorios. El operador no realizó POST a proveedores; este cero
describe sus acciones y no un contador global de producción.

Se conservaron las intenciones fallidas y su diagnóstico: comparación literal
de índice/hijo, socket de 130 bytes frente al límite de 107 y cliente de prueba
sin permiso para leer archivos de la imagen. Cada ajuste tuvo revisión
independiente antes de una nueva intención; no se repitieron las anteriores.
Las 42 guardas finales pasaron. Fuente final del operador, SHA256
`8ef5c916f89213244c8536d168670647ac0c59e81778238644fbe09887b11012`;
revisión de fuentes v5, SHA256
`4314c2b9b9fc33e0b87eaa03333a051c37968384a96a4d5cccfd499555ead561`.
Recibo privado `current-backend-recovery-receipt.json`, bajo
`current-backend-recovery-20261013T230741Z-application-user`, SHA256
`5fa596ceeeb3456388e3d79c1b1278b107f66c14bc5ccd2cc5837c6c3039f73e`.

La revisión independiente del agregado y los recibos confirmó sus hashes,
bindings, comparación y límites: PASS acotado de recuperación DB/autoridad/
arranque. No repitió el ensayo ni accedió a dumps, snapshots privados o
proveedores. Informe `eikon-current-backend-recovery-evidence-review-20261013.md`,
SHA256 `2391177bf7c376f2912ff07171685c47373c71065b46199a98018844d27cace6`.

El selector nativo del icono TikTok sí respondió: seleccionó el PNG propio
1024×1024 y mostró la carga, pero el proveedor terminó con «Failed to upload».
Hubo un intento nuevo, sin reintento, guardado de formulario ni envío a revisión.
La causa específica no quedó demostrada. Recibo privado
`tiktok-icon-upload-attempt-20261013T2247-receipt.json`, SHA256
`42f81de127e04f943323aca28e2cfbafd1d9d98992353a3fdf509bf0601628eb`;
captura `tiktok-icon-upload-failed-20261013T2250.jpg`. El logo de la app aún
no está confirmado y los requisitos de privacidad, términos y demo continúan.

La consulta SSH posterior confirmó servicio 17 inactive/dead, sin InvocationID,
y timer inactive/dead/disabled, sin próxima ejecución. No se recrearon ni
adelantaron Deméter 5/6/7, Agentes 8/9/10, Xenía 11/12/13 o las programaciones
nativas de 13/14/15 de octubre. La prueba debida de las 22:00–23:00 Bogotá,
sus recibos remotos/media/revocación, el segundo barrido con cero POST y la
revisión previa a activar el timer permanecen pendientes. La meta de todas las
redes continúa ACTIVE e incompleta.

### Cotejo incremental de medios de Humanizar con el dump actual

Corte del 13 de octubre, 23:46 UTC. El dump actual ya calificado
`e01a46f0…` se restauró nuevamente sólo para extraer sus referencias y cotejar
los archivos de Humanizar, tenant 17. No se repitieron init, ASGI o lifespan,
ni se consultó otra vez la DB productiva. Imagen índice `4c0fb683…`, hijo
AMD64 `1b68d779…` y backend `f6dc9e36…` coinciden con la revisión servida
`eikon-tiktok-onboarding-20261013`.

El respaldo histórico de storage precedía a la incorporación de Xenía48.
Se consultaron mediante GET únicamente los metadatos GCS de las referencias
actuales de Humanizar. Cada archivo reutilizado se revalidó contra tamaño y
MD5 remoto y contra SHA/tamaño de DB cuando existían; las dos descargas nuevas
fijaron generación y precondición. El conjunto referido conservó generación,
metageneración, tamaño y MD5 entre los dos cortes. Configuración servida e IAM
privado del bucket permanecieron iguales.

Resultado real, exit 0:

- 116 objetos y 90991870 bytes: 17 logos versionados, 46 originales,
  46 miniaturas, dos vídeos y cinco variaciones legacy.
- 114 archivos históricos revalidados y dos descargados: exactamente el
  original de Xenía48, SHA256 `cf954028…`, y su miniatura asociada en DB.
- Lectura y cotejo mediante LocalStorage de la imagen actual, usuario
  1001:1001, red desactivada y copia en tmpfs privada recibida por stdin.
- Ambas lecturas de referencias usaron transacciones READ ONLY. Las filas,
  esquema, secuencias y estados de las 43 tablas del clon quedaron intactos.
- Los seis contenedores registrados y el directorio de datos quedaron
  eliminados; no se leyeron medios de otras empresas.

El respaldo es un subconjunto completo de las referencias durables del tenant
17 en ese dump. No restaura objetos en GCS, no forma una instantánea atómica
DB/storage y no acredita recuperación compuesta o publicación. El cero POST
describe este operador y la lectura MCP siguiente, no el tráfico global.
La aceptación de todas las redes continúa pendiente.

Las 17 pruebas puras y la revisión de fuentes v2 pasaron antes del ensayo.
La primera revisión detectó preparación del workspace fuera de la limpieza;
se corrigió con un contexto que cubre también fallos de chmod, mkdir y journal,
verificados localmente. El informe negativo original se conservó. Fuente final,
SHA256 `4f15e62f3a39b9bab795d974f583329f38eed935fe8d8c47519361a0a4d3610d`;
revisión v2, SHA256
`ccd35adf58f0b072e4f372fde45abc652f53b229f4e77dc86c42a7ff66f10a5f`.
Recibo privado `current-media-coherence-receipt.json`, bajo
`current-media-coherence-20261013T234526Z`, SHA256
`154b5588188aa6de5ef46ffdea4a8bd28190dcdeaf2e3e5b1e30ccc7da3fa446`.
La revisión independiente del agregado y los tres recibos dio PASS del alcance
DB actual → medios de tenant 17, sin repetir el ensayo ni acceder a manifiesto,
inbox, dumps o medios privados. La asignación de las dos descargas a original y
miniatura de Xenía y los contadores del inbox proceden del cotejo saneado de root.
Informe `eikon-current-media-evidence-review-20261013.md`, SHA256
`611c35fb753f01ce0e863d77ec7c77e65c3d670e437e1e8866ab491df241d7fb`;
agregado `eikon-current-media-evidence-20261013.json`, SHA256
`f4b0259be9c0062a0501dc1933ecc16563cd5c2b34232b6e66b7e55b4601b8a6`.

La lectura del planner por el conector nativo de este chat devolvió
`configuration_error`, por ausencia de su token dedicado. El cliente MCP
privado existente sí obtuvo una respuesta autenticada: tenant 17, política 2,
17 campañas y tres conexiones Meta activas. Las revisiones 5/6/7 siguen
retenidas por frecuencia para su ventana original. Se cambió únicamente el
pin de revisión del lector; no se recargó ni reparó el conector global.
Recibo privado `planner-mcp-readonly-20261013T234210Z/receipt.json`, SHA256
`575ace4754df6d26e14d2418ec3516ca4ee2ba3262b784c4ade5f462ad4b5fa8`.
Este resultado acredita lectura del cliente privado y conserva explícitamente
`native_tool_configuration_repaired=false`.

No hubo inicio de server2, habilitación del timer, nueva publicación verificada,
recreación de entregas ni cambios a las programaciones nativas en este corte.
La ventana de 22:00–23:00 Bogotá del 13 de octubre, sus recibos y visibilidad,
el segundo barrido sin POST y su revisión siguen siendo el siguiente paso.


## Deméter: entrega real del 13 de octubre y control del 14

Este corte sustituye el estado pendiente del apartado anterior únicamente para
las entregas 5/6/7. La invocación controlada del 13 de octubre, 22:00:41–22:02:14
Bogotá, terminó con salida 0 y `completed_sweep/processed3`. InvocationID
`1aa6e8bdaf334a8b90a0d5b6d6548f15`. Cada cuenta conserva un intento y un recibo
terminal propio, sin rearmar el intento fallido histórico de Instagram.

| Destino | Entrega | ID remoto | Publicación |
|---|---:|---|---|
| Facebook Systems | 5 | 1045986888587355_122127578901283523 | [Deméter](https://www.facebook.com/122127579183283523/posts/122127578901283523) |
| Facebook Humanizar | 6 | 110421192090737_1010840832052858 | [Deméter](https://www.facebook.com/1008644758939132/posts/1010840832052858) |
| Instagram humanizar.news | 7 | 18148186327573817 | [Deméter](https://www.instagram.com/p/DedXpJeEWOF/) |

El operador obtuvo GET 200 de los tres proveedores, cotejó autor, caption y
fecha y vio en Brave las tres piezas completas con su imagen. La descarga
previa del original JPEG produjo 191953 bytes y SHA256
`99836aae9569ed692bc3605de70f2b4c2ad830c979e83693ba5922d08dc1ae80`.
El ticket de Instagram 1 quedó revocado a las 22:02:13 con el ACK terminal;
la fuente calificada rechaza capacidades revocadas. No se conservó la URL raw,
no se ejecutó GET posterior de esa misma URL ni se midió su fetch por logs.
La imagen visible corrobora el consumo del medio sin atribuir un contador de
bytes o petición de descarga a Meta.

Un segundo barrido real, InvocationID `03b0e80388f8458bba266bcc0aebc8ba`,
22:17:10–22:17:11, terminó con salida 0 e `idle/processed0`. Los snapshots de
claims, materiales, entregas, eventos y tickets fueron idénticos byte a byte:
SHA256 `293a635c536bd729fe668dd3db207de9cfba431c41ab897c7b94371722ac29e2`.
Los doce archivos Python del runtime coinciden con la fuente revisada.
El flujo instalado no puede devolver idle0 tras ejecutar dispatch/recover;
esta correlación acredita cero POST social de ese segundo proceso. No es un
contador de tráfico global ni una lectura directa del outbox protegido.

La revisión independiente final dio PASS acotado del segundo barrido y la
revocación registrada, sin bloqueador concreto adicional para habilitar el
timer Meta. Informe `eikon-daily-dispatch-code-review-20261014.md`, SHA256
`31e90460cd0ea8e945c0442fe636a15140df61e901de5b8c590859a65b2fba83`.
Recibo agregado `second-sweep-evidence-receipt.json`, SHA256
`b9829c140381333d3ce23a9163f4503f63b258bd9ab5d59923206882e60dbd63`.
El timer todavía estaba disabled en la lectura del 14 de octubre, 21:53
Bogotá; la revisión no lo activó.

X publicó mediante su programación nativa a las 22:00 del 13 de octubre:
[Deméter de @HumanizarSystem](https://x.com/HumanizarSystem/status/2110203943074795990).
El operador verificó autor, texto, hora e imagen en Brave, sin API facturable
ni envío manual nuevo. TikTok mostró autor y texto del ID 7696012000295488775,
pero un CAPTCHA impidió completar la comprobación de reproducción; conserva
ese alcance parcial y el handoff existente. No hubo nueva subida nativa.

El preflight de las 21:54 del 14 de octubre confirma las mismas filas 5/6/7
publicadas y 8/9/10 sin inicio. Instagram respondió como humanizar.news,
cuota 1 de 100 en 86400 segundos. El siguiente paso es la entrega de Agentes
8/9/10 en su ventana original, conservando 24 horas desde los starts previos:
22:00:45, 22:00:55 y 22:01:03, respectivamente. Vídeo1 silencioso sigue
aprobado por frames; no equivale a visionado completo. Vídeo2 con audio y
revisión11 permanece retenido. Xenía 11/12/13 y las programaciones nativas
del 14/15 de octubre se conservan. La meta de cinco destinos y los17 productos
sigue incompleta; estas dos ejecuciones no prueban recurrencia ilimitada.


## Agentes: ejecución del 14 de octubre, 22:01 Bogotá

Se conservaron las entregas8/9/10 y sus decisiones8/9/10, sin recreación ni
cambio de fecha. El preflight de las21:55 verificó política2, owner4,
grants4/5/6, conexiones vigentes y hashes canónicos de los tres contratos.
La descarga efectiva del vídeo1, 345720 bytes, coincidió con SHA256
`d395bd2a9cbd8b09066dd04e2138b32f3f596062f8e86e991d1a0faf5616590c`.
Es una tarjeta estática MP4 de6s, H2641080x1920/30fps, sin audio. Su revisión
editorial conserva `frames_only_silent/full_video_watched=false`.

La invocación `6c21e53be287456e83345f1f345f3ae2`,22:01:11–22:01:44,
terminó con exit0 y completed_sweep/processed3. Empezó después de las24h
de los starts de ayer; no adelantó envíos. Facebook respondió con IDs de
subida y processing_pending, que se conservaron como uncertain. El barrido
controlado de conciliación `86ef3a65141a49e2a7a3310624baaaeb`,22:03:26–35,
utilizó los mismos intentos con credenciales reconcile_only/post_permittedfalse
y terminó completed_sweep/processed2, sin volver a subir los vídeos.

| Destino | Entrega | Resultado verificado |
|---|---:|---|
| Facebook Systems | 8 | [Agentes](https://www.facebook.com/reel/1673375187480840/), ID1045986888587355_122127665355283523 |
| Facebook Humanizar | 9 | [Agentes](https://www.facebook.com/reel/1312779384208581/), ID110421192090737_1011814401955501 |
| Instagram humanizar.news | 10 | held/unsupported_media antes de start, sin ticket ni POST social |
| X HumanizarSystem | nativa | [Agentes](https://x.com/HumanizarSystem/status/2110566335994548732),14Oct22:00Bogotá |
| TikTok humanizar.systems | nativa7696024738354695425 | Verificación pendiente por CAPTCHA existente; no nueva subida |

Los dos GET de Facebook devolvieron200 con autor/caption/ID exactos. Brave
mostró ambas publicaciones públicas y la composición completa. La conciliación
correlacionó los IDs de subida con el post de cada página. created_time del
objeto feed y published_at del proveedor conservan sus valores distintos;
no se sustituyen por el instante posterior del ACK. X mostró autor, texto,
fecha22:00, marcaIA y reproducción del vídeo; no se inspeccionó íntegramente
el vídeo ni se usó API facturable. Se guardaron screenshots reales.

Instagram no envió el archivo: el validador local detectó unsupported_media
antes de start. El diagnóstico del original exacto encontró moov antes de
mdat y una lista de edición MP4. `_qualify_video` rechaza esa estructura para
Instagram. Este resultado identifica una condición suficiente del bloqueo
local; no es un rechazo remoto de Meta. Se mantiene la exclusión durable de
la entrega10. Corregir futuros originales requiere nueva calificación y
revisión; no se debilita la regla, altera el original ni rearma esa fila.

El timer existente de Meta se habilitó el14Oct22:05:01 con el comando fijo
sudo -n y quedó active/waiting/enabled, próxima activación22:06:05. Su gate
es la entrega real de fotografías del día anterior, el segundo barrido0POST
y la revisión independiente31e90460…, con los mismos doce archivos de runtime
revalidados hoy. No se atribuye éxito de vídeo Instagram ni de todos los
destinos a esa habilitación. La política conserva frecuencia1440min,
1publicación/destino/día, ventana60min y exclusión de gasto. Timer y heartbeat
diario cumplen funciones distintas: ejecutar entregas vigentes y preparar/
verificar decisiones editoriales, respectivamente.

Recibos privados del corte: `daily-dispatch-20261015-agentes/`, preflight
`agentes-preflight-20261015T025513-private.json` SHA256
`7a4e537c850458f0b3d190432c040aa184f0e82fd4ff114f15fd7d6210b3775e`;
DB después de conciliación SHA256
`5308e7d251259ea963f42dcc471fe92860e467ba3bcbfa777b8eae7d75442df0`;
GET remotos `agentes-remote-verification-20261015T030409-private.json`
SHA256 `bce05efed08499f921abbf7764423b08fdc1d2d7b29af54c2b027e52227a60d6`.
La meta global sigue incompleta. No se reparó OAuthTikTok, CAPTCHA, conectorMCP
nativo ni acceso de edición del perfil FacebookHumanizar; no se desplegó código,
rotaron grants o repitieron respaldos/migraciones/pruebas de recuperación.


La primera activación automática del timer produjo la invocación
`17e2b0e15b1f4ce4a0917b0ffc7df0dc` a las22:06:17: idle/processed0 y
finalización normal. La DB seleccionada antes y después quedó idéntica
byte a byte, SHA2565308e7d251259ea963f42dcc471fe92860e467ba3bcbfa777b8eae7d75442df0.
Esto mantiene intentos/IDs/recibos, retención10 y futuros11–13; no hubo
POST social en esa ejecución conforme al flujo calificado. No es medición de
tráfico global. El timer quedó active/waiting/enabled con próxima activación.

## Xenía: publicación automática del 15 de octubre y cotejo del 17

Las mismas entregas 11/12/13 se publicaron dentro de su ventana original,
sin start manual ni cambio de fecha. El timer ejecutó
`cdbe660ccae54947a8e02bac928d6686` a las 22:00 Bogotá: completed_sweep1,
Instagram 13. La invocación automática
`b81fbbeaab0e4cfd945152b3bc81a02b`,22:02:27–22:02:47, terminó
completed_sweep2 para ambas páginas Facebook. El barrido de 22:01 fue idle0.

| Destino | Entrega | ID remoto | Publicación |
|---|---:|---|---|
| Facebook Systems | 11 | 1045986888587355_122127745635283523 | [Xenía](https://www.facebook.com/122127579183283523/posts/122127745635283523) |
| Facebook Humanizar | 12 | 110421192090737_1012811445189130 | [Xenía](https://www.facebook.com/1008644758939132/posts/1012811445189130) |
| Instagram humanizar.news | 13 | 17947995993347020 | [Xenía](https://www.instagram.com/p/DeihHyskXVr/) |

El GET de cada proveedor devolvió 200 el 16 de octubre y nuevamente el 17 de octubre a las 20:48 UTC,
con autor, caption exacto, ID y fecha dentro de la ventana. Las imágenes
servidas por CDN se descargaron anónimamente el 16 de octubre y se inspeccionaron:
Facebook entregó en ambas cuentas los mismos 33421 bytes/JPEG 720x900,
SHA256 `dee37b49e0e6b3ea8f0c9aeb6f295c0e721f1e4c718f6b68cb929fe7f2cc07a1`;
Instagram, 134308 bytes/JPEG 1080x1350,
SHA256 `c2d3ccef71db97cc196e7e9a7770a77f733bdbc7fcffb1f89b47f47bd2838253`.
La composición completa conserva Xenía, su logo y el paraguas Humanizar.
Es evidencia API/CDN e inspección visual de archivos; no una visita en Brave.

Los barridos automáticos posteriores quedaron idle0. Las filas seleccionadas
de entregas, claims, materiales, tickets y eventos permanecieron iguales entre
03:04:25 y03:05:41UTC del 16 de octubre; hash canónico conjunto
`266c284ae20797efe6b66e602af1a07164ea1abc8f51701db805b249024334b5`.
Los doce archivos del worker coinciden con la fuente revisada. Esa correlación
acredita ausencia de POST adicional en esos procesos idle; no es un contador
global ni una lectura directa del outbox. El snapshot readonly del 17 de octubre
confirmó esas mismas cinco tablas sin nuevas publicaciones antes de preparar
el nuevo ciclo de Graf. No se afirma igualdad de toda la base.

El ticket de Instagram 2 quedó revocado en el ACK terminal. No se observó su
URL raw ni se hizo GET posterior de esa misma URL; tampoco se midieron bytes
descargados por Meta. La revisión independiente final prevista el 16 de octubre se
interrumpió sin producir informe: no se le atribuye PASS. El preflight sí
conserva su revisión acotada anterior.

Corrección de frecuencia: `_limits` tiene en cuenta tanto el inicio como
`published_at` del proveedor cuando está disponible. Para Facebook del 15 de octubre
el mínimo derivado del resultado de Agentes era 22:01:45 y 22:02:02,
respectivamente; el start automático de 22:02:27 respetó ambos. No debe
reutilizarse la estimación anterior basada sólo en los starts 22:01:18/32.

Recibos privados: `daily-timer-20261016-xenia/automatic-dispatch-journals-receipt.json`,
SHA256 `6ee1ae91c9b55c9d153cae75b86af415b988bd0db25c85b94506e115de5c83a1`;
`post-publication-no-duplicate-receipt.json`,
SHA256 `7924a9db91356c517d7a85d59b5ee226e6d139dd02c2807490533d487c467d76`;
GET actual `remote-verify-20261017T204834249532-receipt.json`,
SHA256 `63576592dda6a3c08b24237506635c51b9f5158eb1c73b991b6be7ddd2b9e428`.

## Graf Commerce: nuevo ciclo del 17 de octubre, aún futuro

El trabajo interrumpido del 16 de octubre había creado revisiones 15/16/17 y archivos
de evaluación local sin enviarlos. Su ventana venció sin decisiones ni
entregas. Esas revisiones, fechas y archivos se conservan; no se envían ahora
ni se presentan como publicaciones. Por ello no se acredita publicación
diaria ininterrumpida el 16 de octubre a partir de este flujo.

El 17 de octubre se inspeccionaron de nuevo el JPEG 49 y la referencia oficial Graf 111/v4,
y se consultó [la fuente pública de Humanizar](https://humanizar.tech/).
El caption se limita a catálogo, inventario por tienda, clientes y reportes,
con CTA para solicitar demostración en Humanizar. La dirección admin.graf.com.co
que aparece en la pieza corresponde al administrador; no prueba acceso a una
tienda pública. La imagen es una ilustración, no una captura funcional.

Media 49 conserva el original 33 y el SVG oficial: es una conversión declarada
de formato PNG→JPEG, 1080x1350, 228608 bytes,
SHA256 `605732a13530364090b8684b3b7ee83105dc5981062fc49eb3539cee4aaa02f3`.
No hubo generación de imagen IA nueva ni sustitución del logo.

Se congelaron contratos nuevos y el coordinador Codex realizó tres evaluaciones
editoriales reales, vinculadas a los materiales entregados por MCP y al hash
de cada contrato. Son recibos `client_reported`, no una atestación criptográfica
de razonamiento. La aprobación y creación de entrega se confirmaron por API:

| Conexión | Revisión nueva | Decisión/evaluación | Entrega | Estado observado |
|---|---:|---:|---:|---|
| Facebook Systems | 18 | 15 | 14 | scheduled, sin start ni intento |
| Facebook Humanizar | 19 | 16 | 15 | scheduled, sin start ni intento |
| Instagram humanizar.news | 20 | 17 | 16 | scheduled, sin start ni intento |

Las tres tienen ventana 17 de octubre, 22:15–23:15 Bogotá, campaña 5/proyecto 9,
política 2 y medio 49. Inbox autenticado del 17 de octubre confirma 17 campañas, tres
conexiones activas y stock autorizado 1/déficit 0 en cada cuenta para ese día.
Esto acredita programación de un ciclo, no publicación futura ni recurrencia
indefinida. El claim volverá a verificar permisos, frecuencia, cuota y medio.
Recibo `recurrence-20261017/graf/evaluations-and-scheduled-deliveries-receipt.json`,
SHA256 `1fc82d8cd64d74eacca8ce1efdaa2d38dcce3c153580cca36846281b7f7dee83`.

El 17 de octubre el timer sigue active/waiting/enabled, con barridos idle0 entre ventanas.
El operador no inició el servicio ni hizo POST social en este corte; las
mutaciones fueron nuevos contratos, decisiones y entregas privadas futuras.
Se mantienen el hold permanente de Instagram 10, el intento 4 fallido y vídeo 2
retenido, sin cambios de guardas ni nuevos permisos. Brave no aparece en el
inventario actual; la pregunta de reconexión ya existe y no se duplica.
X/TikTok del 15 de octubre siguen sin verificación nueva. OAuth/legal/CAPTCHA de TikTok,
edición del perfil Facebook Humanizar y cobertura recurrente de 17 productos/
cinco cuentas siguen pendientes. La meta global permanece incompleta.

La revisión independiente nueva del 17 de octubre terminó con **PASS acotado**,
sin hallazgos bloqueantes para estas afirmaciones y las tres entregas futuras.
Recalculó los hashes de contratos, materiales y respuestas de Graf, cotejó
los recibos de Xenía e inspeccionó el JPEG y el render oficial de Graf.
No hizo consultas remotas ni interpretó los snapshots completos: verificó
sus hashes y conservó la comparación saneada del coordinador. No amplía
la evidencia a UI Brave, tráfico global, fetch de Meta, publicaciones futuras
o aceptación de las cinco redes. Informe privado
`recurrence-20261017/independent-evidence-review.md`, SHA256
`9b23dbd571c503edc875bb0912213ae8cae125ee82fdc080e63de5f39ce4cafe`.
Se ejecutó con un subagente Codex de la cuenta actual en Kratos; la cuota
consultada seguía desconocida, sin interpretarla como saldo disponible ni
cambiar de cuenta. No se generaron nuevas imágenes o gastos.


## Corte del 17 de octubre, 22:03 Bogotá: Graf previo y Agora futura

La comprobación previa de Graf terminó con 26/26 verificaciones correctas:
owner, política2, grants4/5/6 vigentes, contratos18/19/20, decisiones15/16/17,
medio49 exacto, identidad111v4, límites y permisos registrados. Las hipótesis
para due/due+120s están separadas del snapshot PG actual de 21:52:39 Bogotá.
La lectura fijada por generación de GCS verificó JPEG1080x1350/228608bytes y
SHA esperado. Doce archivos actuales del worker en server2 coinciden con las
fuentes calificadas. IG respondió dos GET200 como humanizar.news y cuota
actual0/100; no es una promesa de cuota posterior ni una introspección FB nueva.
El timer existente sigue habilitado, sin start manual, reinstalación o despliegue.

Recibo privado `daily-observation-20261018-graf/preflight-validation-20261018T025458814183-receipt.json`,
SHA256 `2f65caeb52bdfb4303ad3097eb34137cb737ba1e7dc609300e7339a4d7ad60af`.
A este corte Graf todavía tiene su ventana futura17Oct22:15–23:15 y las mismas
entregas14/15/16; la comprobación no las recreó ni acreditó una publicación.

Se preparó el siguiente ciclo de **Agora para18Oct22:45–23:45 Bogotá**,
campaña8/proyecto12/marca114v4, conservando el SVG oficial y el PNG36.
El JPEG50,1080x1350/255434bytes, es una conversión técnica de formato sin
recorte, redibujo o generación IA nueva, SHA256
`3300c308bb07ba5d26b7226c01666310f51c6db54845934cac40ddd5051c5192`.
El coordinador inspeccionó los materiales exactos y la referencia oficial,
leyó el catálogo HTTP actual y evaluó cada contrato de publicación. La pieza
ilustra escritura/investigación con figuras sintéticas; no son testimonios
ni una captura funcional. No promete verdad formal universal, métricas,
funcionamiento offline, cifrado o sincronización probados. El CTA dirige a
la demostración en Humanizar.

| Destino | Revisión | Evaluación/decisión | Entrega social | Estado confirmado |
|---|---:|---:|---:|---|
| Facebook Systems | 21 | 18 | 17 | scheduled, sin start/intento |
| Facebook Humanizar | 22 | 19 | 18 | scheduled, sin start/intento |
| Instagram humanizar.news | 23 | 20 | 19 | scheduled, sin start/intento |

Las solicitudes de materiales33/34/35 son distintas de esas entregas sociales.
Las decisiones son `client_reported`, vinculadas a hashes/request_id exactos;
el script transmite la decisión del coordinador y no llama a otro modelo ni
ofrece atestación criptográfica de razonamiento. La galería conserva
pending_review/approval_current=false; no se añadió revisión owner.
La frecuencia depende de la hora real de Graf, no sólo de su due; el claim
futuro reevalúa el mismo registro dentro de la ventana autorizada.
Recibo `next-cycle-agora-20261018/evaluations-and-scheduled-deliveries-receipt.json`,
SHA256 `bc4d743539b6181ea27cec4d2610695061afc56bce335e7bbbf85a4c80686b85`.

La revisión independiente nueva verificó esas correlaciones y materiales,
26 comprobaciones de preflight y52 fixtures locales de los lectores GET:
**PASS acotado**, sin hallazgos bloqueantes sustentados. No hizo llamadas
remotas ni amplía la evidencia a publicación, cuota futura, UI o cinco redes.
Informe `recurrence-20261018/independent-review.md`, SHA256
`c133947905dcec2504415233cc0bedfd16be51636e5e93f99562b57bf2d7a0f0`.
La app aportó cuota actual de Codex:35% y después38% semanal usado; el sondeo
local permaneció apagado y no se cambiaron cuentas/proveedores ni compraron créditos.

El inventario MCP actual conserva17 campañas; Humanizar News carece de un
medio propio en esta galería y varias campañas aún requieren evaluación y
publicación. Brave sigue ausente del inventario; no se repite la pregunta de
reconexión. X/TikTok, los permisos/políticas pendientes de TikTok y el control
total del perfil Facebook Humanizar mantienen sus límites anteriores.
La meta global sigue incompleta y blocked; ni esta cola ni los ensayos
acreditan recurrencia en cinco cuentas o cobertura de17 productos.


### Chrónos: ciclo del19 de octubre, todavía sin envío

También quedaron programadas las entregas20/21/22 para19Oct22:45–23:45
Bogotá, conexiones1/2/3, campaña12/proyecto16/marca118v4, revisiones24/25/26
y evaluaciones/decisiones21/22/23. El recibo final de03:04:16UTC confirma
scheduled/holds[]; los submits tienen start e intento nulos. Son distintas de
las solicitudes de materiales36/37/38. No acreditan publicación futura.

Media51 es JPEG1080x1350/225343bytes, SHA256
`d2bdd72d9fbc30973e483c3d65ed21091c5e06dac0fed5a9c0db6bf7b7116542`.
Es conversión de formato del PNG40 original, conservado junto al SVG oficial;
no se generó una imagen IA nueva ni se redibujó el logo. El subagente Codex
inspeccionó individualmente las piezas/referencias, contratos y seis criterios.
El catálogo y HTML públicos HTTP200 sustentan horas, proyectos, tarifas y
cuentas de cobro; no se prometen factura electrónica, DIAN, cumplimiento legal,
funciones autenticadas probadas o métricas. La attestation sigue siendo
client_reported y la aprobación owner de galería permanece pendiente.

Recibo privado `next-cycle-chronos-20261019/evaluations-and-scheduled-deliveries-receipt.json`,
SHA256 `e674e4c62b06ccb85f1f441d457f4f5121610591b63fd3ec9be680a10caafc16`.
Relectura final `final-scheduled-verification-receipt.json`, SHA256
`f0c9b15ebdae67af996b93bc2bc62a7fd6e371e29cb224b3cc880eb92912ea80`.
Los19 contratos previos conservaron sus hashes, incluidos Graf, Agora y los
retenidos10/11. El claim futuro volverá a calcular frecuencia desde el envío
real anterior:24h entre horarios programados no garantizan24h entre publicaciones.
La revisión independiente posterior terminó PASS acotado,25/25 comprobaciones y
104 referencias hash concordantes. Informe `recurrence-20261018/chronos-independent-review.md`,
SHA256 `70aaac9649fe1e11242e9d8a35801deb5adb16bf4f24ed06d63529a41b0b0ecd`.
Encontró un P2 de reutilización en el preparador privado de este ciclo: una
variable fuera de scope abortaría al detectar un candidato ya existente,
antes de crear. La fixture local lo reprodujo sin red. No afecta los submits
confirmados; la fuente se conserva como evidencia y no se reutilizará.


## Graf publicado automáticamente:17 de octubre,22:15–22:16 Bogotá

La invocación `1bc6408922804ca0aa322f25792448a8` arrancó con el timer existente
a las22:15:02 y terminó a las22:16:37, `completed_sweep/processed3/exit0`.
No hubo start manual, nuevo upload nativo, reenviados o cambios de fechas.
El siguiente barrido automático `bfc80c1996454ab5b4ef00b70a86373c` fue idle0.
Los snapshots PG actuales confirman14/15/16 published, un claim y tres eventos
reserved/start/published por entrega, materiales49 verificados y worker/grant6.
Los nueve eventos nuevos son128–136; la numeración máxima no equivale al
número de filas del tenant. La fila15 conserva started_at1792293315 y su evento
start1792293316, sin corregir artificialmente esa diferencia de un segundo.

| Destino | ID remoto | Fecha publicada del proveedor, Bogotá | Enlace |
|---|---|---|---|
| Systems | 1045986888587355_122127932043283523 |17Oct22:15:07|[Publicación](https://www.facebook.com/122127579183283523/posts/122127932043283523)|
| Humanizar |110421192090737_1014678701669071|17Oct22:15:16|[Publicación](https://www.facebook.com/1008644758939132/posts/1014678701669071)|
| humanizar.news |18035286086852873|17Oct22:16:31|[Publicación](https://www.instagram.com/p/Densd0eFWnV/)|

Los tres GET del proveedor respondieron200 y comprobaron autor, caption exacta,
ID y fecha dentro de la ventana original. Recibo privado
`daily-timer-20261018-graf/remote-verify-20261018T031946723965-receipt.json`,
SHA256 `968e949655e9f7bf86c4adac3100d1c0c2f1160b6291c6a39c05551744196e04`.

Las tres descargas CDN anónimas también fueron200. Facebook sirvió dos archivos
idénticos de35107bytes/JPEG720x900, SHA256
`67071a6f56c9d45b2acaab07b7b64e14abd3acb4f488171d6e009a91a56a1cff`;
Instagram sirvió205248bytes/JPEG1080x1350, SHA256
`04907af820cf486d261749d496826df684631c2ccf2707532814504dc5247e31`.
Se inspeccionaron los dos materiales visuales distintos, cotejando original y
referencia oficial: título, logo, pie Humanizar y textos legibles sin recortes.
El segundo archivo FB se cotejó por igualdad íntegra de bytes con el inspeccionado.
Se conserva que admin.graf.com.co es el administrador y que la escena es una
ilustración sintética, sin atribuir testimonio a un cliente real.
Recibo CDN `remote-media-verify-20261018T031946716511-receipt.json`, SHA256
`83b0c31a0114f4b58f8b2e4274656da9cdec20987bc91e1b56dae43b0835df3e`;
inspección suplementaria `recurrence-20261018/graf-cdn-visual-review-receipt.json`,
SHA256 `589c914287751f3cc2c8cf7450d7a3b732fa38bfe971dffb69cf8c43d1eded4a`.
El recibo CDN original mantiene visual_content_reviewed=false y no se reescribió.

Entre22:16:52.325981 y22:19:56.386439 Bogotá quedaron idénticas las cinco tablas
seleccionadas: deliveries22, claims16, claim_materials16, media_tickets3,
events102. Hash canónico conjunto
`8cae6d3aa1f38f5a75200753b61520327274e9a2e3328e7e09d56c4948502d7e`.
Los barridos automáticos ef46cea2c0a34829b699af91947ff645,
1b9c6c89048f4d81a30bbd020cee84c8 y140e7e19083b48cfa2562798018fc29b
empiezan y terminan dentro de ese intervalo con idle/processed0. Doce archivos
actuales del runtime de server2 siguen coincidentes con las fuentes calificadas;
la fuente de run_once/CLI correlaciona idle0 con ausencia de nuevo dispatch.
Es evidencia de cero POST social adicional de **esos procesos**, sin contador
global, lectura directa del outbox o igualdad de toda la DB. Recibo
`recurrence-20261018/graf-postdispatch-idle-comparison-receipt.json`, SHA256
`b5a2b58e18fe8263d43668121a09c4e0da5fb555b5b002d954f48aaecb908d1e`.

Las entregas1–13,17–22 y los contratos/decisiones/holds anteriores se conservaron.
IG10 sigue retenido por unsupported_media antes de start; el intento4 sigue
failed_before_dispatch con su ACK original. El ticket IG3/media49 se revocó en
ACK terminal1792293395. No se observó ni se solicitó su misma URL raw después,
ni se midió el fetch o los bytes descargados por Meta: no se acredita404.
Las sondas GET/PG cerraron sus proxies y sockets propios; no refrescaron tokens.

Esta es evidencia API/CDN e inspección de archivos, **sin verificación UI Brave**.
El timer sigue active/waiting/enabled, su servicio oneshot inactive/dead/success
entre ticks es normal. Los tres destinos Meta de este ciclo están publicados;
la recurrencia global en cinco cuentas y17 productos continúa sin acreditarse.
La revisión independiente terminó **PASS acotado**:62/62 comprobaciones,
51 cotejos SHA sobre43 archivos únicos, contratos/claims/eventos/ACK y
Graph/CDN concordantes. Informe
`recurrence-20261018/graf-dispatch-independent-review.md`, SHA256
`649ccf43de368a918fcbc78a16e8cbf432c66bdc26773abe7ccb26c371c6939b`.
Documentó un P2 de trazabilidad del observador privado: su stdout sobrescribe
el SHA del resumen con el SHA del raw. Ambos archivos son íntegros y sus
hashes se recalcularon por separado; no se usa ese stdout como hash del resumen.
La fuente se conserva sin reescribir la evidencia. Este PASS no acredita UI,
tráfico global, fetch de Meta, cuotas futuras o publicaciones de Agora/Chrónos.
La cuota actual de la app a03:18UTC fue42% semanal usado/58% restante para
la misma cuenta Codex; get_ai_quotas conservó Codex desconocido y el sondeo
local no se reactivó. No se cambió cuenta/proveedor ni se abrió gasto nuevo.


## Corte del18Oct: Agora automático y reserva de Meta hasta24Oct

El timer existente despachó Agora a22:45:01–22:45:41Bogotá,18Oct2026,
invocación `3f6a2cdd63f246398ac35f5cb77f975e`, completed_sweep3/exit0.
No hubo start manual, nueva subida del operador ni modificación del timer.
Se conservan campaña8/proyecto12/marca114v4/media50 y las revisiones21/22/23,
decisiones18/19/20 y entregas17/18/19 originales. Medio JPEG1080x1350,
255434bytes, SHA256 `3300c308bb07ba5d26b7226c01666310f51c6db54845934cac40ddd5051c5192`.

| Destino | ID remoto | Hora proveedor Bogotá | Enlace |
| --- | --- | --- | --- |
|Facebook Systems|1045986888587355_122128022361283523|22:45:08|https://www.facebook.com/122127579183283523/posts/122128022361283523 |
|Facebook Humanizar|110421192090737_1015715104898764|22:45:19|https://www.facebook.com/1008644758939132/posts/1015715104898764 |
|Instagram humanizar.news|17872888590640292|22:45:36|https://www.instagram.com/p/DeqUs4pjpLC/ |

Los tres GET Graph200 del lector específico de imágenes comprobaron autor,
caption exacto, identificador, tipo IMAGE en Instagram y fecha dentro de la
ventana. El lector genérico auxiliar no llegó a conectar a PG: agotó su guardia
de20s esperando el socket del proxy; cerró antes de DB/vault/Graph y no se
repitió. No se conoce la causa subyacente y ese intento no se presenta como
PASS. El lector específico sí completó las tres verificaciones Graph y CDN.

Las descargas CDN anónimas dieron200: ambos Facebook sirvieron JPEG720x900,
40139bytes, SHA256 `526ba5f801c4ff6e7addeb030626d4117f114d5764e14552e3095f2cd49c49a0`;
Instagram sirvió JPEG1080x1350,232684bytes, SHA256
`a6ff2afab88ebf4478b96a8ed2f8d14c5e02c4772f1c56ff3118e5d70ea5d6b2`.
Se vieron realmente los dos archivos distintos, composición original y
referencia. FB18 se cotejó byte a byte con FB17. Logo, titulares, composición
y pie Humanizar permanecen legibles, sin recortes. No se acredita UI Brave.

La correlación predue/post confirma sólo tres claims/materiales nuevos,
nueve eventos152–160 y ticket4 nuevos; las otras34 entregas1–16/20–37 y
los grupos de autoridad/holds/historial seleccionados se conservaron.
Los starts17/18/19 son1792381506/1517/1528; created_at de cada evento start
es un segundo posterior. Los result_json mantienen published_at_utc/permalink
nulos: las fechas y enlaces de la tabla proceden de Graph, no de ese campo PG.
Ticket4 quedó revocado en ACK terminal1792381539. No se observó ni solicitó
su URL raw, no se midieron bytes descargados por Meta y no se afirma404.

Los snapshots PG de epochs1792381630.866201 y1792381839.584169 contienen las
mismas cinco tablas seleccionadas de tenant17:37 entregas,19 claims,19
materiales de claim,4 tickets y126 eventos. Hash canónico conjunto:
`b0ba3496e66bab3bcd2b2a54cd77d2a54d6bb9b8a166815da71643bb64915b67`.
Entre ambos quedaron completos tres procesos idle0:
`53d09b621b814b69aff99ef0c3bf84a6`,
`8b70498f30454d96b231e2b537ddc555` y
`e7734302a8384c62a03dea8aaf443697`.
El comparadorV3 cotejó mensajes contra diario raw y hashes separados; las12
fuentes runtime coinciden con las locales/calificadas. La correlación de
run_once/CLI, esas fuentes, los idle0 y las cinco tablas idénticas sustenta
cero POST social adicional de ESOS procesos. No demuestra cero HTTP de control,
un contador global, igualdad de toda la DB o lectura directa del outbox.

Recibos privados preservados; se documentan nombres y hashes, sin secretos:

| Evidencia | SHA256 |
| --- | --- |
|agora-prewindow-boundary-current-receipt.json|7f0e911518fe8404132bf78abd305682466e947ca876d85b4f5a74d3f1a8bf6b|
|remote-media-verify-20261019T034700103997-receipt.json|226ecde330c20662adfe5322fc8b4ebe5903e6c84c8fc484899db4e5a0b29835|
|agora-cdn-visual-review-receipt.json|254aaa230110260b1aa35396141bd2ade03cbafdb9deecd4a1d0c31cd4f595ad|
|agora-dispatch-correlation-receipt.json|cba463b020183d0631e295909996e6c895b3f13d7f879790b7165a36f467b964|
|agora-postdispatch-idle-comparison-20261019T035309550247-receipt.json|a96a88aef99b2418dae600f48b3ab3e368dcf10f4b0f6ee7d400d99258c834cd|
|worker-runtime-readonly-20261019T035017148771-receipt.json|abfd0d6fc909ab5243615173933b9e301d99765f81127878293e593ca58c634f|
|agora-generic-reader-readiness-failure-receipt.json|0cc81076d0a6fa7d29e0a8b8ecc4e05d961a6eeb2dc3890ed8f5d50000842f9e|

La revisión independiente terminó **PASS ACOTADO**:309 aserciones locales,
12pins recalculados y medios realmente vistos por el revisor. No hizo
consultas remotas ni ejecutó operadores originales. Informe
`agora-dispatch-independent-review.md`, SHA256
`6f4f0bc046e5941b059617681fb56a0ef3ea7884eecb6d45c78472dac486ba63`;
manifiesto `agora-dispatch-independent-review-manifest.json`, SHA256
`e89534783262a227975530791bcf23b2245f89cc80f59ac7b63316fa4401edea`.
El PASS permanece limitado al despacho17–19 y al intervalo seleccionado.

### Reserva futura de Meta, todavía sin envíos acreditados

Las cinco incorporaciones se evaluaron realmente por IA sobre seis criterios,
con contrato/materiales exactos y atestación client_reported. Cada área tuvo
revisión independiente local PASS acotado. Las composiciones son Codex previas,
convertidas técnicamente de PNG a JPEG opaco1080x1350; no se generó IA nueva,
redibujó un logo ni se cambió el original. Owner de galería sigue pending_review
y approval_currentfalse, separado de las aprobaciones editoriales.
El PG posterior al despacho conserva estos estados y sin inicios/claims:

| Fecha22:45–23:45Bogotá | Producto | Media / SHA256 | Revisiones | Decisiones | Entregas | Estado |
| --- | --- | --- | --- | --- | --- | --- |
|19Oct|Chrónos|51 / d2bdd72d9fbc30973e483c3d65ed21091c5e06dac0fed5a9c0db6bf7b7116542|24/25/26|21/22/23|20/21/22|scheduled|
|20Oct|Koinonía|52 / 36372e33a87ee181bb25277361082b1d44746012eb56d727a7b88c2a6febe4fd|27/28/29|24/25/26|23/24/25|held/frequency_limit|
|21Oct|Cauce|53 / 50e5f3070d502424363fe0c057850bad96c73c97f2cd4af932c23cf171bf6bb8|30/31/32|27/28/29|26/27/28|held/frequency_limit|
|22Oct|Aletheia|54 / c7f2df8f815e65a7117c0dbb1858a5d1a12c7505c12ce41237e83812c651cca3|33/34/35|30/31/32|29/30/31|held/frequency_limit|
|23Oct|Apothḗke|55 / a335250aa2dd0efe294a93f29f935428f40d01405cb154570861cd9e4cc7b7a5|36/37/38|33/34/35|32/33/34|held/frequency_limit|
|24Oct|Gravitatoria|56 / 9767a744703125bf8baea0f5a97040418c8041fb191be640d3f6441455c59053|39/40/41|36/37/38|35/36/37|held/frequency_limit|

Se conservan las mismas filas: el worker reevalúa frecuencia/cuota al claim
debido; no borrar eventos, guardas o consumos, alterar fechas ni recrear
revisiones para forzar publicación. Frecuencia1440min considera starts y
published_at del proveedor cuando está disponible;24h entre due no prueba
la elegibilidad del día siguiente. No reutilizar el preparador Chrónos con
NameError(connection) documentado. No repetir solicitudes completadas.

| Revisión independiente local | SHA256 |
| --- | --- |
|koinonia-independent-review.md|0fd3a2b7fd50c4087fea29d3f601724096b855362b6d93de7c4f6b547f0680e9|
|cauce-independent-review.md|b8bde4d8620e3c98f85a9b834930df73af2ba7ce4256019575bd57ca8a53628c|
|aletheia-independent-review.md|0b10a80788fc7f4fca9a96f3097d76270d828b989b1c81da10d4567b6dcfad15|
|apotheke-independent-review.md|70f4e11aea5a7f090abe32c0f7a6b076c40d7c827ee73d7ad575122e5af2344b|
|gravitatoria-independent-review.md|52788a7280c1cbe09452c5fd8b3d0bfac24e8467ef5365408c5316881c6d4fe8|

Los hechos se limitaron a fuentes actuales. Koinonía se presenta como portal
para comunidades y evaluación piloto, sin clientes o asistencia inventados.
Aletheia no promete conectores Instagram activos ni confunde asociación con
causalidad. Apothḗke conserva su referencia116v4 compartida con el conjunto
Mouseîon, comprobada dos veces por MCP; el mismo hash que Chrónos no se atribuye
a una referencia exclusiva nueva. Gravitatoria usa la propuesta pública actual
de red social de comercios, reconoce que el catálogo heredado describe logística
y evita trasladar esa descripción antigua al caption o imagen.

La app de Codex consultada19Oct03:47UTC marcó64% semanal usado/36% restante,
cuenta actual terminada en6fd3, ordinaryUsageAllowedtrue. ai-usage conserva
Codex desconocido por sondeo deliberadamente apagado. Se usaron subagentes
Codex nativos/heredados de esa misma cuenta en Kratos, un escritor por área,
sin cloud, cambio de cuenta/proveedor, nuevas APIs facturables ni gasto nuevo.
Es una lectura fechada, no saldo futuro.

Brave sigue ausente del inventario; no se utilizó Chrome. No hay nuevos envíos
nativos X/TikTok posteriores al15Oct confirmados ni nuevas verificaciones de
sus pendientes. Las preguntas ya realizadas de reconexión, CAPTCHA/login y
TikTok Developers se conservan sin duplicarlas. Facebook Humanizar permite
publicar pero el logo/datos de perfil aún requieren control total. News sigue
sin pieza propia en la galería capturada; cobertura y recurrencia de17 productos
en cinco destinos siguen sin acreditarse. Instagram10prestart y revisión11con
audio siguen retenidos; intento4failed_before_dispatch y revisiones Graf15–17
vencidas no se rearmaron. Recuperación acotada y producción sin redeploy se
conservan; compound y aceptación social global permanecenfalse.

## 19Oct: reserva Meta hasta30Oct y comprobación previa de Chrónos

Corte PG20Oct03:24:53UTC, antes del vencimiento de Chrónos19Oct22:45Bogotá:
55 entregas,19 claims,19 materiales de claim,4 tickets y144 eventos. Las37
entregas de la lectura anterior y13 grupos seleccionados de autoridad,
contratos, medios e historial permanecen iguales. Las tres filas20/21/22
siguen scheduled, sin inicio, intento, claim, lease, resultado o worker asignado.
Las33 futuras23–55 permanecen held/frequency_limit sin esos campos.
Snapshot `chronos-snapshot-20261020T032442379774-private.json`, SHA256
`ea67cda2c17a45fde89f25b93fc52f67d81d3e4489da8f74272a6ae3a9320416`;
validación `chronos-predue-55-deliveries-validation-receipt.json`, SHA256
`215ff453f7c7f57c01b9db79dbe1337d5074d002abffd6b986b147ccde6d2098`.
Es una comparación de las proyecciones indicadas, no de toda la base.

Las seis incorporaciones conservan la ventana22:45–23:45Bogotá y los tres
destinos Meta autorizados, sin desplazar fechas ni recrear filas retenidas:

| Fecha | Producto | Media JPEG / SHA256 | Revisiones | Decisiones | Entregas |
| --- | --- | --- | --- | --- | --- |
|25Oct|Prizma|57 / 6b12b50058531407b4beddee21e2add74287abed1a7dfd563cfc1c92a552fa67|42/43/44|39/40/41|38/39/40|
|26Oct|Práxis|59 / f8104ad242672b04d8d0c0b7e65b3218b8c39283ddd3e5e1c6f0e41621d3cc5a|48/49/50|42/43/44|41/42/43|
|27Oct|Érgon|58 / d6b1baf9efb504b12fbe27dad6d874468cbd3aa1c802f1dcf4a846465eaf59e5|45/46/47|45/46/47|44/45/46|
|28Oct|Systems|63 / 1b30501c9048fa3799bfeb0a9119b8bf854a1666bca9732c506ab2e271c89588|51/52/53|48/49/50|47/48/49|
|29Oct|News|61 / 655d29ab69b781bab24893a8365ffcad390e3bfb0fdefca7b9c65a4287b97daf|57/58/59|54/55/56|53/54/55|
|30Oct|Sinergia|65 / f300c84f7fcd697ec2c15dc99067da495e4aa12c263df8a9a34cd062dae22bf3|54/55/56|51/52/53|50/51/52|

Cada contrato tuvo evaluación IA real y explícita de seis criterios y materiales
MCP efectivamente vistos. La atestación es client_reported, sin atribuirle prueba
criptográfica del razonamiento. Las decisiones y entregas se confirmaron mediante
respuestas guardadas antes de validarlas, más la lectura PG anterior. El owner
de galería permanece pending_review/approval_currentfalse, una aprobación distinta.

Prizma, Práxis y Érgon convierten composiciones Codex existentes a JPEG opaco
1080x1350. Systems, News y Sinergia incorporan tres escenas nuevas mediante el
generador integrado de Codex, sin API key externa, Google AI ni cambio de cuenta.
La composición nativa conserva los bytes exactos del logo/referencia y los
originales; las conversiones JPEG se reprodujeron byte a byte en revisión.
Systems excluye media1, la antigua prueba de galería. News se limita a identidad
institucional y CTA a Humanizar: no inventa servicio periodístico, verificación
automática o aplicación funcional. Sinergia conserva sus imágenes históricas
PNG31 de Facebook y JPEG46 de Instagram; el nuevo ciclo no las vuelve a enviar.

Las afirmaciones se limitaron a fuentes actuales: Érgon es un servicio con demos
próximas, no una aplicación ya disponible; Prizma no promete integración DIAN
operativa; Sinergia no añade DIAN ni métricas ficticias. La referencia compartida
Mouseîon se conserva donde corresponde, sin inventar un logo exclusivo.

| Revisión independiente local en recurrence-20261020 | SHA256 |
| --- | --- |
|prizma-independent-review.md|a1ffb297267a152637c02f711fbcc080071703f95d6720dd7e2c1362ac03ac31|
|praxis-independent-review.md|175571a289320afc6c89035d554993cf11f28ac81c1d4cff4bea2a6710ce550c|
|ergon-independent-review.md|ea60638920a512b1aed4f99bd126f7e36e8c706ac3837b058794ff69dcbb8f59|
|systems-independent-review.md|1ca01ae4518fa1721c49538383a8cd548971aa5005ef8cacce9522eb5e9d49ed|
|news-independent-review.md|e25855472b7e75e4b9aa4abe6477935f80afba2444059b8984f372964276903e|
|sinergia-independent-review.md|9013c0ceb86873991236acb2a659b57f8c35856d43d2b6a7979d441e5292d23e|

Todos son PASS acotados locales, con inspección de materiales, contratos,
vínculos y preservación del historial. No acreditan envíos futuros, estado
mutable posterior al snapshot, elegibilidad futura, UI Brave o las cinco redes.

Los incidentes locales se conservaron sin replay de operaciones completadas.
El primer preparador News no se ejecutó: su revisión P2 exigió comprobar las
tres cuentas/scopes, toda la ventana y el vínculo exacto medio/brief antes de
mutar; V2 añadió esas guardas y pasó63 fixtures independientes. Dos constructores
locales anteriores se detuvieron por una comprobación de substring demasiado
amplia, antes de escribir el ejecutable o llamar a MCP. Una lectura inicial del
logo recibió PNG donde se esperaba SVG y se detuvo; el diagnóstico comprobó
los bytes PNG correctos. El raw externo de imagegen conserva permisos0640,
directorio0750; los artefactos privados de la tarea son0600/0700.
En Sinergia faltó CairoSVG antes de importar y se usó el renderizador ya presente;
un KeyError local posterior a prepare/get de conexión1 se resolvió leyendo sus
resultados guardados y continuando sólo2/3. No hubo replay del primer prepare.

La comprobación readonly de server2 terminó03:26UTC: timer17 active/waiting/
enabled, servicio oneshot inactive/dead/success entre ticks y12 fuentes runtime
coincidentes. Recibo `worker-runtime-readonly-20261020T032553042896-receipt.json`,
SHA256 `38ac17e5f85a6b7124b3f721c3c22874fdd236568c5dd048e90a87db1d475671`.
No se reinstaló, habilitó de nuevo ni lanzó manualmente. El preflight anterior
conserva29/32 y su frequency_limit en la fecha exacta de Chrónos; el cálculo
due+120s es sólo hipótesis. La misma fila se reevalúa al claim debido.
Las versiones locales descartadas de los correladores siguen conservadas;
para el resultado real se prepararon versiones revisadas que vinculan claims,
materiales, eventos, ACK y ticket, sin tratarlas aún como prueba de publicación.

Brave sigue ausente del inventario20Oct02:48UTC; no se utilizó Chrome ni IAB.
Las preguntas pendientes de reconexión, CAPTCHA y TikTok Developers permanecen
sin duplicación. X conserva cero gasto y no hay nuevas programaciones nativas
posteriores al15Oct confirmadas. El logo/perfil de Facebook Humanizar requiere
control total. IG10, vídeo con audio/revisión11, intentoIG4 y Graf vencido
conservan sus exclusiones. Producción, recuperación previa y secretos se
conservan; la aceptación global y compound siguenfalse.

### Chrónos19Oct: tres publicaciones reales de la misma cola

Invocación automática `2a5a15f297e546aca1a34c5907c3fb6d`, desde
1792467906.830648 hasta1792468005.3221,22:45:06–22:46:45Bogotá:
completed_sweep3 y finalización correcta. El operador no llamó a start,
enable, subida ni publicación. Se conservaron las mismas entregas20/21/22,
revisiones24/25/26, decisiones21/22/23 y media51. El timer seguía habilitado
y ya había completado barridos idle0 posteriores a las22:47.

| Destino | ID remoto | Fecha proveedor Bogotá | Enlace |
| --- | --- | --- | --- |
|Facebook Systems|1045986888587355_122128124091283523|19Oct22:45:12|https://www.facebook.com/122127579183283523/posts/122128124091283523 |
|Facebook Humanizar|110421192090737_1016657021471239|19Oct22:45:25|https://www.facebook.com/1008644758939132/posts/1016657021471239 |
|Instagram humanizar.news|17901547038603961|19Oct22:46:40|https://www.instagram.com/p/Des5gagDfPK/ |

El lector específico readonly V2 ejecutó tres GET Graph200 y tres GET CDN200.
Comprobó identidad, caption exacto, tipo IMAGE y fecha dentro de la ventana
original. No se refrescaron tokens ni hubo POST del lector. Los Facebook
sirvieron JPEG720x900 de34620bytes idénticos, SHA256
`8cbaf743fbd7e616ee2187e9cd309e3787a43283cfc5be017b9bd947ee0a2a59`;
Instagram sirvió JPEG1080x1350 de204247bytes, SHA256
`d9043d26bf2f9f264027217018edc6d8ee1f44021ebedb2315645f953da005af`.
Se inspeccionaron realmente los dos archivos distintos junto con el original
y el render de referencia118v4. Título, símbolo teal compartido, escritorio,
texto y footer Humanizar permanecen legibles y sin recortes. FB21 se cotejó
byte a byte con FB20. No se acredita vista UI Brave, aún ausente.

Recibo `remote-media-verify-20261020T034742012646-receipt.json`, SHA256
`6be9154196dbee8d8c4e889b0e6f1c186ca7566e7796b648b6eb2e7f8f779f2d`;
visual suplementario `chronos-cdn-visual-review-receipt.json`, SHA256
`e58552acd889c92a03f33dfd9cfc1efbafda7b1766746f571acdad4ea80a898a`.
El recibo original mantiene visual_content_reviewedfalse; la inspección real
posterior está en el suplemento, sin modificar la evidencia original.

La correlación local V3 del baseline de55 filas con POST1 confirma únicamente
tres claims/materiales, nueve eventos179–187 y ticket5 nuevos. Las otras52
entregas y13 grupos seleccionados de autoridad, contratos, medios e historial
quedaron iguales. Los starts20/21/22 son1792467910/7923/7933; sus ACK se
registraron en1792467919/7930/8004. Cada start superó el límite de frecuencia
de su cuenta dentro del primer tick, sin añadir eventos held en este ciclo. El
preflight29/32 a la fecha exacta se conserva como observación anterior, no
se reemplaza retroactivamente por este resultado real.

Ticket5 vincula media51, claim e intento de22 y quedó revocado en el ACK
terminal1792468004. No se observó ni solicitó su misma URL raw, no se midió
el fetch de Meta y no se afirma404. Los result_json PG siguen con
published_at_utc/permalink nulos: los valores públicos de la tabla proceden
de Graph. No se rellenó la base para hacer coincidir esta evidencia.
Recibo `chronos-dispatch-correlation-receipt.json`, SHA256
`33fae0fad3c71d19555486d74128ef9ef2e5564c0b11c8bef0e4625927fd57d4`.

Los dos snapshots PG posteriores, epochs1792468117.707246 y1792468317.965843,
conservan iguales55 entregas,22 claims,22 materiales de claim,5 tickets y153
eventos, hash canónico conjunto
`45ad1b5afcc2aaa633caf5bd86135eee26ffb99e595232e943bdbc15096a1fc0`.
Tres invocaciones idle0 completas quedaron estrictamente entre esos epochs:
`9998854b8eb54ac68efb906659e265fc`, `31ee487d2c82443cb833693ad4608fdb`
y `02ad747670724f3f96e5ea835768682e`. Diario raw y resumen tienen hashes
distintos cotejados; no se atribuye al resumen el hash raw de su campo sha256.
El comparador V4 terminó correctamente y referencia la medición runtime
03:25UTC anterior al envío, con12 pins cotejados y fuentes locales conservadas;
no la presenta como otra medición remota posterior al despacho.

La correlación de run_once/CLI, los pins, los idle0 y esas cinco tablas iguales
sustenta cero POST social adicional de ESOS procesos. No prueba cero HTTP de
control, contador global, igualdad de toda la base ni lectura directa del outbox.
POST1 SHA256 `15814e6abc46ee77e7c02c290c403e353726d8b0793174930dfd75b20a3a46c9`;
POST2 SHA256 `2ca93ba9158ddc49df55b5a833108814c1a227a1f6c4d7f3a97ce03c62d83a9d`;
recibo `chronos-postdispatch-idle-comparison-20261020T035452449732-receipt.json`,
SHA256 `7398a7fa887cdf44b550e792ced30a5ee736f102dc5c4081a61bb4fd66a5a53b`.

La cuota app consultada20Oct03:47UTC fue71% semanal usado/29% restante,
ordinaryUsageAllowedtrue, cuenta actual terminada en6fd3. ai-usage conserva
Codex desconocido y no se reactivó el sondeo local. La revisión del despacho
usa un agente Codex nativo/heredado de esa misma cuenta en Kratos; no cloud,
cambio de cuenta/proveedor, nueva API facturable ni gasto API adicional.
Es una lectura fechada, no una garantía de cuota futura.

La revisión independiente del despacho real terminó **PASS ACOTADO**, sin
hallazgos P1/P2 en las correlaciones revisadas. Recalculó42 fuentes, contratos,
hashes de solicitudes/respuestas, claims, materiales, eventos, ACK, ticket y
comparaciones; vio realmente los dos CDN distintos, original y referencia.
Sólo hizo lecturas y cálculos locales, sin ejecutar operadores originales o
consultar upstream. Informe `chronos-dispatch-independent-review.md`, SHA256
`cd9bd1abb457702c159cee89a302eebfc49d042bf25bf1a6a1767b263895b9ab`;
manifiesto `chronos-dispatch-independent-review-manifest.json`, SHA256
`3b550153f3e0a8d7882efdb12026c105292789f65004c795ef9ea1273cda453a`.
No extiende el PASS a Brave, fetch de Meta, toda la base, outbox directo,
stock futuro ni cinco destinos/17productos. El siguiente ciclo ya existente
es Koinonía20Oct22:45–23:45Bogotá, entregas23/24/25; conservar sus filas y
fechas. La meta global y compound siguen incompletos/bloqueados.


## Corte del 21 de octubre de 2026 — Koinonía publicada automáticamente

Ciclo local del 20 de octubre, ventana original 22:45–23:45 Bogotá,
due1792554300/expires1792557900. Se conservaron las entregas23/24/25,
revisiones27/28/29, decisiones24/25/26, campaña11/proyecto15/marca117v4 y
media52. JPEG1080×1350,306481bytes, SHA256
`36372e33a87ee181bb25277361082b1d44746012eb56d727a7b88c2a6febe4fd`.
No se crearon filas, se movieron fechas ni se repitieron evaluaciones editoriales.
La revisión original de Koinonía conserva su alcance de piloto y su atestación
client_reported; la aprobación owner de galería permanece separada y pendiente.

### Requisitos actuales y ejecución

El preflight readonly comprobó release, propietario4, política2, grants4/5/6,
permisos, caducidad, tres conexiones activas, medio y contratos exactos. Instagram
respondió GET200 con la cuenta humanizar.news y consumo1/100 en86400s. El GCS
original se leyó por generación1792378414133447 con hash y dimensiones exactos,
sin cambios antes/después. Las12 fuentes runtime remotas coincidían con las
locales/calificadas a las03:05UTC, antes de la ventana; no es otra medición
remota postdispatch. Los snapshots readonly no alteraron la autoridad o el medio.

El primer tick debido, invocación `cf96d2b466754360969bcbb1b2f655bd`,
22:45:04–22:45:06Bogotá, terminó idle0. La observación de frecuencia en la
fecha exacta y las hipótesis de elegibilidad futura se conservaron; no se
adelantó el envío. La siguiente invocación automática
`0bf0d36267514668ba8b9bec0bfb2dce`,22:46:09–22:46:46Bogotá, terminó
completed_sweep3/exit0. El operador no llamó a start/enable ni realizó envíos.
El timer sigue active/waiting/enabled; oneshot inactive/dead/success entre ticks
es normal. No se reinstaló o habilitó nuevamente.

| Destino | ID remoto | Fecha del proveedor en Bogotá | Enlace |
| --- | --- | --- | --- |
| Facebook Systems | 1045986888587355_122128210719283523 | 20Oct22:46:14 | https://www.facebook.com/122127579183283523/posts/122128210719283523 |
| Facebook Humanizar | 110421192090737_1017574441379497 | 20Oct22:46:25 | https://www.facebook.com/1008644758939132/posts/1017574441379497 |
| Instagram humanizar.news | 18032533778857826 | 20Oct22:46:41 | https://www.instagram.com/p/DeveaqZFRd9/ |

### API, medios servidos y límites

Tres GET Graph200 confirmaron autor, caption exacto, fecha e imagen, y tres GET
CDN anónimos dieron200. Facebook sirvió dos JPEG720×900 de46514bytes idénticos,
SHA256 `9f0463594db344416d71a5b6e75b15ded64a3a07abe1127255d10afb3d564947`.
Instagram sirvió JPEG1080×1350 de280375bytes, SHA256
`2974519ac425e128d58e729a6497ff67c89c30fe1faaa7b02e0e987695b2f1d7`.
Se inspeccionaron realmente ambos archivos distintos junto con el original
preservado y la referencia oficial117v4. Logo, título, escena de comunidad,
texto y pie Humanizar permanecen íntegros y legibles; FB24 es idéntico aFB23
byte a byte. El recibo original del lector conserva visual_content_reviewedfalse;
la inspección posterior se registra en un suplemento, sin reescribir el original.

Recibo `remote-media-verify-20261021T035218431751-receipt.json`, SHA256
`dcd6f4c92164e52d624c0d33c7ce40b3565ccea5173cfa12febeb3539dbaf82f`;
suplemento `koinonia-cdn-visual-review-receipt.json`, SHA256
`27ccaa5788be65096a0e7fde446f93b62ebb434de34a34b795612993857ee35d`.
No se acredita UI autenticada de Brave. El inventario de02:49:35–02:52:04UTC
sólo mostró Chromeid5; no se seleccionó ni operó Chrome/IAB. La precisión
horaria del bootstrap se corrigió con un suplemento sin modificar su original.
No se repitió la petición de reconexión ni las preguntas humanas pendientes.

Los starts23/24/25 son1792554372/4384/4393 y sus ACK1792554381/4390/4404.
Cada start superó la frecuencia aplicable;24horas entre fechas programadas no
se usaron como prueba de elegibilidad. Los result_json PG mantienen
published_at_utc/permalink nulos: fechas y enlaces públicos proceden de Graph,
sin rellenar la base para hacerla coincidir. Ticket Instagram6 está vinculado
al claim/intento/media52 y quedó revocado en ACK1792554404, antes de caducar.
No se observó ni pidió su misma URL raw, no se midió el fetch de Meta y no se
afirma404.

### Conservación de filas y ausencia acotada de repetición

La correlación real V4 del baseline con POST1 confirmó sólo3claims/materiales,
9eventos188–196 y ticket6 nuevos. Las otras52 entregas y13 grupos seleccionados
de autoridad, contratos, medios e historial se conservaron iguales. El primer
tick idle no añadió nuevos eventos held. Recibo
`koinonia-dispatch-correlation-receipt.json`, SHA256
`f338cee7bb4dba6b6f8345f51534fb4dad20aa48c53ff73a873b6868b9280c2d`.

POST1/POST2, epochs1792554507.127121–1792554792.899166, conservaron iguales las
cinco tablas seleccionadas:55deliveries/25claims/25materials/6tickets/162events.
Hash canónico conjunto
`927338b81e15ca85f4a9499c4ae07b9aef3242ecd782fa6eb4c8de5dc5cb286c`.
Cinco invocaciones idle0 completas quedaron estrictamente entre ambos epochs:
`169920efc252426cbfcdf9e2627a5805`, `e4051b1275fc4e5097f68139b86ab731`,
`13362b6cbd964f24b523e0d922f5fd59`, `c50ee4c102f1483884c88a80b19b0ece`
y `f73a1dfe15d146faba696c062981e342`. El resumen se cotejó con el diario raw;
sus hashes son distintos y el campo sha256 del resumen corresponde al raw.
Recibo `koinonia-postdispatch-idle-comparison-20261021T035719784566-receipt.json`,
SHA256 `10b90cff6add9ea431d3b508a5059d192a57b2a903e5a45652cf05bfda63477d`.
La correlación de esas ejecuciones con run_once/CLI, los12 pins predue y las
cinco tablas iguales sustenta cero POST social adicional de ESOS procesos;
no es contador global, cero HTTP de control, igualdad de todaDB ni lectura
directa del outbox.

Las30 entregas futuras26–55 siguen held/frequency_limit, sin start, claim,
intento, lease, resultado o worker. Son10ciclos existentes para21–30Oct, no
publicaciones ni elegibilidad garantizada; se reevalúan esas mismas filas al
claim debido. Recibo `current-future-ten-cycles-receipt.json`, SHA256
`a610d06daddbbdd37233aca3e4320907467e86dd525ecb765e99a8607ac7e822`.
El siguiente es Cauce21Oct22:45–23:45Bogotá, entregas26/27/28, media53, con
sus fechas originales. IG10, intentoIG4, vídeo2/revisión11 y Graf16Oct vencido
conservan sus exclusiones. Los envíos históricos no se repitieron.

La cuota app actual21Oct03:56UTC fue18%semanal usado/82%restante,
ordinaryUsageAllowedtrue, cuenta actual terminada en6fd3. ai-usage Codex
permanece desconocido por sondeo deliberadamente apagado, sin reactivarlo.
Se reutilizaron agentes Codex nativos/heredados de esa misma cuenta en Kratos,
con un escritor por archivo y revisión por área; no cloud, cambio de cuenta o
proveedor, generación nueva de imágenes, gasto API o despliegue nuevo.
La revisión estática de operadores detectó y corrigió localmente unP2 de
intervalos del observador antes de su uso: V4 exige que el resultado esté dentro
de su propia invocación; V3 se preservó y no se ejecutó contra esta evidencia.


La revisión independiente del despacho real terminó **PASS ACOTADO**, sin P1/P2
abiertos en las correlaciones actuales:2041comprobaciones mecánicas sobre46
archivos, contratos y materiales recalculados y los dos CDN distintos vistos
junto con original y referencia. El revisor sólo leyó y calculó localmente;
no ejecutó operadores originales ni consultas remotas. Informe
`koinonia-dispatch-independent-review.md`, SHA256
`2fb7822a88a299c1008f7d9acc0b427784708348d61318c4bba869a08cf5cf96`;
manifiesto `koinonia-dispatch-independent-manifest.json`, SHA256
`efb6acb7b161e834759742d172c7ef9d8babafacb9035080acd28201cb828a89`.
El tipo IMAGE de Instagram está capturado directamente; la attachment photo
única de Facebook fue validada por la guarda del lector congelado, pero su
subconjunto público no retiene attachments/type ni el cuerpo raw Graph. Los
headers y el carácter anónimo del CDN se sustentan en el contrato de ejecución,
no en captura de paquetes. Se conservan estos límites sin repetir lecturas.

La consulta de cuota de cierre04:00:24–04:00:46UTC registró19%usado/81%restante
para la misma cuenta y ai-usage Codex desconocido con sondeo apagado. No se
cambió de cuenta/proveedor. El seguimiento diario21:45Bogotá permanece activo;
la meta global y compound siguen incompletos, con X/TikTok y la publicación
verificada de los 17 productos todavía pendientes de cobertura completa.


## Cauce21Oct — publicación automática y evidencia del 22 de octubre

**Ciclo Meta completado; meta global incompleta.** Se conservaron las entregas
26/27/28, revisiones30/31/32, decisiones27/28/29, campaña7, proyecto11 y marca113v4.
Media53 es el JPEG de 1080×1350 y220534bytes, SHA256
`50e5f3070d502424363fe0c057850bad96c73c97f2cd4af932c23cf171bf6bb8`.
No se reimportó contenido, creó una revisión nueva, cambió una fecha ni inició
manualmente el servicio. La ventana original fue21Oct22:45–23:45Bogotá.

Los barridos de22:45 y22:46 terminaron idle0; no publicaron. Los límites PG de
24horas se cumplían a22:46:12/24/33 según destino. La invocación automática
`2394feab3c0047c294dc1ead9c865f97` corrió de22:47:03.650752 a22:48:44.034759,
con completed_sweep3 y salida normal. Los starts fueron1792640832/0842/0851;
son distintos de las fechas públicas siguientes, verificadas con GraphGET200.

| Destino | ID remoto | Fecha pública en Bogotá | Enlace |
|---|---|---|---|
| Facebook Systems |1045986888587355_122128310061283523|21Oct22:47:14|[Publicación](https://www.facebook.com/122127579183283523/posts/122128310061283523)|
| Facebook Humanizar |110421192090737_1018504701286471|21Oct22:47:23|[Publicación](https://www.facebook.com/1008644758939132/posts/1018504701286471)|
| Instagram humanizar.news |18108880826209002|21Oct22:48:38|[Publicación](https://www.instagram.com/p/DeyDUdxDS5J/)|

Graph confirmó autor y caption exactos. El lector multimedia acotado descargó
los tres CDN mediante GET anónimo200. Facebook sirvió dos JPEG720×900 de35769bytes
idénticos, SHA256
`5184803b8a30a62606aee3272d1c19ba46bbcb1eaa79fd1f977bca4c1de0448b`.
Instagram sirvió un JPEG1080×1350 de197403bytes, SHA256
`b3320de6041bd202c8a9d36ae4f019337c078963005d123423850b255c78cb87`.
El coordinador vio ambos archivos distintos, además del original y referencia:
logo CauceV3, composición, textos y pie Humanizar íntegros. Es evidencia
API/CDN e inspección de archivos; no acredita la interfaz de Brave. El subtipo
photo de Facebook fue validado por la guarda del lector; el recibo público no
retiene attachments/type ni el cuerpo rawGraph para una lectura posterior.

El snapshot POST1, epoch1792640922.978037, ya contiene los tres ACK, pero antecede
al FINISH de la invocación por unos1.06segundos. Por eso la correlación del envío
usa PRE→POST2, epoch1792641166.455859, que sí contiene la invocación completa.
POST1→POST2 se usa sólo para comparar las cinco tablas y los idle0 completos.
No se cambió una captura ni se repitió una consulta para acomodar ese límite.

Las otras52 entregas y13 grupos seleccionados permanecieron iguales. Sólo se
agregaron tres claims/materiales, nueve eventos197–205 y ticketIG7, revocado
al ACK1792640922. No se observó ni solicitó su misma URLraw; no se acredita
404 ni se midieron bytes descargados por Meta. PG conserva published_at_utc y
permalink nulos en result_json: fechas y enlaces públicos proceden de Graph.

Entre POST1 y POST2 quedaron cinco idle0 completos:
`5971486d79dc4491a6a960f48e767bfb`, `1bf75f79ccd34bc09b5c2252a592c750`,
`384feacf19e646689b5b41b9e547efcd`, `a781962a26734cf8afa06d63540e8985` y
`275c2dae16a344fbb08c4ade678dca06`. Las cinco tablas seleccionadas fueron
idénticas:55deliveries/28claims/28materials/7tickets/171events, hash canónico
`599d436fae280e18cec4237d40b2f553066f4629048805188b4c9241ded5f83f`.
La correlación con run_once/CLI y12pins medidos antes de la ventana sustenta
cero POST social adicional de esos procesos idle; no es un contador global,
una lectura directa del outbox, igualdad de todaDB o cero HTTP de control.
No incluye el cierre de la invocación publicada como si fuera un idle0.

La comprobación previa actual cotejó58diagnósticos, actor/política/grants,
revisión desplegada, doce fuentes, media53 por generaciónGCS1792378773498324,
seis materiales locales y logo113v4. Instagram respondió como humanizar.news,
con cuota1/100. Su primer lector de materiales se lanzó por error antes de
existir el snapshot PG y se detuvo localmente en max(empty), antes de upstream.
Se conservaron fallo e intención; una ejecución correctiva posterior al PG
completó la lectura del objeto exacto. No se repitió una operación upstream
ya completada. El wrapperV1 tenía un timeout que podía impedir finally;
se preservó y corrigió antes de uso, con revisión local de nueve fuentes,
246comprobaciones y49referencias. Estos controles no acreditan publicaciones
por sí solos. La revisión independiente LOCAL de las evidencias reales terminó
PASS acotado, sin P1/P2 nuevos: 2370 comprobaciones sobre 89 fuentes, con rehash
de cierre y visión real de los dos CDN, original y referencia. No ejecutó
operadores originales ni consultas remotas; no extiende el resultado a Brave,
fetch de Meta, tráfico global, todaDB, cinco destinos, 17productos o futuros envíos.

Recibos relativos a la raíz privada habitual, sin secretos en Git:

- `daily-timer-20261022-cauce/remote-media-verify-20261022T035149521351-receipt.json`, SHA256`bd9dc6c016b1ce6516835890221d3f5c27769613484dacf9da36f3cfcbd66973`.
- `recurrence-20261022/cauce-cdn-visual-review-receipt.json`, SHA256`075e7b3525130027abfd4981643fc0f06dcd73b5ce7b0c194044219e636b4110`.
- `recurrence-20261022/cauce-dispatch-correlation-receipt.json`, SHA256`e29fea78afcd7d2c303a5302c8618374a6afe993eebc128d9f991c6f4ce878fc`.
- `recurrence-20261022/cauce-postdispatch-idle-comparison-20261022T035623753687-receipt.json`, SHA256`627aa7e7a0b72a5ffe29010e0279c65770ea5068969fd101ffc311b673882c3e`.
- `recurrence-20261022/current-future-nine-cycles-receipt.json`, SHA256`d832023a40245826a3e4ea9e1d6ae3de23b206743a57c295ed165450ed9fe254`.

Quedan nueve ciclos existentes22–30Oct:27filas29–55 held/frequency_limit,
sin start/claim/attempt/lease/worker/resultado. Aletheia22Oct22:45–23:45Bogotá
es el próximo; media54 y entregas29/30/31 conservan sus fechas y contratos.
El claim reevalúa las mismas filas; no se garantiza elegibilidad futura.
La planificación de17productos sigue separada de publicación y recurrencia.
Los holds deIG10, intentoIG4, vídeo2 y Graf vencido continúan intactos.
Brave sigue ausente del inventario actual; sólo se observó Chrome5 y no se
operó. No se repitieron las preguntas humanas ni se usó Chrome/IAB como
sustituto. X/TikTok y el control total del perfil Facebook Humanizar conservan
sus pendientes. No hubo redeploy, generación, gasto API nuevo o POST social
del operador; el envío real lo hizo el timer existente. El seguimiento diario
permanece activo y la meta completa permanece bloqueada e incompleta.


Revisión independiente de Cauce:

- `recurrence-20261022/cauce-dispatch-independent-review.md`, SHA256`09048a0bd71cc232a1cd1bf287c42552e95ebddfed544234db6ed141200e938e`.
- `recurrence-20261022/cauce-dispatch-independent-review-manifest.json`, SHA256`e42e0ffccd1be575ee77810796f85947b44504492ae578836b8a36fd1d81450f`.


## Verificación recuperada el24Oct — Aletheia22Oct publicada por el timer

Las entregas originales29/30/31 se publicaron dentro de22:45–23:45Bogotá,
sin start manual ni reenvío. Los tres ticks22:45/22:46/22:47 fueron idle0;
la invocación `f9cc60bc9e5a4a44b9d361ca672aeb4c`,22:48:13.699–22:49:02.610,
terminó completed_sweep3/exit0. Los starts1792727302/7314/7326 superaron
los límites de frecuencia observados previamente; no se agregaron eventosheld.
La observación interactiva del23Oct se interrumpió antes de la ventana, por lo
que se recuperaron sólo lecturas el24Oct: no se atribuye observación en vivo
al momento del envío ni se ejecutaron otra vez los envíos.

GraphGET200 confirmó autor, caption exacto, IDs y fechas del proveedor:

| Destino | ID | Fecha Bogotá | Enlace |
| --- | --- | --- | --- |
| Facebook Systems |1045986888587355_122128412079283523|22Oct22:48:24|https://www.facebook.com/122127579183283523/posts/122128412079283523|
| Facebook Humanizar |110421192090737_1019457814524493|22Oct22:48:36|https://www.facebook.com/1008644758939132/posts/1019457814524493|
| Instagram humanizar.news |18131792683695958|22Oct22:48:56|https://www.instagram.com/p/De0oQm2lfAd/|

Los tres CDN anónimos devolvieron200. Facebook sirvió dos JPEG720x900/35158B
idénticos SHA256 `66170f3515234cd6704b517ab7ad5fa88e3acfe18578e7b83d61f19b56bdaac0`;
Instagram1080x1350/202007B SHA256
`1d0ca16b75cd4ae2845dbb8b8b52fdce2f5a7f05103c0cbe9b7913af5dbe6e76`.
Se vieron ambas imágenes distintas, JPEG54 original y logo115v4: composición,
textos y pieHumanizar conservados. Es evidencia API/CDN/archivos, sin interfaz
Brave. Los enlaces y fechas proceden deGraph; `published_at_utc` y `permalink`
siguen nulos en el resultadoPG. La guarda valida photo/IMAGE en memoria;
no se retuvo rawbodyGraph ni attachments/typeFacebook. TicketIG8 revocado
al ACK1792727341, sin observar o solicitar su misma URLraw, sin404 ni medición
del fetch de Meta.

PRE→POST2 conservó otras52entregas y13grupos seleccionados; sólo añadió
3claims/materiales,9eventos206–214 yticket8. POST1→POST2 del24Oct, epochs
1792810225.572857–1792810654.560624, dejó idénticas cinco tablas seleccionadas:
55deliveries/31claims/31materials/8tickets/180events, SHA canónico conjunto
`29ec70ec7cffd1895683910ad3fd5144f23771d9523705e879e2316805676fa2`.
Siete invocaciones idle0 completas quedaron dentro del intervalo. Junto con
run_once/CLI y12pins medidos23Oct03:04UTC, esa correlación sustenta cero POST
social adicional de esos procesos; no es un contador global, todaDB, outbox
directo o medición remota actual del runtime después del envío. El journal usa
dos intervalos disjuntos:22Oct22:44–23:46Bogotá y24Oct02:48–02:57UTC. No cubre
el hueco entre ellos. Los hashes del RAW y resumen se conservan por separado.

Recibos reproducibles, sin credenciales ni URLs firmadas:

- `remote-media-verify-20261024T025601900337-receipt.json`: `fd0cb57cd8c724fc8ba2fe691f83aa95a98c178b9e4eef35c2e50f7fd41d4b68`.
- `aletheia-cdn-visual-review-receipt.json`: `5e8e6e072af08d82910c052da447eb89606c4e1a1e32fa090ee2a0006829821f`.
- `aletheia-dispatch-correlation-receipt.json`: `e5e6268e4236f7f6cad8219e4dab27e1438cfa13dbfa7c5d92f64d6a4868a679`.
- `aletheia-postdispatch-idle-comparison-20261024T030026108204-receipt.json`: `9b06be5342e6e41326b7301553bd78cb61c5750aed7d74b6fd9eece1ff0cd892`.

Las proteccionesIG10, intento4, vídeo2 y Graf16Oct vencido permanecen intactas.
La meta de cinco destinos y17productos continúa bloqueada e incompleta.

La revisión independiente local terminó **PASS acotado**, sin P1/P2 reproducidos:
33fuentes recalculadas, cuatro imágenes realmente vistas, contratos,3/3resultados,
9eventos,52otrasfilas/13grupos y cinco tablas con siete idle completos. Informe
`aletheia-dispatch-independent-review.md` SHA256
`0256bf1295f6eaa3cb6aeba525251f1b6501afa626be0eab5187e344f2beded4`; manifiesto
`aletheia-dispatch-independent-review-manifest.json` SHA256
`a2934d5f40008be014fda1ec9a8e4ab63b096dfa4009220b97fa45c4723900f0`.
El revisor no hizo consultas upstream ni ejecutó main originales. El PASS no
amplía los límites anteriores ni acredita cinco destinos o17productos.
