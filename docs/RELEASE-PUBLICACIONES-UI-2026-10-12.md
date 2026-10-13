# Rediseño del centro de publicaciones — 12 de octubre de 2026

Diseño aprobado por el operador: agenda principal, productos compactos con
búsqueda, vistas de contenido y cuentas, superficie clara, tipografía sans y
ajustes técnicos plegables. El objetivo completo aparece en el detalle del
producto. La detención de autonomía permanece accesible.

## Alcance y release

- Commits de interfaz: `e50ae6d7181c287dc35b908318d13c47d2119755` y
  `b3cc392516dfb51d2fe4d17cd02863cd1464244d`.
- Proyecto `emergent-enterprises`, región `us-central1`, servicio `eikon`.
- Revisión `eikon-00064-d4t`, Ready, 100 % del tráfico.
- Imagen `us-central1-docker.pkg.dev/emergent-enterprises/eikon/eikon@sha256:fbbdc956bc54af2421f2a01c8b43c8596467ef40c0c714950fb575e22d9b085a`.
- Se heredó la imagen base fijada y se sustituyó exclusivamente
  `/app/frontend/dist`. La configuración de imagen y el prefijo de capas
  anteriores coinciden; el hash agregado del backend sigue siendo
  `401ad39e7ba3a5b45d7007df10ca0ae9573e2f6f799f36fb1432e6a3ad923276`.
- Único cambio de `template.spec`: imagen. Se conservaron IAM, variables,
  referencias a secretos, recursos, configuración TLS reenviada y bootstrap OAuth.
- Respaldo privado previo: 273552 bytes, SHA256
  `b5b4023e23d5ab2873d361a7c81b8831c13e8435dd5950c15a89a5254ee5b355`.
  No se acredita una prueba nueva de restauración.
- No se desplegó el backend nuevo del checkout, se alteró el esquema, se
  activó el worker/timer ni se efectuaron POST de publicación de proveedores.

## Verificación

Revisión independiente de especificación y calidad aprobada. Dos hallazgos de
contraste AA se corrigieron antes del release. Suite frontend: 26/26 pruebas en
cuatro archivos, build y `git diff --check` aprobados. Revisión independiente de
los operadores de release: seis fixtures aprobados, incluidos rechazo de SHA,
checkout, dist, backup y delta de variables inesperados.

HTML, JavaScript y CSS servidos coinciden byte por byte con el dist sellado en
Cloud Run, `https://eikon.humanizar.cloud` y el proxy Vercel. El fallback HTML de
`/publications/campaigns/3` también coincide en los tres orígenes.

Brave, cuenta Humanizar, tenant 17:

- Agenda, contenido y cuentas visibles; búsqueda de Sinergia POS filtra a una
  campaña y Enter abre su detalle con el objetivo completo.
- Salto al contenido accesible por teclado, con contraste corregido.
- Recarga del enlace directo al detalle aprobada en la comprobación posterior.
  Se conserva el resultado negativo inicial: pantalla blanca. Una navegación
  posterior informó `ERR_NETWORK_CHANGED`; esto no demuestra la causa del
  primer resultado. No se atribuye una corrección de código inexistente.
- Actualizar agenda terminó correctamente con el estado sin entregas.
  El primer intento mostró un error genérico; la API autenticada con cursor 0
  devolvió 200 y la segunda actualización visible funcionó. No se oculta el fallo.
- Las cinco secciones técnicas de cuentas/configuración están plegadas.
- Ancho de escritorio 1885 px y scrollWidth 1885 px: sin desborde horizontal.
- **Móvil pendiente**: la capacidad documentada de Brave aceptó solicitar
  390×844 pero el DOM y la captura continuaron en 1885 px, también en una pestaña
  nueva. Se restableció el viewport. No se acredita una aceptación móvil real.

Capturas locales del resultado: `desktop-agenda.png` y `desktop-cuentas.png`, en
`/home/stev/.codex/visualizations/2026/10/12/eikon-publications-redesign/`.
Recibos operativos privados bajo `/home/stev/.local/share/eikon-humanizar/`;
no se incorporan sesiones, tokens ni configuraciones completas a Git.

## Capacidad actual de publicación

Lectura de producción: owner 4, tenant 17 Humanizar, 17 campañas,
0 revisiones y 0 entregas en el calendario nuevo. Las tres conexiones están
activas y la política 1 conserva `spend_allowed=false`. La política y sus grants
de calificación vencen el 13 de octubre de 2026 a las 17:28:39 de Bogotá.

| Destino | Verificado | Pendiente |
| --- | --- | --- |
| Facebook Humanizar Systems | Conexión activa, permisos de publicación | Evaluación real, servicio worker y envío con recibo/visibilidad/replay sin duplicados |
| Facebook Humanizar | Conexión activa, permisos de publicación | Mismos gates; acceso de edición de perfil es un asunto separado |
| Instagram humanizar.news | Conexión activa, perfil y publicación | Mismos gates de envío real |
| TikTok | Cuenta Developers con app individual en borrador | Icono, categoría, términos, privacidad, dominio; productos/scopes, demo/revisión, OAuth social y consentimiento por contenido |
| X | Cuenta social disponible; decisión expresa sin gasto | No hay conexión operativa en Eikón; no habilitar endpoints facturables ni compras |

En server2 existen ffmpeg y ffprobe; `/opt/eikon` y el nuevo servicio/timer
publicador no están instalados/activos. La llamada nativa de bandeja MCP devuelve
`configuration_error` por configuración del planner/base segura; el stdio privado
anterior no acredita que Desktop haya recargado esa configuración. Completar
esto, las evaluaciones reales y las pruebas de envío antes de activar recurrencia.

**Este release acredita el rediseño y su despliegue. No acredita publicación
automática en todas las redes ni cierra la meta de recurrencia.**
