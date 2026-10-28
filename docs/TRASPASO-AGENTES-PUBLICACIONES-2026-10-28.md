# Traspaso de publicaciones de Humanizar a agentes responsables

Corte: **28 de octubre de 2026, 22:00 UTC / 17:00 Bogotá**. Empresa 17.
Estado: auditoría de los tres últimos ciclos completada; destino de los agentes
pendiente de definición. Este documento prepara el traspaso: **no acredita una
migración activada**. La meta global de cinco destinos y 17 productos continúa
incompleta y bloqueada.

## Decisión del operador

El 28 de octubre el operador pidió revisar los últimos días y eliminar el
programador que mantenía este chat activo para empezar la migración a los
agentes responsables. Se eliminó `humanizar-publicaciones-diarias` mediante
la herramienta nativa de la app: respuesta `deleteStatus=deleted` y archivo de
configuración ausente después del borrado. Se conserva un respaldo privado
del estado anterior y un recibo. **No recrear ese seguimiento automáticamente.**

El publicador de producción en server2 es otro componente. Su timer
`eikon-publisher@17.timer` quedó sin modificar y estaba
`active/waiting/enabled` en la observación del 28 de octubre, 16:47 Bogotá.
El servicio oneshot `inactive/dead/success` entre activaciones es normal.
La eliminación del seguimiento del chat no elimina publicaciones ni filas
de la cola, ni completa la meta.

## Resultado de los últimos tres ciclos

Las nueve publicaciones fueron realizadas por el timer existente, sin inicio
manual ni nuevo envío durante esta auditoría. Se comprobaron con nueve GET
Graph 200, nueve descargas CDN anónimas 200, cotejo de contratos y revisión
visual de los seis archivos CDN distintos, tres originales y tres referencias.
Los pares de Facebook de cada ciclo son idénticos byte a byte. Facebook sirve
720×900 e Instagram 1080×1350, conservando logo, composición, textos y pie
Humanizar. Es evidencia API/CDN/archivos; **no una comprobación de interfaz Brave**.

| Día en Bogotá | Producto | Entregas | Facebook Systems | Facebook Humanizar | Instagram | Resultado |
|---|---|---|---|---|---|---|
| 25 de octubre | Prizma | 38/39/40 | 22:50:22 | 22:50:30 | 22:51:45 | 3/3 publicadas |
| 26 de octubre | Práxis | 41/42/43 | 22:51:22 | 22:51:31 | 22:52:47 | 3/3 publicadas |
| 27 de octubre | Érgon | 44/45/46 | 22:52:23 | 22:52:32 | 22:53:48 | 3/3 publicadas |

Enlaces públicos verificados el 28 de octubre:

| Producto | Facebook Systems | Facebook Humanizar | Instagram |
|---|---|---|---|
| Prizma | [Publicación](https://www.facebook.com/122127579183283523/posts/122128697619283523) | [Publicación](https://www.facebook.com/1008644758939132/posts/1022268400910101) | [Publicación](https://www.instagram.com/p/De8W22ckWiZ/) |
| Práxis | [Publicación](https://www.facebook.com/122127579183283523/posts/122128782309283523) | [Publicación](https://www.facebook.com/1008644758939132/posts/1023343037469304) | [Publicación](https://www.instagram.com/p/De-7xSdEQJ_/) |
| Érgon | [Publicación](https://www.facebook.com/122127579183283523/posts/122128871433283523) | [Publicación](https://www.facebook.com/1008644758939132/posts/1024315674038707) | [Publicación](https://www.instagram.com/p/DfBgrhkjv3U/) |

Las invocaciones identificadas, con START, resultado `completed_sweep3` y
FINISH normal, son `b07b0134ae224a10a0d669821dd27ad7`,
`5dfce6b0b70f4fc6ad70f8b927489dc4` y
`e467a9b4d8934cae8e02e4a74e047335`, respectivamente. El journal se recuperó
en tres intervalos disjuntos: no se afirma un escaneo continuo de 72 horas.

La comparación del snapshot del 25 con el del 28 confirma que las otras
46 entregas y ocho grupos comparables de autoridad/historial siguen iguales.
Sólo se añadieron nueve claims/materiales, 27 eventos (233–259) y tres tickets
Instagram (11–13). No hay comparación de dos snapshots históricos alrededor
de los idle de esos días; no se acredita igualdad de toda la base, lectura
directa de outbox ni un contador global de POST. La auditoría no envió contenido.

Los campos `published_at_utc` y `permalink` de los resultados PG siguen nulos;
las fechas y enlaces anteriores proceden de Graph. Los tickets Instagram se
revocaron en el ACK, sin solicitar posteriormente su misma URL raw. No se
midieron los bytes descargados por Meta ni se afirma un HTTP 404.

## Cola original que recibe el nuevo responsable

Snapshot de producción del 28 de octubre, 21:50:42 UTC. Nueve filas existentes
retenidas por `frequency_limit`, sin inicio, claim, intento, lease, worker o
resultado. Conservan las ventanas **22:45–23:45 Bogotá**:

| Día | Producto | Medio | Entregas originales | Revisiones | Decisiones |
|---|---|---|---|---|---|
| 28 de octubre | Systems | 63 | 47/48/49 | 51/52/53 | 48/49/50 |
| 29 de octubre | News | 61 | 53/54/55 | 57/58/59 | 54/55/56 |
| 30 de octubre | Sinergia | 65 | 50/51/52 | 54/55/56 | 51/52/53 |

El timer despacha contenido autorizado: **no genera ni repone la reserva**.
No hay ciclos posteriores al 30 de octubre acreditados en este corte. Las
fechas son planificación, no publicaciones garantizadas. Cada claim debe
reevaluar la misma fila con autoridad, política, permisos, caducidad, medio,
cuotas y frecuencia actuales. Los 1440 minutos consideran inicios y fecha del
proveedor cuando está disponible en PG; 24 horas entre ventanas no garantizan
elegibilidad a las 22:45. No mover fechas, recrear filas, eliminar guardas o
consumos ni rearmar entregas para forzar una ejecución.

## Responsabilidades propuestas para el traspaso

| Responsabilidad | Entrada y permiso mínimo | Resultado y límite |
|---|---|---|
| Editorial y producción visual | Empresa 17, hechos actuales de los productos, logos originales; Codex propio y MCP de galería/planner/reviewer | Mantener reserva; evaluar realmente los seis criterios del contrato exacto y pertinencia/deduplicación. La aprobación del propietario de galería es un proceso separado. |
| Ejecución social | Worker existente de server2, grant 6 y política 2 | Despachar sólo filas elegibles para las tres conexiones Meta. Mantener un ejecutor, aislamiento por empresa y recibos; no dar el grant worker al cliente MCP editorial. |
| Verificación y conciliación | Recibos, journal y acceso de lectura a cuenta/ID/medio exactos | Comprobar autor, texto, fecha, ID, medio y enlace; conciliar el mismo intento incierto sin nueva subida. Alertar fallos, stock insuficiente y vencimientos. Distinguir API, CDN y UI. |
| Conexión de redes pendientes | Brave autorizado y respuestas humanas concretas | Completar X sin gasto y TikTok sin saltar CAPTCHA/MFA, consentimientos o requisitos del proveedor. No sustituir navegador o copiar sesiones. |
| Propietario de la marca | Control total de la página Facebook Humanizar | Resolver logo/datos antiguos; el acceso actual a tareas permite publicar, pero no acredita esa edición. |

El destino concreto de estos agentes está pendiente de respuesta del operador.
No se han creado agentes persistentes, trasladado secretos, cambiado grants ni
activado un nuevo planificador. El traspaso efectivo deberá registrar identidad
del responsable, tenant y scopes mínimos mediante mecanismos privados; los
tokens, contraseñas y respaldos no se incluyen en este documento ni en Git.
Los grants 4/5/6 vencen el **11 de noviembre a las 22:32:11 Bogotá** según
el corte actual; revisar antes de vencer, sin renovación rutinaria anticipada.

## Pendientes que impiden declarar las cinco redes completas

- Brave no apareció en el inventario actual. La reconexión ya se pidió;
  no se repitió ni se usó Chrome/IAB como sustituto.
- X conserva publicaciones históricas comprobadas del 13/14 de octubre;
  Xenía del 15 no tiene verificación nueva. No hay nuevas programaciones
  posteriores al 15 confirmadas. Mantener cero créditos y API facturable.
- TikTok conserva tres IDs nativos del 13/14/15; el primero tiene verificación
  parcial y CAPTCHA pendiente, y los otros dos carecen de verificación actual.
  No reenviar publicaciones antiguas para sustituir esa comprobación.
- TikTok Developers sigue en Draft, con icono/términos/privacidad/demo y
  Direct Post pendientes. No hay conexión API acreditada. Siguen pendientes
  las decisiones humanas ya solicitadas sobre `user.info.basic` y
  `video.publish` (sin `video.upload`), responsable legal/domicilio/contacto,
  conservación y derechos, y diseño acotado de páginas públicas.
- Los 17 productos tienen historia o planificación. Eso no acredita la
  publicación y recurrencia de todos en los cinco destinos.

Conservar las protecciones: entrega Instagram 10 retenida antes de START por
edit lists del MP4, intento 4 cerrado `failed_before_dispatch` y vídeo con audio
de revisión 11 retenido sin entrega. No rearmar, relajar validaciones ni crear
revisiones para saltar esas exclusiones. Un futuro vídeo requiere original
nuevo calificado y evaluación real; no mutar el original retenido.

La observación histórica de metadata incompleta de Gravitatoria queda abierta:
un resultado sin InvocationID no se atribuye por tiempo/PID/unidad. Los tres
intervalos actuales completos no reparan esa brecha histórica. Los ensayos
anteriores de recuperación y medios siguen acotados; no repetirlos por rutina
ni ampliar su aceptación a restauración GCS, atomicidad o runtime compuesto.

## Evidencia conservada

Recibos privados conservados fuera de Git, con nombres y hashes verificables:

| Evidencia | Archivo | SHA256 |
|---|---|---|
| Borrado nativo verificado del seguimiento | `automation-deleted-verified-receipt.json` | `5be046b67a8f0d18f25b5b8e19ffc1fc038c1a76875556c9acf9a7b8fe525cd2` |
| Snapshot PG de sólo lectura | `recovery-pg-v2-20261028T215035180698-receipt.json` | `8b44aad7606bb709c83568abe8e0ebc2e3dcd1ef490526046e07aed78cc2a2e9` |
| Journal saneado de los tres intervalos | `recovery-journal-summary-20261028T214721117810-receipt.json` | `d6169f4be8c995fd2efaa0c9ff195c3dc513964615bed72b8664d5f26ca4c036` |
| Nueve respuestas Graph/CDN | `exact-nine-remote-v2-verify-20261028T215400829397-receipt.json` | `28c277b98f1fea3eda30b340d78a8c989dc711a9e28d5920f89beb96bba756cb` |
| Inspección visual suplementaria | `coordinator-cdn-visual-review-receipt.json` | `7aae9c15f0a809dbe739f4c4e4a10b61d194a5a0032191ac7011015a35d5817d` |
| Comparación acotada del historial | `local-retrospective-ledger-comparison-receipt.json` | `6fd687f68a123349c50b1f62bfd26597c17dbfe60e9e9a3fc725a1406654e876` |
| Tres ciclos originales pendientes | `current-future-three-cycles-receipt.json` | `cc349256fddb1c3a1303e23a4d9970cb2f531ab05ad84a862234ab333bdf6a88` |
| Revisión independiente final acotada | `review-recovery-final.md` | `6d0596e510fcee10a1f7d2ba603773ecb4f1c60644cea287cc4910d3b798f7f8` |
| Manifiesto de revisión independiente | `review-recovery-final-manifest.json` | `edfdd697cb9d6db02433adfac7386d5d934dd03eb54fb580a8ae2df9d39339e8` |

Dos primeros lectores de esta auditoría fallaron cerrados por supuestos locales
incorrectos: versión numérica del secreto DB en vez de su referencia real
`latest`, e índice OCI en vez de la imagen AMD realmente desplegada. Fallaron
antes de DB/vault/proveedores. Se conservaron, se diagnosticaron mediante
metadata, se revisaron versiones nuevas con los bindings reales y se ejecutó
cada versión correctiva una vez. No fueron fallos del publicador ni motivaron
cambios de producción o reenvíos sociales.
