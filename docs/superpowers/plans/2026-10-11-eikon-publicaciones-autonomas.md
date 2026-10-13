# Eikón: publicaciones autónomas multiempresa — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cada empresa produce con su Codex, recibe decisiones editoriales reales de IA y publica desde Eikón en Facebook, Instagram, TikTok y X conforme a sus permisos y condiciones, sin duplicados ni gastos no autorizados.

**Architecture:** FastAPI/PostgreSQL conserva política, campañas, conexiones, decisiones y ledger. El cliente Codex produce y evalúa mediante MCP; un proceso separado en server2 consume entregas vigentes y publica con adaptadores por cuenta. El cliente y el servidor tienen concesiones distintas y nunca se convierten en owner.

**Tech Stack:** Python/FastAPI, SQLite y PostgreSQL, React/TypeScript, FastMCP/httpx, storage privado GCS/local, AES-GCM y adaptadores HTTP de redes.

**Spec:** `docs/superpowers/specs/2026-10-11-eikon-centro-publicaciones-design.md`, aprobado con enmiendas del operador del 11 de octubre de 2026.

**Estado:** Plan aprobado expresamente por el operador. Implementación iniciada mediante subagentes con revisión independiente de cada tarea. El progreso verificado se registra en `docs/GOAL-CENTRO-PUBLICACIONES.md`; la aprobación del plan no acredita ejecución ni publicación.

## Global Constraints

- Todas las redes forman parte del resultado: Facebook, Instagram, TikTok y X.
- Los logos originales conservan sus bytes y hashes.
- Cada empresa utiliza su propio Codex y sus redes.
- La decisión `approve`, `reject` o `hold` es append-only.
- La ventana por defecto será de 60 minutos desde la fecha aprobada.
- Una entrega con intento iniciado nunca se reasigna automáticamente.
- La misma pieza puede ir a cuentas distintas una vez cada una.
- La exclusión de gasto de X sigue vigente.
- No se sustituyen fallos por un score o aprobación ficticios.
- Los seis scopes actuales no conceden revisión, conexiones o despacho.
- `asset_reviews` y `approval_current` conservan su significado de revisión humana visual.
- Los timers antiguos permanecen apagados y su historial se conserva.
- TikTok necesita los pasos de consentimiento/privacidad exigidos por el proveedor; un `publish_id` no es publicación completada.
- No usar sesión, token, política, grant, proyecto o cuenta de otra empresa.

## Review Focus

1. Fuentes con instrucciones embebidas: la IA trata documentos como datos, sin modificar destinos, permisos o política. Tarea 5.
2. Confusión cookie/Bearer o token de rol equivocado: el evaluador y worker se resuelven exclusivamente en su dependencia; ninguna clave antigua sirve. Tarea 1.
3. Revocación entre evaluación, reserva e inicio: se revalida la misma autorización antes del intento; después se concilia sin duplicar. Tareas 5 y 6.
4. Zona horaria, cambio de día y fechas ambiguas: entrada con offset obligatorio, comparación UTC y cuota diaria en zona de política. Tareas 3 y 6.
5. Canal bloqueado o cliente Codex desconectado: no detiene otros destinos elegibles, no inventa evaluación y no activa un proveedor alternativo. Tareas 7–9.

## Límites, archivos e interfaces

Un escritor por tarea; las siguientes tareas se integran secuencialmente. Una revisión puede rechazar una entrega sin descartar las anteriores. Las comprobaciones productivas citadas en tareas 5, 8 y 9 se ejecutan en la tarea 10, tras su despliegue integrado; siguen siendo requisitos obligatorios de aceptación. La exploración paralela es de solo lectura; los cambios a archivos compartidos se asignan explícitamente al integrador.

| Archivo nuevo | Responsabilidad |
|---|---|
| `webapp/publications/contracts.py` | Modelos cerrados, estados, hash canónico y normalización de fecha/destino |
| `webapp/publications/migrations.py` | DDL incremental con tenant, FK compuestas y marcadores de migración |
| `webapp/publications/policies.py` | Políticas owner versionadas y revocación |
| `webapp/publications/auth.py` | Grants y principales planner/reviewer/worker, separados de API keys existentes |
| `webapp/publications/connections.py` | Identidad/capacidades de cuentas y relación con proyectos |
| `webapp/publications/vault.py` | Cifrado AES-GCM con contexto y key_id, sin secretos públicos |
| `webapp/publications/oauth.py` | State de un uso, PKCE y callback ligado a sesión/empresa |
| `webapp/publications/campaigns.py` | Campañas, variantes y revisiones inmutables |
| `webapp/publications/decisions.py` | Evidencia IA y elegibilidad de revisión completa |
| `webapp/publications/ledger.py` | Eventos, deduplicación histórica e importación idempotente |
| `webapp/publications/deliveries.py` | Programación, reserva, inicio, cancelación y reporte |
| `webapp/api/publications.py` | Endpoints owner/planner de política, campañas y calendario |
| `webapp/api/publication_reviewer.py` | Bandeja y decisión, solo grant reviewer |
| `webapp/api/publication_worker.py` | Claim, original, credencial, inicio y reporte, solo grant worker |
| `mcp_server/publication_tools.py` | Cliente HTTP de candidatos y evaluaciones; no generación de imágenes remota |
| `publisher_worker/` | Paquete instalable separado, outbox SQLite por tenant y adaptadores por canal |
| `frontend/src/pages/Publications/` | Política, campañas, evaluación, calendario y resultados |

Los módulos nuevos no se importan desde `webapp/jobs/worker.py`. El publicador no depende de una cookie owner ni de la clave del cliente Codex. Los adaptadores existentes se leen de `/datos/workspaces/humanizar/ComercialHumanizar/marketing_autopilot/src/social/`; no se modifica aquel repo incidentalmente. Cualquier reutilización mediante copia acotada registra commit y hashes del origen y conserva sus tests. No se importan módulos que inicialicen anuncios/Gemini al arrancar.

### Contrato común, definido en la tarea 1

```python
from typing import Literal, TypedDict

Outcome = Literal["approve", "reject", "hold"]
GrantRole = Literal["planner", "reviewer", "worker"]
Platform = Literal["facebook", "instagram", "tiktok", "x"]

class Principal(TypedDict):
    tenant_id: int
    grant_id: int
    role: GrantRole
    policy_version: int
    subject: str

class DecisionInput(TypedDict):
    revision_id: int
    expected_contract_hash: str
    policy_version: int
    evaluation_receipt_id: int
    outcome: Outcome
    reason: str

class Claim(TypedDict):
    delivery_id: int
    attempt_id: str
    claim_id: str
    contract_hash: str
    lease_until: int

class ProviderResult(TypedDict):
    state: Literal["published", "failed", "uncertain", "held"]
    remote_id: str | None
    permalink: str | None
    evidence: dict
```

Los errores de dominio son `NotFound`, `Conflict(code)`, `Forbidden` y `InvalidInput(code)` en `contracts.py`; las rutas responden 404, 409, 403 y 422 respectivamente, sin incluir excepciones o cuerpos remotos sensibles.

## Task 1: política autónoma y concesiones separadas

**Files:** crear `webapp/publications/{__init__,contracts,migrations,policies,auth}.py`, `webapp/api/publications.py`, `webapp/tests/test_publication_policies.py`, `webapp/tests/test_publication_grants.py`; modificar `webapp/db.py::init_db`, `webapp/app.py` y `webapp/config.py` al integrar routers/configuración.

**Interfaces:**
- `set_policy(db_url, tenant_id, owner_id, expected_version, payload) -> dict`: requiere owner actual; versión monotónica, append-only.
- `issue_grant(db_url, tenant_id, owner_id, role, subject, policy_version, expires_at) -> tuple[str, dict]`: devuelve secreto una vez; guarda SHA256 y rol.
- `resolve_grant(db_url, token, expected_role, now) -> Principal`: solo prefijos y tabla nueva; política activa, owner autorizante vigente, expiración/revocación y rol exactos.
- `canonical_hash(payload: dict) -> str` y `normalize_schedule(value: str) -> int` en `contracts.py`.

- [x] Escribir tests con el fixture `media_clients` existente para dos tenants. Crear política por owner A, denegar B y clave de los seis scopes; probar CAS con versión vieja, degradación del owner autorizante y grants de roles equivocados.

```python
def test_no_legacy_scope_can_enable_autonomy(media_clients):
    a = media_clients.a
    key = a.post("/api/v1/auth/api-keys", json={
        "name": "existing", "scopes": ["media:write"],
    }).json()["key"]
    a.cookies.clear()
    r = a.post("/api/v1/publications/policy", headers={
        "Authorization": f"Bearer {key}",
    }, json={"expected_version": 0, "enabled": True})
    assert r.status_code == 403
```

- [x] Ejecutar `python -m pytest webapp/tests/test_publication_policies.py webapp/tests/test_publication_grants.py -q`; antes del cambio las rutas son inexistentes, no 403. Registrar el fallo.
- [x] Crear tablas `publication_policies` y `publication_grants` con `tenant_id`, owner, versión, timestamps, JSON canónico y secreto hash. Resolver principales nuevos sin tocar `current_user` ni ampliar `API_KEY_SCOPES`. La dependencia worker/reviewer rechaza presencia simultánea de cookie y Bearer, y cualquier token del rol distinto.

```python
def canonical_hash(payload):
    import hashlib, json
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
```

- [x] Política valida listas de proyectos/cuentas propias, zona IANA, frecuencia positiva, máximo diario por destino, fuentes y productos autorizados, vigencia, `spend_allowed=false` inicial. Nuevos tenants empiezan deshabilitados; Humanizar se habilita por el controlador con la autorización actual y recibo, no por slug ni seed global.
- [x] Probar SQLite y PostgreSQL, init dos veces y rollback transaccional; correr también `test_media_permissions.py` sin reinterpretar sus resultados. Revisión independiente y commit `feat: add tenant publication policies and dedicated grants`.

## Task 2: conexiones, vault y OAuth por cuenta

**Files:** crear `webapp/publications/{connections,vault,oauth}.py`, `webapp/tests/test_publication_connections.py`, `webapp/tests/test_publication_oauth.py`; modificar migraciones, router/configuración de la tarea 1 y la lista de dependencias web para AES-GCM.

**Interfaces:**
- `put_connection(db_url, tenant_id, owner_id, payload) -> dict`: plataforma/modo/remote_id/proyectos/capacidades, sin secreto en respuesta.
- `seal(key: bytes, key_id: str, tenant_id: int, connection_id: int, secret: bytes) -> dict` / `unseal(key: bytes, tenant_id: int, connection_id: int, envelope: dict) -> bytes`, en vault.
- `start_oauth(db_url, tenant_id, owner_id, platform, redirect_uri, now) -> dict` y `finish_oauth(db_url, session_owner, state, code, now, client) -> dict`.

- [x] Escribir pruebas de secreto de otra empresa/conexión, AAD alterado, state repetido/ajeno/vencido, ID remoto distinto y scopes insuficientes. No hacer llamadas reales en tests.

```python
def test_ciphertext_cannot_cross_tenant():
    from webapp.publications.vault import seal, unseal
    from cryptography.exceptions import InvalidTag
    import pytest
    key = b"k" * 32
    envelope = seal(key, "test", 1, 8, b"fake-token")
    with pytest.raises(InvalidTag):
        unseal(key, 2, 8, envelope)
```

- [x] Ejecutar los tests y registrar el fallo por módulo ausente. Implementar AES-GCM con nonce aleatorio de 12 bytes y AAD canónica `{tenant_id,connection_id,key_id}`. Una clave ausente o incorrecta retiene, sin fallback JWT. La interfaz de material privado utiliza configuración protegida fuera de Git; su instalación y respaldo productivos se realizan en Task 10.
- [x] Migrar metadatos y cifrado; crear relación explícita proyecto/conexión. OAuth solo guarda conexión activa después de comprobar cuenta y permisos reales; no seguir redirects autenticados fuera de hosts oficiales. Reservar state con una transición atómica y borrar uso, no el historial.

```sql
UPDATE publication_oauth_states
SET consumed_at = ?
WHERE tenant_id = ? AND owner_id = ? AND state_hash = ?
  AND consumed_at IS NULL AND expires_at > ?;
```

- [x] Conservar en el test que `rowcount != 1` impide intercambiar el código. Preparar y probar el script privado de importación de credenciales existentes Humanizar, sin emitir nuevos scopes ni tokens de otro perfil. La aplicación real con respaldos y comprobación de identidad corresponde a Task 10.
- [x] Correr tests con red simulada y ambos motores; revisar que JSON/logs no contienen token/ciphertext. Revisión independiente y commit `feat: isolate social connections and OAuth credentials`.

**Recibo local:** conexiones/OAuth/vault revisados en `b092912487d1c2498051dc6a84e6cbc533d1f1c9`, tras dos rondas de corrección. Ningún hallazgo local abierto. Integración e importación reales permanecen pendientes de Task 10.

## Task 3: campañas y revisiones exactas para todos los canales

**Files:** crear `webapp/publications/campaigns.py`, `webapp/publications/media.py`, `webapp/api/publication_media.py`, `webapp/tests/test_publication_campaigns.py` y `webapp/tests/test_publication_video_media.py`; ampliar contratos, migraciones y router owner/planner. Modificar `Dockerfile` solo para la dependencia ffmpeg/ffprobe necesaria para validar vídeo.

**Interfaces:**
- `create_campaign(db_url, tenant_id, actor, project_id, brand_id, objective) -> dict`.
- `freeze_revision(db_url, tenant_id, campaign_id, media_id, caption, connection_id, scheduled_at, policy_version, channel_metadata) -> dict`.
- `get_revision(db_url, tenant_id, revision_id) -> dict` / `list_candidates(db_url, principal, cursor, limit) -> dict`.
- Una revisión devuelve `contract_hash`, JSON congelado y `eligibility_reasons`; no entrega tokens ni declara éxito remoto.

- [x] Tests usan helpers `project`, `brand`, `brief`, `image_bytes` y subida de `media_helpers.py`; añadir campañas sobre cada tenant y conexión propia de tarea 2. Probar medio ajeno, archivo archivado/rechazado, campaña archivada y caption/metadata inválidos.

```python
def test_contract_changes_for_caption_or_account():
    from webapp.publications.contracts import canonical_hash
    a = {"tenant_id": 1, "media_sha256": "a" * 64,
         "caption": "Producto", "destination": "facebook:7",
         "scheduled_at_utc": 1791784800, "policy_version": 1}
    assert canonical_hash(a) != canonical_hash({**a, "caption": "Otro"})
    assert canonical_hash(a) != canonical_hash({**a, "destination": "facebook:8"})
```

- [x] Ejecutar tests fallidos. Implementar snapshot con todos los campos de la spec, incluido ID remoto normalizado, fuente/derechos, versión de conexión, bytes/hash y metadata de privacidad/comercialidad cuando aplique. `scheduled_at` sin offset o ambiguo se rechaza; se almacena UTC y conserva zona de política.

```python
from datetime import datetime
def normalize_schedule(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise InvalidInput("timezone_required")
    return int(dt.timestamp())
```

- [x] Añadir ingreso privado de MP4 validado y acotado, con hash, metadatos reales, procedencia e identidad congelada en un catálogo separado de vídeos. Referencia explícita `media_kind`/ID distingue imagen de galería y vídeo. El endpoint y MCP de imagen existentes mantienen PNG/JPEG y sus permisos. Verificar un MP4 real, corrupción, límites, aislamiento, replay idempotente y compensación de storage. Esta ampliación corrige la ausencia de entrada de vídeo del plan original, necesaria para el alcance aprobado.

- [x] Una edición inserta revisión nueva; no actualiza bytes o contrato anterior. Variante JPEG, vídeo o canal con otro texto tiene medio/hash y decisión propios. Conectar candidatos a `generation_briefs` existentes sin cambiar retroactivamente encargos.
- [x] Probar fechas equivalentes con offsets distintos, cambios de día local y separación de plataformas; comprobar que imagen importada sigue pendiente de revisión humana aunque pueda entrar a evaluación autónoma. Revisión y commit `feat: freeze autonomous publication candidates`.

## Task 4: ledger e importación completa de historia

**Files:** crear `webapp/publications/ledger.py`, `scripts/import_publication_history.py`, `webapp/tests/test_publication_history.py`; ampliar migraciones.

**Interfaces:**
- `append_event(db_url, tenant_id, attempt_id, event_key, kind, payload) -> dict`: idempotente por empresa/intento/evento.
- `import_history(db_url, tenant_id, source_id, items, evidence) -> dict`: no programa ni autoriza.
- `history_ready(db_url, tenant_id, normalized_destination) -> bool`.
- `seen_media(db_url, tenant_id, normalized_destination, image_sha256) -> bool`.

- [x] Tests incluyen dos bases con delivery_id=1, cuatro retiradas, medio igual/caption distinto, intento incierto y mapping remoto desconocido. Una retirada conserva guardia y recibo.

```python
def test_withdrawal_does_not_clear_media_guard(history_db):
    from webapp.publications.ledger import append_event, seen_media
    db_url, tenant_id, attempt_id = history_db
    append_event(db_url, tenant_id, attempt_id, "withdrawn:confirmed",
                 "withdrawn", {"confirmed": True})
    assert seen_media(db_url, tenant_id, "facebook:7", "a" * 64)
```

El fixture `history_db` crea DB aislada, política/conexión Facebook7 y evento publicado con hash `a*64` mediante `import_history`; nunca usa producción ni auth real.

- [x] Ejecutar tests fallidos. Implementar unicidad `(tenant_id,source_id,source_delivery_id)` y mapping documentado de alias a destino. Un ID no comprobado impide cerrar el corte de ese destino; no inventar equivalencia por nombre.

```sql
CREATE UNIQUE INDEX publication_history_origin
ON publication_history(tenant_id, source_id, source_delivery_id);
CREATE UNIQUE INDEX publication_event_idempotency
ON publication_events(tenant_id, attempt_id, event_key);
```

- [x] Importar las tres bases y las cinco pruebas manuales inventariadas. Incluir enviados, retirados, fallidos, inciertos y en vuelo. Los ocho pendientes retenidos se conservan como historia sin autorización nueva. Registrar hashes de fuente/recibo y conteos; dry-run antes de apply, repetir apply demuestra mismos IDs/eventos.
- [x] Cerrar migración por destino solo con todo su historial conocido conciliado. Conexiones X/TikTok con mapping pendiente siguen retenidas, sin frenar destinos Meta cuyo corte sí está acreditado. No declarar historial remoto universal a partir de las fuentes inventariadas.
- [x] Revisión de integridad/duplicados y commit `feat: preserve publication history and destination media guards`.

Tarea4 cerrada como implementación/local: importación y apply repetido verificados en clones SQLite/PostgreSQL; importación productiva y pruebas de identidad externas permanecen obligatorias en Task10 según ruling. No se activó despacho.

## Task 5: evaluación IA real y herramientas MCP

**Files:** crear `webapp/publications/decisions.py`, `webapp/api/publication_reviewer.py`, `mcp_server/publication_tools.py`, `webapp/tests/test_publication_decisions.py`, `mcp_server/tests/test_publication_tools.py`; modificar `mcp_server/server.py` al registrar tools y `mcp_server/QUICKSTART.md`. El cliente planner/reviewer usa respectivamente `EIKON_PUBLICATION_PLANNER_TOKEN` y `EIKON_PUBLICATION_REVIEWER_TOKEN`; server2 usa `EIKON_PUBLICATION_WORKER_TOKEN`. Sin ellos las rutas nuevas no usan `EIKON_API_KEY` como fallback.

**Interfaces:**
- `record_evaluation(db_url, principal, revision_id, material_hashes, model_receipt, response) -> dict`.
- `append_ai_decision(db_url, principal, payload: DecisionInput, now: int) -> dict`.
- `publication_eligibility(db_url, tenant_id, revision_id, now) -> dict` devuelve `eligible`, `reasons`, `decision_id` y `contract_hash`.
- Tools nativos: `eikon_list_publication_candidates(cursor,limit)`, `eikon_get_publication_candidate(revision_id)`, `eikon_submit_publication_evaluation(revision_id,expected_contract_hash,policy_version,material_hashes,model_receipt,response)`. El rol planner dispone además de `eikon_prepare_publication_candidate`; su grant no emite decisiones.

- [x] Tests: scope antigua, reviewer ajeno/caducado, grant worker, fuente con instrucción de cambiar cuenta, imagen no entregada, JSON inválido, rechazo, hold y decisión sobre versión vieja.

```python
def test_reject_never_becomes_dispatchable(decision_case):
    from webapp.publications.decisions import append_ai_decision, publication_eligibility
    db_url, principal, payload, now = decision_case
    append_ai_decision(db_url, principal, {**payload, "outcome": "reject"}, now)
    r = publication_eligibility(db_url, principal["tenant_id"], payload["revision_id"], now)
    assert not r["eligible"]
    assert "ai_rejected" in r["reasons"]
```

`decision_case` provisiona política, grant reviewer, revisión propia y evaluación de doble de modelo registrada con hashes correctos; este fixture solo prueba contrato, nunca aceptación real de IA.

- [x] Ejecutar tests fallidos. Implementar evaluaciones append-only ligadas al grant y snapshot, comprobación de hashes exactos de imagen/texto/fuentes y decisión cerrada. La respuesta exige pertinencia, fidelidad de logo, legibilidad, afirmaciones justificadas, derechos/contexto y adecuación al canal con razones; no se requiere ni inventa score legacy.

```python
required = {"pertinence", "brand_fidelity", "legibility", "claims_supported",
            "rights_context", "channel_fit"}
valid_checks = set(response["checks"]) == required
if response["outcome"] == "approve" and (
    not valid_checks or any(v["result"] != "pass" for v in response["checks"].values())
):
    raise InvalidInput("incomplete_evaluation")
```

- [x] La concesión autoriza confiar en un evaluador específico, no en indicadores arbitrarios. El cliente debe mostrar que el modelo recibió el PNG exacto y devolver un recibo correlacionado con request/modelo/proveedor, hashes y respuesta; no afirmar atestación criptográfica inexistente. Las fuentes se delimitan como datos no confiables en el prompt.
- [x] Añadir herramienta planner de importación privada de vídeo; la evaluación conserva hash original y evidencia de lo realmente inspeccionado, incluidos contexto de audio cuando exista. No heredar una evaluación de imagen ni declarar inspección de vídeo completo a partir de una sola captura.
- [x] No alterar `asset_reviews`, `approval_current` o tests owner. Revalidar política/grant/media/conexión en transacción y crear entrega solo si `approve` vigente. Probar revocación antes del commit de decisión y mismo receipt aplicado idempotentemente.
- [x] Ejecutar stdio MCP con grant de prueba y revisar/commit `feat: authorize publications through tenant AI decisions`: código local revisado en `3ac2eea13d014e74a66f8a7ad0fee36b2eda0742`, 331 casos finales de consumidores afectados y 121 finales propios, SQLite/PostgreSQL y FastMCP/fallback. La entrega durable la compone tarea6 bajo la misma transacción.
- [x] Gate real obligatorio de tarea10: cliente Codex contra candidato Humanizar desplegado; inspección de archivo/referencia/contexto, razones, decisión y lectura posterior del mismo hash. Dobles y stdio contractual no cierran este gate; vídeo silencioso real y audio retenido también deben comprobarse.
  Evidencia del 13 de octubre: agente actual, cliente MCP stdio real del launcher vigente, vídeo silencioso 1/revisiones 8–10 aprobado y vídeo con audio 2/revisión 11 retenido. GET independientes posteriores, entregas de materiales 20–23, conservaron contratos, hashes y decisiones 8–11. Revisión independiente sin hallazgos Critical/Important. Inspección por tres frames de composición estática, `full_video_watched=false`, audio no escuchado, recibo `client_reported` y slug exacto de modelo no expuesto; no acredita despacho ni visibilidad del proveedor. Ver [pruebas y límites](../../PRUEBAS-PUBLICACIONES-2026-10-12.md#vídeo-nativo-y-lectura-posterior-13-de-octubre).

## Task 6: calendario durable, reserva, inicio y reporte

**Files:** crear `webapp/publications/deliveries.py`, `webapp/api/publication_worker.py`, `webapp/tests/test_publication_delivery_concurrency.py`; ampliar migraciones y router de calendario.

**Interfaces:** `schedule_revision(db_url,tenant_id,revision_id,now)->dict`, `claim_due(db_url,principal,now)->Claim|None`, `start_attempt(db_url,principal,claim_id,contract_hash,now)->dict`, `report_attempt(db_url,principal,attempt_id,event_key,result:ProviderResult,now)->dict`, `cancel_delivery(db_url,tenant_id,owner_id,delivery_id,now)->dict`.

- [x] Pruebas con dos conexiones de DB reales: un claim, dos start concurrents, lease vencido sin inicio, lease vencido después de inicio, revoke y hora > ventana. Fixture `delivery_case` crea decisión válida/corte de historia listo; el reloj es inyectado.

```python
def test_started_attempt_is_never_reclaimed(delivery_case):
    from webapp.publications.deliveries import claim_due, start_attempt
    db_url, principal, now = delivery_case
    claim = claim_due(db_url, principal, now)
    assert claim is not None
    start_attempt(db_url, principal, claim["claim_id"], claim["contract_hash"], now)
    assert claim_due(db_url, principal, now + 7200) is None
```

- [x] Ejecutar en SQLite y PostgreSQL. Implementar reservas atómicas con `BEGIN IMMEDIATE`/locks PG y CAS por estado, claim, grant y hash; outbox/dedup por destino. El inicio confirma un único intento, el timeout de su ACK se concilia antes de POST.

```sql
UPDATE publication_deliveries SET state='attempt_started', started_at=?
WHERE tenant_id=? AND id=? AND state='reserved'
  AND claim_id=? AND worker_grant_id=? AND contract_hash=? AND lease_until>?;
```

- [x] `rowcount != 1` nunca concede intento. Caducidad es `due_at + 3600`; cuota diaria se evalúa en zona de política. Fuera de ventana registra `expired`; no programa tarde por sí mismo. Revocar después de inicio conserva incertidumbre/conciliación, no borra el intento.
- [x] API entrega original y credencial únicamente a reserva vigente de esa conexión/empresa; comprobar hash del PNG exacto. Reportes idempotentes; URLs remotas validadas por host/plataforma. Cancelación solo antes de inicio; retirada añade evento confirmado.
- [x] Pruebas de pérdida de ACK/report, servidor caído y eventos duplicados. Revisión y commit `feat: add durable calendar claims and conservative attempt states`.

## Task 7: trabajador separado y adaptadores de todas las redes

**Files:** crear `publisher_worker/{__init__,__main__,client,outbox,media_delivery}.py`, `publisher_worker/adapters/{__init__,base,facebook,instagram,x,tiktok}.py`, `publisher_worker/tests/test_dispatch.py`, `publisher_worker/tests/test_adapters.py`, `deploy/eikon-publisher.service`, `deploy/eikon-publisher.timer`.

**Interfaces:** `run_once(client,outbox,adapters,now)->dict`; `ProviderAdapter.preflight(connection,variant,now)->dict`, `ProviderAdapter.publish(connection,variant,attempt_id)->ProviderResult`, `ProviderAdapter.reconcile(connection,result)->ProviderResult`.

- [x] Tests sin red real: decisión rechazada, política revocada, credencial ajena, sin stock, SHA distinto, inicio no confirmado, HTTP 5xx/timeout tras POST y fallo de X sin afectar Facebook.

```python
def test_unconfirmed_start_never_posts(dispatch_case):
    from publisher_worker.client import run_once
    client, outbox, adapters, now = dispatch_case
    client.start_attempt_response = {"confirmed": False}
    run_once(client, outbox, adapters, now)
    assert sum(a.post_count for a in adapters.values()) == 0
```

`dispatch_case` utiliza dobles explícitos para cliente y adaptadores, con outbox SQLite temporal; no monkeypatch global de producción.

- [x] Ejecutar tests fallidos. Outbox local por tenant registra autorización antes de POST; recuperar la confirmación de Eikón, no interpretar un timeout como fallo. Una vez `attempt_started` no hay reintentos de publicación implícitos.

```python
started = client.start_attempt(claim)
if not started["confirmed"]:
    return {"state": "held", "reason": "start_not_confirmed"}
outbox.record_started(claim)
result = adapter.publish(connection, variant, claim["attempt_id"])
outbox.record_result(claim, result)
client.report_attempt(claim, result)
```

- [x] Facebook: portar contrato foto/feed conservador; añadir vídeo/reels mediante adaptador independiente y tests de recibo/procesamiento, sin usar módulos de anuncios. Instagram: foto JPEG exacta y vídeo/reels con contenedor/status/publish. No afirmar que PNG recibido por un test simulado es formato aceptado por Meta.
- [x] Contrato local y tests de `media_delivery`: URL HTTPS temporal del único archivo autorizado, sin cookies/token de redes en URL, sin publicar galería; key/TTL/SHA y revocación tras procesamiento o vencimiento.
- [ ] Verificar entrega, revocación, logs y dominio reales antes de activar URLs o TikTok: aceptación obligatoria en Task 10.
- [x] X: conservar contrato v2 imagen y vídeo por fases y guardia económica antes de cualquier endpoint facturable. TikTok: implementar creator_info, OAuth scopes reales, init foto/vídeo, dominio verificado, commercial/AIGC/privacidad y status final; si falta consentimiento no iniciar transferencia. Las pruebas privadas no se presentan como publicación pública. No asumir que las cards de marca existentes cumplen las reglas TikTok: evaluar una variante específica y comprobar restricciones de branding/agua añadida, sin alterar ni redibujar logos oficiales para pasar la prueba.
- [x] Añadir matriz explícita `unknown|verified|requires_auth|requires_provider_review|requires_post_consent|blocked_by_budget|unsupported_media|rate_limited`. Los fallos por destino no detienen el barrido de otras cuentas. Timer nuevo inicialmente disabled, red de prueba sin proveedores reales.
- [x] Revisión del paquete/concurrencia y commit `feat: add isolated publisher worker and channel adapters`.

**Recibo local:** trabajador/adaptadores revisados hasta `9fb8e588d082480e03eabf45eaa0b4a798105ec0`, tras una corrección de recuperación Instagram. Las interfaces y pruebas locales quedan completas; prueba real de proveedores, revocación de URL y runtime permanecen en Task 10. TikTok GET/start de consentimiento pertenece a Task 8.

## Task 8: recorrido integrado, política y panel

**Files:** crear `frontend/src/api/publications.ts`, `frontend/src/pages/Publications/{PublicationsPage,PolicyPanel,CampaignDetail,CalendarPanel,ConnectionPanel,AttemptDetail}.tsx` y sus tests; modificar `frontend/src/App.tsx`, `frontend/src/components/AppShell.tsx` y estilos de publicaciones.

**Interfaces:** cliente tipado consume solo metadatos públicos; `GET /api/v1/publications/overview`, `/campaigns`, `/calendar`, `/connections`, `/deliveries/{id}` y política. La API de overview devuelve decisiones/policy y estados por cuenta, sin tokens ni secretos.

- [x] Tests de interfaz: empresa activa, candidato retenido por IA, fecha expirada, post confirmado con enlace, resultado incierto y TikTok requiere consentimiento. Las etiquetas distinguen evaluación IA y revisión humana visual.

```tsx
it("no muestra publicado para un intento incierto", () => {
  render(<AttemptDetail attempt={{state: "uncertain", permalink: null}} />);
  expect(screen.getByText(/resultado incierto/i)).toBeVisible();
  expect(screen.queryByRole("link", {name: /ver publicación/i})).toBeNull();
});
```

- [x] Ejecutar `npm test -- --run` y registrar el fallo focal. Implementar vista de producto→campaña→candidato→decisión→calendario→recibo, política editable solo owner y botón detener autonomía. Permitir revisar razones/fuentes/archivo exacto sin aprobar manualmente por defecto.
- [x] En TikTok mostrar cuenta, preview editable, selector de privacidad sin default y controles de divulgación/consentimiento requeridos; guardar evidencia del paso externo contra la revisión exacta. Editar texto/privacidad crea nueva revisión y evaluación, no altera una decisión ya congelada.
- [x] Commit local `feat: connect autonomous campaigns calendar and operational status`, seguido de corrección revisada del replay de consentimiento.
- [ ] Mobile/desktop por navegador cliente real, accesibilidad y copy finales: aceptación obligatoria en Task 10, sin sustituirla por DOM o maqueta.

**Recibo local:** panel y autoridad TikTok revisados hasta `0bb3e53395179830a24011fb42cab405d5a5b2fc`, con replay exacto que conserva recibo y expiración. GUI, evidencias externas y operación diaria reales siguen en Task 10. Historial/previews sin límite y deprecación del runner están documentados para el cierre.

## Task 9: funcionamiento diario del cliente Codex

**Files:** crear `docs/OPERACION-CODEX-PUBLICACIONES.md`, `mcp_server/tests/test_publication_stdio.py`; ampliar tools de tarea 5 y configuración de bandeja sin almacenar sesiones.

**Interfaces:** bandeja por política expone candidatos pendientes y déficit de stock. El cliente planner crea encargo/candidato; el reviewer concede decisión dentro de política. Worker solo consume entregas vigentes.

- [x] Test stdio real con grants de prueba prueba aislamiento, respuesta tipada e invalidación; no requiere herramientas de imágenes remotas.

```python
def test_disconnected_reviewer_does_not_authorize_candidate(candidate_without_decision):
    from webapp.publications.decisions import publication_eligibility
    db_url, tenant_id, revision_id, now = candidate_without_decision
    result = publication_eligibility(db_url, tenant_id, revision_id, now)
    assert result["eligible"] is False
    assert "evaluation_missing" in result["reasons"]
```

- [x] Escribir instrucciones del agente diario con política/cuentas/fuentes y reglas de evaluación. No guardar auth.json ni tokens en prompt/docs. Seleccionar producto/variante sin repetir medios históricos, producir con image_gen integrado y componer con logo exacto si falta stock; evaluar realmente, conservar respuesta y entregar por MCP.
- [ ] En el cliente Humanizar configurar automatización mediante herramientas oficiales de la app (heartbeat para este chat), no editar RRULE/crontab como sustituto. Cada empresa configura su propio cliente/automatización. El worker server2 no utiliza la suscripción de otra empresa.
- [ ] Ejecutar una vez en cliente real; conservar correlación candidato→archivo→modelo→decisión→entrega, no solo registro de automation. Desconectar cliente en prueba controlada: déficit visible, ninguna evaluación inventada; las entregas autorizadas vigentes siguen su curso.
- [x] Revisión y commit `docs: validate daily tenant Codex production and evaluation`.

**Recibo local:** bandeja planner y MCP28 revisados en `93d1d73d678eb8bac29d5fa075f4c8e45c816d97`, sin hallazgos Critical/Important. Pruebas de consumidores afectados: 713 aprobadas; refuerzo final: 34 aprobadas. Modelo, imagen, conexión nativa, ejecución diaria y publicaciones reales siguen pendientes de Task10; stdio con evaluación sintética no los acredita. El motivo contractual vigente es `ai_decision_required`; `evaluation_missing` del snippet es ilustrativo.

## Task 10: despliegue y aceptación completa por canal

**Files:** crear `docs/DEPLOY-CENTRO-PUBLICACIONES.md`, `docs/QA-CENTRO-PUBLICACIONES.md`, `scripts/check_publication_acceptance.py`; ampliar `docs/GOAL-CENTRO-PUBLICACIONES.md`. No escribir credenciales o backups en repo.

**Interfaces:** verifier recibe recibo saneado del release y exige requisitos por canal. El resultado global distingue `verified`, `externally_blocked` y `incomplete`; no convierte un bloqueo en PASS total.

- [x] Ejecutar la matriz local integrada con PostgreSQL de prueba, frontend tests/build y stdio MCP: snapshot1.932 PASS/2 omisiones demo; finales acotados55 verifier y191 logging/media/OAuth/worker. Tipos109/116 PASS; Ruff global43 heredados conserva FAIL. Revisión de integración local aprobada tras una corrección; no acredita cliente/modelo/proveedores reales.
- [x] Revisión independiente de fronteras de la rama y resolución de los cinco hallazgos: corrección `a4389e8`, revisión focal conforme/aprobada, sin hallazgos nuevos. La cobertura de galería anterior, recursos, lockfile y suites masivas fue parcial; no se afirma aprobación exhaustiva del diff histórico.
- [ ] Completar la cobertura real de invariantes y formatos en la aceptación siguiente, conservando los gates heredados fallidos/omitidos y la limitación de revisión declarada.
- [ ] Respaldo privado de DB/storage/config server2 y runtime; restaurar en clon aislado y ejecutar init dos veces. Crear imagen Docker y fijar digest/revisión/commit. Secretos nuevos se suministran mediante configuración privada y respaldo; rollback conserva el ledger y no devuelve rutas antiguas con permisos nuevos sin guards.
- [ ] Desplegar Eikón en el servicio Cloud Run y proxy existentes, worker separado en server2 con timer aún disabled. Verificar salud y rutas autenticadas, aislamiento ajeno y UI real; estos checks no acreditan publicación.
  Avance comprobado: API/SPA desplegadas en `eikon-00061-6lk`, código `a4389e8`, digest OCI `sha256:9eef3179f126238b288b71da071b86db3e5949459e2e41b99783b9717d420e4e`. Configuración e IAM conservadas; tres orígenes sirven la misma SPA y sesión API Humanizar owner obtiene perfil/publicaciones HTTP200. Worker, aislamiento real y GUI pendientes; el checkbox compuesto sigue abierto.
- [ ] Activar política Humanizar con las autorizaciones de este chat, importar historia y conexiones comprobadas, emitir grants dedicados y ejecutar evaluación IA real sobre una pieza completa. La fuente Graf que enlaza admin requiere explicación o alternativa acreditada; el modelo puede retenerla por pertinencia del CTA.
- [ ] Facebook e Instagram: ejecutar una entrega vigente por cuenta elegible, confirmar recibo/visibilidad y segunda ejecución sin nuevo POST. Foto, vídeo y reel se verifican separadamente; no heredar evidencia de una foto a vídeo. La IA elige contenido pertinente, no un score de test.
- [ ] TikTok: completar OAuth/auditoría y consentimiento cuando sean exigibles; probar con cuenta/visibilidad adecuadas y confirmar estado final. Si no se puede completar externamente, conservar evidencia del bloqueo y paso exacto, sin afirmar publicación pública ni automatización desatendida.
- [ ] X: con la restricción actual, probar localmente contratos e informar `blocked_by_budget` hasta capacidad económica compatible acreditada. No realizar llamadas facturables ni comprar créditos. La futura habilitación económica requiere instrucción directa del operador.
  Ampliación autorizada por el operador: preparar y probar la vía gratuita de Brave. Foto Sinergia publicada y dos filas nativas conciliadas para el 13/14 de octubre; no equivale a habilitar la API ni completar recurrencia. Ver el corte actual de pruebas. La restricción de gasto API se conserva.
- [ ] Probar caída antes/después de inicio, timeout/ACK perdido, policy/grant revocado, retiro confirmado y original cambiado. No eliminar una publicación para evadir duplicación.

```python
def channel_complete(evidence):
    return (evidence["ai_decision_real"]
            and evidence["revision_current"]
            and evidence["receipt_confirmed"]
            and evidence["visible_after_publish"]
            and evidence["second_run_post_count"] == 0)
```

- [ ] Solo tras la prueba diaria real y revisión de evidencias habilitar timer nuevo; mantener ambos timers legacy disabled/inactive. Frecuencia por cuenta definida por política y stock, con ventana de 60 minutos y sin ráfagas. No cambiar presupuesto publicitario ni otros servicios.
- [ ] Commit `docs: record production autonomous publication acceptance`; push de branch/PR y despliegue autorizado, sin presentar documentación como código integrado. Cierre de meta requiere requisito por requisito; si faltan canales operativos, el objetivo sigue pendiente con bloqueos explícitos.

## Revisión del plan y estado de ejecución

Cobertura: tareas 1–3 política/cuentas/candidatos; 4 historia; 5 evaluación real; 6 calendario; 7 todos los adaptadores/media; 8 panel; 9 operación diaria de cada Codex; 10 despliegue/pruebas por formato/canal. Familia visual ya entregada se conserva y entra en QA, sin redibujar logos ni reabrir generación previa.

Las rutas, tablas, fixtures y firmas de este documento son **contratos a implementar**, salvo helpers existentes identificados. No hay runtime nuevo, nuevos scopes activos o publicación ejecutada por escribirlo. La elección de subagentes/revisión por tarea ya está preservada. El operador aprobó este plan antes de iniciar su implementación.
