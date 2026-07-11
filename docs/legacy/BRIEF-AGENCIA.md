# BRIEF DE DISEÑO — Regeneración de Identidad Visual
## Steven Vallejo · Sistemas Cloud Atlas (Pinakothḗke) y Prizma Enterprise
**Documento vivo:** 2026-06-19  
**Motor de render:** Eikon (HTML/CSS + Playwright)  
**Estatus:** Definición de specs antes de ejecutar plantillas

---

> ## Sobre el alcance de este brief
>
> Este brief define el **subconjunto editorial** que Eikón necesita
> para producir los assets CORE de las marcas Cloud Atlas (Pinakothḗke)
> y Prizma Enterprise. Específicamente: lockup, wordmark, isotipo,
> business card, banners, OG y stationery.
>
> La **fuente narrativa amplia** de Cloud Atlas (los 14 productos
> griegos, los 3 frentes, el ethos de catálogo) **vive en `/workspace/Yo/`**
> y no se reproduce acá. Eikón consume el brief vía `marcas/<slug>.json`;
> la taxonomía técnica de assets está en `MASTER-TAXONOMIA.md`.
>
> Si necesitás el marco narrativo completo de Cloud Atlas: ver
> `/workspace/Yo/docs/`. Si necesitás la taxonomía de assets: ver
> `MASTER-TAXONOMIA.md` en este mismo repo.

---

## 1. Contexto Estratégico

### 1.1 Dos líneas de marca

Steven Vallejo opera bajo dos identidades de marca distintas, cada una con propósito y público diferenciado:

| Línea | Nombre | Público | Propuesta |
|-------|--------|---------|-----------|
| **A: Personal/OSS** | Cloud Atlas · Pinakothḗke | Académico, investigador, comunidad tech | Catálogos educativos de 3 frentes (Filosofía, Ciencias, Ingeniería). Marca de autor-productor. |
| **B: Corporativo** | Prizma Enterprise | Corporaciones, PyME, equipos. | Suite de productos para operación (Hermes, Pistis, Iris, Nous, Talanton, etc.). Marca de proveedor de soluciones. |

Ambas líneas **NO comparten identidad visual.** Cada una tiene su paleta, isotipo, tipografía y lenguaje de marca. El brief define ambas simultáneamente.

### 1.2 Propósito de este documento

Especificar la **arquitectura visual** (no mockups ni assets finales) para 9 assets CORE de cada línea:
- **Logo Lockup Color** — marca completa con símbolo + texto + subtítulo.
- **Logo Wordmark** — texto puro, sin símbolo.
- **Logo Symbol/Color** — isotipo aislado, uso para favicón/app icon.
- **Business Card** — 3.5" × 2" @150dpi, anverso (identidad corporativa).
- **LinkedIn Banner** — 1584×396, identidad en red profesional.
- **LinkedIn Post** — 1200×627, card de noticia/lanzamiento en feed.
- **Instagram Post** — 1080×1080, pieza visual de catálogo.
- **Instagram Story** — 1080×1920, anuncio temporal/call to action.
- **OG Product** — 1200×630, previa de link (OpenGraph).

**Para cada asset:** layout, jerarquía visual, uso de símbolo/isotipo, tipografía, color/gradiente, y regla dura de que **nunca lleve labels internos** ("CARDS 01/10", "+LINKEDIN", "PRICING") ni se parezca a mockup de UI.

---

## 2. LÍNEA A: CLOUD ATLAS (Pinakothḗke + Personal)

### 2.1 Identidad de Marca

| Componente | Valor |
|------------|-------|
| **Wordmark** | Pinakothḗke (Π en mayúscula de Playfair Display negra) |
| **Isotipo** | Lemniscata ∞ en gradiente teal → púrpura (símbolo de continuidad/eternidad científica) |
| **Colores primarios** | Teal #43b5a6 (primario), púrpura #8d7cc0 (acento 2), crema #e8e0d4 (texto) |
| **Color de fondo** | Negro profundo #0b1417 |
| **Tipografía títulos** | Playfair Display (serif, elegante, científico-filosófico) |
| **Tipografía cuerpo** | Inter (sans, limpio, accesible, universal) |
| **Tono** | Científico, sistémico, visual. Rigurosidad + belleza. |

### 2.2 Componentes Visuales por Asset

#### **2.2.1 Logo Lockup Color** (1200×400 @2x)

**Layout:**
- Disposición horizontal izq-der.
- Izq: isotipo (lemniscata ∞) a 172px, gradiente teal→púrpura, 0.85 opacidad.
- Centro: divisor línea fina blanca (h=160px).
- Derecha: bloque de texto (max 680px).
  - Línea 1: wordmark "Pinakothḗke" (70px, Playfair Display 900, gradiente).
  - Línea 2: subtítulo tagline (18px, Inter, color `--texto-muted`).

**Jerarquía:**
- Símbolo domina visualmente; wordmark es entrada de ojos.
- Tagline proporciona contexto sin competir.

**Fondo:**
- Gradiente radial `radial-gradient(ellipse at 30% 40%, #131e22 0%, #0b1417 70%)`.
- Orbs borrosos (blur 100px) en teal/púrpura, opacity 0.15.
- Ruido fractal muy sutil (opacity 0.05).

**Color / Gradiente:**
- Símbolo + wordmark: `linear-gradient(135deg, #43b5a6 0%, #8d7cc0 60%, #4a3a80 100%)` (gradiente definido en JSON como `gradiente_hero`).

**Contenido:**
- Sin labels tipo "LOGO 01"; sin versión "light" embebida; sin mockup de UI.
- Solo marca: símbolo + wordmark + tagline.

---

#### **2.2.2 Logo Wordmark** (1200×300 @2x)

**Layout:**
- Disposición centrada, vertical o ligeramente izquierda.
- Solo texto: "Pinakothḗke" (Playfair Display 900, 70–90px según contexto).

**Tipografía & Color:**
- Playfair Display negra, boldest (900).
- Gradiente teal→púrpura idéntico al lockup.
- Sin símbolo.

**Fondo:**
- Fondo transparente o fondo mínimo (1–2 orbs muy sutiles).
- Prioridad: legibilidad pura.

**Variantes:**
- **Monocromo claro:** wordmark blanco sobre fondo oscuro.
- **Monocromo oscuro:** wordmark negro sobre fondo claro (raro; para contextos editorial).

---

#### **2.2.3 Logo Symbol/Color** (512×512 @2x)

**Layout:**
- Isotipo lemniscata ∞ aislado, centrado, sin texto.
- Padding equilibrado (margen = 15% del tamaño total).

**Tipografía & Color:**
- Símbolo Playfair Display 900, 172px en 512×512 @2x.
- Gradiente teal→púrpura idéntico.

**Fondo:**
- Fondo transparente (alfa = 0).
- Aplicable a favicón 32×32, app icon 192×192, redes sociales.

**Sin sombra ni efecto 3D.**

---

#### **2.2.4 Business Card** (1050×600 @2x, 3.5"×2" @150dpi)

**Layout:**
- Vertical lado izq: isotipo (160px) + texto corporativo pequeño ("Pinakothḗke" 15px uppercase).
- Divisor línea fina blanca (h=160px).
- Lado derecho: bloque de contacto.
  - Nombre/Producto (58px, Playfair Display 900, gradiente).
  - Línea accent (36px × 2px, gradiente).
  - Cargo/descripción (18px, Inter, color muted).
  - Contacto: URL en teal, línea de texto gris (16–18px).

**Fondo:**
- Gradiente radial `radial-gradient(ellipse at 20% 50%, #152028 0%, #0b1417 60%)`.
- Orbs sutiles (opacity 0.13–0.16).
- Ruido (opacity 0.07).
- Marcas de corte en esquinas (24×24px, líneas teal 50% opacity).

**Color & Tipografía:**
- Gradiente hero en nombre y accent line.
- Sans (Inter) para contacto; serif (Playfair) para títulos.
- Teal (#43b5a6) para URLs.

**Contenido (data-driven):**
- `data-logo-simbolo`: lemniscata ∞.
- `data-logo-texto`: "Pinakothḗke".
- `data-titulo`: nombre del frente (ej: "Kósmos", "Agón", "Clavis").
- `data-subtitulo`: cargo/rol.
- `data-url`: URL del sitio (ej: kosmos.stevenvallejo.com).
- `data-copy`: línea de descripción breve.

**Sin labels internos** ("BUSINESS CARD 01/10", "PRINT VERSION", etc.).

---

#### **2.2.5 LinkedIn Banner** (1584×396)

**Layout:**
- Horizontal, 4:1 aspect ratio.
- Izq (40%): bloque logo.
  - Símbolo (72px).
  - Texto corporativo (15px uppercase, muted).
- Centro (1px divisor sutil).
- Derecha (50%): bloque de contenido.
  - Accent line (48×3px, gradiente).
  - Título (56px, Playfair, gradiente).
  - Copy (22px, Inter, negrita light, opacity 0.9).
  - URL (15px, muted, small).

**Fondo:**
- Gradiente radial `radial-gradient(ellipse at 15% 50%, #152028 0%, #0b1417 55%)`.
- Orbs en teal/púrpura (opacity 0.14).
- Ruido (opacity 0.05).
- Banda derecha con gradient overlay (270deg, teal 4% → transparent).
- Línea inferior accent (3px, gradiente, opacity 0.5).

**Decoración:**
- SVG mínimo derecha (circles + path, opacity 0.06): solo geometría científica, no pictórico.

**Color & Tipografía:**
- Gradiente hero en título y accent line.
- Inter para copy; Playfair para título.
- Teal + crema en paleta de contraste.

**Contenido (data-driven):**
- `data-titulo`: título de anuncio.
- `data-copy`: descripción breve (máx 2–3 líneas).
- `data-url`: link (ej: kosmos.stevenvallejo.com).
- `data-logo-simbolo` + `data-logo-texto`.

**Sin labels internos** ("LINKEDIN BANNER", "+ANALYTICS", etc.).

---

#### **2.2.6 LinkedIn Post** (1200×627)

**Layout:**
- Vertical centrado, aspect ratio 1.9:1.
- 60% superior: zona visual (gradiente + isotipo grande como fondo, semi-trasparente).
- 40% inferior: bloque de contenido en surface oscuro.

**Zona visual:**
- Gradiente de fondo (hero).
- Isotipo lemniscata (400px, opacity 0.08) centrado, blurred ligeramente.
- Accent line (48px × 3px) centrado.

**Zona de contenido:**
- Fondo #131e22.
- Título (44px, Playfair, gradiente).
- Subtítulo (18px, Inter, muted).
- Copy (16px, Inter normal, crema).

**Color & Tipografía:**
- Gradiente hero en título.
- Paleta teal + crema + muted.
- Ruido (opacity 0.06).

**Contenido (data-driven):**
- `data-titulo`, `data-subtitulo`, `data-copy`.
- Sin logo replicado (solo isotipo de fondo).

---

#### **2.2.7 Instagram Post** (1080×1080)

**Layout:**
- Cuadrado 1:1.
- Centro: isotipo lemniscata (480px, gradiente, opacidad 0.95).
- 3 zonas de texto: superior (15%), central (50%, con isotipo), inferior (15%).

**Zona superior:**
- Accent line pequeña (32px × 2px, centrada).
- Título (40px, Playfair, blanco).

**Zona central:**
- Isotipo gradiente (lemniscata).

**Zona inferior:**
- Subtítulo (28px, Inter, teal).
- Copy (18px, Inter, crema).

**Fondo:**
- Gradiente radial (mismo que otros, pero optimizado para cuadrado).
- Orbs (opacity 0.12).
- Ruido (opacity 0.04).

**Contenido (data-driven):**
- `data-titulo`, `data-subtitulo`, `data-copy`.

**Sin hashtags embebidos, sin "SWIPE UP", sin UI mockup.**

---

#### **2.2.8 Instagram Story** (1080×1920)

**Layout:**
- Vertical 9:16 (mobile portrait).
- Espacios: 15% superior (marca), 50% central (isotipo grande), 30% inferior (CTA).

**Superior:**
- Wordmark "Pinakothḗke" pequeño (32px, Playfair).
- Accent line (24px × 2px).

**Central:**
- Isotipo lemniscata (700px, gradiente, opacidad 0.9) centrado.

**Inferior:**
- Título call-to-action (32px, Playfair, gradiente).
- Descripción breve (18px, Inter, crema).
- Línea URL o CTA (16px, teal, pequeño).

**Fondo:**
- Gradiente radial (optimizado vertical).
- Orbs (opacity 0.14).

**Contenido (data-driven):**
- `data-titulo`, `data-subtitulo`, `data-copy`.

**Sin "SWIPE UP" animado, sin botones de UI, sin transiciones embebidas.**

---

#### **2.2.9 OG Product** (1200×630)

**Layout:**
- Horizontal 1.9:1.
- Izq (50%): bloque logo.
  - Wordmark "Pinakothḗke" grande (64px, Playfair).
  - Subtítulo tagline (20px, Inter, muted).
- Derecha (50%): bloque contenido.
  - Accent line (48×3px).
  - Título producto (48px, Playfair, gradiente).
  - Copy (18px, Inter, crema).

**Fondo:**
- Gradiente radial (ellipse at 60% 40%).
- Orbs (opacity 0.13).
- Ruido (opacity 0.05).

**Color & Tipografía:**
- Gradiente hero en wordmark y título.
- Paleta teal + crema + muted.

**Contenido (data-driven):**
- `data-titulo`, `data-subtitulo`, `data-copy`.

**Sin "PREVIEW", sin chrome de navegador, sin mockup.**

---

### 2.3 Reglas de Aplicación — Cloud Atlas

1. **Símbolo único:** Lemniscata ∞ en todas las variantes (no alterar forma).
2. **Gradiente hero:** `linear-gradient(135deg, #43b5a6 0%, #8d7cc0 60%, #4a3a80 100%)` es la norma.
3. **Fondos:** Gradiente radial + orbs + ruido fractal, sin ilustración pictórica.
4. **Tipografía:** Playfair Display (títulos), Inter (cuerpo). Nunca serif en copy largo.
5. **Paleta:** Teal #43b5a6, púrpura #8d7cc0, crema #e8e0d4, negro #0b1417.
6. **Spacing:** Padding = 5–8% del ancho de canvas.
7. **Bordes / corner marks:** Solo en business card (sutil, 50% opacity).
8. **Decoración:** Líneas accent (3px), divisores sutiles (1px, 8–15% opacity), SVG geométrico (no pictórico).
9. **Sin labels internos:** Nunca etiquetas tipo "CARD 01/10", "+SOCIAL", "DRAFT", etc.
10. **Sin mockup de UI:** Estos son assets de marca, no screenshots de aplicación.

---

## 3. LÍNEA B: PRIZMA ENTERPRISE

### 3.1 Identidad de Marca

| Componente | Valor |
|------------|-------|
| **Wordmark** | Hermes (ejemplo: Π mayúscula Prizma en Inter bold) |
| **Isotipo** | Rayo ⚡ (símbolo de velocidad/conexión empresarial) |
| **Colores primarios** | Ámbar/dorado #f0b94a, naranja profundo #d4622e, crema #f0ece6 |
| **Color de fondo** | Negro profundo #0c0e10 |
| **Color complementario** | Teal #43b5a6 (secundario, para contraste) |
| **Tipografía títulos** | Inter Tight o Inter Bold (sans-serif, corporativo, directo) |
| **Tipografía cuerpo** | Inter (sans, neutral, profesional) |
| **Tono** | Ágil, corporativo, conector. Velocidad + confiabilidad. |

### 3.2 Componentes Visuales por Asset

#### **3.2.1 Logo Lockup Color** (1200×400 @2x)

**Layout:**
- Horizontal izq-der.
- Izq: isotipo (rayo ⚡) a 172px, gradiente ámbar→naranja, 0.9 opacidad.
- Centro: divisor línea fina ámbar (h=160px, opacity 0.2).
- Derecha: bloque de texto.
  - Línea 1: wordmark "Prizma" (70px, Inter Bold, gradiente).
  - Línea 2: subtítulo "Enterprise Solutions" (18px, Inter, color muted).

**Jerarquía:**
- Rayo domina izq; wordmark es entrada.
- Subtítulo proporciona contexto corporativo.

**Fondo:**
- Gradiente radial `radial-gradient(ellipse at 70% 30%, #1a120a 0%, #0c0e10 65%)`.
- Orbs ámbar/naranja (blur 100px, opacity 0.12).
- Ruido (opacity 0.05).

**Color / Gradiente:**
- Símbolo + wordmark: `linear-gradient(135deg, #f0b94a 0%, #d4622e 55%, #9e3015 100%)`.

**Contenido:**
- Sin labels; solo marca corporativa.

---

#### **3.2.2 Logo Wordmark** (1200×300 @2x)

**Layout:**
- Centrado.
- "Prizma" (Inter Bold 900, 80px).
- Opcional: "ENTERPRISE" pequeño debajo (Inter Regular 600, 22px).

**Tipografía & Color:**
- Inter Bold/ExtraBold, sin serif.
- Gradiente ámbar→naranja.
- Opción monocromo: ámbar sólido #f0b94a.

---

#### **3.2.3 Logo Symbol/Color** (512×512 @2x)

**Layout:**
- Rayo ⚡ centrado, padding 15%.

**Tipografía & Color:**
- Rayo (Unicode ⚡) 172px Inter Bold.
- Gradiente ámbar→naranja o sólido ámbar.

**Fondo:** Transparente.

---

#### **3.2.4 Business Card** (1050×600 @2x)

**Layout:**
- Izq: rayo (160px) + "Prizma" pequeño (15px uppercase, muted).
- Divisor (h=160px, ámbar 20% opacity).
- Derecha: contacto.
  - Nombre persona (58px, Inter Bold, gradiente).
  - Línea accent (36×2px, gradiente).
  - Cargo/dept (18px, Inter, muted).
  - URL corporativa (16px, ámbar).
  - Email/teléfono (16px, crema).

**Fondo:**
- Gradiente radial (ellipse at 20% 50%).
- Orbs ámbar/naranja (opacity 0.12–0.15).
- Ruido (opacity 0.07).
- Corner marks sutiles (ámbar 40% opacity).

**Color & Tipografía:**
- Gradiente hero ámbar→naranja.
- Inter Bold para títulos; Inter Regular para cuerpo.
- Ámbar #f0b94a en URLs y líneas accent.

---

#### **3.2.5 LinkedIn Banner** (1584×396)

**Layout:**
- Izq (40%): bloque logo.
  - Rayo (72px).
  - "Prizma" (15px uppercase, muted).
- Centro: divisor (1px, ámbar 15% opacity).
- Derecha (50%): contenido.
  - Accent line (48×3px, gradiente).
  - Título (56px, Inter Bold, gradiente).
  - Copy (22px, Inter Light, opacity 0.9).
  - URL/CTA (15px, muted).

**Fondo:**
- Gradiente radial (ellipse at 70% 30%).
- Orbs (opacity 0.12).
- Ruido (opacity 0.05).
- Banda derecha overlay ámbar (270deg, 5% → transparent).
- Línea inferior (3px, gradiente, opacity 0.6).

**Decoración:**
- SVG minimalista derecha (iconografía corporativa: líneas, nodos, sin pictórico).

---

#### **3.2.6 LinkedIn Post** (1200×627)

**Layout:**
- Vertical 1.9:1.
- 60% superior: zona visual (gradiente + rayo grande, opacity 0.1).
- 40% inferior: contenido en surface (#16120e).

**Zona visual:**
- Gradiente hero.
- Rayo grande (400px, opacity 0.08).
- Accent line (48×3px).

**Zona contenido:**
- Título (44px, Inter Bold, gradiente).
- Subtítulo (18px, Inter, muted).
- Copy (16px, Inter, crema).

---

#### **3.2.7 Instagram Post** (1080×1080)

**Layout:**
- Cuadrado 1:1.
- Centro: rayo (480px, gradiente, opacity 0.9).
- Zonas de texto alrededor (15% arriba, 15% abajo).

**Superior:**
- Accent line pequeña (32×2px).
- Título (40px, Inter Bold, blanco).

**Inferior:**
- Subtítulo (28px, Inter, ámbar).
- Copy (18px, Inter, crema).

**Fondo:**
- Gradiente radial (ellipse at 70% 30%, optimizado para cuadrado).
- Orbs ámbar/naranja (opacity 0.11).
- Ruido (opacity 0.04).

---

#### **3.2.8 Instagram Story** (1080×1920)

**Layout:**
- Vertical 9:16.
- 15% superior: "Prizma" wordmark pequeño (32px, Inter Bold).
- 50% central: rayo (700px, gradiente).
- 30% inferior: CTA.
  - Título (32px, Inter Bold, gradiente).
  - Descripción (18px, Inter, crema).
  - URL/CTA (16px, ámbar).

**Fondo:**
- Gradiente radial (vertical).
- Orbs (opacity 0.13).

---

#### **3.2.9 OG Product** (1200×630)

**Layout:**
- Horizontal 1.9:1.
- Izq (50%): wordmark "Prizma" grande (64px, Inter Bold).
  - Tagline (20px, Inter, muted).
- Derecha (50%): contenido.
  - Accent line (48×3px).
  - Título (48px, Inter Bold, gradiente).
  - Copy (18px, Inter, crema).

**Fondo:**
- Gradiente radial (ellipse at 70% 30%).
- Orbs (opacity 0.13).
- Ruido (opacity 0.05).

---

### 3.3 Reglas de Aplicación — Prizma Enterprise

1. **Símbolo único:** Rayo ⚡ en todas las variantes.
2. **Gradiente hero:** `linear-gradient(135deg, #f0b94a 0%, #d4622e 55%, #9e3015 100%)`.
3. **Fondos:** Gradiente radial + orbs + ruido, sin pictórico.
4. **Tipografía:** Inter Bold (títulos), Inter Regular (cuerpo). Cero serif.
5. **Paleta:** Ámbar #f0b94a, naranja #d4622e, crema #f0ece6, negro #0c0e10, teal #43b5a6 (raro).
6. **Spacing:** 5–8% padding del canvas.
7. **Decoración:** Líneas accent (3px), divisores ámbar (1px, 15–20% opacity), SVG corporativo (nodos, líneas, iconografía).
8. **Sin labels internos:** Nunca "CARD 01/10", "+PRIZMA", "DRAFT", etc.
9. **Sin mockup de UI:** Assets de marca, no screenshots.
10. **Tono visual:** Corporativo moderno, no playful; energía sin informalidad.

---

## 4. Especificaciones Técnicas de Render

### 4.1 Motor Eikon

- **Render:** Playwright (browser automation).
- **Formato salida:** PNG 2x (HiDPI), PDF opcional para print (business card).
- **Colores:** RGB sRGB (web), CMYK para print.
- **Fuentes:** Google Fonts (Playfair Display, Inter); fallbacks serif/sans-serif.
- **Data-binding:** Atributos `data-*` leídos de JSON de marca (`pinakotheke-kosmos.json`, `prizma-hermes.json`, etc.).
- **Flexibilidad:** Font-size adaptativo via `data-fit` + `data-fit-min` (overflow handling).

### 4.2 Validación de Calidad

| Criterio | Paso/Fallo |
|----------|-----------|
| Sin labels internos ("CARD 01/10") | Obligatorio PASAR |
| Sin UI mockup visible | Obligatorio PASAR |
| Símbolo/gradiente vs. JSON | Debe coincidir |
| Tipografía correcta | Font-weight, font-family según spec |
| Paleta de colores | RGB exacto del JSON ±5% |
| Aspect ratios | Exacto (ej: 1584×396 para LinkedIn) |
| Ruido/orbs proporcionados | Opacity dentro de range ±2% |
| Data-binding funciona | Todos los `data-*` inyectables sin errores |

---

## 5. Fases de Ejecución

### Fase 1: Validación (Esta sesión)
- ✅ Brief completado.
- ✅ Specs de layout, color, tipografía documentadas.
- ✅ Datos JSON verificados.
- ✅ Reglas de aplicación definidas.

### Fase 2: Desarrollo de Plantillas
- Crear/actualizar 9 archivos HTML/CSS por línea (18 total).
- Inyectar JSON de marca (datos + colores + tipografía).
- Render Playwright de previsualizaciones.
- Validación contra checklist QA.

### Fase 3: Optimización & Exportación
- Generar PNGs @2x (web).
- Generar PDFs (business card print-ready).
- Testear en redes (LinkedIn, Instagram con simuladores Figma/web).
- Archivar en `/workspace/Pinakotheke/eikon/exports/`.

### Fase 4: Documentación & Handoff
- README: cómo usar el motor, cómo inyectar nuevas marcas.
- Guía de uso: qué asset para qué contexto.
- Versión viva del BRIEF (este documento).

---

## 6. Glosario

| Término | Definición |
|---------|-----------|
| **Cloud Atlas** | Marca paraguas de Pinakothḗke + frentes personales (Filosofía, Ciencias, Ingeniería). |
| **Prizma Enterprise** | Marca corporativa: suite de productos SaaS/servicios. |
| **Isotipo** | Símbolo único de la marca (lemniscata para Cloud Atlas, rayo para Prizma). |
| **Wordmark** | Texto de la marca (Pinakothḗke, Prizma) sin símbolo. |
| **Logo Lockup** | Marca completa: símbolo + wordmark + subtítulo. |
| **Data-driven** | Asset cuyo contenido (texto, colores) se inyecta desde JSON. |
| **Eikon** | Motor de render HTML/CSS → PNG/PDF via Playwright. |
| **Gradiente hero** | Gradiente principal de la marca (teal→púrpura para Cloud Atlas, ámbar→naranja para Prizma). |
| **Orbs** | Elementos visuales borrosos de fondo (círculos con blur, simula profundidad). |
| **Ruido fractal** | Textura sutilísima (turbulence SVG) para añadir dimensión. |
| **OG** | Open Graph: metadatos de preview en redes/busca de links. |
| **Corner marks** | Líneas en esquinas de tarjeta (marcar zona de corte). |

---

## 7. Archivo Fuente de Verdad

Este documento es la **especificación maestra** para todas las plantillas de marca. Cualquier cambio futuro debe:
1. Actualizar este BRIEF.
2. Re-renderizar templates afectadas.
3. Re-validar contra QA.
4. Versionar en git.

**Última actualización:** 2026-06-19  
**Responsable:** Steven Vallejo (dirección creativa)  
**Motor:** Eikon (Playwright + HTML/CSS)  
**Estado:** Listo para Fase 2 (Desarrollo)

---

## Apéndice A: Assets por Línea

### Cloud Atlas (Pinakothḗke)

```
├── logo_lockup_color.html      [1200×400 @2x]
├── logo_wordmark.html           [1200×300 @2x]
├── logo_symbol_color.html       [512×512 @2x]
├── business_card.html           [1050×600 @2x]
├── linkedin_banner.html         [1584×396]
├── linkedin_post.html           [1200×627]
├── ig_post.html                 [1080×1080]
├── ig_story.html                [1080×1920]
└── og_product.html              [1200×630]
```

### Prizma Enterprise

```
├── prizma_logo_lockup_color.html      [1200×400 @2x]
├── prizma_logo_wordmark.html          [1200×300 @2x]
├── prizma_logo_symbol_color.html      [512×512 @2x]
├── prizma_business_card.html          [1050×600 @2x]
├── prizma_linkedin_banner.html        [1584×396]
├── prizma_linkedin_post.html          [1200×627]
├── prizma_ig_post.html                [1080×1080]
├── prizma_ig_story.html               [1080×1920]
└── prizma_og_product.html             [1200×630]
```

---

## Apéndice B: Paletas de Referencia

### Cloud Atlas — Pinakothḗke
- **Primario:** #43b5a6 (teal)
- **Acento 2:** #8d7cc0 (púrpura)
- **Acento 3:** #A3E4D7 (teal claro)
- **Texto:** #e8e0d4 (crema)
- **Texto muted:** #8fa3a8 (gris teal)
- **Superficie:** #131e22 (negro azulado)
- **Fondo:** #0b1417 (negro profundo)
- **Gradiente hero:** `linear-gradient(135deg, #43b5a6 0%, #8d7cc0 60%, #4a3a80 100%)`

### Prizma Enterprise — Hermes
- **Primario:** #f0b94a (ámbar/dorado)
- **Acento 2:** #d4622e (naranja profundo)
- **Acento 3:** #43b5a6 (teal complementario, raro)
- **Texto:** #f0ece6 (crema)
- **Texto muted:** #a09080 (gris cálido)
- **Superficie:** #16120e (negro marrón)
- **Fondo:** #0c0e10 (negro profundo)
- **Gradiente hero:** `linear-gradient(135deg, #f0b94a 0%, #d4622e 55%, #9e3015 100%)`

---

**FIN DEL BRIEF**
