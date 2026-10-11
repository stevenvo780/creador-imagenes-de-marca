# Meta: Eikón como centro de marca y publicaciones

Creada por instrucción del operador el **11 de octubre de 2026**, America/Bogota.
Estado: **activa**. La meta del chat es el seguimiento principal; este documento
conserva requisitos, avances y evidencia del repositorio.

## Resultado esperado

Cada empresa organiza sus productos, conserva sus logos, conecta su propio
Codex y sus redes, prepara campañas, revisa las piezas completas y publica
desde un calendario. El panel muestra pendientes, bloqueos y resultados reales.
Humanizar es la primera empresa; Facebook es el primer recorrido de publicación.

## Requisitos y aceptación

| Punto | Resultado comprobable | Estado inicial al 11 de octubre |
|---|---|---|
| Identidad de producto | Familia Humanizar común, originales exactos, estados correctos y variación acotada por producto | 15 marcas; 9 referencias originales; 6 referencias por resolver. Corrección de frontend y perfil de familia en desarrollo. |
| Producción | Pieza final con texto, imagen y formato; retícula y contraste comprobados; procedencia Codex | 15 ilustraciones pendientes de revisión. Hay estudio y MCP; falta completar piezas de campaña. |
| Campañas | Proyecto, objetivo, secuencia y variantes por destino; autorización de cada revisión completa | Subsistema aún no implementado. |
| Calendario | Fechas con zona, retenciones visibles, reserva concurrente y recibos por destino | Publicador externo existe; Eikón no tiene calendario. |
| Conexiones | Cuentas de cada empresa, identidad remota comprobada, permisos y vencimientos visibles | Accesos Humanizar externos; no hay módulo social multiempresa en Eikón. |
| Panel operativo | Crear, revisar, programar, corregir y comprobar resultados desde el mismo recorrido | Pantallas actuales de proyectos/marcas/estudio/galería; falta el recorrido integrado. |

## Entregas

1. **Familia e identidad en el flujo existente.** Corregir el estado de logos
   importados; introducir perfil Humanizar explícito y composición coherente,
   conservando otras familias. Pruebas, revisión independiente y QA cliente.
2. **Campañas y autorización completa.** Revisiones inmutables de imagen,
   caption, cuenta y horario; revisión owner y bandeja de trabajo para Codex.
3. **Conexiones, calendario y trabajador.** Primero Humanizar/Facebook, luego
   Instagram según stock y permisos. Cuentas y credenciales aisladas por empresa.
4. **Panel y ampliaciones elegibles.** Estados, conciliación y retirada; después
   métricas disponibles, vídeos/reels y TikTok. X conserva la decisión de no gasto.

La segunda y tercera entrega siguen el
[diseño del centro](superpowers/specs/2026-10-11-eikon-centro-publicaciones-design.md),
pendiente de revisión del documento y posterior plan. La primera corresponde al
diseño visual acotado presentado y confirmado en el chat.

## Restricciones permanentes

- No redibujar logos oficiales ni cambiar propietario de marcas existentes.
- Codex genera desde el cliente; MCP entrega encargos y recibe archivos. El
  timer del servidor no invoca una herramienta integrada de imágenes ficticia.
- Subir una imagen, fijar identidad o puntuarla no equivale a aprobación editorial.
- No ampliar silenciosamente los permisos de las claves Codex ni devolver secretos.
- Conservar el historial, las retiradas y la protección contra repeticiones.
- No utilizar la cola Humanizar como una base compartida entre empresas.
- No reactivar el calendario antiguo con imágenes repetidas o borradores pendientes.
- No introducir proveedores pagados, comprar créditos X ni considerar revisiones
  de TikTok/Meta resueltas sin evidencia externa.

## Evidencia inicial

El 11 de octubre se verificó por API la empresa Humanizar (tenant 17): 17
proyectos, 15 marcas de producto, 9 referencias de logo, 15 medios pendientes,
12 versiones rechazadas preservadas y 1 medio aprobado de la entrega anterior.
La API desplegada no contiene rutas de campañas, calendario, publicación u OAuth
social. Es una lectura de estado; no acredita implementación de esos subsistemas.

Facebook: cuatro repeticiones retiradas por autorización del operador; las dos
originales permanecen. Los dos timers de server2 están deshabilitados y las ocho
entregas antiguas repetidas retenidas. Ver el informe canónico en ComercialHumanizar:
`docs/INCIDENTE-PUBLICACIONES-REPETIDAS-20261011.md`.

## Avance verificado: primera entrega, 11 de octubre

- Frontend distingue logo original, procedural e identidad pendiente; la
  fijación de logo no equivale a aprobación editorial de las piezas.
- Perfil Humanizar explícito, Manrope, contraste y espaciado común. Las marcas
  de otra familia conservan su comportamiento. La fila de la empresa prevalece
  sobre archivos antiguos cuando el perfil está seleccionado, incluso con
  slugs coincidentes.
- Publicación vertical 1080×1350 disponible en Estudio y catálogo, con retícula
  efectiva de doce columnas y logos originales sin recorte. Las variantes de
  cuatro y ocho columnas siguen siendo metadata, no layouts implementados.
- Revisión independiente aprobó las correcciones y el recorrido HTTP
  `202 → plan 200`, con respuesta 404 para otra empresa.
- Suite completa: **867 aprobadas, dos omitidas** por artefactos de demostración
  ausentes; PostgreSQL de prueba aislado habilitado. Pruebas finales añadidas:
  **45 aprobadas**, incluyendo PostgreSQL. Frontend: **67 aprobadas** y build
  TypeScript/Vite correcto. Ruff de archivos nuevos y mypy focal pasan.
- Navegador local: acceso, tres estados de marca y generación vertical
  verificados. Se descargó PNG 2160×2700, pero la inspección descubrió recorte
  en preview, logo demasiado pequeño y pie fuera del PNG. Corregidos con TDD:
  marco de preview, ancho útil de logo 231 px y mínimos del body fijados al
  viewport. Frontend final: **75 aprobadas**, build correcto; core final:
  **24 aprobadas**. Revisión independiente aprobada. La comprobación visual
  posterior a esos cambios se detuvo otra vez por panel de extensión.
- Respaldo privado fresco de producción restaurado en un clon sin red:
  init_db dos veces conserva filas y columnas. Imagen Docker local construida.
  No se ha desplegado esta entrega ni cambiado marcas reales.

La meta permanece activa. Campañas, revisión completa, conexiones, calendario
y panel siguen pendientes del diseño escrito y posterior plan de ejecución.
