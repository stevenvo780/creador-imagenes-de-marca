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
