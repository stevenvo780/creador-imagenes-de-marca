# Decisiones de implementación del centro de publicaciones

Registro al 12 de octubre de 2026. Complementa el diseño y el plan aprobados;
no acredita despliegue ni publicaciones reales. Los informes de implementación
y revisión conservan la evidencia detallada por tarea.

| Decisión | Motivo | Coste o límite |
|---|---|---|
| Cada empresa conecta su propio cliente Codex y sus cuentas; el trabajador ejecuta únicamente entregas autorizadas de esa empresa. | Aislar suscripción, identidad, contenido y permisos. | Un cliente desconectado deja déficit de contenido visible; el servidor no inventa imágenes o decisiones. |
| Mantener separados la revisión humana visual y el juicio editorial autónomo de IA. | La aprobación del logo o de una imagen no autoriza por sí sola texto, cuenta y horario. | Son estados diferentes en la interfaz; ninguna puntuación legacy equivale a decisión editorial. |
| Congelar archivo, logo, texto, formato, cuenta, fuentes y horario antes de evaluar. | La IA y el trabajador deben referirse a la misma pieza exacta. | Cualquier edición exige nueva revisión y evaluación; los hashes históricos no se recalculan. |
| Preservar los bytes originales de los logos y la familia Humanizar. | Completar identidad visual sin redibujar signos oficiales ni separar en exceso los productos. | Las ilustraciones se componen con el logo exacto; el medio final requiere revisión propia. |
| Usar grants distintos para planner, reviewer y worker, además de las claves existentes de galería. | Evitar que un permiso de importar archivos conceda evaluación o despacho. | Configuración privada adicional por empresa; no hay fallback a una clave antigua. |
| Conservar el recibo de evaluación como declaración del cliente vinculada a materiales y modelo. | Registrar razonamiento real y correlación sin afirmar una atestación criptográfica inexistente. | La prueba con el modelo y MCP reales sigue siendo obligatoria; un double no la reemplaza. |
| Entregar contexto factual congelado y URLs autorizadas a la IA. | Evaluar afirmaciones contra la evidencia realmente disponible. | El cliente debe recuperar hechos antes de congelar; una URL sola no prueba el contenido ni permite inventar hashes de documentos. |
| Permitir que la decisión editorial `approve` programe en una segunda transacción idempotente. | Recuperar un fallo entre evaluación y calendario sin duplicar decisiones. | La revalidación puede retener la entrega aunque la decisión se conserve aprobada. |
| Deduplicar por empresa, cuenta canónica y SHA del medio, conservando retiradas e intentos inciertos. | Evitar repeticiones incluso al cambiar alias, texto o modo de API. | Una entrega incierta necesita conciliación; borrar un post no libera la pieza para repetirla. |
| Registrar fases durables antes de cada operación remota; recuperar mediante consultas. | Un ACK perdido no debe producir otro POST. | Si falta evidencia de resultado, se muestra incertidumbre en lugar de éxito o reenvío. |
| Retener el mismo candidato tras una retención previa del trabajador. | Evitar ciclos de reclamación y envío con requisitos incompatibles. | Reintentar requiere una nueva revisión y evaluación; no se reinician guardias silenciosamente. |
| Contar el inicio y, cuando se acredita, el día real de publicación en la zona de la política. | La llegada tardía de un reporte no es la fecha de publicación. | Un resultado entre días sin hora remota comprobada puede retener conservadoramente esa cuenta. |
| Mantener las URLs temporales deshabilitadas hasta comprobar descarga, revocación y logs desplegados. | El proveedor necesita acceder al archivo exacto sin exponer secretos en observabilidad. | Horizonte máximo de procesamiento de 65 minutos, sin renovaciones indefinidas; la prueba real es requisito de activación. |
| Conservar Instagram vídeo como REELS y declarar explícitamente `share_to_feed`; distinguir Facebook feed de reel. | Publicar el formato soportado y evaluado, sin inventar un tipo remoto. | Foto, vídeo y reel tienen pruebas de aceptación independientes. |
| Importar evidencia TikTok únicamente por un controlador privado confiable. | Ningún checkbox o valor del planner acredita dominio, revisión, elegibilidad o auditoría pública del proveedor. | Frontera de confianza operativa, sin endpoint público de verificación; exige evidencia externa real en producción. |
| Fijar el recibo exacto de consentimiento TikTok al primer GET válido de la reserva. | Impedir que el inicio valide un recibo distinto del que recibió el trabajador. | Rotar, revocar o vencer ese recibo retiene la reserva; no se sustituye automáticamente por otro. |
| Congelar privacidad y las cuatro opciones TikTok de comentarios, duet, stitch y contenido generado por IA. | Los ajustes publicados deben coincidir con los evaluados y consentidos. | Valores ausentes retienen; cambiar una opción exige nueva revisión. La procedencia IA conocida requiere divulgación explícita. |
| Exigir creator_info fresco al confirmar, pero limitar el consentimiento final por ventana, evidencia, conexión y política. | Permitir consentir una pieza programada sin obligar a hacerlo cinco minutos antes. | El trabajador consulta de nuevo las opciones actuales antes de iniciar; incompatibilidad o revocación retienen. |
| Tratar SELF_ONLY como contenido privado. | Un procesamiento terminado o publish_id no acredita publicación pública. | No se presenta como éxito público ni cierra el requisito de auditoría pública. |
| Exponer la bandeja al planner con su permiso existente y un objetivo de stock explícito del cliente. | Consultar pendientes y entregas autorizadas sin utilizar la sesión owner o el grant reviewer. | El máximo diario sigue siendo un techo, no una demanda. La proyección no modifica decisiones ni permisos. |
| Calcular stock para el día local de la política, por cuenta y SHA únicos, reutilizando la cuota existente. | Evitar contar dos veces una pieza o descontar capacidad con una regla distinta del trabajador. | Entregas iniciadas, inciertas, vencidas o retenidas por el trabajador no son stock disponible; cada bloqueo se muestra por separado. |
| Mostrar hashes históricos de cuentas permitidas con límites de lectura explícitos. | Ayudar al cliente a elegir medios que no se hayan usado antes. | Una lista parcial no acredita historial completo; la guardia del backend conserva la autoridad contra duplicados y retiradas. |
| Devolver el mismo consentimiento TikTok para un reintento idéntico todavía vigente. | Recuperar una respuesta perdida sin invalidar el recibo fijado al claim. | No se renueva el vencimiento ni se revive un recibo revocado; un refresh real puede rotar autoridad y retener el claim antiguo. |
| Mantener X retenido por presupuesto. | El operador decidió no pagar créditos ni añadir un método de pago. | No se hacen llamadas facturables; la operación real de X sigue bloqueada externamente. |
| Cerrar primero código y revisión, luego ejecutar el despliegue con respaldos y pruebas reales. | Evitar activar un trabajador antes de revisar contratos y verificador. | Cualquier defecto encontrado en producción vuelve a implementación y revisión antes del nuevo despliegue. |
| Habilitar el nuevo timer y heartbeat sólo tras la prueba diaria real y su segunda ejecución. | La instalación o el registro de una automatización no prueban funcionamiento ni ausencia de duplicados. | Los timers antiguos permanecen apagados; el heartbeat local requiere el equipo encendido y la app abierta. |

La aceptación final distingue `verified`, `externally_blocked` e `incomplete`.
Un bloqueo de proveedor, auditoría o presupuesto no se convierte en PASS global.
Los cambios de rama y el despliegue están autorizados; esta iteración no incluye
merge a `main` ni cambios de presupuesto publicitario.
