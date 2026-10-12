# Meta: Eikón como centro de marca y publicaciones

Creada por instrucción del operador el **11 de octubre de 2026**, America/Bogota.
Estado de trabajo: **plan aprobado; implementación con subagentes en curso**.
La entrega de identidad y galería se conserva; el objetivo completo sigue pendiente. La meta del chat es el seguimiento principal; este documento
conserva requisitos, avances y evidencia del repositorio.

## Resultado esperado

Cada empresa organiza sus productos, conserva sus logos y conecta su propio
Codex y sus redes. Una IA evalúa las piezas completas y decide su publicación
dentro de la política autorizada por empresa. El calendario y panel muestran
pendientes, bloqueos y resultados reales. Humanizar es la primera empresa;
Facebook, Instagram, TikTok y X forman parte de la aceptación por canal, con
las restricciones de consentimiento y gasto indicadas abajo.

## Requisitos y aceptación

| Punto | Resultado comprobable | Estado inicial al 11 de octubre |
|---|---|---|
| Identidad de producto | Familia Humanizar común, originales exactos, estados correctos y variación acotada por producto | 15 marcas; 9 referencias originales; 6 referencias por resolver. Corrección de frontend y perfil de familia en desarrollo. |
| Producción | Pieza final con texto, imagen y formato; retícula y contraste comprobados; procedencia Codex | 15 ilustraciones pendientes de revisión. Hay estudio y MCP; falta completar piezas de campaña. |
| Campañas | Proyecto, objetivo, secuencia y variantes por destino; autorización de cada revisión completa | Subsistema aún no implementado. |
| Calendario | Fechas con zona, retenciones visibles, reserva concurrente y recibos por destino | Publicador externo existe; Eikón no tiene calendario. |
| Conexiones | Cuentas de cada empresa, identidad remota comprobada, permisos y vencimientos visibles | Accesos Humanizar externos; no hay módulo social multiempresa en Eikón. |
| Panel operativo | Crear, revisar, programar, corregir y comprobar resultados desde el mismo recorrido | Pantallas actuales de proyectos/marcas/estudio/galería; falta el recorrido integrado. |

## Entregas

1. **Familia e identidad en el flujo existente.** Corregir el estado de logos
   importados; introducir perfil Humanizar explícito y composición coherente,
   conservando otras familias. Pruebas, revisión independiente y QA cliente.
2. **Campañas y autorización completa.** Revisiones inmutables de imagen,
   caption, cuenta y horario; revisión owner y bandeja de trabajo para Codex.
3. **Conexiones, calendario y trabajador.** Primero Humanizar/Facebook, luego
   Instagram según stock y permisos. Cuentas y credenciales aisladas por empresa.
4. **Panel y ampliaciones elegibles.** Estados, conciliación y retirada; después
   métricas disponibles, vídeos/reels y TikTok. X conserva la decisión de no gasto.

La segunda y tercera entrega siguen el
[diseño del centro](superpowers/specs/2026-10-11-eikon-centro-publicaciones-design.md),
pendiente de revisión del documento y posterior plan. La primera corresponde al
diseño visual acotado presentado y confirmado en el chat.

## Restricciones permanentes

- No redibujar logos oficiales ni cambiar propietario de marcas existentes.
- Codex genera desde el cliente; MCP entrega encargos y recibe archivos. El
  timer del servidor no invoca una herramienta integrada de imágenes ficticia.
- Subir una imagen, fijar identidad o puntuarla no equivale a aprobación editorial.
- No ampliar silenciosamente los permisos de las claves Codex ni devolver secretos.
- Conservar el historial, las retiradas y la protección contra repeticiones.
- No utilizar la cola Humanizar como una base compartida entre empresas.
- No reactivar el calendario antiguo con imágenes repetidas o borradores pendientes.
- No introducir proveedores pagados, comprar créditos X ni considerar revisiones
  de TikTok/Meta resueltas sin evidencia externa.

## Evidencia inicial

El 11 de octubre se verificó por API la empresa Humanizar (tenant 17): 17
proyectos, 15 marcas de producto, 9 referencias de logo, 15 medios pendientes,
12 versiones rechazadas preservadas y 1 medio aprobado de la entrega anterior.
La API desplegada no contiene rutas de campañas, calendario, publicación u OAuth
social. Es una lectura de estado; no acredita implementación de esos subsistemas.

Facebook: cuatro repeticiones retiradas por autorización del operador; las dos
originales permanecen. Los dos timers de server2 están deshabilitados y las ocho
entregas antiguas repetidas retenidas. Ver el informe canónico en ComercialHumanizar:
`docs/INCIDENTE-PUBLICACIONES-REPETIDAS-20261011.md`.

## Avance verificado: primera entrega, 11 de octubre

- Frontend distingue logo original, procedural e identidad pendiente; la
  fijación de logo no equivale a aprobación editorial de las piezas.
- Perfil Humanizar explícito, Manrope, contraste y espaciado común. Las marcas
  de otra familia conservan su comportamiento. La fila de la empresa prevalece
  sobre archivos antiguos cuando el perfil está seleccionado, incluso con
  slugs coincidentes.
- Publicación vertical 1080×1350 disponible en Estudio y catálogo, con retícula
  efectiva de doce columnas y logos originales sin recorte. Las variantes de
  cuatro y ocho columnas siguen siendo metadata, no layouts implementados.
- Revisión independiente aprobó las correcciones y el recorrido HTTP
  `202 → plan 200`, con respuesta 404 para otra empresa.
- Suite completa: **867 aprobadas, dos omitidas** por artefactos de demostración
  ausentes; PostgreSQL de prueba aislado habilitado. Pruebas finales añadidas:
  **45 aprobadas**, incluyendo PostgreSQL. Frontend: **67 aprobadas** y build
  TypeScript/Vite correcto. Ruff de archivos nuevos y mypy focal pasan.
- Navegador local: acceso, tres estados de marca y generación vertical
  verificados. Se descargó PNG 2160×2700, pero la inspección descubrió recorte
  en preview, logo demasiado pequeño y pie fuera del PNG. Corregidos con TDD:
  marco de preview, ancho útil de logo 231 px y mínimos del body fijados al
  viewport. Frontend final: **75 aprobadas**, build correcto; core final:
  **24 aprobadas**. Revisión independiente aprobada. La comprobación visual
  posterior a esos cambios se detuvo otra vez por panel de extensión.
- Respaldo privado fresco de producción restaurado en un clon sin red:
  init_db dos veces conserva filas y columnas. Imagen Docker local construida.
  No se ha desplegado esta entrega ni cambiado marcas reales.

La meta permanece activa. Campañas, revisión completa, conexiones, calendario
y panel siguen pendientes del diseño escrito y posterior plan de ejecución.

## Continuación: referencias y preparación de las marcas

La lectura fresca por API vuelve a confirmar quince marcas de producto, nueve
referencias originales y cero perfiles Humanizar seleccionados. Se verificaron
los nueve hashes locales contra las referencias remotas.

Se exportaron desde código existente el símbolo de Cauce y el glifo de Aletheia,
con hashes de archivos/fragmentos y revisión independiente. Aletheia no se
presenta como firma completa: el glifo no incluye nombre ni caja externa.
Ambos permanecen pendientes de revisión visual. Ver
`docs/brand-references/2026-10-11-existing-marks/README.md`.

El perfil admite ahora un modo inicial explícito `texts.family_mode` para
conservar visible una firma clara, como la de Agentes, en fondo oscuro. La
selección no cambia los bytes originales. Siete casos nuevos revisados pasan;
core completo de familia y exportaciones: **36 aprobados**. Se prepararon
los cambios de metadata para las quince marcas, sin aplicarlos ni aprobar medios.

Siguen pendientes la comprobación visual final, el despliegue de esta entrega
y la revisión del diseño escrito para preparar el plan de los módulos nuevos.

## Entrega de identidad desplegada, 19:36 UTC

Se cerró la comprobación visual local del PNG vertical, pie, logo horizontal
y vista móvil. Se comprobaron además Agentes con fondo oscuro y Cauce con su
símbolo original recuperado. El observador de descarga agotó su tiempo, pero
el archivo nuevo descargado fue localizado y verificado por píxeles y SHA.

Código `0d1a9bc7bef918a619cf06896dd9cc4d68c80727` desplegado en
`eikon-00059-9h5`, tráfico 100%, sin tags; configuración y permisos conservados.
Tres orígenes sirven el frontend exacto de la imagen; owner17 funciona y el
acceso anónimo a marcas continúa rechazado. La GUI de producción sigue
pendiente del acceso del operador en la pestaña preparada.

Los quince perfiles fueron aplicados con respaldos, comprobaciones frescas y
revisión independiente del procedimiento. Se preservaron los nueve originales,
otros textos y campos; no se cambiaron nombres, slugs o proyectos. Cauce recibió
su símbolo existente tras verificación visual y de procedencia. Ahora hay diez
referencias de logo fijadas; quedan Deméter, Aletheia, Gravitatoria, Prizma y
Práxis. MCP nativo confirma Cauce113/v4 y su nuevo hash de referencia.

La API de producción devolvió planes correctos para Sinergia, Agentes y Deméter,
incluyendo originales byte exactos, modo oscuro y ausencia de logo sin inventar
un símbolo, respectivamente. No se aprobaron nuevos medios ni se publicaron
posts. Ambos temporizadores antiguos permanecen deshabilitados e inactivos.

Recibo y límites en `docs/RELEASE-FAMILIA-HUMANIZAR-20261011.md` y su JSON.
La meta sigue activa: módulos nuevos pendientes de revisión del diseño escrito
y del plan; no se presentan como implementados por esta entrega.

## Recuperación de referencias, 19:56 UTC

Aletheia115/v4 conserva ahora el cuadro del componente Wordmark y su glifo,
no sólo las barras. El exportador rechaza estilos o dimensiones distintas y
documenta escala rem16/Tailwind estándar. Prizma120/v5 recibió el master exacto
del encabezado actual, con hash idéntico entre `_brand-truth` y `public/icon.svg`.
No se alteraron las variantes antiguas de su repositorio.

Se comprobaron fuentes, comparación visual local, escritura y recuperación
byte exacta mediante API owner de Humanizar, y lectura nativa MCP de ambas
versiones. Otros campos se conservaron; no se aprobaron medios ni se enviaron
posts. La prueba del Estudio se interrumpió por otro panel de extensión; la
GUI de producción sigue esperando acceso del operador. Pruebas focales: 47
aprobadas y Ruff correcto; revisión independiente sin bloqueantes restantes.

Quedan tres referencias: Deméter (lockup con Lucide Sprout; F es Ficadirecta),
Gravitatoria (Lucide Package) y Práxis (marca compartida con Mouseîon/personal).
No se presentan iconos genéricos o de cliente como masters exclusivos.
La revisión de fuentes fue local y no acredita los encabezados públicos actuales.

El bloqueo de revisión del diseño para campañas/conexiones/calendario persiste
desde varios turnos. La recuperación independiente de fuentes inequívocas quedó
cerrada; se espera la aprobación del documento antes de preparar el plan. También
están pendientes el acceso GUI de producción y cerrar el nuevo panel de extensión
que detuvo la prueba local. La meta no está completa ni pausada por decisión propia.

## Continuación: Estudio y preparación social

El navegador volvió a responder. Aletheia y Prizma generaron PNGs de 2160×2700
completos con sus originales y contenido de cada producto. Se localizó el PNG
de Aletheia producido por el clic aunque el observador de descarga agotó su
tiempo. La prueba nueva detectó copy/URL de otro producto al cambiar marca y
PNG previo aún descargable tras editar. Se corrigieron y el navegador confirma
limpieza e invalidación; campos, marca y formato no cambian durante generación.
Frontend: 78 pruebas aprobadas, build TS/Vite y revisión independiente correctos.

Los tres destinos Meta se comprobaron por GET con permisos exactos a las20:08 UTC.
La preparación del historial incluye tres bases: nueve envíos, ocho pendientes
y cuatro retiradas, sin modificación. Las pruebas manuales web todavía requieren
conciliación. Ver docs/PREPARACION-CONEXIONES-HUMANIZAR-20261011.md.

## Corrección del Estudio desplegada, 20:19 UTC

SHA e956d37 en eikon-00060-kkl al100%, sin tags; imagen y SPA cotejadas,
configuración y permisos conservados. Respaldo fresco restaurado en clon sin
red, con doble init_db que mantiene filas/columnas. Las quince marcas y doce
referencias siguen iguales por API. Frontend 78 pruebas, build correcto,
revisión independiente y análisis de secretos aprobados. Prueba local de los
PNG completos Aletheia/Prizma terminada. Ver el recibo
`docs/RELEASE-ESTUDIO-HUMANIZAR-20261011.md`.

La meta permanece activa. La revisión escrita para módulos nuevos y el login
GUI de producción están pendientes; los temporizadores viejos siguen detenidos.

## GUI de producción y pruebas manuales conciliadas

Se encontró la sesión existente de Humanizar en eikon.humanizar.cloud. Tras
recargar su SPA anterior, los estados de marcas son correctos. Prizma generó
y descargó una pieza completa por UI: lote2495, variación3048, tenant17;
el archivo persistido coincide por SHA con el PNG2160×2700 descargado. La
variación queda sin seleccionar; su score legacy0.5 no es aprobación editorial.
El bloqueo de acceso GUI se cerró sin copiar sesiones ni emitir credenciales.

Las cinco pruebas web del 8 de octubre siguen visibles. Se conciliaron los tres
destinos Meta por GET y el alias del perfil antiguo de Facebook por una misma
foto comprobada en UI y API. X/TikTok se leyeron públicamente sin gasto; su
mapping de ID estable todavía necesita evidencia de proveedor. Se conservaron
errores GET iniciales y el procedimiento corregido; no se ampliaron permisos.
El inventario no se importó y no afirma historial remoto completo.

La meta sigue activa. Campañas/conexiones/calendario/worker/panel requieren
revisión escrita del diseño y posterior plan; tres referencias y revisión de
piezas actuales también siguen pendientes. No se envió contenido social nuevo.


## Referencias vigentes y prueba de producción, 20:49 UTC

Deméter110 y Gravitatoria119 pasan de v3/sin referencia a v4 con símbolos y
encuadres extraídos de sus lockups UI actuales. Se corrigió la exigencia anterior
de master exclusivo: preservar el uso vigente con origen Lucide documentado
cumple conservar logos sin atribuir exclusividad ni apropiarse de Ficadirecta.
Capturas DOM y apariencia calculada, paths exactos, comparación visual y revisión
independiente respaldan ambos SVG. Otros campos, familia y modo se conservaron.

El Estudio de producción de la cuenta Humanizar generó y descargó dos PNG
2160×2700 completos: Deméter2496/3049 y Gravitatoria2497/3050. API confirma bytes
idénticos a los descargados, lotes completados y selected=false. Score0.5 es
baseline legacy, no aprobación editorial. No se aprobaron medios ni publicaron
posts nuevos. Hay catorce referencias de producto; Práxis sigue compartiendo
marca con Mouseîon/personal y requiere decisión de referencia.

Este cambio es de datos y documentación: conserva runtimee956d37/revisión60.
La revisión escrita de los nuevos módulos sigue pendiente tras tres turnos
reanudados. Cerrados estos trabajos independientes, la meta queda bloqueada
por esa revisión, no completada; falta el plan y la implementación del centro.


## Continuación: Práxis y quince piezas completas, 23:20 UTC

Se revalidó la cabecera de Práxis: aria-label «Práxis — Mouseîon», enlace personal
original y SVG exacto sin efectos CSS externos. El criterio de conservación
no exige exclusividad: se fija como signo compartido vigente, sin presentar
un logo propio exclusivo Humanizar. Referencia121/v3null→v4, bytes recuperados
iguales y otros campos conservados; revisión independiente aprobada.
Las quince marcas de producto tienen ahora referencia, sin alterar originales.

Las quince ilustraciones Codex del9 de octubre se conservaron y compusieron
con los logos/versiones actuales, Manrope y layout común4x5, sin redibujar logos
ni generar imágenes nuevas con otro proveedor. Canvas en navegador produjo
PNG1080×1350 con fit/contain/márgenes; revisión visual independiente15/15 sin
bloqueantes. El rótulo textual HUMANIZAR del pie no es el archivo oficial de firma.

Tools MCP nativos crearon briefs30–44 e importaron medios31–45. API owner17
comprueba PNG descargado igual al local para los quince, snapshot actual,
pending_review, sin reviews y approval_currentfalse. GUI real abre pieza43,
original, snapshot Práxisv4 e historial vacío. Conteos actuales:30pending,
12rejected,1approved conservado. No se eliminaron versiones ni aprobaron piezas.
También se prepararon quince captions en borrador, sin destino/horario elegido.

No se cambió código runtime ni se desplegó una funcionalidad de campañas.
La meta sigue activa; es el primer turno reanudado tras el bloqueo. El diseño
escrito para módulos nuevos sigue pendiente de revisión; no se ha creado su
plan ni implementación. No hubo nuevas publicaciones o activación de timers.


## Revalidación previa a la siguiente fase

El segundo turno de continuación conserva la revisión escrita pendiente.
La entrega anterior fue progreso: importó quince medios completos y fijó la
referencia de Práxis. No hay un proceso de implementación esperando ni se
considera una conversación un trabajo en ejecución.

Se contrastaron los routers montados, MediaReviewRequest, permisos y rutas React
con el diseño: la revisión actual congela archivo e identidad, pero no caption,
cuenta o fecha; los seis scopes Codex no conceden publicaciones; WorkerPool
renderiza. Se aclaró en el diseño que el publicador duradero de server2 será
separado del renderizador existente. No se creó un plan ni código de subsistemas.

Los quince enlaces de los borradores respondieron HTTP 200 por GET público
sin autenticación desde este host. El recibo guarda fecha, título y SHA del HTML.
Es evidencia de transporte, no de función, identidad, consentimiento ni
aprobación comercial. El enlace de Graf sigue siendo el panel administrativo;
se añadió esta observación al borrador para la revisión del CTA. No se inventó
una URL comercial alternativa ni se modificaron medios, cuentas o horarios.
Ver VERIFICACION-ENLACES-BORRADORES-20261011.json.


## Bloqueo confirmado tras tres turnos de continuación

La revisión humana del diseño escrito sigue pendiente en tres turnos consecutivos
del tramo reanudado. Los dos primeros completaron trabajo independiente: quince
referencias y composiciones, luego enlaces y aclaración del contrato del trabajador.
La comprobación siguiente encontró el repositorio limpio en 37fb01e y el diseño
todavía marcado para revisión. Los cuatro subagentes de esta entrega están
completados; no hay un trabajo vivo que justifique esperar su resultado.

La regla explícita de brainstorming exige aprobación del documento antes de
preparar el plan, y revisión del plan antes de implementación. No hay trabajo
independiente adicional necesario que permita completar campañas, conexiones,
calendario y publicación sin esa revisión. La meta se marca bloqueada, no
completada. El alcance, piezas, historial y restricciones permanecen íntegros.

Para desbloquear: el operador revisa y aprueba, o solicita cambios concretos en
`docs/superpowers/specs/2026-10-11-eikon-centro-publicaciones-design.md`.


## Diseño aprobado con decisión autónoma por IA

El operador aprobó expresamente el diseño y server2, exigió todos los canales,
sustituyó la revisión manual de cada pieza por evaluación/decisión autónoma IA
y conservó la ventana de 60 minutos y protección contra duplicados. La IA
evalúa y programa dentro de una política autorizada por empresa; no se presenta
como owner ni se amplían los seis scopes existentes. Esta instrucción sustituye
la revisión humana obligatoria del diseño anterior.

El plan escrito es `superpowers/plans/2026-10-11-eikon-publicaciones-autonomas.md`.
Incluye política/grants, conexiones cifradas, campañas, historia, evaluación real,
calendario, todos los adaptadores, panel, cliente Codex diario y aceptación por
canal/formato. El método previo de subagentes con revisión por tarea se conserva.
No se implementó ni desplegó producto nuevo al redactarlo.

Las restricciones oficiales TikTok de privacidad/consentimiento por contenido
y auditoría se distinguen de pertinencia editorial IA. X conserva no gasto;
no se consultó saldo actual ni se ejecutaron endpoints potencialmente cobrables.
Estos requisitos externos siguen visibles, sin inventar publicaciones exitosas.


## Plan aprobado: implementación reanudada

El operador respondió «Apruebo el plan; implementa con subagentes». Queda
resuelto el bloqueo de revisión del diseño/plan registrado anteriormente.
La implementación utiliza un escritor por tarea y un revisor independiente;
no requiere otra aprobación entre tareas dentro del alcance autorizado.

Se reutiliza el worktree `codex/eikon-codex-publicaciones`. La primera tarea
es política por empresa y concesiones exclusivas de planner/reviewer/worker,
sin ampliar los seis scopes de galería. Se prepara una base PostgreSQL16
efémera, sin red ni puertos publicados, para verificar ambos motores. La
configuración de producción, credenciales y timers permanecen en el estado
anterior durante esta etapa. Todavía no hay un runtime nuevo desplegado ni
publicaciones acreditadas de esta implementación.


## Tarea 1 completada y revisada: política y grants

Commit `46075cdd1e4d7f5949075a0403603295dcb57bf6`: política owner append-only
por empresa con CAS, alcance de proyectos/productos/cuentas/fuentes, zona,
frecuencia, vigencia, ventana de 60 minutos y gasto deshabilitado. Concesiones
planner/reviewer/worker separadas con secreto hash-only y revocación; ninguna
clave de los seis scopes anteriores obtiene autonomía. El catálogo de cuentas
es estructural, sin OAuth/secrets/seed; su gestión real corresponde a tarea 2.

Pruebas nuevas y existentes en SQLite/PostgreSQL: **1.021 correctas y 2 skips
previos**, frente a la base de 895/2. La revisión independiente dio conformidad
de especificación y calidad aprobada sin hallazgos pendientes. Siete avisos
Ruff RUF036 de firmas anteriores en db.py se cotejaron con la base; los módulos
nuevos y diff-check están limpios.

Es una entrega de código en la rama de desarrollo. No se desplegó ni emitió
política o grant productivo, no cambió el significado de revisión humana de
medios y no se publicó contenido. Las pruebas reales de cliente/UI/operación
mencionadas en tareas 5, 8 y 9 se conservan para la aceptación integrada de
tarea 10, después del despliegue; no cuentan como aprobadas por pruebas locales.


## Tarea 2 completada y revisada: conexiones y credenciales

Código hasta `b092912487d1c2498051dc6a84e6cbc533d1f1c9`: conexiones aisladas
por empresa, cifrado AES-GCM con clave independiente, OAuth ligado a
propietario/empresa/navegador y transporte configurado por proveedor. El script
de importación usa archivos privados y dry-run; no se aplicó a producción.

La revisión independiente encontró dos defectos: catálogo antiguo sin detalles
y filtrado que perdía el token anterior al cambiarlo. Se corrigieron con
regresiones; una regresión de clasificación del código de éxito TikTok también
se corrigió. La revisión final confirmó todos los hallazgos resueltos y ningún
rompimiento nuevo dentro del alcance.

Suite completa previa a las correcciones: **1.110 correctas y 2 omisiones
previas**. Pruebas finales de los módulos afectados: **115 correctas en SQLite
y PostgreSQL**, incluidas todas las regresiones, sin skips; lint/diff limpios.
No se atribuye la suite completa histórica al commit final sin haberla repetido.

OAuth real, vigencia de las cuentas Humanizar, instalación privada de claves
e importación efectiva se comprobarán en tarea 10. X conserva bloqueo de gasto;
una vigencia o permiso no comprobable mantiene la conexión retenida. La próxima
tarea congela campañas/revisiones y añade entrada privada validada de vídeo;
la ruta anterior PNG/JPEG y revisión humana de galería conservan su significado.


## Tarea 3 completada y revisada: campañas, revisiones y vídeo privado

Código hasta `f2d7112679a73d01d4970133b7cb6b59b3cda8bb`: campañas por
empresa/proyecto/marca y revisiones inmutables que fijan medio, hash, texto,
fuentes, derechos, cuenta y horario UTC/zona. Imagen y vídeo tienen referencias
distintas; el ingreso MP4 privado valida H264/AAC y decodificación real con
límites de recepción, tamaño, duración, dimensiones, CPU y memoria.

La revisión independiente encontró pérdida de originales admitidos tras un
commit ambiguo y recepción multipart anterior a autenticar. Ambas se corrigieron
y la revisión acotada confirmó los dos hallazgos resueltos, sin rompimientos
nuevos. Las regresiones recorren el router y transacciones reales en SQLite y
PostgreSQL: rechazo de acceso consume cero cuerpo; exceso corta la recepción;
rechazo/archivo posteriores al commit conservan los bytes originales.

Suite amplia del commit inicial `74a21f4`: **1.224 correctas y 2 omisiones
previas de demos**. Suite final de campañas/vídeo en `f2d7112`: **102 correctas**,
sin skips ni warnings, lint/diff limpios. Mypy sigue fallido con **35 errores
introducidos en tarea 2**, idénticos antes/después de tarea 3; se conserva el
resultado negativo para corregirlo en el triage de la rama completa.

Esto acredita código local revisado. La imagen Docker, inspección IA real,
cliente MCP nativo, panel y publicaciones por canal se probarán en la aceptación
integrada. Ningún timer ni runtime productivo se activó aquí. La tarea siguiente
conserva historial y guardias contra duplicados por destino.


## Tarea 4 completada y revisada: historial y guardias por cuenta

Código hasta `084ec051944b3231e8a674dfdf7e813fdc379b09`: historial y eventos
inmutables, importación idempotente de fuentes completas y guardias por empresa,
cuenta canónica y SHA exacto. Las retiradas conservan la guardia; un caption
distinto no habilita la repetición. La conciliación de identidad añade evidencia
ligada a fuente/ítem/cuenta sin reescribir el recibo original.

Dry-run y dos aplicaciones en clones SQLite/PostgreSQL conservan 22 registros
de historia, 26 eventos, cuatro retiradas y ocho retenciones. Tres destinos Meta
cierran su corte conocido; X/TikTok siguen sin mapping comprobado. Esto describe
el inventario conocido y la prueba aislada, sin afirmar historial remoto universal
ni importación productiva.

La revisión independiente encontró dos defectos: aceptar evidencia escalar para
cerrar incertidumbre y retener una cuenta ajena tras conciliar un mapping. Ambos
se corrigieron; revisión final de especificación y calidad aprobada. Archivo
final: **114 casos correctos en ambos motores**, sin skips; lint/tipos propios
correctos. La suite anterior de 415 casos conserva su atribución a su commit.

La siguiente tarea añade evaluación/decisión IA y herramientas MCP. La aceptación
real del cliente, importación productiva y publicaciones siguen en tarea10; el
calendario debe demostrar primero su autoridad y CAS transaccionales en tarea6.


## Tarea 5 completada y revisada: evaluación editorial por IA

Código hasta `3ac2eea13d014e74a66f8a7ad0fee36b2eda0742`: roles planner/reviewer
separados, entrega de medio y referencia exactos, recibos correlacionados y
evaluación con seis criterios razonados. Las decisiones approve/reject/hold
son inmutables; rechazo, ausencia de contexto, cambios de autorización o medios
impiden la elegibilidad. La confianza está ligada al grant del evaluador: el
recibo declara client_reported, sin atribuir atestación criptográfica al modelo.

La prueba real de dos conexiones PostgreSQL reprodujo y corrigió una aprobación
anterior al commit de rechazo visual. La relectura de medios bloqueados y el
lock NO KEY UPDATE conservan CAS/revocación sin bloquear los FK del owner. Las
operaciones lentas quedan fuera del lock, con revalidación antes de guardar recibos.
La revisión independiente aprobó especificación y calidad, sin hallazgos bloqueantes.

Pruebas finales: **331 casos de consumidores afectados y 121 propios**, ambos
motores y stdio FastMCP/fallback; lint limpio y siete fuentes sin errores de tipos.
La suite amplia anterior conserva **726 correctas y 4 fallos** de count22→27,
corregidos y cubiertos por los consumidores finales. El aviso heredado de mypy
sobre jinja2 y los 35 diagnósticos de tarea2 siguen en el triage global.

Vídeo se evalúa por muestras visuales silenciosas; audio sin inspección queda
retenido. Fuentes son contexto factual congelado y URLs, sin cuerpos remotos
inventados. Esto acredita contrato local revisado: Codex real, GUI, heartbeat,
importación productiva y publicaciones por las cuatro redes siguen en tarea10.
La tarea6 compone elegibilidad, historial, deduplicación y CAS en la cola durable.


## Tarea 6 completada y revisada: calendario y autoridad de envío

Código hasta `05e3addcfe6630fa3fe354457114579216167878`: reservas e inicio
único con CAS y guardias transaccionales, ventana de 60 minutos, cuotas por día
en zona de la política y reportes idempotentes. Un ACK perdido nunca devuelve
autoridad para otro POST. Owner y worker pueden conciliar con prueba ligada al
intento/cuenta, conservando el historial y el identificador remoto canónico.

El API sirve el original exacto y credencial de la reserva propia. Las URLs
temporales permanecen deshabilitadas hasta comprobar logs y descarga desplegados;
se limitan al archivo/intento y a un horizonte de procesamiento de 65 minutos.
La credencial de conciliación puede tener scopes de escritura: su uso exclusivo
para consultar el resultado depende del trabajador confiable de tarea7.

La revisión detectó evidencia capaz de guardar credenciales y sustitución de ID
remoto mediante un reporte incierto intermedio. Ambos corregidos y aprobados en
revisión independiente. La evidencia pública acepta solo siete campos tipados;
los mensajes completos del proveedor y URLs se rechazan antes de persistir.

Pruebas: **787 correctas** en el commit inicial; tras las correcciones, **193
correctas** en los módulos completos de entregas y medios, SQLite/PostgreSQL,
sin omisiones. Lint/formato y tipos focales pasan; el aviso jinja2 y los tipos
pendientes de tarea2 mantienen su atribución. No se repitió la suite anterior
como prueba del nuevo commit.

En ese corte faltaban trabajador/adaptadores (7), panel integrado (8), operación
Codex (9) y aceptación/despliegue (10). La automatización productiva sigue pendiente.


## Tarea 7 completada y revisada: trabajador y adaptadores

Código hasta `9fb8e588d082480e03eabf45eaa0b4a798105ec0`: trabajador aislado
por empresa, outbox durable y fases registradas antes de cada operación remota.
La recuperación consulta resultados sin repetir transferencias, finalizaciones
o publicaciones. El permiso proviene del único ACK de inicio; una retención
previa requiere nueva revisión inmutable y nueva evaluación para reintentar.

Facebook e Instagram admiten fotos y contratos de vídeo/reels. Instagram declara
REELS con share_to_feed explícito; TikTok exige un recibo por contenido y pruebas
externas; X conserva el bloqueo económico antes de cada endpoint. El estado de
procesamiento y un ID de upload nunca se presentan como publicación confirmada.
Facebook feed vídeo conserva incertidumbre hasta comprobar el post final real.

La revisión detectó que Instagram descartaba FINISHED durante recuperación.
Corregido: persiste prueba de procesamiento y retira el enlace temporal incluso
tras otra caída, manteniendo incertidumbre si falta el ID final. Revisión acotada
aprobada, sin nuevos hallazgos importantes.

Pruebas relevantes iniciales: 441 correctas y dos fallos de fixture al cruzar
medianoche Bogotá; fallo reproducido en el código base y corregido únicamente
en la fecha del caso hoy, con seis casos finales correctos en ambos motores.
Corrección Instagram: cinco fallos RED esperados y **58 pruebas finales correctas**
en sus dos módulos afectados, incluyendo HTTP SQLite/PostgreSQL. Lint, formato
y tipos focales pasan con nota heredada explícita; no se inventa un total443 PASS.
La verificación systemd en el checkout no pasó por falta de la ruta runtime;
instalación real y diagnósticos pendientes se conservan para tarea10.

No se instalaron ni activaron timers, no hubo publicaciones reales. Panel y
consentimiento/backend TikTok (8), operación Codex (9), gates integrados y
despliegue/aceptación por canal (10) siguen pendientes.


## Tarea 8 completada y revisada: panel y consentimiento por pieza

Código hasta `0bb3e53395179830a24011fb42cab405d5a5b2fc`: recorrido de
producto, campaña, revisión, decisión IA, calendario y recibo en la SPA
existente. La política es editable por owner; las conexiones pertenecen a
la empresa y admiten varios productos. Preview privado verifica el SHA y
la sesión; editar crea una revisión nueva, pendiente de evaluación IA.

TikTok congela privacidad y divulgaciones. Evidencia externa se importa
por un controlador privado; el owner confirma la pieza exacta. El primer
GET válido fija su recibo al claim y el inicio revalida bajo lock. El
reintento idéntico conserva recibo y expiración; rotación real o revocación
retienen el inicio. Creator_info debe estar fresco al confirmar y el
trabajador vuelve a consultarlo antes de iniciar una pieza programada.

La revisión independiente detectó la rotación accidental del recibo al
repetir el mismo POST; quedó corregida y aprobada en revisión acotada.
Pruebas iniciales finales: 604 backend y 4 focales adicionales; 12 DOM,
78 QA y build. Corrección: 66 casos del módulo, después 14 focales y dos
de lease en ambos motores; no se afirma una ejecución conjunta final de
68 ni repetición de los 604. Ruff y tipos frontend focales pasan.

Quedan 34 diagnósticos OAuth en el gate global, cinco avisos audit de
versiones BASE y una deprecación transitoria del runner. Historial y
previews de campañas no tienen límite; se conserva este límite para la
aceptación real. GUI, Docker, pruebas de proveedor, consentimiento real,
MCP nativo y ejecución diaria siguen pendientes. No se desplegó ni publicó
esta entrega. Las decisiones y sus costes constan en
`docs/DECISIONES-CENTRO-PUBLICACIONES-20261012.md`.


## Bandeja diaria local revisada, 12 de octubre

Código `93d1d73d678eb8bac29d5fa075f4c8e45c816d97`: lectura planner de política,
cuentas, stock y déficit por día; herramienta MCP número28 e historial de hashes
paginado por destino. La cuota utiliza el mismo cálculo que el trabajador.
Revisión independiente conforme y aprobada, sin Critical/Important.

Pruebas de consumidores afectados:713 aprobadas en SQLite/PostgreSQL;
34 finales refuerzan la desconexión del cliente con snapshot sin escrituras
inventadas. Ruff y cinco fuentes de tipos pasan, con nota heredada de jinja2.
No se ejecutó una nueva suite global ni se cambió producción.

Las tareas1–9 están cerradas en su alcance local revisado. La tarea10 conserva
la revisión integrada, despliegue respaldado, cliente/modelo/imagen reales,
GUI Humanizar, pruebas por cuenta/formato y segunda ejecución sin duplicados.
X mantiene la restricción de gasto; TikTok requiere evidencias y consentimiento
reales. La meta completa continúa pendiente.


## Integración local y preflight, 12 de octubre

Código hasta `19ca555b9a98c749423db51be8615d2a1ab02901`: verificador de
recibos por cuenta y formato, recuperación de Facebook vídeo y protección
de registros de fuente. Revisión independiente aprobada tras corregir el
formatter real de Uvicorn y limitar la sustitución de errores a callback/media.

Snapshot integrado: 1.932 pruebas correctas y dos omisiones históricas de
archivos demo; frontend 12 Vitest, 78 QA y build. El verificador final tuvo
55 pruebas directas; el fix posterior de registros tuvo 191 casos focales
correctos sin omisiones. No se atribuye el snapshot a una suite completa
ejecutada después de esos cambios. Tipos configurados:109 fuentes; matriz
explícita de producción:116. Los 34 diagnósticos OAuth quedaron corregidos.
Ruff global conserva 43 diagnósticos anteriores al inicio de esta rama, sin
nuevos por código/archivo/mensaje; el gate global sigue FAIL.

Respaldo privado nuevo de DB/config/storage y del publicador anterior de
server2. Clon DB sin red: 14 tablas originales preservadas, 41 tras migración,
siete entradas esperadas de metadata añadidas, segundo init idéntico y cero
autorizaciones creadas. Storage se restauró localmente con igualdad SHA de
3.003 archivos; esto no prueba restauración operativa en Google Cloud Storage.

Pendientes: revisión completa de rama, digest/despliegue, calificación de logs
reales, Humanizar en GUI, permisos/cuentas actuales, MCP nativo28 y evaluación
real, trabajador, publicación por cuenta/formato y segundo ciclo sin POST.
Bitwarden sigue bloqueado; server2 no tiene ffmpeg/ffprobe y sudo requiere
intervención. X sigue sin gasto; TikTok necesita los requisitos externos
actuales. Producción continúa en su versión anterior y la meta sigue pendiente.

## Revisión final y correcciones en curso

La revisión del candidato `84db9f2` encontró tres problemas importantes:
editar una pieza no retenía su versión anterior; OAuth impedía activar fotos
de TikTok; un inventario legítimamente vacío no habilitaba una cuenta nueva.
Se corrigen en una sola ronda con pruebas de sus recorridos completos y una
revisión posterior del cambio. También se limita el crecimiento por campaña,
se cargan previews bajo demanda y se distingue una retirada en el calendario.

El informe revisó en profundidad las fronteras del centro de publicaciones;
su cobertura de la galería anterior, recursos, lockfile y pruebas fue parcial.
No constituye una aprobación exhaustiva de toda la rama. Los gates reales
de la tarea10 permanecen pendientes; no se activó el trabajador diario.

Las cinco correcciones quedaron en `a4389e898bb34bed876616afc052fd9499664dae`.
Su revisión independiente aprobó el delta completo, sin hallazgos nuevos.
La ejecución afectada conservó 873 PASS y nueve fallos de fixtures antiguos;
tras reparar esos consumidores, campañas y consentimiento dieron128 PASS.
No se suman esas corridas ni se presentan como una nueva suite global verde.
Interfaz:16 pruebas y build correctos; lint de archivos propios y seis fuentes
de tipos correctos, con la nota heredada de jinja2 conservada.

Nuevo clon de la base respaldada:14→42 tablas, ocho entradas de migración
previstas, datos originales preservados, segundo init estable y cero permisos
o sustituciones creados por defecto.

## Despliegue comprobado, 12 de octubre

La imagen del código `a4389e898bb34bed876616afc052fd9499664dae` está desplegada
en `eikon-00061-6lk`, con el 100 % del tráfico. Digest OCI:
`sha256:9eef3179f126238b288b71da071b86db3e5949459e2e41b99783b9717d420e4e`.
Sólo cambió la imagen del servicio; configuración restante e IAM se conservaron.
El contenedor aislado comprobó migraciones, rutas y redacción con el formatter
real. Los tres orígenes públicos sirven exactamente la nueva SPA. La sesión
API propia de Humanizar comprobó perfil, política, conexiones y overview con
HTTP 200; esto no acredita la sesión del navegador ni publicación social.

La exclusión de logs se limita a solicitudes gestionadas de callback/media y
Referer sensibles de este servicio. Su primera calificación sintética conserva
un resultado negativo: dos entradas stdout contienen un marcador añadido a
la query ordinaria de /health. La prueba discriminante, con el marcador sólo
en Referer, obtiene cero entradas sensibles y dos entradas de control normal;
también se observan diez diagnósticos redactados de callback/media. No demuestra
filtración del Referer. Esta prueba sintética pasa, pero los recorridos reales
de sesión, descarga, revocación y errores todavía deben verificarse. La ingestión
del diagnóstico JSON INFO propio tampoco quedó acreditada.

El trabajador de server2, sus autorizaciones dedicadas, la evaluación IA real
y las publicaciones por cuenta/formato permanecen pendientes. No se activó
ningún timer ni se enviaron nuevas publicaciones durante este despliegue.
X conserva el bloqueo de presupuesto; TikTok requiere habilitación real del
proveedor. La meta completa sigue abierta.
