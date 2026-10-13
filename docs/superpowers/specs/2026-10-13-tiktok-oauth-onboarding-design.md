# Alta inicial de TikTok por OAuth

Diseño acotado aprobado directamente por el usuario el 13 de octubre de 2026:
«Sí, implementa ese flujo». Amplía la conexión existente; no concede permisos
remotos ni habilita publicaciones por sí mismo.

Una cuenta nueva se identifica mediante OAuth sin pedir previamente `open_id`.
El servidor cruza el identificador del token con `user/info` mediante el cliente
oficial existente y valida empresa, owner, sesión, permisos y caducidad antes de
crear conexión y vault. Las reconexiones conservan la identidad original estricta.
Se prueban alta, identidad distinta, empresas ajenas, repetición del callback y
conexiones duplicadas.

## Contrato y persistencia

- Sólo TikTok `oauth2` recibe el nuevo alta. Facebook, Instagram y X mantienen
  sus contratos actuales y X conserva gasto desactivado.
- `POST /api/v1/publications/oauth/onboarding/start` recibe
  `{platform:"tiktok",api_mode:"oauth2",project_ids:[...],redirect_uri:"https://..."}`.
  No acepta `remote_id`, `connection_id`, permisos, credenciales ni autoridad
  afirmados por el navegador. Responde con `authorization_url`, `state` y
  `expires_at`, como el inicio OAuth existente.
- Un intento de alta separado y aditivo conserva tenant, owner, hash de sesión,
  hash de state, configuración pública congelada y proyectos autorizados; dura
  diez minutos. No crea una conexión provisional ni altera cuentas existentes.
- El callback existente identifica el tipo de intento y consume el state una
  sola vez ANTES del exchange. La autoridad se revalida después de la red y
  antes de crear conexión, detalles y vault en una transacción.
- La creación exige `user.info.basic` y `video.publish`, token vigente y evidencia
  concordante de perfil/token. El ID procede exclusivamente del proveedor.
- Una conexión duplicada para el mismo tenant/plataforma/modo/open_id produce
  conflicto sin renovar, cambiar proyectos ni destruir el vault existente.
  Dos empresas mantienen credenciales, permisos y conexiones independientes.
- Cancelación, expiración, owner/proyecto revocado, replay, fallo remoto, scope
  insuficiente, mismatch, configuración cambiada o vault no disponible dejan
  cero conexiones nuevas y cero vault nuevos. No se publican secretos en errores.
- La migración agrega una tabla/versión; no cambia ni elimina registros,
  restricciones o triggers existentes y funciona en SQLite y PostgreSQL.
- La interfaz oculta el ID remoto para el alta de TikTok y envía directamente
  el nuevo contrato. Para una conexión ya existente usa `/oauth/start` sin cambios.

## Aceptación

Pruebas RED/GREEN del servidor y la interfaz, callback real de FastAPI con
transporte externo simulado, SQLite y PostgreSQL efímeros, suites del proyecto,
lint y build. Revisión independiente por tarea y revisión integrada. Despliegue
en el servicio existente conservando OAuth config v2, secretos, IAM, recursos,
colas, worker, guards y política 2. La prueba del consentimiento TikTok real
queda separada y sigue su aprobación de acceso remoto, requisitos del portal y
auditoría. Las programaciones nativas no se recrean.
