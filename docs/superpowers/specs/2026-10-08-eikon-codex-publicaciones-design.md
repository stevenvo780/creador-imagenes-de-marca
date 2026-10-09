# Eikón: galería privada, Codex y publicaciones por empresa

Fecha: 8 de octubre de 2026, America/Bogota. Estado: diseño para revisión; no implementado.

## Resultado acordado

Cada empresa conecta **su propio Codex y sus propias redes**. Eikón organiza proyectos, identidades de marca, imágenes y calendario dentro de esa empresa. Codex produce los archivos desde su cliente, usando las herramientas de generación disponibles allí; MCP facilita los encargos, las referencias y la entrega a Eikón. El servicio publica únicamente versiones aprobadas, con las credenciales de la empresa correspondiente.

La primera entrega será el recorrido completo **proyecto → referencia de marca → imagen de Codex → galería privada → revisión**. La conexión de redes y el publicador se construirán como entregas posteriores con contratos compatibles con esta base. El objetivo global conserva las tres entregas; aprobar esta especificación permite preparar el plan de la primera.

No se añade facturación, generación de vídeo, compra de créditos ni un proveedor de imágenes pagado. Los logotipos oficiales se conservan como archivos originales. El generador determinista actual continúa disponible como otra fuente de contenido.

## Evidencia de partida

| Elemento | Verificación del 8 de octubre | Límite de la evidencia |
|---|---|---|
| Repositorio | `stevenvo780/creador-imagenes-de-marca`, `main` en `74454f9bd82ee5f48002f2ba5a3ce3e750bde002` | El repositorio es público; los datos privados de clientes no se incorporarán a Git. |
| Rama de trabajo | `codex/eikon-codex-publicaciones`, checkout separado | Las dos copias locales anteriores tienen modificaciones que se preservan. |
| Vercel | Proyecto `eikon-proxy`, despliegue de producción marcado READY | No hay enlace Git configurado en sus metadatos. |
| Servicio público | `https://eikon-proxy.vercel.app/health`: HTTP 200 | Un health no demuestra generación, aislamiento ni publicación. |
| Backend documentado | `https://eikon-633619052458.us-central1.run.app/health`: HTTP 200 | Ambos responden `eikon-api`, versión `1.0.0`; falta probar un recorrido autenticado. |
| Interfaz | `/` y `/gallery` responden HTTP 200 | La portada se presenta como generador determinista. No se verificó la galería de un usuario. |
| Autenticación | `/api/v1/brands` sin credenciales responde 401 | No sustituye las pruebas entre dos empresas. |
| Código | FastAPI, React, SQLite/Postgres, storage local/GCS, MCP por stdio | No hay proyectos, importación de Codex con revisión ni calendario social en `main`. |
| Inventario | 56 JSON de marca: Elenxos 4, Prizma 12, Pinakothḗke 26, Steven Vallejo 14 | Son configuraciones del repositorio, no 56 marcas comprobadas en una cuenta de producción. |
| Pruebas locales | Los dos entornos Python anteriores no tienen `pytest` | Las pruebas no se ejecutaron; no se declara una línea base aprobada. |

El upload de renderizado cliente existente no es un mecanismo de aprobación: admite una comprobación parcial de PNG, asigna un score de referencia y puede escribir antes de resolver una variación existente. La nueva importación tendrá validación y persistencia independientes. `GCSStorage.url_for()` construye una URL pública: los nuevos archivos privados necesitan descarga autenticada y entrega temporal controlada.

## Alternativas y decisión

1. **Ampliar Eikón y mantener un trabajador separado para publicar.** Aprovecha su API, galería y aislamiento actuales. Mantiene los procesos duraderos fuera de Vercel y permite migrar el publicador de Humanizar por fases. Es la opción elegida para este diseño.
2. Incorporar una interfaz de galería al publicador de Humanizar. Evita parte de la integración inicial, pero exige crear de nuevo autenticación y organización multiempresa, y deja dos productos de marca separados.
3. Rehacer Eikón como aplicación exclusivamente en Vercel. Simplifica un alojamiento, pero reemplaza el backend y obliga a migrar almacenamiento, motor y trabajos existentes. Se descarta para este alcance.

## Recorrido de la primera entrega

1. El administrador entra en su empresa y crea o selecciona un proyecto.
2. Asocia una marca al proyecto y fija su identidad con el logo oficial, colores, tipografía y fuentes de información vigentes.
3. Conecta a Codex el MCP de Eikón con una clave de esa empresa y permisos acotados.
4. Codex pide un encargo con formato, dimensiones, objetivo, textos, referencias y versión de marca. Genera la imagen en su cliente. La disponibilidad y los límites de generación pertenecen a esa cuenta de Codex.
5. Codex entrega los bytes a Eikón mediante el MCP. El servidor valida tipo, tamaño, dimensiones y correspondencia con el encargo, calcula el hash y registra la procedencia.
6. La imagen aparece en la galería privada, asociada al proyecto y marca, en estado **Pendiente de revisión**.
7. Un revisor examina los píxeles, textos, logo y afirmaciones. Aprueba o rechaza esa versión. Una modificación de imagen, texto de publicación o marca exige una nueva revisión.

MCP no ejecuta por sí mismo la herramienta integrada de imágenes de Codex. El servidor entrega encargos y recibe archivos; el cliente hace la generación. Tampoco se importa una ruta local del servidor enviada por un cliente: cada cliente transmite el archivo que está autorizado a leer.

## Organización e identidad

Una empresa contiene proyectos. Cada proyecto tiene una o varias marcas; en la primera entrega una marca pertenece a un único proyecto, evitando compartir identidades accidentalmente. Una futura reutilización entre proyectos será una asociación explícita.

Las marcas existentes se conservan. Una migración asigna las marcas ya almacenadas a un proyecto «General» **dentro de su empresa actual**, sin cambiar sus propietarios. Las 56 configuraciones del repositorio se ofrecen como inventario para importar exclusivamente al tenant del propietario, tras cotejar nombre y logo; no se insertan automáticamente en todas las empresas.

Humanizar será la primera empresa de uso real. Se organizarán sus proyectos Systems y News y después los productos de su catálogo vigente. El kit oficial se toma de HumanizarDocs/HumanizarComercial y se incorpora mediante una operación autenticada, nunca como datos privados de ejemplo en el repositorio público. La importación es idempotente por empresa y slug, preserva IDs existentes y presenta conflictos para revisión.

Cada identidad tiene una versión y hashes de sus referencias. Codex recibe el logo original para incorporarlo; si el resultado altera ese logo, la pieza se rechaza. Un logo nuevo solo se genera ante un encargo específico de identidad, no al producir contenido con una identidad ya aprobada.

## Datos de la primera entrega

Todas las entidades incorporan `tenant_id`. El servidor lo obtiene de la sesión o clave autenticada; nunca confía en un tenant enviado en el cuerpo.

| Entidad | Datos y reglas esenciales |
|---|---|
| `projects` | ID, empresa, nombre, slug, descripción, archivo; slug único por empresa. |
| Marca existente | Añade `project_id` y versión de identidad; la empresa del proyecto debe coincidir. |
| `generation_briefs` | Proyecto, marca y versión, texto del encargo, dimensiones, referencias, creador, estado y vencimiento. |
| `media_assets` | Proyecto, marca, encargo, fuente `codex`/`deterministic`/`upload`, hash SHA-256, MIME verificado, dimensiones, tamaño, clave de storage, procedencia declarada y estado. |
| `asset_reviews` | Empresa, asset, hash y versión revisados, decisión, motivo, revisor humano y fecha. Historial inmutable. |
| API keys existentes | Añade nombre, scopes y vencimiento; secret almacenado como hash y mostrado una sola vez. |

La procedencia enviada por Codex se registra como declaración del cliente; no equivale a una certificación del proveedor. Se guardan el encargo, la herramienta/modelo declarados, la fecha y hashes de referencias, sin credenciales ni conversaciones completas.

Los assets nuevos se almacenan bajo el prefijo de empresa utilizando `get_storage()`. Se decodifica realmente PNG/JPEG, se rechazan formatos falsos y archivos excesivos: máximo 20 MiB y 40 millones de píxeles en esta entrega. Dimensiones válidas: 256–8192 píxeles por eje y coincidencia con el encargo. El original y su hash permanecen inmutables; una nueva edición crea otra versión. Miniaturas normalizadas eliminan metadatos innecesarios.

Las variaciones deterministas anteriores se conservan y siguen disponibles en la galería actual. La galería presenta ambas fuentes con identificadores diferenciados. Para revisar una variación antigua se crea un `media_asset` que referencia una copia inmutable validada y la variación de origen; la selección o el score anterior no se convierten en aprobación. Así se evita reemplazar tablas y recorridos de renderizado existentes.

Una clave de idempotencia identifica la importación dentro de la empresa. Repetirla con los mismos bytes devuelve el asset creado; repetirla con otros bytes devuelve conflicto. Ni el hash ni una ruta de storage permiten descubrir archivos de otra empresa. La base de datos y el almacenamiento compensan fallos parciales con limpieza de objetos huérfanos y estados explícitos, sin mostrar como listo un archivo incompleto.

## API, MCP y permisos

Contratos de la primera entrega, con paginación y filtros por proyecto y marca:

- `/api/v1/projects`: crear, listar, actualizar y archivar proyectos propios.
- `/api/v1/generation-briefs`: crear y consultar encargos y referencias autorizadas.
- `/api/v1/media`: importar por multipart, listar y consultar archivos.
- `/api/v1/media/{id}/download`: descarga autenticada; miniaturas con el mismo control.
- `/api/v1/media/{id}/reviews`: revisión humana sobre el hash/versiones indicados.

El MCP conserva sus herramientas actuales y añade `eikon_list_projects`, `eikon_create_project`, `eikon_get_brand_brief`, `eikon_create_generation_brief`, `eikon_import_image` y `eikon_list_media`. `eikon_import_image` lee un archivo del cliente MCP y lo transmite por HTTPS; rechaza tamaños inválidos antes de enviarlo y no expone su ruta como una ruta del servidor.

La primera conexión utiliza el transporte stdio existente y una clave revocable por empresa. Los scopes nuevos son `projects:read`, `projects:write`, `brands:read`, `briefs:write`, `media:read` y `media:write`. Codex no recibe `media:approve` ni acceso para administrar credenciales. El revisor aprueba desde una sesión humana autorizada. Las claves antiguas mantienen el comportamiento anterior para las rutas anteriores, pero no heredan los permisos nuevos: requieren una concesión explícita.

Emitir nuevas claves y cambiar permisos requiere una sesión humana de administrador, no otra API key. La conexión remota HTTP con OAuth es una entrega posterior; no se presenta una clave stdio como si fuera OAuth multiusuario.

En esta primera entrega, el administrador/revisor es el usuario autenticado con el rol `owner` que ya existe en `users`. El rol se consulta en la base de datos en cada operación sensible; no se acepta un rol enviado por el cliente. Las cuentas con otros roles y las API keys no pueden aprobar ni administrar claves. No se añade gestión de equipos ni una asignación automática de propietarios a cuentas antiguas.

## Interfaz

La navegación incorpora Proyectos y conserva Marcas y Estudio. La galería permite filtrar por proyecto, marca, origen y estado, mostrando miniatura, dimensiones y revisión. El detalle muestra el encargo, referencias de marca, versión e historial. «Aprobar» y «Rechazar» solo aparecen para revisores autorizados.

Los estados visibles son **Pendiente de revisión**, **Aprobado**, **Rechazado** y **Archivado**. Un rechazo conserva sus motivos y no pasa al calendario. Los errores de importación ofrecen reintento con la misma clave de idempotencia. Un archivo no aprobado no muestra acciones de publicación.

El primer cambio visual seguirá la interfaz existente y se verificará en escritorio y móvil. No modifica las plantillas protegidas `ad_leaderboard.html`, `letterhead.html` ni `stat_card.html`. Las piezas del Estudio continúan usando el renderizado cliente actual y se prueban por ese recorrido real.

## Aislamiento y alojamiento

Cada consulta, escritura, referencia cruzada, descarga y trabajo incluye la empresa autenticada. Las referencias a proyecto, marca, encargo y asset de otra empresa devuelven 404 y no revelan sus nombres. Las claves se revocan de forma efectiva en las llamadas siguientes.

El control de carpetas no reemplaza la autorización. Las nuevas piezas no tendrán enlaces públicos permanentes. Para previsualizar se usa descarga autenticada; cuando una plataforma social necesite obtener una imagen aprobada, una entrega posterior emitirá un enlace temporal limitado a ese asset y trabajo, sin exponer directorios o borradores.

Se revisan también los permisos reales del bucket y las URLs emitidas para variaciones anteriores. Si hay objetos públicos, no se declara privada toda la galería: se registra el alcance, se corrige su exposición mediante una migración controlada y se prueba la descarga sin sesión. Retirar un enlace no revoca copias que terceros hayan descargado antes.

Vercel conserva la entrada pública y el proxy. FastAPI mantiene los datos y reglas de negocio. Producción requiere Postgres y almacenamiento persistente privado; SQLite/disco son opciones de desarrollo, no almacenamiento efímero en funciones de Vercel. Antes de desplegar se comprobarán la configuración real de Cloud Run, la base de datos, el bucket y el proxy, sin asumirlos a partir de la documentación.

No se cambia el despliegue activo ni el almacenamiento antes de obtener una copia privada recuperable y probar la migración. Las migraciones son aditivas y funcionan en SQLite de pruebas y Postgres de producción. El rollback conserva los archivos originales y no elimina filas ajenas a la ampliación.

## Contrato para las siguientes entregas: redes y calendario

La segunda entrega añadirá conexiones sociales por empresa, identidad de cuenta verificada, capacidades efectivas y calendario. La tercera añadirá el trabajador duradero en server2 y las pruebas de publicación. Tendrán su propio diseño y plan sobre esta base.

Una conexión guarda proveedor, cuenta remota, permisos concedidos, vigencia y una referencia a un secreto cifrado. Las credenciales nunca llegan a la galería, MCP, navegador de otro cliente o Git. Cada empresa autoriza sus cuentas mediante el consentimiento correspondiente; no hereda las de Humanizar. Se valida `state` de OAuth, empresa y usuario iniciador; se usa PKCE cuando el proveedor lo admite.

Una publicación fijará empresa, conexión, proyecto, versión de imagen aprobada, texto aprobado, fecha local/zona horaria y clave de idempotencia. El trabajador volverá a comprobar aprobación, hashes, permisos y titular de la cuenta antes de enviar. Una modificación invalida la autorización de esa versión. Un reintento tras timeout se reconcilia con el proveedor; no se repite ciegamente un POST cuyo resultado sea incierto.

Se reutilizarán las reglas y adaptadores de `ComercialHumanizar/marketing_autopilot`, no su configuración global de secretos. La cola tendrá leases duraderos y recibos con ID remoto, estado y fecha. El aislamiento se comprueba también al consumir trabajos. La interfaz diferenciará **Programado**, **Publicando**, **Publicado y verificado**, **Pendiente de comprobar** y **Bloqueado**, indicando la causa.

La migración de Humanizar conservará los IDs y recibos de su cola actual. No se habilitarán dos consumidores para el mismo envío. Sus temporizadores de server2 se preservan hasta comprobar la migración y hacer un corte controlado. La generación recurrente mediante Codex exige además un cliente conectado y una ejecución programada real: un calendario de stock finito no demuestra producción continua.

Las capacidades serán específicas: foto publicada, vídeo publicado o carga como borrador son resultados distintos. X permanece sin gasto por la instrucción del propietario; TikTok depende de sus permisos/aprobación reales. Se mantienen deshabilitadas las acciones que no tengan permiso o saldo autorizado. Una publicación manual anterior no demuestra que su API esté habilitada.

## Criterios de aceptación de la primera entrega

1. Dos empresas de prueba con usuarios y claves diferentes crean proyectos y assets propios. Intentos cruzados de lectura, descarga, importación, actualización y revisión fallan sin filtrar datos.
2. La revocación y los scopes impiden usar claves antiguas o de importación para aprobar archivos o emitir más claves.
3. Codex, conectado al MCP de la empresa autorizada, obtiene el kit, genera una imagen e importa los bytes. La pieza llega a la galería con su hash y procedencia, sin usar una API de generación pagada.
4. Una persona revisa la imagen real y puede aprobar o rechazar. El sistema no interpreta un score del renderer o el éxito de un upload como aprobación.
5. MIME falso, archivo corrupto, exceso de tamaño/píxeles, referencia ajena y reintento con contenido distinto son rechazados. El mismo reintento válido no duplica filas ni sobrescribe el original.
6. Enlaces y miniaturas de piezas privadas no son accesibles sin autenticación. Se verifica tanto almacenamiento local como el contrato del backend privado de producción.
7. La importación del inventario se muestra primero como resumen de cambios y solo escribe en la empresa del propietario; repetirla no duplica marcas ni sustituye logos sin revisión.
8. Las pruebas existentes relevantes de autenticación, marcas, galería, storage y renderizado siguen pasando. La UI y el recorrido MCP se verifican realmente; un build exitoso no sustituye estas pruebas.
9. La entrega incluye SHA, resultados de pruebas, comprobación del despliegue y evidencia visual. Se declara por separado cualquier verificación externa que falte.

## Riesgos y límites que se conservan visibles

- El servicio en producción está disponible, pero no se verificó aún una sesión autenticada ni su versión de código exacta.
- Las copias anteriores contienen prototipos y cambios sin publicar. Se evaluarán por separado; no se importarán en bloque ni se presentarán como funcionalidades de `main`.
- Generar con Codex depende de la cuenta y capacidad de cada empresa. MCP no aporta cuota adicional ni permite cambiar de cuenta automáticamente.
- Los proyectos y marcas encontrados son un inventario inicial; debe revisarse su vigencia antes de escribir textos o publicar contenido sobre ellos.
- Esta especificación prepara la galería y sus contratos. La publicación automática multiempresa quedará pendiente hasta completar las entregas de conexiones y trabajador con pruebas reales.

## Revisión del documento

Se comprobó que los estados, permisos, contratos y criterios corresponden a la primera entrega; el calendario y el trabajador se mantienen como entregas posteriores explícitas. El documento no incluye credenciales, datos de soporte de Meta ni identificadores personales de administradores. No se modificó código de producto ni se ejecutaron migraciones de producción.
