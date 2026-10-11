# Familia Humanizar: entrega desplegada

Evidencia del 11 de octubre de 2026; recibo saneado en
`RELEASE-FAMILIA-HUMANIZAR-20261011.json`.

## Resultado comprobado

- Código `0d1a9bc7bef918a619cf06896dd9cc4d68c80727`, revisión
  `eikon-00059-9h5`, 100% del tráfico, sin tags.
- OCI index `sha256:16ceb5983dd2cc178014d284b1159ebd16d8ec79126fe2833b4ab3d0a6cef1ea`.
  Manifest linux/amd64 efectivo
  `sha256:ad4872c0038c9f9326baa821ac9c4297ce6b333ced2c8c23e7441cb83ead491a`;
  pertenencia al index verificada, archivos runtime y frontend coinciden con el código.
- Actualización exclusivamente de imagen: recursos, variables, secretos,
  red, permisos del servicio y bucket preservados. Cloud Run sólo cambió su
  nonce de revisión; no se ignoran otros cambios de configuración.
- Los dos orígenes del servicio y el proxy Vercel sirven la SPA exacta de la
  imagen para proyectos, estudio y medios. Owner Humanizar responde 200;
  marcas anónimas responden 401; plantilla vertical autenticada byte exacta.
- Los quince productos seleccionan el perfil Humanizar y Manrope. Se
  conservaron originales, paletas, nombres, slugs, proyectos y otros textos.
  Agentes conserva su firma clara y usa el modo oscuro explícito.
- Cauce recibió el símbolo existente extraído de su landing local, después
  de revisar su procedencia y composición real en Estudio. No se redibujó.
  MCP nativo obtiene marca 113, versión 4, perfil y hash nuevos correctos.
- Diez referencias de logo fijadas. Deméter, Aletheia, Gravitatoria, Prizma
  y Práxis siguen pendientes de una referencia completa e inequívoca.

## Pruebas de recorrido

En una empresa sintética local, el navegador real generó una pieza vertical
con logo horizontal original. Se comprobó el PNG descargado 2160×2700, pie
visible y composición sin recorte; SHA
`e9273dc82435526422ce3a36044ef937569f0ce2bf0694b01138df082a154834`.
Desktop y móvil 390×844 muestran lienzo y controles sin desbordamiento horizontal.
Se comprobaron también los casos de Agentes oscuro y símbolo de Cauce.

El observador de descarga agotó 15 segundos; el clic produjo un archivo nuevo
en Descargas, cuyas dimensiones, hash y píxeles se comprobaron directamente.
No se convierte ese timeout en una afirmación de evento observado.

En producción se crearon tres planes de render de cliente, sin renderer de
servidor ni publicaciones: Sinergia 2492, Agentes 2493 y Deméter 2494.
`202 → plan 200` devuelve 1080×1350, Manrope y contenido de su producto.
Los bytes de originales coinciden por SHA; Agentes devuelve fondo `#111319`;
Deméter conserva ausencia de logo, sin inventar un isotipo.

La suite general anterior a los últimos casos de tema/exportación tuvo 867
aprobadas y dos omisiones por demos ausentes. Los deltas de familia y
exportación tuvieron 36 aprobadas; frontend final 75 aprobadas y build TS/Vite
correcto. No se atribuye una nueva corrida global al SHA desplegado.
Código y procedimiento de aplicación recibieron revisión independiente.

## Conservación y límites

El respaldo de producción se restauró en un clon sin red; doble `init_db`
conservó filas y columnas. Antes de aplicar perfiles se respaldaron las quince
marcas y se validaron todos los payloads, hashes, versiones y slugs persistidos.
La API de marcas no ofrece CAS: se hicieron comprobaciones antes y después
de cada PUT, sin prometer una transacción atómica entre las quince marcas.
Los quince cambios terminaron verificados; no se hizo rollback automático.

No hay medios nuevos aprobados ni publicaciones sociales enviadas por esta
entrega. Las versiones anteriores e historial se conservan; las piezas nuevas
requieren briefs y revisión sobre la versión actual. Los temporizadores
antiguos de Humanizar siguen deshabilitados e inactivos.

La pestaña de producción pide iniciar sesión; su prueba visual autenticada
sigue pendiente del acceso del operador. La revisión visual local y la lectura
API desplegada no se presentan como ese recorrido GUI terminado.

Campañas, revisión completa, conexiones sociales multiempresa, calendario y
panel operativo siguen sin implementar. Su diseño escrito del 11 de octubre
está pendiente de aprobación antes de preparar el plan. La meta del chat
permanece activa; este recibo acredita sólo la entrega de identidad existente.

## Referencias recuperadas después del despliegue

El 11 de octubre, 19:56 UTC, se fijaron Aletheia115/v4 y Prizma120/v5 en la
empresa Humanizar. La primera exporta el cuadro y glifo del componente original
(SHA `d86f747d80f6513191c21b67767948fd620a451e5e7332691c94ead4aac262b2`);
la segunda copia el master exacto del Header actual
(SHA `1972d07aa3c96ccd3925580271b514ed187599fc1fc8d16c0fb50df95d3dc9c1`).
La API devuelve los mismos bytes y conserva todos los otros campos. MCP nativo
confirma ambas versiones y hashes. Hay doce referencias fijadas; quedan
Deméter, Gravitatoria y Práxis. Sus fuentes no justifican fijar un signo propio
inequívoco: dos usan Lucide y la otra comparte marca con Mouseîon/personal.

La comparación de fuentes se vio en navegador local; la prueba del Estudio
quedó interrumpida por un panel de extensión. No es una prueba GUI de producción
ni una aprobación editorial. El delta del exportador tiene revisión independiente,
16 pruebas; junto al core de familia pasan 47. No hubo nuevo despliegue runtime:
las referencias son datos atendidos por la revisión `eikon-00059-9h5` existente.
