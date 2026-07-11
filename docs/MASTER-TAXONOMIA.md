# MASTER TAXONOMÍA EIKON: ASSETS DE MARCA

## 1. RESUMEN EJECUTIVO

Esta taxonomía define la matriz completa y sistemática de assets de marca generados mediante el motor Eikon (HTML/CSS + Playwright) para las líneas Cloud Atlas (Pinakothḗke) y Prizma Enterprise. Su propósito es proveer a los sistemas de automatización con un esquema exhaustivo propio de una agencia de diseño profesional, asegurando coherencia visual a gran escala, accesibilidad estricta (WCAG AA), y adaptabilidad omnicanal. A través de este sistema de inyección de datos y variantes CSS, se generarán cientos de assets listos para producción (desde brand guidelines hasta social media kits) manteniendo la identidad, proporciones, contrastes y tipografías específicas de cada línea sin requerir ajustes manuales.

## 2. TAXONOMÍA POR LÍNEA

## CLOUD ATLAS (Pinakothḗke)

### Categoría: logos

#### Tipo: lockup_horizontal
- **Dimensión:** 1200x400 @72dpi
- **Formato:** PNG @2x | PDF | SVG
- **Variantes:** 3 (Color, Mono, Inverse)
  - `variant="v1_color"` — Símbolo con gradiente hero (Teal/Púrpura) y texto oscuro sobre fondo crema.
  - `variant="v2_mono"` — Símbolo y texto en negro puro (#0b1417) sobre fondo crema (#e8e0d4).
  - `variant="v3_inverse"` — Símbolo y texto en crema (#e8e0d4) sobre fondo negro (#0b1417).
- **Atributos data-* inyectables:** `data-logo-simbolo`, `data-logo-texto`
- **Archivo plantilla:** `/templates/cloud_atlas_lockup_horizontal.html`
- **Salida:** `/output/pinakotheke-kosmos/logos/lockup_horizontal-v{N}.png`
- **Reglas de contraste:** El texto de la marca hereda el color contrastante según luminancia del fondo (L > 128 = #0b1417, L <= 128 = #e8e0d4), garantizando ratio > 4.5:1.

#### Tipo: lockup_vertical
- **Dimensión:** 800x800 @72dpi
- **Formato:** PNG @2x | PDF | SVG
- **Variantes:** 3 (Color, Mono, Inverse)
  - `variant="v1_color"` — Isotipo centrado arriba, wordmark abajo. Colores primarios.
  - `variant="v2_mono"` — Monocromático para impresión/fax.
  - `variant="v3_inverse"` — Versión negativa para dark mode.
- **Atributos data-* inyectables:** `data-logo-simbolo`, `data-logo-texto`
- **Archivo plantilla:** `/templates/cloud_atlas_lockup_vertical.html`
- **Salida:** `/output/pinakotheke-kosmos/logos/lockup_vertical-v{N}.png`
- **Reglas de contraste:** Luminancia autoevaluada.

#### Tipo: wordmark
- **Dimensión:** 1000x300 @72dpi
- **Formato:** PNG @2x | PDF | SVG
- **Variantes:** 2 (Dark, Light)
  - `variant="v1_dark"` — Texto negro sobre fondo transparente/crema.
  - `variant="v2_light"` — Texto crema sobre fondo transparente/negro.
- **Atributos data-* inyectables:** `data-logo-texto`
- **Archivo plantilla:** `/templates/cloud_atlas_wordmark.html`
- **Salida:** `/output/pinakotheke-kosmos/logos/wordmark-v{N}.png`
- **Reglas de contraste:** Ratio estricto según la luminosidad del contenedor.

#### Tipo: isotipo
- **Dimensión:** 800x800 @72dpi
- **Formato:** PNG @2x | PDF | SVG
- **Variantes:** 3 (Color, Mono, Inverse)
  - `variant="v1_color"` — Lemniscata ∞ con gradiente hero 135deg.
  - `variant="v2_mono"` — Isotipo en negro sólido.
  - `variant="v3_inverse"` — Isotipo en crema sólido.
- **Atributos data-* inyectables:** `data-logo-simbolo`
- **Archivo plantilla:** `/templates/cloud_atlas_isotipo.html`
- **Salida:** `/output/pinakotheke-kosmos/logos/isotipo-v{N}.png`
- **Reglas de contraste:** Para v1, asegurar fondo oscuro o muy claro para no competir con el gradiente de saturación media.

#### Tipo: favicon
- **Dimensión:** 512x512 @72dpi
- **Formato:** PNG @2x | ICO
- **Variantes:** 3 (Tamaños base adaptados)
  - `variant="v1_32"` — Optimizado para 32x32 (símbolo simplificado).
  - `variant="v2_180"` — Optimizado para Apple Touch Icon (fondo oscuro sólido, símbolo claro).
  - `variant="v3_512"` — App icon para PWA/Android.
- **Atributos data-* inyectables:** `data-logo-simbolo`
- **Archivo plantilla:** `/templates/cloud_atlas_favicon.html`
- **Salida:** `/output/pinakotheke-kosmos/logos/favicon-v{N}.png`
- **Reglas de contraste:** Icono centrado sin texto para legibilidad extrema.

#### Tipo: watermark
- **Dimensión:** 1000x1000 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 2 (Light, Dark)
  - `variant="v1_light"` — Blanco/Crema al 15% de opacidad.
  - `variant="v2_dark"` — Negro al 10% de opacidad.
- **Atributos data-* inyectables:** `data-logo-simbolo`
- **Archivo plantilla:** `/templates/cloud_atlas_watermark.html`
- **Salida:** `/output/pinakotheke-kosmos/logos/watermark-v{N}.png`
- **Reglas de contraste:** Uso sobre fotografías o layouts densos.

### Categoría: banners

#### Tipo: linkedin_header
- **Dimensión:** 1584x396 @72dpi
- **Formato:** PNG @2x | JPEG
- **Variantes:** 3 (Institucional, Producto, Evento)
  - `variant="v1_institucional"` — Gradiente hero de fondo + isologo sutil a la derecha. Sin copy invasivo.
  - `variant="v2_producto"` — Fondo oscuro (#0b1417), título serif (Playfair) a la izquierda, orb teal abstracto.
  - `variant="v3_evento"` — Fondo crema, acentos púrpura (#8d7cc0) para llamados a la acción rápidos.
- **Atributos data-* inyectables:** `data-titulo`, `data-subtitulo`, `data-logo-simbolo`, `data-acento`
- **Archivo plantilla:** `/templates/cloud_atlas_linkedin_header.html`
- **Salida:** `/output/pinakotheke-kosmos/banners/linkedin_header-v{N}.png`
- **Reglas de contraste:** El texto en v2 usa #e8e0d4 (L<128) para ratio >7:1. Seguro para zona libre de avatar.

#### Tipo: twitter_header
- **Dimensión:** 1500x500 @72dpi
- **Formato:** PNG @2x | JPEG
- **Variantes:** 3 (Brand, Lanzamiento, Comunidad)
  - `variant="v1_brand"` — Lemniscata gigante sangrada en gris sutil sobre negro puro.
  - `variant="v2_lanzamiento"` — Teal como color dominante, título en crema.
  - `variant="v3_comunidad"` — Collage de grid asimétrico con espacios para retratos, marcos púrpura.
- **Atributos data-* inyectables:** `data-titulo`, `data-logo-simbolo`, `data-acento`
- **Archivo plantilla:** `/templates/cloud_atlas_twitter_header.html`
- **Salida:** `/output/pinakotheke-kosmos/banners/twitter_header-v{N}.png`
- **Reglas de contraste:** Textos en cuadrante superior derecho para evitar la foto de perfil en responsive.

#### Tipo: youtube_header
- **Dimensión:** 2560x1440 @72dpi
- **Formato:** PNG @2x | JPEG
- **Variantes:** 3 (Visual, Grid, Textual)
  - `variant="v1_visual"` — Composición centralizada en el área de seguridad de 1546x423. Fondo completo en gradiente.
  - `variant="v2_grid"` — Líneas de sistema y nodos conectivos (enfoque científico).
  - `variant="v3_textual"` — Tipografía hero central en Playfair Display.
- **Atributos data-* inyectables:** `data-titulo`, `data-subtitulo`, `data-logo-simbolo`, `data-acento`
- **Archivo plantilla:** `/templates/cloud_atlas_youtube_header.html`
- **Salida:** `/output/pinakotheke-kosmos/banners/youtube_header-v{N}.png`
- **Reglas de contraste:** SafeArea central estrictamente monitoreada, fondos en los extremos para TV.

#### Tipo: web_hero_desktop
- **Dimensión:** 1920x600 @72dpi
- **Formato:** PNG @2x | JPEG
- **Variantes:** 4 (Split, Central, Video_fallback, Minimal)
  - `variant="v1_split"` — 50% texto izq, 50% gráfico dcha.
  - `variant="v2_central"` — Título y subtítulo centrados sobre gradiente rico.
  - `variant="v3_video_fallback"` — Oscuro puro con viñeta para superponer UI/play button.
  - `variant="v4_minimal"` — Fondo crema, tipografía negra masiva (científica).
- **Atributos data-* inyectables:** `data-titulo`, `data-subtitulo`, `data-copy`, `data-acento`
- **Archivo plantilla:** `/templates/cloud_atlas_web_hero_desktop.html`
- **Salida:** `/output/pinakotheke-kosmos/banners/web_hero_desktop-v{N}.png`
- **Reglas de contraste:** Se aplica regla L > 128 al overlay para elegir texto claro/oscuro dinámicamente.

#### Tipo: ad_leaderboard
- **Dimensión:** 728x90 @72dpi
- **Formato:** PNG @2x | JPEG
- **Variantes:** 3 (Brand, Promo, CTA_driven)
  - `variant="v1_brand"` — Logo izq, lema central, botón dcha.
  - `variant="v2_promo"` — Acento Teal vibrante, urgencia visual.
  - `variant="v3_cta_driven"` — Texto directo, botón inverso de alto contraste.
- **Atributos data-* inyectables:** `data-titulo`, `data-url`, `data-logo-simbolo`
- **Archivo plantilla:** `/templates/cloud_atlas_ad_leaderboard.html`
- **Salida:** `/output/pinakotheke-kosmos/banners/ad_leaderboard-v{N}.png`
- **Reglas de contraste:** Botones con contraste WCAG AAA para accesibilidad de clics.

#### Tipo: ad_rectangle
- **Dimensión:** 300x250 @72dpi
- **Formato:** PNG @2x | JPEG
- **Variantes:** 3 (Visual, Data, Testimonial)
  - `variant="v1_visual"` — Lemniscata sangrada, título abajo.
  - `variant="v2_data"` — Número grande hero (stat), contexto breve.
  - `variant="v3_testimonial"` — Cita en cursiva (Playfair), autor.
- **Atributos data-* inyectables:** `data-titulo`, `data-numero`, `data-copy`, `data-logo-simbolo`
- **Archivo plantilla:** `/templates/cloud_atlas_ad_rectangle.html`
- **Salida:** `/output/pinakotheke-kosmos/banners/ad_rectangle-v{N}.png`
- **Reglas de contraste:** En data_card, número en color primario Teal, texto secundario crema/negro según L.

### Categoría: cards

#### Tipo: business_card
- **Dimensión:** 1050x600 @300dpi (equiv 3.5x2" web preview)
- **Formato:** PNG @2x | PDF
- **Variantes:** 2 (Anverso, Reverso)
  - `variant="v1_front"` — Limpio. Logo central.
  - `variant="v2_back"` — Datos de contacto izq, nombre (Playfair) y cargo (Inter) en la dcha.
- **Atributos data-* inyectables:** `data-autor`, `data-cargo`, `data-copy`, `data-logo-simbolo`
- **Archivo plantilla:** `/templates/cloud_atlas_business_card.html`
- **Salida:** `/output/pinakotheke-kosmos/cards/business_card-v{N}.png`
- **Reglas de contraste:** Texto en negro #0b1417 o #8d7cc0 (púrpura oscuro) para legibilidad tipográfica print.

#### Tipo: stat_card
- **Dimensión:** 1080x1080 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 3 (Hero_num, Dual_stat, Graph_abstract)
  - `variant="v1_hero_num"` — Número masivo, gradiente en texto.
  - `variant="v2_dual_stat"` — Dos métricas divididas por línea de acento Teal.
  - `variant="v3_graph_abstract"` — Gráfico de fondo, número en cuadrante superior.
- **Atributos data-* inyectables:** `data-numero`, `data-etiqueta`, `data-copy`, `data-acento`
- **Archivo plantilla:** `/templates/cloud_atlas_stat_card.html`
- **Salida:** `/output/pinakotheke-kosmos/cards/stat_card-v{N}.png`
- **Reglas de contraste:** El gradiente hero se usa como color de relleno de texto numérico SOLO si el fondo es negro (#0b1417) para garantizar >=4.5:1.

### Categoría: social

#### Tipo: instagram_post
- **Dimensión:** 1080x1080 @72dpi
- **Formato:** PNG @2x | JPEG
- **Variantes:** 8 (Sistematizadas)
  - `variant="v1_tesis"` — Título en bloque sólido (Playfair), acento inferior.
  - `variant="v2_diferenciador"` — Split diagonal, texto vs isologo.
  - `variant="v3_dato"` — Módulo numérico protagonista.
  - `variant="v4_cita"` — Layout de quote con marcas de cita gigantes.
  - `variant="v5_cta"` — Invitación de acción con botón simulado masivo.
  - `variant="v6_case_study"` — Marco para imagen/UI de fondo, superposición de texto oscura con viñeta.
  - `variant="v7_testimonial"` — Foto de perfil circular, nombre y cargo + quote.
  - `variant="v8_promocion"` — Borde perimetral en Teal, énfasis en palabras clave.
- **Atributos data-* inyectables:** `data-titulo`, `data-copy`, `data-logo-simbolo`, `data-numero`, `data-autor`, `data-cargo`
- **Archivo plantilla:** `/templates/cloud_atlas_instagram_post.html`
- **Salida:** `/output/pinakotheke-kosmos/social/instagram_post-v{N}.png`
- **Reglas de contraste:** `data-fit-min` ajustado por variante para evitar texto ilegible. L evalúa si el fondo general usa DarkMode (usa #e8e0d4) o LightMode (usa #0b1417).

#### Tipo: linkedin_post
- **Dimensión:** 1200x627 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 6 (Tesis, Framework, Insight, Noticia, Equipo, Informe)
  - `variant="v1_tesis"` — Orientado a texto, jerarquía corporativa alta.
  - `variant="v2_framework"` — Diagrama conectivo de fondo.
  - `variant="v3_insight"` — Revelación o stat, layout centrado.
  - `variant="v4_noticia"` — Tag/etiqueta arriba, titular grande.
  - `variant="v5_equipo"` — Retrato/autor destacado, estilo entrevista.
  - `variant="v6_informe"` — Estilo portada de reporte PDF.
- **Atributos data-* inyectables:** `data-titulo`, `data-subtitulo`, `data-copy`, `data-acento`
- **Archivo plantilla:** `/templates/cloud_atlas_linkedin_post.html`
- **Salida:** `/output/pinakotheke-kosmos/social/linkedin_post-v{N}.png`
- **Reglas de contraste:** Texto siempre WCAG AA contra fondo crema o negro. Elementos gráficos secundarios (nodos) en #8d7cc0.

### Categoría: stories

#### Tipo: instagram_story
- **Dimensión:** 1080x1920 @72dpi
- **Formato:** PNG @2x | MP4-ready (Base)
- **Variantes:** 5 (Cover, Text_block, Poll_ready, QnA, Swipe_up)
  - `variant="v1_cover"` — Título fuerte, isotipo superior.
  - `variant="v2_text_block"` — Párrafo extenso, márgenes interiores anchos (safe area vertical).
  - `variant="v3_poll_ready"` — Espacio negativo inferior para sticker nativo de IG.
  - `variant="v4_qna"` — Estilo pregunta/respuesta.
  - `variant="v5_swipe_up"` — Flechas direccionales o CTA inferior.
- **Atributos data-* inyectables:** `data-titulo`, `data-copy`, `data-logo-simbolo`, `data-acento`
- **Archivo plantilla:** `/templates/cloud_atlas_instagram_story.html`
- **Salida:** `/output/pinakotheke-kosmos/stories/instagram_story-v{N}.png`
- **Reglas de contraste:** Respetar safe zones de UI nativa de Instagram (10% arriba, 20% abajo).

### Categoría: carousels

#### Tipo: instagram_carousel
- **Dimensión:** 1080x1080 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 5 (Portada, Paso_a_Paso, Continuo, Destacado, Cierre)
  - `variant="v1_portada"` — Enganche inicial masivo, flecha de swipe dcha.
  - `variant="v2_paso"` — Título superior, número de paso gigante desvanecido.
  - `variant="v3_continuo"` — Elemento gráfico (lemniscata) cortado a la mitad para conectar con slide anterior/siguiente.
  - `variant="v4_destacado"` — Inversión de color (Dark Mode abrupto) para romper monotonía.
  - `variant="v5_cierre"` — CTA centralizado, logos apilados, invitación a guardar.
- **Atributos data-* inyectables:** `data-titulo`, `data-copy`, `data-numero`, `data-logo-simbolo`
- **Archivo plantilla:** `/templates/cloud_atlas_instagram_carousel.html`
- **Salida:** `/output/pinakotheke-kosmos/carousels/instagram_carousel-v{N}.png`
- **Reglas de contraste:** Cálculo estricto de fondo en v4 para invertir toda la jerarquía tipográfica.

### Categoría: og

#### Tipo: og_general
- **Dimensión:** 1200x630 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 3 (Website, Artículo, Feature)
  - `variant="v1_website"` — Logo central y gradiente.
  - `variant="v2_articulo"` — Titular gigante alineado izq, isotipo inferior dcha.
  - `variant="v3_feature"` — Mockup o forma abstracta a la dcha, texto corto izq.
- **Atributos data-* inyectables:** `data-titulo`, `data-subtitulo`, `data-logo-simbolo`
- **Archivo plantilla:** `/templates/cloud_atlas_og_general.html`
- **Salida:** `/output/pinakotheke-kosmos/og/og_general-v{N}.png`
- **Reglas de contraste:** Tipografía pesada (Inter o Playfair Bold) asegurando lectura rápida en previews de Twitter/Slack.

### Categoría: stationery

#### Tipo: letterhead
- **Dimensión:** 2480x3508 @300dpi (A4)
- **Formato:** PDF | PNG @2x
- **Variantes:** 2 (Oficial, Interno)
  - `variant="v1_oficial"` — Membrete superior clásico, detalles legales pie de página, marca de agua sutil.
  - `variant="v2_interno"` — Minimalista, acento Teal en lateral izquierdo.
- **Atributos data-* inyectables:** `data-titulo`, `data-copy`, `data-logo-simbolo`
- **Archivo plantilla:** `/templates/cloud_atlas_letterhead.html`
- **Salida:** `/output/pinakotheke-kosmos/stationery/letterhead-v{N}.png`
- **Reglas de contraste:** Siempre fondo blanco/crema puro para legibilidad PDF/impresión. Texto oscuro #0b1417.

---

## PRIZMA ENTERPRISE

### Categoría: logos

#### Tipo: lockup_horizontal
- **Dimensión:** 1200x400 @72dpi
- **Formato:** PNG @2x | PDF | SVG
- **Variantes:** 3 (Color, Mono, Inverse)
  - `variant="v1_color"` — Rayo ⚡ con gradiente hero (Ámbar/Naranja/Rojo) y texto oscuro sobre crema (#f0ece6).
  - `variant="v2_mono"` — Rayo y texto en negro puro (#0c0e10) sobre crema.
  - `variant="v3_inverse"` — Rayo y texto en crema (#f0ece6) sobre negro puro (#0c0e10).
- **Atributos data-* inyectables:** `data-logo-simbolo`, `data-logo-texto`
- **Archivo plantilla:** `/templates/prizma_lockup_horizontal.html`
- **Salida:** `/output/prizma-hermes/logos/lockup_horizontal-v{N}.png`
- **Reglas de contraste:** Cálculo dinámico; si L>128 usar #0c0e10, si L<=128 usar #f0ece6. Ratio >4.5:1.

#### Tipo: lockup_vertical
- **Dimensión:** 800x800 @72dpi
- **Formato:** PNG @2x | PDF | SVG
- **Variantes:** 3 (Color, Mono, Inverse)
  - `variant="v1_color"` — Rayo superior masivo, wordmark inferior en Inter Bold.
  - `variant="v2_mono"` — Versión 1-tinta corporativa.
  - `variant="v3_inverse"` — Blanco sobre negro, alto contraste.
- **Atributos data-* inyectables:** `data-logo-simbolo`, `data-logo-texto`
- **Archivo plantilla:** `/templates/prizma_lockup_vertical.html`
- **Salida:** `/output/prizma-hermes/logos/lockup_vertical-v{N}.png`
- **Reglas de contraste:** Luminancia autoevaluada.

#### Tipo: wordmark
- **Dimensión:** 1000x300 @72dpi
- **Formato:** PNG @2x | PDF
- **Variantes:** 2 (Dark, Light)
  - `variant="v1_dark"` — Tipografía Inter Bold (#0c0e10).
  - `variant="v2_light"` — Tipografía Inter Bold (#f0ece6).
- **Atributos data-* inyectables:** `data-logo-texto`
- **Archivo plantilla:** `/templates/prizma_wordmark.html`
- **Salida:** `/output/prizma-hermes/logos/wordmark-v{N}.png`
- **Reglas de contraste:** Tipografía de pesos bold asegura un mejor performance en test WCAG de tamaño de fuente.

#### Tipo: isotipo
- **Dimensión:** 800x800 @72dpi
- **Formato:** PNG @2x | SVG
- **Variantes:** 3 (Color, Mono, Inverse)
  - `variant="v1_color"` — Rayo ⚡ con gradiente de fuego corporativo (135deg, Ámbar a Rojo oscuro).
  - `variant="v2_mono"` — Rayo oscuro puro.
  - `variant="v3_inverse"` — Rayo claro puro.
- **Atributos data-* inyectables:** `data-logo-simbolo`
- **Archivo plantilla:** `/templates/prizma_isotipo.html`
- **Salida:** `/output/prizma-hermes/logos/isotipo-v{N}.png`
- **Reglas de contraste:** El gradiente no se usa sobre gris medio; siempre fondos polares.

#### Tipo: favicon
- **Dimensión:** 512x512 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 3 (32px, 180px, 512px)
  - `variant="v1_32"` — Rayo vectorial crudo (máxima legibilidad).
  - `variant="v2_180"` — Fondo negro, rayo gradiente.
  - `variant="v3_512"` — Full app icon corporativo.
- **Atributos data-* inyectables:** `data-logo-simbolo`
- **Archivo plantilla:** `/templates/prizma_favicon.html`
- **Salida:** `/output/prizma-hermes/logos/favicon-v{N}.png`
- **Reglas de contraste:** Silueta exterior afilada.

#### Tipo: watermark
- **Dimensión:** 1000x1000 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 2 (Light, Dark)
  - `variant="v1_light"` — Crema 15% opacidad.
  - `variant="v2_dark"` — Negro 10% opacidad.
- **Atributos data-* inyectables:** `data-logo-simbolo`
- **Archivo plantilla:** `/templates/prizma_watermark.html`
- **Salida:** `/output/prizma-hermes/logos/watermark-v{N}.png`
- **Reglas de contraste:** Evitar interferencia con datos tabulares subyacentes.

### Categoría: banners

#### Tipo: linkedin_header
- **Dimensión:** 1584x396 @72dpi
- **Formato:** PNG @2x | JPEG
- **Variantes:** 3 (Corporate, Speed, Connectivity)
  - `variant="v1_corporate"` — Minimalista, negro dominante, acento ámbar/naranja (#f0b94a).
  - `variant="v2_speed"` — Líneas de movimiento horizontales, título ágil.
  - `variant="v3_connectivity"` — Red nodal corporativa con isotipo.
- **Atributos data-* inyectables:** `data-titulo`, `data-subtitulo`, `data-logo-simbolo`, `data-acento`
- **Archivo plantilla:** `/templates/prizma_linkedin_header.html`
- **Salida:** `/output/prizma-hermes/banners/linkedin_header-v{N}.png`
- **Reglas de contraste:** Naranja #d4622e no cruza textos pequeños sobre fondos claros.

#### Tipo: twitter_header
- **Dimensión:** 1500x500 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 3 (Launch, Brand, Event)
  - `variant="v1_launch"` — Tipografía sans gigante, estilo ticker.
  - `variant="v2_brand"` — Rayo dinámico centrado.
  - `variant="v3_event"` — Bloques modulares para info de evento y fechas.
- **Atributos data-* inyectables:** `data-titulo`, `data-subtitulo`, `data-logo-simbolo`, `data-acento`
- **Archivo plantilla:** `/templates/prizma_twitter_header.html`
- **Salida:** `/output/prizma-hermes/banners/twitter_header-v{N}.png`
- **Reglas de contraste:** Fondo oscuro dominante.

#### Tipo: youtube_header
- **Dimensión:** 2560x1440 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 3 (Enterprise, Series, Abstract)
  - `variant="v1_enterprise"` — Layout central de seguridad corporativa.
  - `variant="v2_series"` — Etiqueta de serie web a la izquierda.
  - `variant="v3_abstract"` — Ondas de velocidad, puramente visual.
- **Atributos data-* inyectables:** `data-titulo`, `data-subtitulo`, `data-logo-simbolo`, `data-acento`
- **Archivo plantilla:** `/templates/prizma_youtube_header.html`
- **Salida:** `/output/prizma-hermes/banners/youtube_header-v{N}.png`
- **Reglas de contraste:** Safe areas 1546x423 rigurosamente validadas.

#### Tipo: web_hero_desktop
- **Dimensión:** 1920x600 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 4 (Split, Central, Tech, Minimal)
  - `variant="v1_split"` — Grid estricto 50/50, estilo dashboard.
  - `variant="v2_central"` — Mensaje heroico centrado.
  - `variant="v3_tech"` — Detalles terminal/código de fondo sutil.
  - `variant="v4_minimal"` — Inter Bold aplastante, fondo claro.
- **Atributos data-* inyectables:** `data-titulo`, `data-subtitulo`, `data-copy`, `data-acento`
- **Archivo plantilla:** `/templates/prizma_web_hero_desktop.html`
- **Salida:** `/output/prizma-hermes/banners/web_hero_desktop-v{N}.png`
- **Reglas de contraste:** Automático L > 128 (Dark/Light text toggle).

#### Tipo: ad_leaderboard
- **Dimensión:** 728x90 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 3 (B2B, Action, Velocity)
  - `variant="v1_b2b"` — Corporativo estricto, logo izq.
  - `variant="v2_action"` — Botón "Learn More" en Ámbar.
  - `variant="v3_velocity"` — Efectos de motion blur en fondo, texto fijo.
- **Atributos data-* inyectables:** `data-titulo`, `data-url`, `data-logo-simbolo`
- **Archivo plantilla:** `/templates/prizma_ad_leaderboard.html`
- **Salida:** `/output/prizma-hermes/banners/ad_leaderboard-v{N}.png`
- **Reglas de contraste:** Altamente contrastante.

#### Tipo: ad_rectangle
- **Dimensión:** 300x250 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 3 (Stat, CTA, Grid)
  - `variant="v1_stat"` — Gran número (Velocidad/Milisegundos).
  - `variant="v2_cta"` — Propuesta de valor directa + botón.
  - `variant="v3_grid"` — Cajas delimitadoras tipo UI corporativa.
- **Atributos data-* inyectables:** `data-titulo`, `data-numero`, `data-copy`, `data-logo-simbolo`
- **Archivo plantilla:** `/templates/prizma_ad_rectangle.html`
- **Salida:** `/output/prizma-hermes/banners/ad_rectangle-v{N}.png`
- **Reglas de contraste:** Textos en Inter Bold para maximizar área de color.

### Categoría: cards

#### Tipo: business_card
- **Dimensión:** 1050x600 @300dpi
- **Formato:** PNG @2x | PDF
- **Variantes:** 2 (Front, Back)
  - `variant="v1_front"` — Oscura (#0c0e10), isologo Ámbar/Naranja centrado.
  - `variant="v2_back"` — Clara (#f0ece6), tipografía estricta alineada a grid.
- **Atributos data-* inyectables:** `data-autor`, `data-cargo`, `data-copy`, `data-logo-simbolo`
- **Archivo plantilla:** `/templates/prizma_business_card.html`
- **Salida:** `/output/prizma-hermes/cards/business_card-v{N}.png`
- **Reglas de contraste:** Inversión total de colores base entre anverso y reverso.

#### Tipo: stat_card
- **Dimensión:** 1080x1080 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 3 (Big_Data, Comparativa, Uptime)
  - `variant="v1_big_data"` — Número masivo Inter Black.
  - `variant="v2_comparativa"` — Dos columnas (Nosotros vs Ellos).
  - `variant="v3_uptime"` — Diseño tipo SLA, 99.999%.
- **Atributos data-* inyectables:** `data-numero`, `data-etiqueta`, `data-copy`, `data-acento`
- **Archivo plantilla:** `/templates/prizma_stat_card.html`
- **Salida:** `/output/prizma-hermes/cards/stat_card-v{N}.png`
- **Reglas de contraste:** Gradientes solo para acentos o textos hero si el fondo es #0c0e10.

### Categoría: social

#### Tipo: instagram_post
- **Dimensión:** 1080x1080 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 8 (Sistematizadas Prizma)
  - `variant="v1_tesis"` — Declaración fuerte, tipografía gruesa.
  - `variant="v2_diferenciador"` — Lista de checks / viñetas veloces.
  - `variant="v3_dato"` — KPI corporativo destacado.
  - `variant="v4_cita"` — Frase de CEO/CTO corporativa.
  - `variant="v5_cta"` — Pantalla de cierre "Contact Sales".
  - `variant="v6_case_study"` — Marco rígido, estilo terminal UI.
  - `variant="v7_testimonial"` — Review B2B estilo G2/Capterra.
  - `variant="v8_promocion"` — Alerta de webinar / whitepaper.
- **Atributos data-* inyectables:** `data-titulo`, `data-copy`, `data-logo-simbolo`, `data-numero`, `data-autor`, `data-cargo`
- **Archivo plantilla:** `/templates/prizma_instagram_post.html`
- **Salida:** `/output/prizma-hermes/social/instagram_post-v{N}.png`
- **Reglas de contraste:** Evitar pesos tipográficos finos para asegurar legibilidad B2B rápida.

#### Tipo: linkedin_post
- **Dimensión:** 1200x627 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 6 (Tech, Release, B2B, Webinar, Growth, Report)
  - `variant="v1_tech"` — Orientado a arquitectura/ingeniería.
  - `variant="v2_release"` — Notas de versión, diseño estilo changelog.
  - `variant="v3_b2b"` — Ventaja competitiva empresarial.
  - `variant="v4_webinar"` — Panel de speakers, fecha en ámbar.
  - `variant="v5_growth"` — Gráfico ascendente abstracto.
  - `variant="v6_report"` — Portada de Whitepaper o Estado de la Industria.
- **Atributos data-* inyectables:** `data-titulo`, `data-subtitulo`, `data-copy`, `data-acento`
- **Archivo plantilla:** `/templates/prizma_linkedin_post.html`
- **Salida:** `/output/prizma-hermes/social/linkedin_post-v{N}.png`
- **Reglas de contraste:** Respetar jerarquía tipográfica H1 vs body, contraste AAA en CTAs.

### Categoría: stories

#### Tipo: instagram_story
- **Dimensión:** 1080x1920 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 5 (Headline, Bullet_points, Stat_flash, Event, CTA_up)
  - `variant="v1_headline"` — Titular explosivo corporativo.
  - `variant="v2_bullet_points"` — Lista de 3 beneficios (SaaS style).
  - `variant="v3_stat_flash"` — Número de impacto visual.
  - `variant="v4_event"` — Cuenta regresiva / Recordatorio visual.
  - `variant="v5_cta_up"` — Diseño enfocado en el link/sticker inferior.
- **Atributos data-* inyectables:** `data-titulo`, `data-copy`, `data-logo-simbolo`, `data-acento`
- **Archivo plantilla:** `/templates/prizma_instagram_story.html`
- **Salida:** `/output/prizma-hermes/stories/instagram_story-v{N}.png`
- **Reglas de contraste:** Textos masivos y rápidos de leer, L-check dinámico.

### Categoría: carousels

#### Tipo: instagram_carousel
- **Dimensión:** 1080x1080 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 5 (Hook, Problema, Solucion, Features, LeadGen)
  - `variant="v1_hook"` — Pregunta de negocio dura.
  - `variant="v2_problema"` — Fondo oscuro, dolor del cliente.
  - `variant="v3_solucion"` — Fondo claro (#f0ece6), alivio veloz.
  - `variant="v4_features"` — Grid de características (iconos/texto).
  - `variant="v5_leadgen"` — Botón de agendar demo, logos de clientes.
- **Atributos data-* inyectables:** `data-titulo`, `data-copy`, `data-numero`, `data-logo-simbolo`
- **Archivo plantilla:** `/templates/prizma_instagram_carousel.html`
- **Salida:** `/output/prizma-hermes/carousels/instagram_carousel-v{N}.png`
- **Reglas de contraste:** Consistencia de borde a borde para swipe fluido.

### Categoría: og

#### Tipo: og_general
- **Dimensión:** 1200x630 @72dpi
- **Formato:** PNG @2x
- **Variantes:** 3 (Docs, Enterprise_Blog, Tool)
  - `variant="v1_docs"` — Título estilo documentación API.
  - `variant="v2_enterprise_blog"` — Estilo artículo B2B pesado.
  - `variant="v3_tool"` — Mockup o captura abstracta de herramienta SaaS.
- **Atributos data-* inyectables:** `data-titulo`, `data-subtitulo`, `data-logo-simbolo`
- **Archivo plantilla:** `/templates/prizma_og_general.html`
- **Salida:** `/output/prizma-hermes/og/og_general-v{N}.png`
- **Reglas de contraste:** Tipografía Inter Bold maximizada.

### Categoría: stationery

#### Tipo: letterhead
- **Dimensión:** 2480x3508 @300dpi
- **Formato:** PDF | PNG @2x
- **Variantes:** 2 (Corporate, Invoice)
  - `variant="v1_corporate"` — Formal, grid de 12 columnas.
  - `variant="v2_invoice"` — Tabular, enfocado en datos de facturación y contrato.
- **Atributos data-* inyectables:** `data-titulo`, `data-copy`, `data-logo-simbolo`
- **Archivo plantilla:** `/templates/prizma_letterhead.html`
- **Salida:** `/output/prizma-hermes/stationery/letterhead-v{N}.png`
- **Reglas de contraste:** Alta definición para impresión láser monocromática (B/W safe).

---

## 3. CONTRATO DE PLANTILLA

Para garantizar que el motor Eikon pueda inyectar datos de forma universal en las dos marcas, TODA plantilla HTML debe adherirse a esta estructura estricta:

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  :root {
    /* Variables inyectadas por Playwright (CSS nativo) */
    --primario: #000;
    --acento-2: #000;
    --texto: #000;
    --bg: #000;
    --gradient-hero: linear-gradient(135deg, var(--primario), var(--acento-2));
  }
  
  body {
    margin: 0; padding: 0; box-sizing: border-box;
    background-color: var(--bg);
    color: var(--texto);
    font-family: 'Inter', sans-serif; /* Override por línea si aplica */
  }

  /* SISTEMA DE VARIANTES */
  
  /* Ejemplo variante 1 */
  [data-variant="v1_tesis"] {
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 10%;
  }
  
  /* Ejemplo variante 2 */
  [data-variant="v2_dato"] {
    display: grid;
    grid-template-columns: 1fr 1fr;
    background-color: var(--primario);
    /* Lógica CSS calc o pre-inject para color de texto WCAG */
  }
</style>
</head>

<!-- El motor asigna la variante desde ?variant=X en la URL -->
<body data-variant="v1_tesis">

  <!-- Atributos data-* obligatorios inyectables -->
  <h1 data-titulo data-fit data-fit-min="32"></h1>
  <h3 data-subtitulo></h3>
  <p data-copy></p>

  <div class="metrics">
    <span data-numero></span>
    <span data-etiqueta></span>
  </div>

  <div class="author-block">
    <span data-autor></span>
    <span data-cargo></span>
  </div>

  <!-- Span vacío con background/mask CSS o tag SVG embebido -->
  <span data-logo-simbolo></span>
  <span data-logo-texto></span>

  <!-- URL visible para ads/cards -->
  <a href="#" data-url></a>

  <!-- Divs ornamentales para acentos de color -->
  <div data-acento style="background: var(--primario);"></div>
  <div data-acento-2 style="background: var(--acento-2);"></div>

</body>
</html>
```

### Reglas de Contraste Automático (WCAG AA >= 4.5:1)
El motor de generación inyectará las variables `--texto` y `--bg` calculando la luminancia `L = 0.299*R + 0.587*G + 0.114*B` del color base principal.
- **Si L > 128 (Fondo Claro):** `--texto` forzará a `#0b1417` (Cloud) o `#0c0e10` (Prizma).
- **Si L <= 128 (Fondo Oscuro):** `--texto` forzará a `#e8e0d4` (Cloud) o `#f0ece6` (Prizma).
- **Prohibiciones:** No usar colores acento (`--acento-2`) como texto de cuerpo regular sobre fondos negros o blancos sin verificar manualmente; limitar acentos visuales a `<div data-acento>` o headers gigantes de `> 24px` (peso bold).

### Mecanismo de Archivos
- **Entrada:** `/workspace/Pinakotheke/eikon/templates/{slug}_{tipo}.html` (ej: `cloud_atlas_instagram_post.html`)
- **Salida:** `/workspace/Pinakotheke/eikon/output/{slug}/{categoria}/{tipo}-v{N}.png`

---

## 4. RESUMEN DE CONTEOS

| Línea | Categoría | Tipos | Variantes/tipo (Promedio) | Total Assets Base |
|-------|-----------|-------|---------------------------|-------------------|
| Cloud Atlas | logos | 6 | ~3 | 17 |
| Cloud Atlas | banners | 6 | ~3.3 | 20 |
| Cloud Atlas | cards | 2 | ~2.5 | 5 |
| Cloud Atlas | social | 2 | ~7 | 14 |
| Cloud Atlas | stories | 1 | 5 | 5 |
| Cloud Atlas | carousels | 1 | 5 | 5 |
| Cloud Atlas | og | 1 | 3 | 3 |
| Cloud Atlas | stationery | 1 | 2 | 2 |
| **Cloud Atlas Total** | | **20** | | **~71 layouts** |
| Prizma | logos | 6 | ~3 | 17 |
| Prizma | banners | 6 | ~3.3 | 20 |
| Prizma | cards | 2 | ~2.5 | 5 |
| Prizma | social | 2 | ~7 | 14 |
| Prizma | stories | 1 | 5 | 5 |
| Prizma | carousels | 1 | 5 | 5 |
| Prizma | og | 1 | 3 | 3 |
| Prizma | stationery | 1 | 2 | 2 |
| **Prizma Total** | | **20** | | **~71 layouts** |

**TOTAL SISTEMA EIKON:** ~142 composiciones matrices (Variantes únicas prontas para inyección masiva infinita de contenido JSON).
