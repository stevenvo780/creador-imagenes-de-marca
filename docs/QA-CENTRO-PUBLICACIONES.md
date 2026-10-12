# QA y evidencia de publicaciones autónomas

Estado de este documento: preparación Task10A; **aceptación runtime Task10B pendiente**.
La producción anterior no acredita los contratos nuevos. El cierre exige todos
los requisitos del diseño aprobado, por cuenta canónica y formato; un bloqueo
externo nunca cuenta como publicación ni éxito global.

## Matriz local integrada

Desde la raíz del checkout y con el DSN PostgreSQL de prueba leído privadamente
como `EIKON_TEST_POSTGRES_URL`, sin imprimirlo. Fixtures usan schemas aleatorios;
no conectar DB productiva. Para tests aislados, `PYTHONPATH` apunta al checkout.

```text
.venv/bin/python -m pytest -o addopts= tests webapp/tests mcp_server/tests publisher_worker/tests -q -ra --tb=short
.venv/bin/ruff check .
.venv/bin/mypy
cd frontend
npm test -- --run
node --test qa/*.test.mjs
npm run build
```

Registrar código de salida, conteos, skips, duración y hash/log privado saneado.
Además tipar todos los archivos de producción de `eikon_core`, `webapp`,
`mcp_server`, `publisher_worker`, sin tratar tests como gate de producto ni omitir
módulos productivos. Conservar la salida del comando configurado aunque falle
al incluir tests. Comparar diagnósticos con BASE; no usar ignores/casts/suppressions
para declarar PASS. La configuración CI actual no ejecuta toda esta matriz,
y un push de branch no despliega.

| Invariante | Evidencia local y prueba real pendiente |
|---|---|
| Tenant y principal | HTTP SQLite/PG y stdio roles, cookie/Bearer, proyecto/media/cuenta/grant ajenos; luego UI/API reales con identidad correcta |
| Revisión exacta | Archivo/logo/snapshot/caption/destino/fecha/flags inmutables, hashes, modificación invalida IA; inspección nativa de los mismos bytes |
| Política/decisión | Append-only, revocación y grants separados; modelo real, hechos permitidos, readback exacto |
| Historia/dedup | Corte íntegro, mappings canónicos, SHA/destino, retirados y failed/inflight conservados; inventario Humanizar14FB/2IG/1X +5manual +4retiradas real |
| Calendario/quotas | Ventana60min, offset/zona/día, started/provider time, countonce, destino desconocido retenido; horario y límites reales por cuenta |
| Concurrencia/caída | Dos workers, CAS, ACK perdido, outbox durable, lease no abre nuevo POST; recuperación real del mismo intento |
| Media/logs | Bytes SHA, qualification exacta sin transcode, tickets TTL/revoke; GET/revocar y logging de tres capas reales |
| Consentimiento TikTok | Proof privado trusted, creator_info, flags/privacidad/hash/owner/version, pinA→B/revoke/start; consentimiento/proveedor/dominio reales |
| UI | DOM y78QA, bundle/build; recorrido owner desktop/móvil, product/campaign/calendar/results/consent y volumen de historias/previews |
| Cliente diario | Inbox/stock/deficit y desconexión con dobles; tools28/reconnect/modelo y ejecución diaria nativos reales |

## Aceptación por cuenta y formato

| Canal | Formatos independientes | Prueba necesaria |
|---|---|---|
| Facebook | image, video_feed, reel | Recibo canónico final, lookup/visibilidad de la cuenta propia y segundo run cero POST; vídeo uploadID no basta |
| Instagram | image, video_feed, reel | JPEG específico y REELS API para ambas variantes de vídeo; share_to_feed true/false según contrato; container FINISHED no es publicación |
| TikTok | image, video | Privacidad/consentimiento actual, flags explícitos, review/audit/dominio/content proof y finalID/visibilidad; publish_id no basta |
| X | image, video | Contratos locales; blocked_by_budget y cero gasto/endpoints facturables hasta nueva instrucción |

No heredar una foto a vídeo, un formato a otro, una cuenta a otra, un contenedor
o ID de procesamiento a un recibo visible. SELF_ONLY TikTok es privado y no se
contabiliza como aceptación pública. Si el proveedor no ofrece finalID público,
conservar evidencia privada e incertidumbre/bloqueo, sin fabricar ID. Los límites
más estrictos del ingest no certifican todos los parámetros del proveedor.
Actual expansión/permisos Facebook, GET visible, intervalos GOP y originaltime
son obligatorios antes de decir soporte operativo.

## Contrato del verificador v1

Ejecutar sobre **recibo saneado del operador**, guardado fuera de Git:

```text
.venv/bin/python scripts/check_publication_acceptance.py /ruta/privada/receipt-saneado.json
```

Es un validador estático acotado, sin red, firmas, credenciales, evaluación ni
activación. Puede rechazar formas falsas, desalineación y pruebas locales
presentadas como live; **no puede demostrar que un JSON bien formado sea auténtico**,
ni releer logs/proveedores, detectar cambios posteriores o atestiguar que la IA
vio los bytes. Root conserva y revisa los originales correlacionados. No existe
archivo synthetic ALLPASS de release; los ejemplos en código/tests son solo datos
de prueba. Código de salida0 solo verified,1 incomplete/externally_blocked,
2 inválido/no saneado. Salida nunca imprime entrada cruda ni secretos.

Objeto superior cerrado: `schema_version=1`, `release`, `destinations`,
`local_gates`, `runtime_gates`, `channels`. No claves extras. `release` contiene
`commit`40hex, `tenant_id` entero positivo, `policy_version` positivo,
`image_digest=sha256:<64hex>` y `revision` identificador. `destinations` enumera
cada cuenta canónica `platform:remote_id`, sin duplicados, con las cuatro redes;
el operador acredita que el inventario está completo. El verificador exige los
formatos de la tabla para cada cuenta enumerada. No descubre cuentas omitidas.

Cada evidence cerrado contiene `mode` (local/live), `source` (test_runner para
local; operator/provider/runtime/native_codex para live), `captured_at` ISO8601
con offset, `tenant_id`, `commit`, `artifact_sha256`64lowerhex,
`reference` identificador saneado y `details`. Sin URL de recurso/ticket, token, DSN,
password, header ni ruta privada. Única URL permitida: `consent.verified_domain_prefix`,
prefijo HTTPS público exacto `/api/v1/publications/delivery-media/`, sin ticket,
usuario/contraseña, query, fragment ni puerto distinto de443. Su presencia no
prueba aceptación del dominio por TikTok; las referencias reales la acreditan.
Frescura fija24h y ninguna fecha futura;
para pruebas extendidas emitir nuevo recibo saneado con nuevas comprobaciones,
no cambiar fechas de evidencia histórica. SHA/tenant/commit deben coincidir.
Referencias1–128 `[A-Za-z0-9_.:-]`; hashes minúsculos; bool no es entero.
No hashes/refs inventados: hash de artefacto real, referencia interna a su original
privado. El v1 es el recibo de aceptación **Humanizar**; los conteos históricos
no son un contrato universal de importación de otras empresas.

Cada gate cerrado tiene `status` y `evidence`. Gate ausente o `incomplete` con
null deja incompleto. `incomplete` también admite evidencia con details
`reason`/`next_step` saneados para conservar un fallo concreto. Un bloqueo externo
admite únicamente razón conocida y paso humano (`reason`, `next_step`) con
provenance live; los fallos de implementación no son bloqueo externo.
`verified` exige evidence concreta y campos siguientes, sin extras:

| Gate | `details` requerido |
|---|---|
| local: backend_sqlite/backend_postgresql/frontend_vitest/frontend_qa/frontend_build/mcp_stdio/worker/ruff/mypy | command saneado, exit_code0, passed positivo, failed0, skipped0; baseline skips/fallos se conservan fuera de verified |
| backup_restore | backup_id, clone_id, restore_sha256, init_runs2, ledger_before/after_sha256 iguales, outbox_before/after_sha256 iguales, rollback_guards_ref |
| packaging | image_digest, manifest_sha256, worker_commit, ffmpeg_version, ffprobe_version |
| deployment | cloud_run_revision, image_digest, proxy_deployment_id, authenticated_http_status200, foreign_tenant_http_status403, private_storage_http_status403 |
| logging | uvicorn_source_ref, cloud_run_source_ref, vercel_source_ref, probe_sha256, retained_marker_count0, persistent_protection_ref, sink_inventory_sha256, positive_diagnostics_sha256, sensitive_transport run_same_origin, trusted_buffer_limit google_log_router_temporary; control de persistencia después de ingestión y trayecto sensible evita Vercel |
| history | inventory_sha256, cut_receipt_sha256, manual_events5, withdrawals4, legacy_facebook14, legacy_instagram2, legacy_x1 |
| native_reconnect | mechanism, client_run_id, tool_count28, planner_grant_id, reviewer_grant_id, scope_inventory_sha256 |
| native_daily | client_run_id, inbox_receipt_sha256, decision_readback_sha256, disconnected_snapshot_sha256, worker_attempt_id |
| ui | owner_id, tenant_id, desktop_trace_sha256, mobile_trace_sha256, campaign_id, calendar_receipt_sha256, consent_trace_sha256, load_limit_trace_sha256 |
| recovery | prestart_failure_sha256, poststart_crash_sha256, lost_ack_sha256, grant_revoke_sha256, policy_revoke_sha256, withdrawal_sha256, changed_original_sha256, second_post_count0 |
| timers | legacy_publication/legacy_planner/new_timer=disabled_inactive, frequency_policy_ref, window_minutes60; aceptación previa a activar nuevo timer |
| reviews | task_review_ref, branch_review_ref, reviewed_commit, unresolved_findings0 |

Deployment/packaging/worker/reviews/UI deben corresponder al release.
El campo de comandos es texto, no se ejecuta. El operador debe registrar la
suite completa y conteos reales; este validador no calcula cobertura de tests.
Para herramientas sin tests, `passed` representa checks exitosos documentados,
no tests inventados. Un check estático exitoso puede registrar passed1.

Una entrada de canal verified contiene `status`, `binding`, `evidence`.
Binding cerrado: tenant_id/policy_version/revision_id enteros positivos,
destination/format, file_sha256/media_sha256 iguales y contract_hash.
Cada etapa evidence lleva además **ese mismo binding**. Etapas/details:

| Etapa | Datos requeridos |
|---|---|
| identity | connection_id, remote_id exacto, api_mode del catálogo actual, scope_evidence remote_introspection/token_exchange/capability_probe, scopes que cubran REQUIRED_SCOPES de ese proveedor/modo, grant_id |
| original | media_id, byte_size, inspected_sha256 igual al medio |
| model | source native_codex, provider codex, model, material_receipt_id, source_mode frozen_metadata_context, context_sha256, response_sha256 |
| decision | decision_id, evaluation_id, outcome approve, current_revision_id igual al binding, readback_contract_hash exacto |
| authorization | attempt_id, claim_id, grant_id igual a identity, started_at, expires_at (inicio dentro de vigencia) |
| provider | attempt_id igual, remote_id final, state published, receipt_sha256, published_at original consciente de zona |
| visibility | mismo remote_id, visibility public, lookup_sha256 |
| second_run | mismo attempt_id/remote_id, post_count entero0, run_id |
| consent (solo TikTok, obligatoria) | DTO de authority exacto: confirmed true, tenant_id/revision_id/contract_hash/normalized_destination/media_sha256 ligados al binding, consent_id, expires_at Unix entero posterior al inicio, privacy_level ofrecido en privacy_level_options y distinto de SELF_ONLY, disable_comment/disable_duet/disable_stitch/brand_content_toggle/brand_organic_toggle/is_aigc bool estrictos, music_acknowledged true, creator_receipt_sha256, verified_domain_prefix público fijo, domain_proof_ref/provider_review_ref/content_eligibility_ref/public_audit_ref no vacíos |

El catálogo de permisos refleja `webapp/publications/connections.py`, con test de
igualdad para evitar drift. Facebook page/facebook_login exige pages_manage_posts,
pages_read_engagement y pages_show_list. Instagram facebook_login exige
instagram_basic, instagram_content_publish, pages_show_list y pages_read_engagement;
instagram_login exige instagram_business_basic y instagram_business_content_publish.
TikTok oauth2 exige user.info.basic y video.publish. X oauth2 conserva tweet.read,
tweet.write, users.read y media.write, sin permitir aceptación pública bajo el bloqueo
económico actual. Permisos de un modo no califican el otro. Consentimiento TikTok
se informa por revisión/medio/cuenta/formato: hashes y opciones no se heredan entre
contenidos. El operador comprueba flags contra la revisión frozen y los originales;
el JSON y sus hashes no reemplazan esa revisión ni atestiguan autoridad remota.

La hora de publicación no precede inicio; observaciones provider/visibility/rerun
no preceden publicación. Un `externally_blocked` de canal tiene status,
destination, format, evidence live con `reason` y `next_step`; `incomplete`
usa los mismos campos y evidence null. X siempre debe quedar bloqueado por
presupuesto; v1 rechaza promoverlo a verified bajo la autorización actual.
Razones externas cerradas: blocked_by_budget, requires_auth,
requires_provider_review, requires_post_consent, requires_platform_audit,
logging_source_unqualified, native_client_unavailable. La aceptación se informa
por gate/cuenta/formato; si queda cualquiera incompleto, global incomplete;
si todo lo restante está comprobado pero existe bloqueo, global externally_blocked.
**Ni ese resultado ni local_status verified habilitan timer o cierran la meta.**

## Gates runtime todavía pendientes

Backup/restore aislado e init doble; imagen real por digest; configuración privada;
worker/ffmpeg server2; logs calificados (baseline real FAIL8marcadores, Vercel
NO CONCLUYENTE); identidad ownHumanizar y scopes; historia/cortes/grants; tools28,
modelo/imagen/fuentes/readback nativos; día real y desconexión; UI desktop/móvil y
volumen; entregas/visibilidad/segundo run por formato/cuenta; fallos/retirada/revoke;
consentimiento/auditoría TikTok y presupuesto X; timer nuevo y heartbeat tras
calificación. Ninguno queda ejecutado por escribir estas guías o por dobles stdio.
