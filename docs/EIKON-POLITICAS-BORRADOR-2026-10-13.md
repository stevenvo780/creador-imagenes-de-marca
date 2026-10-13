# Eikón: textos públicos propuestos

**Borrador para revisión del operador. No publicado ni aceptado como contrato.**
Fecha del borrador: 13 de octubre de 2026.

Este documento prepara dos páginas necesarias para la revisión de la app de
TikTok. Describe capacidades verificadas en el código; no acredita publicaciones
por API, cumplimiento legal completo ni funciones de borrado que aún no existen.

## Decisiones antes de publicar

1. Confirmar el nombre completo o razón social, domicilio y datos de contacto del
   responsable de Eikón. Humanizar es la marca del servicio; no se ha verificado
   aquí la identidad jurídica del operador. Se propone `admin@humanizar.tech`
   como canal de privacidad y soporte, sujeto a confirmar quién lo atiende.
2. Aprobar o corregir los textos propuestos más abajo. Los plazos de conservación
   por clase de datos y sus mecanismos de purga siguen sin definir; no sustituir
   esta decisión por una promesa de borrado automático.
3. Confirmar el procedimiento operativo para atender acceso, corrección,
   exportación, revocación y supresión, incluyendo copias de seguridad, outbox y
   registros inmutables. La ausencia de un botón de borrado no elimina estos
   derechos ni justifica conservar todos los datos indefinidamente.

El encabezado con identidad y contacto confirmados debe incorporarse a ambas
páginas antes de convertir este borrador en una publicación pública. Los tres
puntos anteriores son pendientes reales; este documento no los da por resueltos.

---

## Texto propuesto: privacidad

### Para qué sirve Eikón

Eikón permite a una empresa organizar proyectos, marcas, encargos creativos,
imágenes, vídeos y calendarios. Cada empresa utiliza sus propias cuentas y
autoriza las herramientas y redes que conecta. El contenido de una empresa no
forma parte de la galería privada de otra.

### Datos que trata el servicio

Al registrar una cuenta se solicita el correo electrónico, una contraseña y el
nombre de la empresa. Se guardan también identificadores internos, rol y fechas.
La contraseña se almacena como un hash con sal; esta protección no significa que
todos los archivos y textos del servicio estén cifrados de la misma manera.

Cuando utilizas proyectos y marcas se conservan sus nombres, descripciones,
logos, paletas, tipografías y textos. Los encargos creativos conservan el prompt
y una copia de la identidad utilizada. Al importar una imagen o un vídeo se
guardan el archivo, sus datos técnicos, procedencia, vínculo con el encargo y
revisiones. Los logos anteriores pueden conservarse como referencias versionadas.

Una conexión social conserva la plataforma, el identificador y nombre de la
cuenta autorizada, permisos comprobados y vigencia de la autorización. Los tokens
OAuth se almacenan cifrados en una bóveda de la aplicación. Las claves de acceso
de agentes y las autorizaciones del publicador se verifican mediante sus hashes.

Las publicaciones conservan el texto, contenido, destino, horario, política,
revisiones, decisiones, intentos y comprobantes. El trabajador de publicación
mantiene una copia operativa de contratos y resultados para evitar envíos
duplicados y poder recuperar intentos interrumpidos.

### Finalidades y conexiones externas

Estos datos se utilizan para autenticarte, separar las empresas, mantener la
identidad de marca, revisar contenido, ejecutar los envíos autorizados y comprobar
qué ocurrió con una publicación. Eikón no solicita acceso a tus contactos o
mensajes privados mediante su integración de publicación de TikTok.

Cuando la integración Direct Post esté habilitada y aprobada para el uso
correspondiente, se solicitarán `user.info.basic` y `video.publish`: perfil básico
y publicación de contenido. El envío puede incluir el texto, archivo o enlace temporal al archivo, privacidad,
interacciones y declaraciones de contenido que hayas elegido. El consentimiento
de una publicación no se sustituye por un permiso general de cuenta cuando el
proveedor exige confirmar ese contenido concreto.

Facebook, Instagram, X y TikTok tratan los datos que reciben conforme a sus
propias políticas. Conectar una cuenta no garantiza que el proveedor permita
todos los formatos o que haya aprobado la app para publicación pública.

Los agentes autorizados acceden al contenido permitido por sus credenciales.
Cuando generas imágenes con tu propio Codex, el tratamiento realizado por Codex
y sus proveedores depende de la cuenta y configuración de ese cliente. La
integración MCP recibe el resultado importado y la información del encargo; no
ejecuta remotamente la herramienta de generación de imágenes del cliente.

La infraestructura documentada del servicio utiliza Google Cloud, un proxy de
Vercel y un trabajador de publicación en un servidor administrado por el
operador. La ubicación y retención de cada componente deben describirse en la
versión definitiva una vez verificadas. No se afirma que todos los datos
permanezcan en un único país ni que las copias desaparezcan al cerrar sesión.

### Cookies y almacenamiento del navegador

La aplicación utiliza una cookie de sesión, una cookie temporal para completar
OAuth y una preferencia local para el tema claro u oscuro. Cerrar sesión elimina
la cookie de acceso; no elimina la cuenta o sus archivos. La cookie de sesión
tiene una duración configurable y puede renovarse mientras se utiliza la cuenta.

No se han encontrado píxeles publicitarios ni herramientas de analítica en la
aplicación inspeccionada. La página pública heredada carga fuentes de Google
Fonts, lo que implica solicitudes a ese proveedor; no se promete ausencia de
conexiones a terceros en todo el sitio.

### Conservación y controles disponibles

La caducidad de un encargo, permiso o enlace limita su uso, pero no equivale a
borrar el registro o el archivo original. Los proyectos y campañas pueden
archivarse. Las claves de agentes y autorizaciones del publicador pueden
revocarse. Iniciar una reconexión o guardar cambios de una conexión elimina su
credencial anterior de la bóveda de Eikón y suspende su uso por esa conexión.

Estos controles no revocan por sí solos todos los permisos en la plataforma
externa ni eliminan publicaciones que ya se hayan entregado allí. Puedes revisar
y retirar el acceso de Eikón desde la configuración de la red correspondiente.

La implementación actual no ofrece un procedimiento integrado de eliminación
completa de cuenta, empresa o archivos. Existen eliminaciones puntuales de marcas
y variaciones, que no acreditan la supresión de todos sus originales, historiales
y respaldos. Los comprobantes y revisiones de publicación se conservan como
historial inmutable; revocar un consentimiento añade una revocación y no borra
el comprobante original. Las copias de seguridad y la copia operativa del
publicador requieren tratamiento adicional en cualquier solicitud de supresión.

### Acceso, corrección y solicitudes

Puedes solicitar información sobre el tratamiento, acceso a tus datos,
actualización, corrección, exportación, revocación o supresión cuando corresponda.
El canal y responsable confirmados aparecerán al inicio de esta página. No envíes
contraseñas, tokens o documentos sensibles en tu primera consulta. Se verificará
tu relación con la cuenta antes de facilitar datos privados o modificar accesos.

La solicitud debe contemplar los registros y copias conservados, y cualquier
conservación necesaria debe tener una finalidad y fundamento identificables. La
versión definitiva debe concretar el procedimiento y los plazos de atención.

---

## Texto propuesto: condiciones de uso

### Servicio y cuenta

Eikón es un servicio de organización de marca, contenido y publicaciones para
empresas. Cada empresa registra su propio espacio y conecta las cuentas y
herramientas que tiene autorización para utilizar. Quien administra la empresa
debe mantener sus credenciales seguras y conceder a cada agente únicamente los
permisos necesarios.

### Contenido y derechos

Conservas los derechos que tengas sobre el contenido que aportas. Debes tener
autorización para utilizar y publicar los logos, imágenes, vídeos, textos,
música y demás materiales que subas. El uso de una herramienta de IA no garantiza
que un resultado sea correcto o que esté libre de derechos de terceros.

Los materiales se procesan para las funciones que utilizas: organizar, generar
piezas deterministas, importar resultados de tu cliente, revisar y entregar
publicaciones autorizadas. No debes introducir contraseñas ni secretos de acceso
en textos creativos, prompts o publicaciones.

### Publicación y automatización

Una autorización de cuenta y una publicación concreta cumplen funciones
distintas. La empresa define cuentas, contenido, calendario y permisos. La
automatización puede evaluar y preparar contenido dentro de esa política; los
consentimientos adicionales que exija una red deben completarse para ese envío.
Para TikTok deben mostrarse y confirmarse las opciones disponibles del creador,
la privacidad y las declaraciones correspondientes antes de iniciar el envío.

Las redes pueden limitar formatos, frecuencia, gasto, acceso a API o visibilidad.
La configuración de una integración y un envío programado no demuestran una
publicación visible. Los resultados sólo se dan por confirmados con comprobantes
y verificaciones del destino; el servicio puede retener un envío si no puede
comprobar sus requisitos o si su resultado es incierto.

No se autoriza automáticamente una compra de créditos o suscripción de un
proveedor. Cualquier gasto adicional requiere una decisión separada del titular.

### Retirar accesos y corregir contenido

Puedes revocar claves y autorizaciones del publicador y archivar proyectos o
campañas con los controles disponibles. Puedes retirar permisos desde la
configuración de cada red. Archivar, revocar o cerrar sesión no equivale a borrar
la cuenta, todos sus archivos o una publicación remota; las solicitudes
adicionales se tramitan por el canal confirmado del operador.

Si una pieza o dato requiere corrección, revisa su estado y utiliza los controles
disponibles antes de permitir un nuevo envío. Un historial de publicación se
conserva como evidencia de lo ocurrido; la corrección o revocación no se presenta
como si el envío original nunca hubiera existido.

### Contacto y cambios

Los datos del operador y contacto confirmados aparecerán al inicio de estas
condiciones. Las versiones publicadas deben indicar su fecha. Los cambios que
amplíen permisos, introduzcan gastos o alteren un consentimiento concreto deben
presentarse antes de ejecutar la acción correspondiente.

---

## Fuentes y límites internos, fuera de las páginas públicas

Revisión read-only independiente del código realizada el 13 de octubre de 2026.
No se inspeccionaron secretos, bases privadas, logs, navegador ni la configuración
de producción para producir ese mapa.

| Afirmación | Fuente del repositorio | Límite |
| --- | --- | --- |
| Registro y hash de contraseña | `webapp/app.py:74`, `webapp/storage.py:105`, `webapp/security.py:21` | No hay borrado de cuenta comprobado. |
| Encargos y referencias versionadas | `webapp/brand_briefs.py:74`, `webapp/brand_briefs.py:249` | Caducar no borra; cambiar logo conserva versiones. |
| Media y revisiones | `webapp/migrations.py:198`, `webapp/publications/migrations.py:126` | No se encontró borrado de media expuesto. |
| Permisos y vault | `webapp/publications/connections.py:24`, `webapp/publications/vault.py:24` | AES-GCM protege tokens; no todos los datos. |
| Reconexión | `webapp/publications/connections.py:145`, `webapp/publications/oauth.py:189` | Borra la entrada anterior del vault; no revoca remotamente ni borra historial. |
| Consentimiento e historial | `webapp/publications/consent.py:211`, `webapp/publications/consent.py:440`, `webapp/publications/migrations.py:245`, `webapp/publications/migrations.py:562` | Revocación append-only; triggers impiden editar/borrar comprobantes. |
| Enlaces de media | `webapp/publications/media_delivery.py:75` | Máximo 3.900 segundos; vencer no borra el original o el post. |
| Outbox | `publisher_worker/outbox.py:23` | SQLite privada, sin cifrado propio ni purga acreditados. |
| Cookies y tema | `webapp/config.py:21`, `webapp/api/deps.py:70`, `frontend/src/theme/ThemeProvider.tsx:45` | TTL configurable, no asumir configuración efectiva. |
| Fuentes externas | `webapp/templates/landing.html:17`, `webapp/templates/_layout.html:7` | Google Fonts en HTML heredado. |
| Infraestructura | `docs/DEPLOY-CENTRO-PUBLICACIONES.md:9` | Runbook, no inventario completo de regiones/retención. |

Requisitos de producto consultados en fuentes oficiales:

- [Revisión de apps TikTok](https://developers.tiktok.com/docs/en/app-review-guidelines):
  app desarrollada, sitio accesible, políticas visibles, permisos mínimos y
  demostración real de los productos y permisos solicitados.
- [Publicación de contenido TikTok](https://developers.tiktok.com/docs/en/content-sharing-guidelines):
  consentimiento del contenido, opciones del creador y auditoría para visibilidad
  pública. Sin auditoría, la vía API exige cuentas privadas y `SELF_ONLY`;
  no convertir la cuenta pública de Humanizar en privada para eludir esa limitación.
- [Principio de finalidad, SIC](https://www.sic.gov.co/recursos_user/boletin-juridico-feb2017/articulo/datos/el-principio-de-la-finalidad-debe-tenerse-en-cuenta.html):
  el plazo de tratamiento debe responder a su finalidad. La ausencia de purga
  implementada no permite afirmar conservación legalmente ilimitada.

Este borrador no declara cumplida la auditoría de TikTok, ni resuelve por sí solo
los pendientes de identidad jurídica, conservación y atención de derechos.

**Revisión técnica/editorial independiente:** PASS como borrador el 13 de octubre
de 2026; incorporadas sus tres precisiones sobre disponibilidad de Direct Post,
eliminaciones puntuales y referencias de revocación. La revisión no valida
jurídicamente los textos ni autoriza publicarlos.
