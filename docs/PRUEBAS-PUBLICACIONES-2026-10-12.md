# Pruebas reales de publicaciones — 12 de octubre de 2026

Tenant Humanizar: 17. Fecha local: America/Bogota. Las publicaciones de prueba
no acreditan todavía una recurrencia diaria activa en todas las redes.

## Resultado comprobado por destino

| Destino | Prueba de imagen | Vía | Recurrencia nueva |
|---|---|---|---|
| Facebook Humanizar Systems | Publicada y visible | Worker canónico en server2 | Pendiente de activación |
| Facebook Humanizar | Publicada y visible | Worker canónico en server2 | Pendiente de activación |
| X @HumanizarSystem | Publicada y visible | Brave, sin gasto API | Pendiente de automatización del cliente |
| TikTok, cuenta confirmada por el operador | Creada; Studio retiró «Contenido en revisión» y muestra «Todo el mundo» | Brave / TikTok Studio Fotos | Pendiente; API de desarrollo bloqueada |
| Instagram @humanizar.news | PNG retenido antes del inicio; JPEG posterior quedó incierto antes de la fase de proveedor | Worker canónico en server2 | Pendiente de corrección y prueba real |

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

El servicio aislado está instalado en server2. Durante pruebas controladas se
creó temporalmente el marcador de habilitación; se retiró al terminar. El timer
nuevo y los dos timers legacy permanecen deshabilitados e inactivos.

El primer barrido publicó las dos fotos de Facebook y retuvo el PNG de
Instagram por formato no admitido. El segundo barrido procesó cero entregas
nuevas: el outbox mantuvo exactamente las dos filas de fases de Facebook.
Se verificaron los dos posts en Brave además de sus IDs y recibos del proveedor.

Las tres conexiones activas y la política de calificación de 24 horas permiten
pruebas acotadas; no sustituyen grants duraderos, stock nuevo y ejecución diaria.
La política y los grants de calificación vencen el 13 de octubre a las
17:28:39 de Bogotá. No se rotan mientras el intento iniciado de Instagram
necesite resolverse con su grant original.

## Fallo de Instagram y reparación necesaria

Delivery 3 quedó retenido antes de `started_at`: el formato era PNG. Se importó
un JPEG nuevo y se obtuvo una evaluación editorial nativa nueva para delivery 4.
El worker confirmó el inicio de delivery 4, pero no obtuvo la capacidad de
entrega antes de entrar a `dispatching`.

La revisión de API desplegada `eikon-00066-gmp` carece de las dos variables
`EIKON_PUBLICATION_MEDIA_DELIVERY_ENABLED` y `EIKON_PUBLICATION_MEDIA_ORIGIN`.
La ruta de emisión valida ese gate antes de crear el ticket. El outbox original
mantiene `start_confirmed`, cero filas de fases para ese intento —también se
cuentan fases sin recibo— y ningún remote_id. La primera clasificación
`network_timeout` era demasiado amplia; ocultaba también errores HTTP de API.
La segunda ejecución conservó incertidumbre y no añadió fases de proveedor.

La corrección preventiva añade readiness autenticado antes del inicio y
diagnósticos acotados. La revisión independiente fue aprobada; 367 pruebas de
regresión SQLite/PostgreSQL y 121 del worker final pasaron. Dos observaciones
menores posteriores quedaron corregidas con diez pruebas focales aprobadas.
El logging y la entrega de media tienen además 40 pruebas locales aprobadas;
esto no acredita aún una descarga real de Meta ni la revisión de API nueva.
La corrección no recupera el intento antiguo ni concede otro POST.
Cerrar ese intento requiere cuarentena durable, evidencia del worker original,
verificación de cero tickets históricos de API y calificación explícita del owner.
No se deben editar SQLite, fabricar un recibo remoto o crear otra revisión con
el mismo SHA para evitar el guard.

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

La meta permanece abierta: cerrar Instagram, verificar su primer envío,
preparar contenido nuevo y activar la programación diaria con deduplicación y
seguimiento de permisos. No se declara «todas las redes automatizadas» con
estos resultados parciales.
