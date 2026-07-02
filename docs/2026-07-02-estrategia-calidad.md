# Eikón — Estrategia de calidad (síntesis de crítica integral)

> 2026-07-02. Síntesis (Opus) de una crítica integral hecha en workflow por Codex (logos,
> arquitectura), OpenCode (composición, color/tipografía) y MiniMax (inventario).
> Detonante: el dueño juzgó los outputs "muy feos y poco profesionales".

## 1. Diagnóstico unificado (por qué se ve amateur)

**Tesis central (las 5 críticas coinciden):** Eikón confunde **variación paramétrica** con
**decisión de diseño**. Es un motor de permutación (8 ejes → 3.3M combos) que aplica **decoración
sobre una estructura de diseño débil**. Los pros hacen lo opuesto: parten de un brief semántico,
curan 3-5 direcciones, y entregan menos-pero-mejor.

Tres causas raíz:

1. **Los "logos" no son marcas, son gráficos científicos.** De 102 algoritmos, ~60-75 son
   plots matemáticos puros (curvas, espirales, fractales, ondas, teselados, distribución): bonitos
   pero sin intención, significado, memorabilidad ni distinción. Solo ~24 sirven como marca
   (tipográfico, emblemas, algunos círculos, polígonos simples).

2. **No hay engine de diseño (tokens).** Espaciado ad-hoc (28/22/60px, no múltiplos de 8),
   tamaños tipográficos mágicos (62/54/17/28px, sin escala modular), colores como strings hex
   sueltos (sin HSL/armonías/tintes), contraste parcheado *después* con hexes mágicos. Además
   **53% de las marcas rinden con la fuente equivocada** (piden JetBrains Mono / Cormorant sin
   `@font-face` → fallback silencioso a Times/Courier).

3. **Composición sin criterio editorial.** La fórmula "símbolo-en-disco + wordmark + accent-bar +
   tagline + gradiente 135°" repetida en todos los assets. Tres elementos compiten por ser el héroe.
   El disco es un band-aid que tapa la falta de retícula. `og_general.html` tiene 707 líneas de CSS.

## 2. La bifurcación estratégica

| | **Camino A — Rescatar el engine** | **Camino B — Reinventar como Director Creativo IA** |
|---|---|---|
| **Qué** | Convertir el generador procedural en uno **con criterio**: design tokens + engine de color HSL + marcas curadas + plantillas editoriales. | Brief semántico (LLM) → 3-5 direcciones → generación con **modelos de imagen** (Recraft V4 / Ideogram 4) → hard gates → ranking multimodal (Vision) → curación top-3. |
| **Cómo se ve** | Eikón sigue siendo procedural y rápido, pero con taste. | Eikón se vuelve un "director de arte automatizado" tipo Looka/Brandmark. |
| **Esfuerzo** | ~semanas (Python + CSS, sin dependencias externas). | ~3-4 meses; APIs generativas (costo por imagen) + reescritura del pipeline. |
| **Costo operativo** | ~0 (todo local/HTML). | Recurrente (Recraft/Ideogram por generación). |
| **Riesgo** | Bajo; mejora garantizada. | Alto valor, mayor incertidumbre y costo. |

**No son excluyentes.** El Camino A construye la **base de diseño (tokens, color, tipografía,
plantillas)** que el Camino B también necesita. La recomendación es **A primero**, y evaluar B como
capa posterior para el "wow" de los logos.

## 3. Plan recomendado (Camino A — rescate del engine)

### Fase 1 — Curar el catálogo de marcas (de 102 a ~40)
- **Eliminar** ~60 algoritmos de ruido: curvas (lissajous, rosa_polar, mariposa…), espirales
  genéricas, fractales complejos, ondas, teselados, distribución.
- **Mantener** ~24 curados: tipográfico (monograma, letra_negativa, stencil, ligadura,
  inicial_circulo), emblemas (escudo, sello, laurel, banderín), círculos con símbolo (vesica,
  triquetra, flor_vida, anillos_borromeos, metatron), polígonos simples (regular, estrella_np,
  anidados, reuleaux, corona_picos), espiral áurea, dragon/hilbert.
- **Construir ~15 sistemas de marca reales**: monograma reticulado, grid modular, trazo monoline,
  negativo puro, ícono+letra, simetría bilateral/radial, escudo heráldico avanzado, etc. (marcas
  con intención, no ecuaciones ploteadas).

### Fase 2 — Engine de diseño (design tokens en Python + CSS) — el 80% del arreglo
- **Escala de espaciado**: solo múltiplos de 8 (0,8,16,24,32,48,64,96). CI falla si aparece un
  valor fuera de escala.
- **Escala tipográfica modular**: base 16px × ratio 1.25/1.333; tracking derivado del tamaño;
  line-height por familia. Nada de 62/54/17px.
- **Engine de color HSL/OKLCH** (`mapping.py`): armonías (complementaria/análoga/triádica), tintes/
  sombras generados, `palette_scheme` reales (mono, light, dark que conserven identidad), gradientes
  procedurales. **Pre-flight WCAG**: ajustar luminosidad *antes* de renderizar (invertir el validador),
  eliminar los parches de hex mágicos.
- **Validación de fuentes** + agregar `@font-face` para JetBrains Mono y Cormorant Garamond
  (arregla el 53% de marcas rotas). Error claro si una fuente no está cargada.

### Fase 3 — Plantillas editoriales (tokens, no fórmula)
- **Matar** gradiente 135° por defecto y logo-en-disco. Logo **protagonista** sobre retícula, no
  encerrado.
- **Componentes atómicos** (`_symbol-stage`, `_title-block`, `_meta-footer`) que las plantillas
  componen. Regla: cada plantilla ≤150 líneas CSS (hoy `og_general` tiene 707).
- Layouts **distintos por asset** (tarjeta ≠ banner ≠ OG ≠ favicon), no la misma receta.
- La escala tipográfica se **computa por dimensión de canvas** en la inyección (título 49px en
  1200×630, 31px en 1050×600), no hardcodeada.

### Fase 4 — Curación y quality gates
- Ranking que mida **calidad de marca** (memorabilidad, escalabilidad, fit), no solo "¿está roto?".
- **Menos-pero-mejor**: mostrar 6-10 opciones curadas por marca, no 100 accidentes.

## 4. Camino B (opcional, fase posterior) — Director Creativo IA
Cuando la base (A) esté, evaluar: `BrandBrief` vía LLM (industria/audiencia/tono) → direcciones
creativas → generación de logo con **Recraft V4.1 Vector** (calidad + vectorización) o **Ideogram 4**
(texto en imagen) con negative-prompts por industria → hard gates (OCR, escalabilidad a 16px, ≤3
colores, distinctiveness por CLIP/dHash, anti-clichés) → ranking multimodal con Vision LLM →
plantillas editoriales → top-3 + expansión del sistema + brand guide. Roadmap del análisis: 3-4 meses.

## 5. Decisión pendiente (owner)
1. **¿Camino A, B, o A→B?** (recomendado: A primero.)
2. **Alcance de A:** ¿full (curación + engine + plantillas) o empezar por Fase 2 (engine de tokens/
   color/tipografía), que es el mayor salto de calidad con menor riesgo?
3. **Restricción:** plantillas protegidas (Prizma: og_general, letterhead, stat_card) — ¿se pueden
   tocar en el rediseño con tu OK, o quedan fuera?

_Fuentes: transcript del workflow `eikon-critica-integral` (Codex/OpenCode/MiniMax), 2026-07-02._
