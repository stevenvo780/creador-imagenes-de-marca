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
