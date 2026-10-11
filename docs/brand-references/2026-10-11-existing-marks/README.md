# Signos existentes recuperados del código

Exportados el 11 de octubre de 2026. Cauce fue comprobado visualmente en
Estudio local y fijado como referencia en Eikón (marca 113, v4), conservando sus
trazos y gradiente. Después se recuperaron el símbolo completo de Aletheia y
el icono vigente del encabezado de Prizma. Ambos fueron fijados en Eikón tras
comparación visual local de las fuentes. Tras cerrar el panel de extensión,
el Estudio generó y descargó ambos PNG completos con originales, texto y pie
(2160×2700). Es QA local con cuenta sintética; no se han aprobado medios ni
publicado contenido social. Ver `docs/RELEASE-ESTUDIO-HUMANIZAR-20261011.md`.

| Producto | Archivo | Qué conserva | Qué no acredita |
|---|---|---|---|
| Cauce V3 | `cauce-simbolo-existente.svg` | Los dos trazados ondulados y su gradiente en la cabecera de la landing local | No es una firma con texto ni una comprobación del despliegue público actual |
| Aletheia | `aletheia-glifo-existente-claro.svg` | Las cuatro barras del componente Wordmark; atributos XML y color claro resuelto desde su CSS | No incluye la caja externa ni el nombre; no se presenta como firma completa |
| Aletheia | `aletheia-simbolo-existente-claro.svg` | Cuadro de 28 px, borde de 1 px, radio exterior de 4 px y glifo original de 12 px centrado; colores del tema claro | No incluye el nombre; escala basada en rem16 y Tailwind estándar. Marca115/v4, bytes recuperados por API iguales |
| Prizma | `prizma-icono-existente.svg` | Copia byte exacta del master `_brand-truth/prizma/icon.svg`, idéntica a la referencia del Header actual | No unifica las variantes antiguas del pie/grafo ni acredita su despliegue público. Marca120/v5 |

`provenance.json` registra archivos fuente, hashes completos, hashes de los
fragmentos y hashes de los SVG resultantes. La geometría no se ha redibujado.
En Cauce se añade únicamente el namespace XML. En Aletheia se convierten los
atributos React y se resuelve el token `--measure` de tema claro como `#4338ca`.

El extractor reproducible está en `scripts/export_existing_marks.py`. Exige
un signo inequívoco y falla si no encuentra el patrón, si encuentra varios,
si hay tokens no resueltos o si el fragmento contiene contenido dinámico.
Es un extractor específico para estas dos fuentes; no es un parser JSX
general ni un sanitizador para subir SVG arbitrarios.

Dieciséis pruebas del exportador pasaron después de comprobar su fallo inicial. La revisión
independiente volvió a extraer las fuentes actuales: todos los hashes y bytes
coinciden. Esta comprobación no sustituye revisión visual ni aprobación de
marca. El glifo de Aletheia requiere conservar su contexto al componer una firma.

Prizma se seleccionó por coincidencia entre master y encabezado actual; no se
redibujó. Deméter y Gravitatoria recibieron después símbolos y encuadres
extraídos de sus lockups UI existentes, con procedencia Lucide explícita.
La ausencia de símbolo exclusivo no impide conservar la composición que el
producto ya utiliza; se corrigió ese criterio anterior. No son masters
históricos encontrados ni acreditan exclusividad o registro. El asset F sigue
siendo de Ficadirecta; el sprite de la maqueta no sustituyó al Package actual.
Práxis121/v4 conserva después el símbolo compartido de Mouseîon/personal que
su cabecera vigente asocia expresamente a «Práxis — Mouseîon». Se conserva el
fragmento SVG exacto del DOM, sin salto añadido ni cambios de trazo/gradientes.
CSS calculado confirma tamaño30×30, opacity1, sin filter o transform. El enlace
original apunta a stevenvallejo.com; se documenta como signo compartido usado
en Práxis, sin atribuir exclusividad ni un master independiente histórico.
La comparación visual y revisión independiente aprobaron conservar esta fuente.
El original importado en la pieza43 aparece en galería real y snapshotv4,
pendiente de revisión editorial.

Deméter110/v4 conserva tema claro: glifo verde, fondo transparente y anillo
azul50%, tal como se verificó por CSS calculado en la landing publicada.
No se inventó el fondo verde15% que pretendían clases no compiladas.
Gravitatoria119/v4 conserva la variante oscura observada: cuadro azul claro,
Package exacto del DOM actual y trazo oscuro. Sus paths coinciden con las
capturas guardadas; el renderer usa el SVG como referencia autónoma.
Sólo se resuelve currentColor y se serializa XML; la caja Deméter normaliza
medidas subpíxel a38/22 nominales. El nombre no forma parte de estos SVG.

Las dos referencias y todos los campos conservados se verificaron por API
owner17. El navegador real de Humanizar generó PNG2160×2700 para ambos:
lotes2496/2497, variaciones3049/3050, bytes descargados iguales a los persistidos.
Los originales, textos y pies están visibles; no hay aprobación editorial ni
publicación. Ver `docs/RELEASE-REFERENCIAS-DEMETER-GRAVITATORIA-20261011.json`.

## Aplicación preparada a las quince marcas

`humanizar-family-prepared.json` registra el estado leído por API de la empresa
Humanizar, tenant 17: quince marcas de producto, nueve originales y ningún
perfil de familia seleccionado todavía. Los nueve archivos locales coinciden
por SHA con sus referencias remotas. El archivo prepara cambios de metadata
y tipografía sin incluir sesiones ni credenciales, conservando otros campos.

Agentes conserva su firma original clara y propone `family_mode="dark"`;
las otras catorce proponen `light`. El mapper respeta el modo explícito del
producto y las selecciones de tema de cada combinación. No recolorea logos.

El archivo conserva la preparación anterior a la aplicación; sus versiones
y hashes no deben usarse para repetir las escrituras. `slug` identifica el
producto y `expected_remote_slug` identifica la marca persistida en Eikón.
Tras desplegar y verificar, se aplicaron los quince perfiles conservando otros
campos. Cauce, Aletheia y Prizma recibieron después sus símbolos originales:
ahora hay quince referencias de producto fijadas. Deben emitirse nuevos briefs/revisiones
para las versiones actuales. Ver `docs/RELEASE-FAMILIA-HUMANIZAR-20261011.json`.
