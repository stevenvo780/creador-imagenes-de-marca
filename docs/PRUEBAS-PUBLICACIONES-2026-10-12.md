# Pruebas reales de publicaciones — 12 de octubre de 2026

Tenant Humanizar: 17. Fecha local: America/Bogota. Las publicaciones de prueba
no acreditan todavía una recurrencia diaria activa en todas las redes.

## Resultado comprobado por destino

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
