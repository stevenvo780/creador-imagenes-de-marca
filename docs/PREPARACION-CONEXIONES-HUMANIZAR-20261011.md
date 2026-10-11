# Conexiones y conservación del historial Humanizar

Inspección real del 11 de octubre de 2026. Es preparación de migración y
verificación GET; no implementa conexiones multiempresa ni importa autorizaciones.

## Identidades y permisos comprobados

Desde server2, usando exclusivamente las credenciales existentes en ese host:

| Alias actual | Destino canónico candidato | GET verificado UTC | Permisos efectivos |
|---|---|---|---|
| facebook_systems | facebook:1045986888587355 | 20:08:28 | pages_manage_posts, pages_read_engagement, pages_show_list |
| facebook_humanizar | facebook:110421192090737 | 20:08:29 | Los mismos tres |
| instagram_news | instagram:17841434345672986 | 20:08:29 | instagram_business_basic, instagram_business_content_publish |

Instagram coincide con humanizar.news. La respuesta no informó su vencimiento
(`expiry_known=false`): validez en ese instante y renovación sostenida son
comprobaciones distintas. Facebook usa facebook_login e Instagram instagram_login;
cambiar modo no crea otro destino para deduplicación. No se emitieron nuevas
credenciales ni se ampliaron permisos. X conserva gasto excluido; TikTok conserva
sandbox y OAuth social/publicación por API pendientes. No se comprobaron ambos.

## Tres colas privadas existentes, sin modificación

El [inventario saneado](MIGRACION-HUMANIZAR-INVENTARIO-20261011.json) contiene:

- Cola diaria: 14 entregas, seis envíos históricos y ocho pendientes retenidos.
- Pruebas Facebook del 8 de octubre: dos envíos históricos adicionales.
- Prueba Instagram del 8 de octubre: un envío histórico adicional.
- Cuatro retiradas cotejadas por ID de entrega, foto y destino con la cola diaria.

Los hashes de los tres archivos SQLite no cambiaron durante las lecturas.
Ambos temporizadores antiguos siguen disabled/inactive. No se transfieren las
ocho fechas antiguas como autorizaciones nuevas ni se reactivan los timers.

Los IDs se repiten entre bases: entrega1 de la cola diaria y entrega1 de una
base de prueba son hechos distintos. La futura clave de importación debe
incluir fuente/cola/ID y empresa; no basta delivery_id.

Los siete posts diarios usan una imagen SHA idéntica y siete contratos
editoriales distintos. image_review.sha256 identifica el archivo;
editorial_review.reviewed_sha256 congela contenido y archivo. Se verificó
el contrato almacenado contra content_digest_with_image_hash del publicador
instalado; no se confundieron esas huellas. Cambiar caption no elimina la
guardia histórica para la misma imagen y cuenta.

## Corte de migración todavía incompleto

Las cinco pruebas manuales web del 8 de octubre están documentadas en
ComercialHumanizar, docs/PUBLICACIONES-PRUEBA-20261008.md. No están en estas
bases y deben conciliarse antes del primer claim nuevo. La URL antigua de
Humanizar no se da por equivalente a un ID API por parecido del nombre;
se necesita evidencia de alias/destino.

El inventario conserva complete_history_claimed=false e import_executed=false.
No prueba un ledger instalado, aprobación nueva ni visibilidad actual de todos
los recibos. Las retiradas conservan el hecho de envío y su guardia histórica.
