# Auditorías Eikon

Las auditorías complementan los gates automáticos; no los sustituyen.

Flujo recomendado:

1. Definir scope de fase.
2. Ejecutar gates relevantes (`make qa`, `make run-ironman`, etc.).
3. Guardar evidencia: comandos, resúmenes y rutas de reportes.
4. Registrar findings con severidad y remediación verificable.
5. Firmar estado: `done`, `blocked` o `accepted-risk`.

Usa `TEMPLATE-phase.md` para nuevas auditorías y guarda instancias en `audit/reports/`.
