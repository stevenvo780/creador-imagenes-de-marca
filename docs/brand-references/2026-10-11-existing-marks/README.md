# Signos existentes recuperados del código

Exportados el 11 de octubre de 2026. **Referencias locales pendientes de
revisión visual**; no se han cambiado logos, briefs ni medios en producción.

| Producto | Archivo | Qué conserva | Qué no acredita |
|---|---|---|---|
| Cauce V3 | `cauce-simbolo-existente.svg` | Los dos trazados ondulados y su gradiente en la cabecera de la landing local | No es una firma con texto ni una comprobación del despliegue público actual |
| Aletheia | `aletheia-glifo-existente-claro.svg` | Las cuatro barras del componente Wordmark; atributos XML y color claro resuelto desde su CSS | No incluye la caja externa ni el nombre; no se presenta como firma completa |

`provenance.json` registra archivos fuente, hashes completos, hashes de los
fragmentos y hashes de los SVG resultantes. La geometría no se ha redibujado.
En Cauce se añade únicamente el namespace XML. En Aletheia se convierten los
atributos React y se resuelve el token `--measure` de tema claro como `#4338ca`.

El extractor reproducible está en `scripts/export_existing_marks.py`. Exige
un signo inequívoco y falla si no encuentra el patrón, si encuentra varios,
si hay tokens no resueltos o si el fragmento contiene contenido dinámico.
Es un extractor específico para estas dos fuentes; no es un parser JSX
general ni un sanitizador para subir SVG arbitrarios.

Cinco pruebas pasaron después de comprobar su fallo inicial. La revisión
independiente volvió a extraer las fuentes actuales: todos los hashes y bytes
coinciden. Esta comprobación no sustituye revisión visual ni aprobación de
marca. El glifo de Aletheia requiere conservar su contexto al componer una firma.

No se seleccionó una variante arbitraria de Prizma, un logo de cliente para
Deméter, el icono genérico de caja de Gravitatoria ni una marca personal para
Práxis. Sus decisiones de referencia siguen visibles como pendientes.

## Aplicación preparada a las quince marcas

`humanizar-family-prepared.json` registra el estado leído por API de la empresa
Humanizar, tenant 17: quince marcas de producto, nueve originales y ningún
perfil de familia seleccionado todavía. Los nueve archivos locales coinciden
por SHA con sus referencias remotas. El archivo prepara cambios de metadata
y tipografía sin incluir sesiones ni credenciales, conservando otros campos.

Agentes conserva su firma original clara y propone `family_mode="dark"`;
las otras catorce proponen `light`. El mapper respeta el modo explícito del
producto y las selecciones de tema de cada combinación. No recolorea logos.

El archivo no se ha aplicado: primero hay que desplegar y verificar el código,
revalidar empresa/versiones/hashes, mezclar campos conservando los existentes
y emitir nuevos briefs y revisiones de medios. Los seis productos sin una
referencia fija siguen identificados como tales. Las dos exportaciones no se
cuentan como identidades aprobadas por estar pendientes de revisión visual.
