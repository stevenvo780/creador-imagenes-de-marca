# Temas globales de Eikón — 12 de octubre de 2026

Solicitud del operador: resolver la diferencia entre Publicaciones clara y el
resto oscuro, con modos Claro y Oscuro. El selector global añade también Sistema
y conserva la preferencia al navegar y recargar. El script de arranque aplica
el tema antes de montar React; el fallback admite almacenamiento bloqueado.

## Release verificado

- Fuente: `ed7e6379f42b1356255dd0a114f3def809c3b87f`, sobre
  `4e26c57156660c9a4a2905a372ed9bd08c412067`.
- Cloud Run: proyecto `emergent-enterprises`, región `us-central1`, servicio
  `eikon`, revisión `eikon-00065-hg9`, Ready y 100 % del tráfico.
- Imagen:
  `us-central1-docker.pkg.dev/emergent-enterprises/eikon/eikon@sha256:0f3db6b97e74fcaf2422784dff283d62307ef8847efbf3c6a3c72d07130aee16`.
- Imagen anterior:
  `us-central1-docker.pkg.dev/emergent-enterprises/eikon/eikon@sha256:fbbdc956bc54af2421f2a01c8b43c8596467ef40c0c714950fb575e22d9b085a`.
- Cambio exclusivo de `/app/frontend/dist`; hash agregado del backend
  `401ad39e7ba3a5b45d7007df10ca0ae9573e2f6f799f36fb1432e6a3ad923276` conservado.
  Único delta de `template.spec`: imagen. IAM, variables, referencias a secretos,
  recursos y bootstrap OAuth conservados.
- Respaldo privado previo: 273552 bytes, SHA256
  `708f594742ec4b1180fcfbd62886b8db4550594ae93a0b1631921a73bfc4ab8b`.
  No se acredita una nueva prueba de restauración.

Las paletas y logos de los productos se conservan. El renderer cliente recibe
sus variables en un contenedor propio: los tokens de interfaz ya no contaminan
las piezas. Se conserva la precedencia local de variantes monocromáticas e
inversas. No se modificaron las plantillas protegidas.

## Evidencia y límites

Revisión independiente de especificación y calidad aprobada. Frontend: 34/34
pruebas en siete archivos; ocho cubren tema, persistencia, almacenamiento
bloqueado y aislamiento de plantillas reales. Build TypeScript/Vite y
`git diff --check` aprobados. El auditor comprobó adicionalmente ocho casos de
renderer con plantillas reales y el contraste principal en ambos temas.

HTML, JavaScript, CSS y `theme-init.js` coinciden con el dist sellado en Cloud Run,
`https://eikon.humanizar.cloud` y `https://eikon-proxy.vercel.app`.

Brave, cuenta Humanizar: Marcas y Publicaciones muestran ambos temas; Claro
persiste tras recargar y Oscuro al navegar a Galería y Proyectos. Las capturas
de escritorio están bajo
`/home/stev/.codex/visualizations/2026/10/12/eikon-global-themes/`.
La aceptación móvil real sigue pendiente: la capacidad de viewport de Brave
no aplicó el ancho solicitado en la comprobación anterior.

Se conserva un resultado negativo: tras recargar Publicaciones apareció un
error genérico de carga de agenda; Actualizar también falló en una prueba nueva.
Galería mostró errores de conexión de algunas imágenes. Esto no se acredita
como resuelto por los temas. La revisión identifica el mensaje como un error
fuera de `ApiError`, compatible con rechazo de fetch antes de recibir HTTP;
no demuestra si la causa es red, proxy o navegador.

### Corrección posterior de recuperación de agenda

Fuente `6fabd4b44d4b9737534d97df56744def54c28b06`, revisión
`eikon-00066-gmp`, Ready y 100 % del tráfico. Imagen
`us-central1-docker.pkg.dev/emergent-enterprises/eikon/eikon@sha256:d24f706677f6209a715ee04aa58f6e186acf21b156ba58b1fd027c25bf0f11ab`.
Conserva los temas globales y el mismo backend/configuración; cambia únicamente
los archivos SPA. Respaldo previo privado: 273552 bytes, SHA256
`ce1686591e2ea5ed134d1358e6ed1b687a15a6e24ab932726e3e42007ea059bc`.

La agenda limpia la alerta cuando un GET posterior recupera la lista o el estado
vacío, y después de cancelar y recargar correctamente. El cliente distingue un
rechazo de transporte de errores HTTP y JSON. No añade repetición automática de
POST. Ocho pruebas nuevas cubren fallo/recuperación, cancelación, abortos y
clasificación; suite completa 42/42, build y diff-check aprobados. La revisión
del diff por el integrador aprobó el alcance de tres archivos.

Se comprobaron otra vez los bytes servidos en los tres orígenes y las lecturas
autenticadas de tenant 17. Esta corrección no acredita arreglar la causa externa
de conexión; permite recuperarse y mostrar una explicación más precisa.

## Publicador

Este release no activa worker/timer ni efectúa publicaciones. La lectura
autenticada sigue mostrando tenant 17, 17 campañas, tres conexiones activas y
cero entregas nuevas. La prueba de un cliente Codex nuevo usando el launcher MCP
privado sí consultó correctamente la bandeja y los candidatos: tenant 17,
déficit de tres destinos, ningún candidato ni stock autorizado. Esto verifica
ese cliente; no demuestra que Desktop recargara su proceso MCP anterior.

No se incorporan credenciales, sesiones, configuraciones privadas ni respaldos
completos a Git. La meta de publicaciones recurrentes en todas las redes sigue
abierta.
