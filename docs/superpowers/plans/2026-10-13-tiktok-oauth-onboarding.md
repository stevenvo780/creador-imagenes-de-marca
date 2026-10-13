# TikTok OAuth Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox syntax for tracking.

**Goal:** Dar de alta TikTok sin conocer open_id previamente, conservando aislamiento y reconexión estricta.

**Architecture:** Intento de alta separado de las conexiones existentes; state durable ligado a empresa/owner/sesión y proyectos. Callback común consume antes del proveedor, verifica evidencia y crea la conexión/vault atómicamente. La UI envía el nuevo contrato sólo para altas TikTok.

**Tech Stack:** Python/FastAPI/Pydantic, SQLite/PostgreSQL dual, vault AES-GCM, React/TypeScript/Vitest.

**Spec:** `docs/superpowers/specs/2026-10-13-tiktok-oauth-onboarding-design.md`, diseño acotado aprobado por el usuario en este turno. La ejecución con subagentes y revisión por tarea ya está autorizada.

## Global Constraints

- Sólo TikTok oauth2 recibe el nuevo alta; Facebook, Instagram, X y reconexiones permanecen compatibles.
- State ligado a tenant/owner/sesión, vigencia diez minutos, consumo una sola vez antes del exchange.
- Sin conexión provisional ni vault antes de evidencia remota concordante, permisos y caducidad válidos.
- Revalidar autoridad y proyectos después de la red; deduplicar bajo lock por empresa, conservando conexiones/vault previos.
- Migración aditiva SQLite/PostgreSQL, sin modificar datos/guards/colas/política existentes.
- Sin secretos, red de proveedor real, navegador, GCP ni operaciones productivas por subagentes. Fixtures ficticias y transporte HTTP simulado.
- Un escritor por archivo; no revertir cambios ajenos; commits serializados por root con pathspecs explícitos.
- Proyecto ya aislado en `codex/eikon-codex-publicaciones`. No cambiar cuentas, configuración de cuotas, auth.json ni sesiones.

## Review Focus

1. Consentimiento válido pero token/profile con IDs diferentes: cero conexiones/vault y error seguro.
2. Owner/proyecto revocado durante exchange: revalidación final rechaza el alta.
3. Callback concurrente/repetido o alta duplicada: un exchange por state, una conexión, vault previo intacto.
4. State/sesión/empresa ajena, expires_at exacto o configuración rotada: no consumir autoridad ajena ni crear conexiones.
5. Frontend abortado o URL OAuth host/protocolo inválidos: no navegar ni completar trabajo de otra sesión; reconexión conserva contrato.

### Task 1: Servidor, intento durable y callback

**Files:**
- Create: `webapp/publications/oauth_onboarding.py` — inicio/consumo/creación atómica del alta TikTok.
- Modify: `webapp/publications/migrations.py` — tabla y versión aditivas de intentos.
- Modify: `webapp/api/publications.py` — endpoint estricto y despacho del callback común.
- Modify only if sharing validation is needed: `webapp/publications/oauth.py` — extraer evidencia común sin relajar remote_id de reconexión.
- Test: `webapp/tests/test_publication_oauth_onboarding.py`; ajustes mínimos de pruebas OAuth existentes sólo si el contrato común lo requiere.

**Interfaces:**
- Consumes: `OAuthConfig`, `VerifiedAccount`, `VerificationClient`, cliente oficial token→user/info, `lock_tenant`, `require_owner`, vault y `connection_metadata` existentes.
- Produces: POST `/oauth/onboarding/start` con body `{platform:"tiktok",api_mode:"oauth2",project_ids:number[],redirect_uri:string}` y respuesta `{state,authorization_url,expires_at}`; GET `/oauth/callback` común devuelve metadatos de conexión sin credenciales después de alta válida.
- Motor `start_onboarding(db_url,tenant_id,owner_id,platform,redirect_uri,now,*,project_ids,session_binding,config,key,key_id)`; `finish_onboarding(db_url,session_owner,state,code,now,client,*,key,key_id,provider_error=False)`. Los parámetros privados nunca llegan a JSON público.

- [x] Crear fixtures propias efímeras con dos empresas, owner/member, proyectos activos/archivados, config/clave/token ficticios. Parametrizar SQLite/PostgreSQL conforme al fixture dual existente; transporte simulado sólo al borde remoto.
- [x] RED: iniciar sin ID, verificar que no existe ninguna conexión; callback válido descubre `open-42`, devuelve active, proyectos correctos y vault descifrable con AAD de esa empresa/conexión. Antes de implementar, capturar FAIL esperado por endpoint/función ausente.

```python
assert result["remote_id"] == "open-42"
assert result["status"] == "active"
assert result["project_ids"] == [own_project_id]
assert len(list_connections(db_url, own_tenant_id, owner_id)) == 1
```

- [x] Añadir RED de identidad token/perfil distinta usando `OfficialOAuthClient` + `httpx.MockTransport`, scopes insuficientes, vencimiento exacto, rechazo del proveedor, vault ausente y errores reflejando secretos; cada caso deja cero conexión/vault.
- [x] Añadir RED de miembro no owner, proyecto/empresa ajena, nonce distinto, state repetido/expirado, owner/proyecto revocado durante exchange y configuración rotada. Comprobar ausencia de efectos sobre cuentas previas y un solo exchange ante replay.
- [x] Añadir RED de dos intents a mismo destino, y concurrencia con SQLite/PostgreSQL: segundo alta conflicto seguro, no cambia versión/proyectos/ciphertext de la primera. Reconexión a otro ID conserva rechazo `remote_identity_mismatch`.
- [x] Implementar tabla de intentos sin FK a conexión provisional, hashes/state/config/project snapshot y consumo durable; usar transacción/lock existentes. Guardar conexión, detalles, proyectos y vault conjuntamente sólo después de la evidencia y revalidación final.
- [x] Registrar endpoint estricto, runtime configurado existente y cookie nonce HttpOnly/SameSite; callback distingue intento de alta y reconexión sin buscar identificadores fuera de tenant/owner.
- [x] GREEN focal: `.venv/bin/python -B -m pytest -p no:cacheprovider webapp/tests/test_publication_oauth_onboarding.py webapp/tests/test_publication_oauth.py webapp/tests/test_publication_connections.py -q`. Ruff/diff-check de archivos propios. Root ejecutará la suite Python completa una vez integradas ambas tareas.
- [x] Autor­revisión y reporte con comandos, stdout RED/GREEN, fuentes, límites PG y cambios. Root serializa commit de esta tarea y despacha revisión de especificación/calidad; no auto-delegar ni editar interfaz/documentación.

### Task 2: Alta TikTok desde la interfaz

**Files:**
- Modify: `frontend/src/pages/Publications/ConnectionPanel.tsx`.
- Modify: `frontend/src/api/publications.ts` — permitir ruta nueva y errores específicos seguros si hace falta.
- Test: `frontend/src/pages/Publications/connection-onboarding.test.tsx` o pruebas existentes de publicaciones si un ajuste mínimo evita duplicar fixtures.

**Interfaces:**
- Consumes: contrato exacto POST `/oauth/onboarding/start` de Task1, respuesta `authorization_url`, `usePrivateOperation`, allowlist de hosts HTTPS existentes.
- Produces: alta nueva TikTok sin campo ID remoto ni POST `/connections`; proyectos y callback canónico enviados. Conectar/renovar cuenta existente continúa con `/oauth/start` y `connection_id` original.

- [x] RED: renderizar ConnectionPanel real, elegir TikTok, introducir proyectos y enviar sin ID; observar solicitud al nuevo endpoint, sin remote_id/connection_id y sin crear metadatos por `/connections`.

```typescript
expect(body).toEqual({
  platform: "tiktok", api_mode: "oauth2", project_ids: [11],
  redirect_uri: window.location.origin + "/api/v1/publications/oauth/callback",
});
```

- [x] RED: IDs malformados/ceros, respuesta OAuth HTTP/host extraño/credenciales en URL, sesión abortada o cambio de empresa mientras espera: no navegar; errores visibles seguros. Reconexión TikTok usa ID existente; demás redes conservan formulario/endpoint y requisito ID.
- [x] Implementar derivación del body y navegación validada. Extraer helper común pequeño si evita duplicar la validación de URL; no rediseñar tema, política, consentimientos o tarjetas.
- [x] GREEN: `npm test -- --run` completo una vez y `npx tsc --noEmit`; root hará build de entrega con ambos cambios y suite de integración.
- [x] Autor­revisión y reporte RED/GREEN con archivos propios y límites; root serializa commit y revisión. No editar backend/docs ni ejecutar proveedor/producción/navegador.

### Task 3: Integración, evidencia y despliegue preservando configuración

**Files:**
- Modify: `docs/PRUEBAS-PUBLICACIONES-2026-10-12.md`, `docs/DEPLOY-CENTRO-PUBLICACIONES.md` sólo con evidencia actual.
- Root owns: operadores/recibos privados nuevos para revisión, calificación y promoción; nunca modificar operadores históricos fijados.

**Interfaces:** Consumes commits/reviews PASS de Task1/2; produces build verificado, pruebas integradas, entrega al servicio existente y checkpoint/seguimiento actualizados sin dar consentimiento TikTok por completado.

- [x] Ejecutar suite Python del proyecto (pytest testpaths completo), PostgreSQL efímero para nuevos tests y reconexión/migración, lint/mypy pertinentes y `npm run build`. Registrar todos los fallos preexistentes; no confundir skips con PG verificado.
- [x] Revisión integrada en Codex GPT-6 Astra del rango completo desde baseline y diff empaquetado. Una única ronda de fixes integrada si aparece riesgo nuevo; no tocar proveedores o otros pendientes.
- [x] Build de imagen misma receta del servicio actual; calificar una nueva revisión 0% con OAuth config2/IAM/recursos/secretos intactos. Prueba de migración idempotente y callback/alta usando fixtures aisladas; nunca activar conexiones/worker de empresa17 con un doble remoto. Se heredó el digest actual para conservar dependencias exactas; overlay y único label de fuente verificados.
- [x] Promover sólo imagen/revisión después de gates; comprobar frontend autenticado, alta sin campo ID, rechazo anónimo del endpoint, callbacks canónicos, rutas públicas TikTok TXT/PNG y cuentas/cola/política preservadas.
- [x] Mantener service/timer17 apagados hasta prueba real prevista22–23Bogotá; no recrear Deméter5/6/7, Agentes8/9/10 ni colas nativas X/TikTok.
- [ ] Actualizar documentación, checkpoint y heartbeat existente21:45 con nuevo release y estado aprobado/implementado. El consentimiento remoto, cuatro requisitos del portal y recurrencia real conservan sus gates y no se marcan completos por este despliegue.
