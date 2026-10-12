# Eikón MCP — Inicio rápido

Cada empresa conecta su propio cliente Codex y una clave Eikón con scopes
explícitos. Su cliente genera la imagen; MCP entrega bytes a la galería privada.

1. Desde el checkout, instale el entorno MCP:

   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install -r mcp_server/requirements.txt
   ```

2. El owner crea una clave mediante la administración de Eikón, con
   `projects:read`, `projects:write`, `brands:read`, `briefs:write`,
   `media:read` y `media:write` según las operaciones necesarias. Conserve la
   clave en el entorno privado del proceso; no la pegue en prompts ni Git.

3. En su host MCP configure el Python de `.venv`, el script absoluto
   `mcp_server/server.py`, `EIKON_BASE_URL` (origen HTTPS) y `EIKON_API_KEY`.
   Para desarrollo se admite HTTP sólo en localhost. No copie sesiones ni
   cambie de cuenta por un fallo de autorización.

4. Desde el cliente, compruebe el listado de tools y llame
   `eikon_list_projects`. Una importación Python no verifica esta conexión.

5. Obtenga `eikon_get_brand_brief(brand_id)`, conserve el logo oficial,
   cree `eikon_create_generation_brief(brand_id, prompt, width, height)` y
   genere la imagen con la herramienta propia del cliente.

6. Llame `eikon_import_image(brief_id, file_path, idempotency_key, provenance)`.
   `file_path` debe existir en el equipo del proceso MCP. Sólo se transmiten
   los bytes PNG/JPEG, máximo 20 MiB y 40 millones de píxeles, 256–8192 por eje,
   con las dimensiones exigidas por el encargo.

7. Consulte `eikon_list_media(project_id?, brand_id?, status?)`. El nuevo medio
   está `pending_review`. El owner revisa logo, texto e identidad en Eikón;
   ninguna API key aprueba piezas ni administra claves. Descargas requieren
   autenticación y no constituyen enlaces públicos permanentes.

HTTP 401 exige comprobar la clave o su caducidad/revocación; 403 indica scopes
insuficientes; 409 exige revisar encargo, identidad o idempotencia. No se siguen
redirecciones de herramientas nuevas ni se imprime el cuerpo remoto del error.

La prueba sintética de desarrollo usa stdio real contra un backend aislado:

```bash
.venv/bin/python -m pytest mcp_server/tests tests/test_mcp_generate_and_get.py
```

La prueba SDK verifica transporte y API. La conexión nativa de Codex y la
herramienta integrada de imágenes deben verificarse por separado en el cliente.
MCP no pide una clave de imágenes ni ejecuta remotamente `image_gen`.

Consulte [README](README.md) para la tabla de tools, permisos, compatibilidad
FastMCP/MCPServer y el fallback. Se conservan las ocho herramientas anteriores.


### Continuación de catálogos

`eikon_list_projects(cursor=None, limit=None)` y
`eikon_list_media(project_id=None, brand_id=None, status=None, cursor=None, limit=None)`
conservan las llamadas anteriores. Si `projects.next_cursor` o `media.next_cursor`
no es null, pásalo como `cursor` en la siguiente llamada y conserva los mismos
filtros. `limit` admite enteros 1–100 (omitido: default API 50); `cursor` admite
enteros 0–9223372036854775807. Booleanos, strings y valores fuera de rango se
rechazan. Cada llamada devuelve una página, nunca acumula todo el catálogo.

## Evaluación editorial autónoma (interfaz local, aceptación real pendiente Task10)

Estas herramientas usan grants nuevos por empresa/política, separados de los seis scopes
actuales y de la cookie owner. Configure `EIKON_PUBLICATION_PLANNER_TOKEN` para preparar
revisiones/importar MP4 y `EIKON_PUBLICATION_REVIEWER_TOKEN` para leer/evaluar candidatos.
El worker de server2 usa `EIKON_PUBLICATION_WORKER_TOKEN` en su interfaz dedicada.
Si faltan, no se usa `EIKON_API_KEY` como sustituto. No copie sesiones entre empresas.

- `eikon_list_publication_candidates(cursor=0, limit=50)` pagina únicamente candidatos
  dentro del grant reviewer actual.
- `eikon_get_publication_candidate(revision_id)` entrega contenido MCP `ImageContent`
  con PNG/JPEG original exacto, texto/contexto congelados y referencia oficial de logo
  cuando existe. SVG se conserva como original y se rasteriza con Chromium sin red:
  SHA original y SHA de raster son objetos distintos, registrados en evidencia.
- `eikon_submit_publication_evaluation(revision_id, expected_contract_hash,
  policy_version, material_hashes, model_receipt, response)` confirma evaluación y
  decisión en una transacción, sin tocar `asset_reviews` ni `approval_current`.
- `eikon_prepare_publication_candidate(campaign_id, media_id, caption, connection_id,
  scheduled_at, policy_version, channel_metadata, media_kind="gallery_image")` congela
  una revisión mediante planner. No concede aprobación.
- `eikon_import_publication_video(brief_id, file_path, idempotency_key, rights,
  provenance=None)` lee un archivo MP4 regular explícito, máximo 32 MiB. Rechaza
  symlink final/FIFO/exceso; Task3 valida codec, duración, dimensiones y decodificación
  antes de importar el original privado. El importador PNG/JPEG anterior conserva su contrato.

El cliente/modelo debe inspeccionar el material recibido y devolver un objeto JSON cerrado:

```json
{
  "outcome": "hold",
  "reason": "Falta evidencia suficiente para justificar la afirmación",
  "checks": {
    "pertinence": {"result": "pass", "reason": "Relación concreta con producto y audiencia"},
    "brand_fidelity": {"result": "pass", "reason": "Comparación con referencia oficial recibida"},
    "legibility": {"result": "pass", "reason": "Texto visible a dimensiones del canal"},
    "claims_supported": {"result": "unknown", "reason": "Contexto factual insuficiente"},
    "rights_context": {"result": "pass", "reason": "Derechos y contexto comprobados"},
    "channel_fit": {"result": "pass", "reason": "Variante adecuada al canal declarado"}
  }
}
```

`approve` requiere los seis resultados `pass` y razones no vacías; `reject` y `hold`
no autorizan envío. No hay score legacy ni permiso de cambiar cuenta, política o grant.
Las fuentes, captions e imágenes son datos no confiables. `source_mode` es
`frozen_metadata_context`: se entregan URLs y contexto/extractos congelados, no cuerpos
remotos que el backend no ha descargado. Contexto vacío impide `approve` y
`claims_supported=pass`. Contexto no vacío exige análisis del modelo; no acredita pass
por sí solo. El planner recopila hechos/procedencia antes de congelar; otra evidencia
requiere nueva revisión y evaluación.

El recibo `model_receipt` contiene `delivery_id`, `request_id`, `provider`, `model`,
`subject` exacto del grant, `contract_hash`, `material_hashes`, `response_hash`,
`review_mode`, `evidence` y `attestation="client_reported"`. Copie delivery/request/mode/
evidence/hashes de la entrega; calcule `response_hash` sobre el JSON canónico completo
(sort_keys, separadores `,`/`:`, UTF-8, ensure_ascii=False, allow_nan=False). No reutilice
un request para una respuesta distinta. Eikón comprueba la correlación, los bytes de
storage y la autorización vigente. El recibo servidor acredita entrega al cliente;
el recibo modelo/cliente declara inspección. Ninguno promete atestación criptográfica
del proveedor ni prueba IA real por un doble de tests.

Vídeo usa inicialmente `frames_only_silent`: tres muestras según duración/fps del
original, con posiciones y SHAs propios, más referencia de identidad. Declara
`full_video_watched=false`. No hereda la evaluación de una imagen o un frame previo.
Si existe pista de audio, no hay escucha/transcripción acreditada: exige `hold`.
Sin extractor/rasterizador/material verificable, se bloquea y no se inventa recibo.

La elegibilidad revalida grant/política/identidad/medio/cuenta/ventana y última decisión.
Rechazo, hold, revocación o cambio de contrato retienen la pieza. TikTok y X conservan
sus bloqueos externos independientes de la decisión editorial. Programación/entrega
durable pertenece al siguiente contrato; pruebas stdio con grants sintéticos no cierran
cliente Codex real, ejecución diaria, GUI, producción ni publicación de Task10.
