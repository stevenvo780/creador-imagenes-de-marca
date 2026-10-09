# Runbook de release: galería privada y Codex MCP

Estado al **2026-10-09 16:24:04 UTC**: preflight y flujo nativo local con pieza aprobada documentados; **release no ejecutado**. GUI sigue bloqueada por panel de extensión Brave. Producción conserva código anterior `6fe3ad5`, revisión **`eikon-00056-jjs`**; comprobación saneada del controlador 15:34Z. SHA de release, digest e IDs de producción están pendientes.

Este runbook prevalece para esta entrega sobre los ejemplos de provisionamiento de [DEPLOY.md](DEPLOY.md). Destino existente: proyecto **`emergent-enterprises`**, Cloud Run **`eikon`**, región **`us-central1`**; frontend/proxy Vercel existente **`eikon-proxy`**, con rewrite hacia Cloud Run. Se conserva la cuenta autorizada actual, sin copiar sesiones, cambiar perfil ni crear recursos externos. Producción requiere Postgres y almacenamiento persistente privado.

## Responsabilidades y orden

El controlador opera cuenta/vault/inventario real, backups privados, conexión nativa Codex, `image_gen`, Cloud Run/Vercel y los recibos reales. Task7 opera GUI; Task8 escribe estas guías y el ledger de evidencia. Un solo escritor por área. Ante defecto de producto, volver al escritor asignado y revisar el delta antes de avanzar.

1. Código y pruebas con SHA exacto; revisión Task8 y revisión independiente de rama completa.
2. GUI real, logo/font/renderer cliente, revisión humana y sesión/tenant. El bloqueo GUI actual impide cerrar aceptación.
3. Preflight real de cuenta/servicio/DB/bucket/proxy, copia recuperable y ensayo aislado de migración/compatibilidad.
4. Build saneado y actualización **sólo de imagen** en el servicio existente, preservando configuración/recursos/costos/IAM/red.
5. Prueba funcional acotada desplegada; recibo SHA/digest/revisión, autenticación/proxy/MCP/privacidad, timers/cola; actualización de evidencia documental.

No ejecutar ciegamente `bash deploy/cloud-run.sh`: además del build, cambia memoria/CPU, throttling/boost, concurrencia, timeout, min-instances e IAM mediante `--allow-unauthenticated`. Esta fase no autoriza esos cambios ni habilita generación de imágenes pagada. No añadir servicios o un nuevo publicador para conseguir un gate verde.

## Preflight privado

Guardar configuración completa, referencias a secrets, DB dump, metadatos/hash y comandos de recuperación **fuera de Git**, con permisos privados y sin imprimir valores. Los agentes sólo reciben los recibos saneados.

| Comprobación | Estado recibido | Siguiente evidencia |
|---|---|---|
| Cuenta/service/region/proyecto | Cuenta actual autorizada, servicio existente ready | Revalidar justo antes de mutación, sin login alternativo |
| Recursos actuales | CPU2, memoria2Gi, revisión eikon-00056-jjs | Capturar y comparar configuración privada completa antes/después; conservar escalado/IAM/red/secrets |
| PostgreSQL backup/restauración | PG17 restaurado sin red/puertos, Python final 259101b `init_db` dos veces; datos originales idénticos | Confirmar que DB/migration/schema no cambiaron desde el recibo; backup actual antes de release |
| Rollback compatible | Código anterior 6fe3ad5: startup y lecturas `/auth/me`, `/api/v1/brands`, `/health`200, anónimo brands401 en clon migrado | No extrapolar a worker/escrituras ni borrar tablas/historia |
| Bucket real | IAM sin allUsers/allAuthenticatedUsers; objeto anterior anónimo403 | Confirmar ACL/política de objetos nuevos, persistencia y descarga autenticada por backend |
| Vercel proxy | Proyecto existente con rewriteall al servicio | Probar rutas profundas, cookies y multipart realmente; no inferirlo del archivo de configuración |
| Sesión propia/inventario | Login API propio 16:24:04Z por proxy HTTPS: /auth/login200, /auth/me200, owner, cookie Secure/HttpOnly/SameSiteLax. Systems/News sólo importadas localmente | Sin key nueva ni release; inventario propio de producción pendiente |
| Humanizar | Dos timers existentes activos y sin cambios | Confirmar estado/cola antes/después sin iniciar worker nuevo |

Lecturas CLI de preflight sugeridas, **a ejecutar sólo por el controlador**, con cuenta actual explícita y salida saneada:

```bash
gcloud auth list --filter=status:ACTIVE --format='value(account)'
gcloud run services describe eikon --project emergent-enterprises --region us-central1 --format='value(status.latestReadyRevisionName)'
gcloud meta list-files-for-upload
```

La primera salida se compara en privado con la cuenta autorizada; no adjuntar cuentas adicionales. No imprimir YAML completo, DATABASE_URL, keys ni secrets. Verificar el contexto de build antes de subirlo: sin `.env`, vault, dumps, logs de conversaciones, sesiones, artefactos/datos privados ni dependencias locales.

Si el bucket comparte objetos públicos con otra aplicación, documentar la dependencia y obtener la decisión necesaria antes de tocar IAM/ACL compartidos. No privatizar objetos ajenos ni hacer público el nuevo prefijo. Si faltan permisos externos o la sesión no funciona, entregar el preview local verificado y el bloqueo concreto.

## Ensayo de migración y recuperación

Usar dump privado restaurado en instancia aislada sin red/puertos. Ejecutar `init_db` dos veces y comparar columnas originales contra otra restauración limpia del mismo dump; no aceptar sólo que arranque. El recibo actual conservó4 tenants / 4 users / 62 brands / 6 keys y cuatro tablas nuevas vacías. SQLite/PG16 sintéticos cubren las pruebas; PG17 privado prueba compatibilidad con el snapshot real. Mantener estos alcances separados.

No hay downgrade destructivo aprobado. La reversión de aplicación conserva esquema aditivo, assets e historial. Si las lecturas legacy dejan de funcionar o la imagen nueva falla, usar el digest/revisión anterior capturado para revertir tráfico o imagen, preservando configuración. No eliminar filas, reseedear producción, perder revisiones o restaurar un dump sobre escrituras nuevas para ocultar fallos. El recibo actual no demuestra todo el worker ni el rollback de escrituras; un flujo afectado exigiría ensayo adicional aislado.

## Build y actualización de imagen

Elegir el SHA después del gate de revisión y registrar tree limpio, test receipts y manifest de build saneado. Resolver la imagen a digest inmutable; una etiqueta `latest` sola no identifica el release. Mantener referencias locales en variables ya resueltas por el controlador:

```bash
git rev-parse HEAD
git status --short
git diff --check
# EIKON_RELEASE_IMAGE_REF: imagen existente construida de ese SHA, fijada por @sha256.
# Sin cambiar env, secretos, recursos, IAM, red o proyecto:
gcloud run services update eikon \
  --project emergent-enterprises \
  --region us-central1 \
  --image "$EIKON_RELEASE_IMAGE_REF"
```

Este bloque es una receta condicionada a los gates, **no un recibo de ejecución**. El controlador debe comprobar que la variable apunta al digest autorizado y que la configuración realmente permanece igual. El flujo de build existente se verifica antes de usarlo; no crear repositorios/servicios ni habilitar facturación nueva. Conservar revisión previa y reparto de tráfico para reversión. Vercel mantiene el proxy existente; sólo tocar su configuración si un defecto verificado lo exige dentro del alcance autorizado.

## Prueba funcional desplegada

No cerrar release con `/health`200. Ejecutar en la URL HTTPS real del proxy y, cuando corresponda, del backend:

1. Owner inicia sesión; `Set-Cookie` `HttpOnly`, `Secure`, `SameSite` y ámbito same-origin comprobados sin copiar cookie a recibos. Refresh de `/projects` y `/gallery` carga la SPA correcta; assets/chunks funcionan.
2. Inventory dry-run con referencias vigentes y logos exactos: conservar conflictos, aplicar únicamente marcas del propietario autorizado. Nunca importar las56 legacy a Humanizar ni sustituir identidad/tenant por coincidencia de nombre.
3. Owner crea/revoca key scoped por canal privado; cliente Codex **real** ejecuta list/brief/import/list contra el **destino desplegado**. El recibo local CLI no satisface este paso; la prueba SDK stdio tampoco.
4. Importar pieza válida de empresaA mediante multipart **a través del proxy**: MIME/dimensiones/hash exactos, `pending_review`, replay mismo recurso, thumbnail/original propios200 privados/no-store; archivo/texto/identidad no se sobrescriben. Conservar logo original y Manrope, inspeccionar píxeles.
5. Owner decide revisión sobre hash+versión actuales; key-review403, historia persistida. Obtener otra pieza autorizada de empresaB y probar ambas direcciones: encargo/original/thumbnail ajenos404, anónimo401. Comprobar también que URLs directas de GCS no permiten descarga anónima de esos objetos.
6. GUI real desktop/mobile: filtros/paginación/detalle/snapshot/logo, roles/keys/foco y cambio A→logout→B sin datos de A; modern-screenshot/FontFace y upload cliente reales. Conservar capturas privadas y respuestas saneadas.
7. Revalidar SHA/digest/revisión ready, Postgres persistente, bucket privado, configuración sin cambios y timers/cola de Humanizar. No aprobación automática ni publicación social.

Si el proxy trunca multipart, la cookie se pierde, GCS expone objetos o aparece una diferencia de configuración, preservar evidencia negativa y detener aceptación. Corregir por el escritor asignado y repetir sólo los checks afectados; no saltar al backend directo para declarar el proxy PASS.

## Recibo de release y pendientes

Completar sin secretos ni datos de otros clientes:

| Campo | Valor actual |
|---|---|
| Estado Task8/release | Documentación con reservas; release pendiente |
| SHA candidato base | ea9aab7d01bb23b901adafb0a0cdf949c97f062c; el SHA final se fija después de revisión |
| SHA desplegado anterior / revisión | 6fe3ad5 / eikon-00056-jjs, recibo 15:34Z |
| SHA/digest/revisión nueva | PENDIENTE |
| Build local previo a docs | ea9aab7 exact git archive, UID1001/sin red/ASGI sintético PASS; ImageID sha256:0de3c7be576e7b2098f6f7194156be15f2b5977c14b1f158a5d3a780d8fa086a; no digest publicado |
| Proyecto/región/servicio/proxy | emergent-enterprises / us-central1 / eikon / eikon-proxy |
| Copia/migración/rollback | Recibos privados PG17; sólo compatibilidad startup/lecturas legacy comprobada |
| Codex nativo local | Pieza 3/brief 1/review 2 approved; SHA aa58e57f036e6f979616301fd1fed07c346891b7f6c7e4c74451fbb4b44f7255 |
| Auth/MCP/UI de producción | Auth API por proxy HTTPS verificada las 16:24:04Z con credencial original propia; cookie Secure/HttpOnly/SameSiteLax. MCP y UI siguen PENDIENTES. Bridge clipboard fallido preservado como negativo |
| IDs/hash/upload/review/aislamiento de producción | PENDIENTE; los IDs locales no se trasladan al entorno desplegado |
| GUI | BLOCKED panel extensión Brave, GET /auth/me401 en servidor sintético |
| Cookie/proxy/multipart/GCS nuevo real | Cookie login en proxy verificada; rutas profundas/multipart/objetos nuevos GCS PENDIENTES |
| Timers/cola | Timers existentes activos/sin cambios según controlador; recibo posterior pendiente |
| Hallazgos anteriores | Gitleaks historia 1 hallazgo comentado; delta previo 0. Npm lock 5 vulnerabilidades heredadas. Sin ocultarlos ni marcar whole-lint limpio |

La evidencia completa queda fuera de Git. El recibo saneado registra timestamp, origen de evidencia, SHA/digest, IDs autorizados, hashes, HTTP/resultados y límites. Una omisión mantiene `PENDIENTE/BLOCKED`; no es PASS. Tras el release, Task8 actualiza estas guías y recibe revisión del delta documental. Redes sociales/calendario/publicador diario tienen entregas separadas.
