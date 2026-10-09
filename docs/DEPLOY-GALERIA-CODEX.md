# Runbook de release: galería privada y Codex MCP

Estado verificado al **2026-10-09 UTC**; releasefinal **19:42:39Z** y timers≈19:46Z: código **`2ee2ca2349098991e09ac30e919a2aafeb577873`** en **`eikon-00058-t9n` al100%, cero tags**, configuración salvoimagen/IAMservicio-bucket preservados. MCP nativo persistente, privacidad simétrica, ownerreview, business_cardcliente y ajustevisualmóvil verificados. **Primera entrega desplegada con límitesQA explícitos**: descarga del botónGUI no confirmada/otrosformatos y matrizGUI completa no certificados. Sin mainmerge ni publicaciónsocial.

Este runbook prevalece para esta entrega sobre los ejemplos de provisionamiento de [DEPLOY.md](DEPLOY.md). Destino existente: proyecto **`emergent-enterprises`**, Cloud Run **`eikon`**, región **`us-central1`**; frontend/proxy Vercel existente **`eikon-proxy`**, con rewrite hacia Cloud Run. Se conserva la cuenta autorizada actual, sin copiar sesiones, cambiar perfil ni crear recursos externos. Producción requiere Postgres y almacenamiento persistente privado.

## Responsabilidades y orden

El controlador opera cuenta/vault/inventario real, backups privados, conexión nativa Codex, `image_gen`, Cloud Run/Vercel y los recibos reales. Task7 opera GUI; Task8 escribe estas guías y el ledger de evidencia. Un solo escritor por área. Ante defecto de producto, volver al escritor asignado y revisar el delta antes de avanzar.

1. Código y pruebas con SHA exacto; gate independiente de código/re-review035 aprobado. Conservar alcance/SHA de pruebas anteriores y cobertura enfocada035; no inferir una corrida global nueva.
2. GUI real, logo/font/renderer cliente, revisión humana y sesión/tenant. El release parcial fue autorizado por el usuario; la aceptación completa GUI/Estudio sigue pendiente del recibo final.
3. Preflight real de cuenta/servicio/DB/bucket/proxy, copia recuperable y ensayo aislado de migración/compatibilidad.
4. Build saneado y actualización **sólo de imagen** en el servicio existente, preservando configuración/recursos/costos/IAM/red.
5. Prueba funcional acotada desplegada; recibo SHA/digest/revisión, autenticación/proxy/MCP/privacidad, timers/cola; actualización de evidencia documental.

No ejecutar ciegamente `bash deploy/cloud-run.sh`: además del build, cambia memoria/CPU, throttling/boost, concurrencia, timeout, min-instances e IAM mediante `--allow-unauthenticated`. Esta fase no autoriza esos cambios ni habilita generación de imágenes pagada. No añadir servicios o un nuevo publicador para conseguir un gate verde.

## Preflight privado

Guardar configuración completa, referencias a secrets, DB dump, metadatos/hash y comandos de recuperación **fuera de Git**, con permisos privados y sin imprimir valores. Los agentes sólo reciben los recibos saneados.

| Comprobación | Estado recibido | Siguiente evidencia |
|---|---|---|
| Cuenta/service/region/proyecto | Cuenta actual autorizada, servicio existente ready | Revalidar justo antes de mutación, sin login alternativo |
| Recursos actuales | Final2ee/eikon-00058-t9n al100%, cero tags,19:42:39Z; config completa salvoimagen/IAMservicio-bucket preservados | Conservar comparación privada; ninguna nueva modificación de recursos/costos/IAM autorizada por este recibo |
| PostgreSQL backup/restauración | Backup fresco 19:12:22Z PG17 restaurado aislado, init_db dos veces y columnas originales iguales: snapshot: 4 tenants / 4 users / 62 brands / 6 keys | Sin fence live ni migración destructiva; renovar backup antes de cambios posteriores que alteren el alcance |
| Rollback compatible | Código anterior 6fe3ad5: startup y lecturas `/auth/me`, `/api/v1/brands`, `/health`200, anónimo brands401 en clon migrado | No extrapolar a worker/escrituras ni borrar tablas/historia |
| Bucket real | IAM sin cambios; cuatro objetos nuevos con HEAD anónimo403, originales/thumbnail propios privados por API | No extender el recibo a todaACLlegacy o datos ajenos |
| Vercel proxy | Tres orígenes finalhealth200/proyectos-mediaSPAexactbundle; proxyexistentehttps://eikon-proxy.vercel.app, originalbyteexacto/no-store | Otrosformatos y matrizGUI completa no verificados; lecturaAPI no sustituye descargaGUI |
| Sesión propia/inventario | Owner y nativeCLI de producción reales; Systems proyecto 4/marca 106, News proyecto 5/marca 107, identidad v2/logo original; importación idempotente | Sólo identidades autorizadas, sin importar56legacy a Humanizar; recarga del chat para MCP global pendiente |
| Humanizar | SSHserver2≈19:46Z: ambos timers existentes active exit0, sin mutacionesworkers/cola/timers | No iniciar publicador/redes/calendario; conservar alcance de primera entrega |

Lecturas CLI de preflight sugeridas, **a ejecutar sólo por el controlador**, con cuenta actual explícita y salida saneada:

```bash
gcloud auth list --filter=status:ACTIVE --format='value(account)'
gcloud run services describe eikon --project emergent-enterprises --region us-central1 --format='value(status.latestReadyRevisionName)'
gcloud meta list-files-for-upload
```

La primera salida se compara en privado con la cuenta autorizada; no adjuntar cuentas adicionales. No imprimir YAML completo, DATABASE_URL, keys ni secrets. Verificar el contexto de build antes de subirlo: sin `.env`, vault, dumps, logs de conversaciones, sesiones, artefactos/datos privados ni dependencias locales.

Si el bucket comparte objetos públicos con otra aplicación, documentar la dependencia y obtener la decisión necesaria antes de tocar IAM/ACL compartidos. No privatizar objetos ajenos ni hacer público el nuevo prefijo. Si faltan permisos externos o la sesión no funciona, entregar el preview local verificado y el bloqueo concreto.

## Ensayo de migración y recuperación

Usar dump privado restaurado en instancia aislada sin red/puertos. Ejecutar `init_db` dos veces y comparar columnas originales contra otra restauración limpia del mismo dump; no aceptar sólo que arranque. El backup fresco 19:12:22Z conservó 4 tenants / 4 users / 62 brands / 6 keys antes de las importaciones/revisiones del release; init_db dos veces y columnas originales iguales en restorePG17aislado. El recibo anterior259101b incluía cuatro tablas nuevas vacías: no describe el contenido live posterior. SQLite/PG16 sintéticos cubren las pruebas; PG17 privado prueba compatibilidad con el snapshot real. Mantener estos alcances separados.

No hay downgrade destructivo aprobado. La reversión conserva esquema aditivo, assets e historial. **No devolver tráfico a `6fe3ad5` hasta completar el fence de autorización siguiente**: su resolver ignora `scopes_json`/`expires_at` y convertiría una key scoped incluso vacía o expirada en una key legacy amplia. Startup y lecturas sobre el clon migrado no probaron esta propiedad. No eliminar filas, reseedear producción, perder revisiones o restaurar un dump sobre escrituras nuevas. El worker y el rollback general de escrituras siguen sin certificación; un flujo afectado exige ensayo adicional aislado.

### Rollback seguro de autorización (F-I2; absorbe T8-M1)

**Ningún `arm`, `disarm` ni revocación global del fence se ha ejecutado en producción.** La revocación del probe read-only individual está documentada como prueba normal de keys, sin activar el helper administrativo. El helper es una herramienta administrativa PostgreSQL independiente, nunca un hook de release/startup. Su acción por defecto `audit` es de sólo lectura y devuelve únicamente contadores agregados; rechaza SQLite. El schema explícito debe coincidir con el utilizado por el servicio. El operador obtiene `DATABASE_URL` por su canal privado: no pasar DSN como argumento, no imprimirlo, no usar `set -x` ni adjuntarlo a recibos.

Armar afecta **todas las claves scoped de todos los tenants**, incluidas concesiones vacías y expiradas. Debe revisarse como revocación de grants externa en el momento del rollback. Conserva las claves legacy con `scopes_json IS NULL`, sesiones owner, registros e historial. Las claves ya revocadas conservan su fecha. La restricción vive sólo mientras el operador mantenga armado el rollback; no cambia las migraciones ni el arranque normal.

1. Preparar desde el respaldo privado vigente las revisiones anteriores **resueltas**, sus digest exactos, porcentajes y tags. Quiescer la emisión y drenar requests antes de recuperar cualquier ruta legacy, incluidos URLs de revisión/tag; ningún request antiguo ya autenticado debe quedar en vuelo. No confiar únicamente en el porcentaje principal. Una revisión vieja accesible por tag es una ruta legacy aunque tenga 0% del reparto principal.
2. Ejecutar auditoría y revisar el alcance agregado; después armar explícitamente:

```bash
# DATABASE_URL ya está disponible mediante canal privado; no se muestra.
# EIKON_DB_SCHEMA: schema real verificado por el operador (habitualmente public).
.venv/bin/python scripts/rollback_scoped_keys.py --schema "$EIKON_DB_SCHEMA"
.venv/bin/python scripts/rollback_scoped_keys.py arm --schema "$EIKON_DB_SCHEMA"
.venv/bin/python scripts/rollback_scoped_keys.py audit --schema "$EIKON_DB_SCHEMA"
```

`arm` toma primero `ACCESS EXCLUSIVE` sobre `api_keys`, espera las escrituras anteriores, revoca toda fila `scopes_json IS NOT NULL AND revoked_at IS NULL` e instala en la **misma transacción** el CHECK validado `eikon_rollback_no_active_scoped_keys`: `scopes_json IS NULL OR revoked_at IS NOT NULL`. Las emisiones anteriores al lock se revocan; las que esperan o llegan después no pueden insertar una key scoped activa, aun si otra revisión nueva sigue atendiendo. También queda bloqueada la reactivación de esas filas. Un UPDATE aislado no proporciona esta garantía. El helper tiene límites de espera y falla sin recibo de éxito ante error; ante resultado ambiguo, volver a auditar antes de actuar. Detecta colisiones con restricciones diferentes y no las sustituye.

3. Exigir `fence_active: true` **y** `unrevoked_scoped: 0`; conservar contadores antes/después y comprobar que las claves legacy autorizadas permanecen. Si falta cualquiera, no mover tráfico. La receta siguiente vuelve a exigir ambas condiciones y compara los digest antes de restaurar el reparto exacto.
4. El operador normaliza su respaldo real en un JSON privado indicado por `EIKON_ROLLBACK_PLAN`, con `project`, `region`, `service`; `traffic` como mapa revisión→porcentaje; `tags` como mapa tag→revisión; `revision_images` como mapa de **cada** revisión referida→imagen completa `@sha256`. Usar nombres resueltos, nunca `LATEST`. Conservar incluso revisiones que sólo tenían tags. No rellenar con un supuesto 100% a una revisión. `EIKON_OPERATOR_ACCOUNT` identifica explícitamente la cuenta ya autorizada, sin cambio de sesión.

Receta ejecutable desde este checkout, **sólo por el controlador después de revisar revocación/quiesce y el plan privado**:

```bash
.venv/bin/python - <<'ROLLBACK_TRAFFIC'
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from scripts.rollback_scoped_keys import operate

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def restore_traffic():
    plan = json.loads(Path(os.environ["EIKON_ROLLBACK_PLAN"]).read_text())
    require((plan["project"], plan["region"], plan["service"]) == ("emergent-enterprises", "us-central1", "eikon"), "plan privado o resultado de tráfico inválido")
    traffic, tags, images = plan["traffic"], plan["tags"], plan["revision_images"]
    require(isinstance(traffic, dict) and traffic and isinstance(tags, dict), "plan privado o resultado de tráfico inválido")
    require(all(type(percent) is int and 0 <= percent <= 100 for percent in traffic.values()), "plan privado o resultado de tráfico inválido")
    require(sum(traffic.values()) == 100, "plan privado o resultado de tráfico inválido")
    revisions = set(traffic) | set(tags.values())
    require(all(re.fullmatch(r"[a-z][a-z0-9-]*", revision) for revision in revisions), "plan privado o resultado de tráfico inválido")
    require(all(re.fullmatch(r"[a-z][a-z0-9-]*", tag) for tag in tags), "plan privado o resultado de tráfico inválido")
    require(all(re.fullmatch(r"[^\s]+@sha256:[a-f0-9]{64}", images[revision]) for revision in revisions), "plan privado o resultado de tráfico inválido")
    common = ["--project", plan["project"], "--region", plan["region"], "--account", os.environ["EIKON_OPERATOR_ACCOUNT"]]
    for revision in sorted(revisions):
        actual = subprocess.check_output(["gcloud", "run", "revisions", "describe", revision, *common, "--format=value(status.imageDigest)"], text=True).strip()
        require(actual == images[revision], "digest anterior no coincide: no restaurar tráfico")
    audit = operate(os.environ["DATABASE_URL"], schema=os.environ["EIKON_DB_SCHEMA"])
    require(audit["fence_active"] and audit["unrevoked_scoped"] == 0, "fence incompleto: no restaurar tráfico")
    cmd = ["gcloud", "run", "services", "update-traffic", plan["service"], *common,
           "--to-revisions", ",".join(f"{revision}={percent}" for revision, percent in sorted(traffic.items()) if percent)]
    cmd += ["--set-tags", ",".join(f"{tag}={revision}" for tag, revision in sorted(tags.items()))] if tags else ["--clear-tags"]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    state = json.loads(subprocess.check_output(["gcloud", "run", "services", "describe", plan["service"], *common, "--format=json(status.traffic)"], text=True))["status"]["traffic"]
    actual_traffic = {}
    for entry in state:
        if entry.get("percent", 0):
            revision = entry["revisionName"]
            actual_traffic[revision] = actual_traffic.get(revision, 0) + entry["percent"]
    actual_tags = {entry["tag"]: entry["revisionName"] for entry in state if entry.get("tag")}
    require(actual_traffic == {revision: percent for revision, percent in traffic.items() if percent}, "plan privado o resultado de tráfico inválido")
    require(actual_tags == tags, "plan privado o resultado de tráfico inválido")
    print("Reparto y tags anteriores verificados; fence permanece armado.")

try:
    restore_traffic()
except Exception:
    print("Rollback no confirmado; revisar en privado plan, digest, fence y tráfico. No continuar.", file=sys.stderr)
    raise SystemExit(1) from None
ROLLBACK_TRAFFIC
```

La receta reutiliza las revisiones existentes y verifica su imagen inmutable: no crea una revisión alternativa con porcentaje adivinado ni sustituye recursos/configuración. Si falta una revisión/digest o la verificación posterior falla, detener aceptación y conservar evidencia; no improvisar otro destino. Esta receta y el JSON son instrucciones, **no evidencia de una operación ya realizada**.

5. Con fence armado, probar autenticación legacy conservada y sesiones owner; probar que claves scoped de lectura, vacías, expiradas y revocadas devuelven 401, incluida emisión de claves y mutación de identidad. No reactivar una key revocada para obtener un PASS. El ensayo sintético automatizado ejecuta el resolver, dependencia y endpoints de `6fe3ad5`, además de carreras reales de emisión PostgreSQL; no sustituye comprobaciones privadas del operador ni certifica todo el worker.
6. Al retornar al código nuevo, mantener fence hasta verificar **todas** las rutas, tags, URLs directas y reparto: ninguna debe alcanzar código legacy. Antes de habilitar inicialmente nuevas keys scoped en cualquier release, también debe cumplirse esa inaccesibilidad. Sólo entonces desarmar explícitamente:

```bash
.venv/bin/python scripts/rollback_scoped_keys.py disarm \
  --schema "$EIKON_DB_SCHEMA" --legacy-unreachable-confirmed
.venv/bin/python scripts/rollback_scoped_keys.py audit --schema "$EIKON_DB_SCHEMA"
```

El flag declara una comprobación del operador, no la ejecuta. `disarm` elimina exclusivamente el fence; no restaura grants ni cambia `revoked_at`. Las keys scoped anteriores **siguen revocadas** y necesitan una emisión nueva explícita mediante sesión owner. La política legacy NULL anterior se conserva deliberadamente durante rollback; no se presenta como la política scoped del código nuevo.

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
3. Antes de la **primera emisión scoped**, comprobar que revisiones anteriores y URLs directas/de tags no pueden alcanzar autorización legacy conforme al protocolo anterior. Sólo entonces el owner crea/revoca key scoped por canal privado; cliente Codex **real** ejecuta list/brief/import/list contra el **destino desplegado**. El recibo local CLI no satisface este paso; la prueba SDK stdio tampoco.
4. Importar pieza válida de empresaA mediante multipart **a través del proxy**: MIME/dimensiones/hash exactos, `pending_review`, replay mismo recurso, thumbnail/original propios200 privados/no-store; archivo/texto/identidad no se sobrescriben. Conservar logo original y Manrope, inspeccionar píxeles.
5. Owner decide revisión sobre hash+versión actuales; key-review403, historia persistida. Obtener otra pieza autorizada de empresaB y probar ambas direcciones: encargo/original/thumbnail ajenos404, anónimo401. Comprobar también que URLs directas de GCS no permiten descarga anónima de esos objetos.
6. GUI real desktop/mobile: filtros/paginación/detalle/snapshot/logo, roles/keys/foco y cambio A→logout→B sin datos de A; modern-screenshot/FontFace y upload cliente reales, incluyendo PNG `business_card` v1_front con logo no cuadrado y proporción/píxeles nativos. Conservar capturas privadas y respuestas saneadas.
7. Revalidar SHA/digest/revisión ready, Postgres persistente, bucket privado, configuración sin cambios y timers/cola de Humanizar. No aprobación automática ni publicación social.

Si el proxy trunca multipart, la cookie se pierde, GCS expone objetos o aparece una diferencia de configuración, preservar evidencia negativa y detener aceptación. Corregir por el escritor asignado y repetir sólo los checks afectados; no saltar al backend directo para declarar el proxy PASS.

## Recibo de release y aceptación restante

Recibos reales del controlador; sin secretos ni datos de otros clientes. El writer documental no ejecutó estas operaciones.

| Campo | Valor comprobado / límite |
|---|---|
| Estado Task8/release | Release final2ee ejecutado; entrega con límitesGUI/descarga y otrosformatos documentados. SHA documental posterior no desplegado |
| SHA desplegado | `2ee2ca2349098991e09ac30e919a2aafeb577873` |
| Gate de código | Astra035 Spec/Quality APPROVED/F-I1–F-I4/T8-M1 resueltos; R-STUDIO/R-MOBILE2ee aprobadoindependiente sin hallazgos. Guard/all47frontendPASS, npmTS/VitePASS,2reglasCSSbuild/reviewPASS; sin duplicar suitePython |
| Revisión/tráfico | eikon-00058-t9n al100%, cero tags,19:42:39Z. Releases00056/00057 son antecedentes |
| OCI index | `sha256:d98b8d31568ca9b495d3a954aa88f7f9584794c2e560d7eecb1c6a00a9a52a66` |
| Manifest linux/amd64 | `sha256:129219b1b9e9112e047c71ddb0ce1a50ff5b5693cc9666421777a4be9aaf04fc`, membershipdelindex verificada |
| Config/IAM | Config completa exceptoimagen e IAM bucket-servicio sin cambios |
| Proyecto/región/servicio/proxy | emergent-enterprises/us-central1/eikon / [proxy existente](https://eikon-proxy.vercel.app); tres orígenes health200/proyectos-mediaSPAexactfinalbundle |
| Copia/migración/rollback | Backup 19:12:22Z PG17 restore aislado/init_db×2/columnas originales iguales; snapshot: 4 tenants / 4 users / 62 brands / 6 keys; sin fence live/downgrade destructivo, worker/escrituras generales sin certificación |
| Inventario propio | Systems proyecto 4/marca 106, News proyecto 5/marca 107, v2/idempotente; logo original SHA 31d8d267ea1db2af060c77fe42be2375a4f15102028b7e9a199774c0a28cd343 |
| Gate antes primera key | Antes key 7: revisionslist completo name/statusURL, revisiones anteriores sin statusURL; tráfico100%00057/cero tags y sin revision/tagURL published en config. Tres orígenes conocidos del servicio/proxy sirvieronSPA bytes exactos de imagen nueva. Sin eliminar revisiones |
| Codex producción | CLI 0.160.1 real, listprojects/getbrandbrief/createbrief/importimage/listmedia; dos importsreales conreplay, asset 1/brief 1 1024×1024; SHA aa58e57f036e6f979616301fd1fed07c346891b7f6c7e4c74451fbb4b44f7255 |
| Privacidad/autorización | Original proxy byte exacto/no-store, thumbnail propio200; anónimo401×3, empresa QA404×3 ambos sentidos, cuatro objetos GCS HEAD anónimo403; key-review/key-identity403; probe read-only revocado401 |
| GUI verificada parcial | Ownerasset1/history1/currentv2 approved19:22:48Z, conservadospostrelease; captura19:48 muestra original/encargo/logo/historyAprobado sinerror. Rechazovacíoalert/sinreview; filtroAprobado/mobile390×844detalle/Escape/foco y desktop1440×900 verificados |
| GUI desktop/recuperación | Desktop1440×900 modal original/snapshot/historia verificados con screenshot real; errores intermitentes conexión/thumbnail/brief al abrir y recuperación visible «Actualizar detalle» completó original+encargo+logo+history sin mutación; causa sin concluir |
| GUI límites/negativos | MatrizGUI completa/otrosformatos/textosespecíficos no verificados. ClickDescargarPNG EVENTdownload15s timeout: descargaGUI no confirmada, archivoAPI200byteintacto separado. Erroresintermitentes conexión/thumb/brief recuperados con Actualizar detalle, causa sin concluir |
| Estudio final | HumanizarSystems reference-only sinwarning/Tipoenabled; nativeFontFace/modern-screenshot clientbusiness_card Generado, variation3047/filepropio200; layout1050×600/PNG2100×1200/scale2, SHAbf4d2ec3132df31a882f40a50e26d82cd8793600f489b6575dbd88b6e4ff43f1, logooficialsinwarp pequeñoenlayout. v1_front sinclaim de payloadtextos/otrosformatos; legacyDBasset-only nohabilitado/backendreadonly |
| Móvil final |390×844 navright363/documentwidth375 (antes632), linksaccesibles2filas/viewportreset/capturasguardadas; no toda matrizdesktop/mobile |
| MCP del chat | Global eikon agregado sin secret config/otros settings preservados; CLI real persistente listprojects4/5 PASS≈19:37Z, misma cuenta. Chat actual requiere reload. CLIprodreal no prueba tool ya invocada desde este chat |
| Timers/cola | Ambos timers existentes active≈19:46Z exit0, sin mutacionesworkers/cola/timers |
| PR/CI | [PR2 draft](https://github.com/stevenvo780/creador-imagenes-de-marca/pull/2), sin main merge. Job GitHubActions no iniciado por restricción administrativa, no fallo de suite ni CIgreen |
| Hallazgos anteriores | Gitleakshistoria1ejemplocomentado, delta188..2eePASS/cero (ademásdedeltasprevios); npm5 vulnerabilidadesheredadas y skips/RUF036/notatyping conservados. Sin whole-lint/history limpio |

El release final2ee tiene index y manifest separados/verificados y no reutiliza el digest188 como prueba del ajuste. Releaseinicial188/00057 queda como antecedente: index8fc4ec86a95f4a9f69a87eddd189703ea5aea3a33a4347a64287ca1d114778aa/manifestf9aaba26c69434a840d833387927665836e1d2af35befbea424e17f2425ea30d. Evidencia completa fuera deGit; negativos preservados. Entrega desplegada con límites explícitos: no afirmar matrizTask7/Task8 íntegramente ejecutada, descargaGUI confirmada, todosformatos ni publicaciónsocial. Publicador/redes/calendario tienen entregas separadas.
