/**
 * Mapa de términos técnicos → español humano para el wizard.
 * Nunca mostrar claves técnicas crudas al usuario.
 */

// ── Nombres de ejes ────────────────────────────────────────────────────────────

export const AXIS_LABELS: Record<string, string> = {
  isotype_style:       "Estilo de símbolo",
  palette_scheme:      "Paleta de color",
  typography_pairing:  "Tipografía",
  layout:              "Composición",
  density_scale:       "Espaciado",
  corner_shape:        "Esquinas",
  background_treatment:"Fondo",
  accent_placement:    "Acento",
};

// ── Descripciones cortas por eje ────────────────────────────────────────────────

export const AXIS_DESCRIPTIONS: Record<string, string> = {
  isotype_style:       "La forma del símbolo gráfico de tu marca.",
  palette_scheme:      "Cómo se aplican los colores de tu marca.",
  typography_pairing:  "Qué fuentes usa el logo.",
  layout:              "Cómo se dispone el símbolo y el nombre.",
  density_scale:       "El tamaño relativo de los elementos.",
  corner_shape:        "Si las esquinas son rectas, redondeadas o en píldora.",
  background_treatment:"El estilo de fondo de la imagen generada.",
  accent_placement:    "Dónde aparece el color de acento.",
};

// ── Opciones por eje ───────────────────────────────────────────────────────────

export const OPTION_LABELS: Record<string, Record<string, string>> = {
  isotype_style: {
    none:        "Sin símbolo",
    lettermark:  "Monograma",
    geometric:   "Geométrico",
    abstract:    "Abstracto",
    enclosure:   "Emblema",
  },
  palette_scheme: {
    brand:       "De tu marca",
    mono:        "Monocromo",
    light:       "Claro",
    dark:        "Oscuro",
    accent_bg:   "Fondo de color",
    gradient:    "Degradado",
  },
  typography_pairing: {
    brand_default:   "De tu marca",
    sans_serif:      "Sin serifa",
    serif_modern:    "Con serifa",
    display:         "Display",
    geometric_sans:  "Geométrica",
  },
  layout: {
    symbol_only:          "Solo símbolo",
    wordmark_only:        "Solo nombre",
    lockup_horizontal:    "Horizontal",
    lockup_vertical:      "Vertical",
  },
  density_scale: {
    compact:   "Compacto",
    normal:    "Normal",
    spacious:  "Amplio",
  },
  corner_shape: {
    sharp:    "Rectas",
    rounded:  "Redondeadas",
    pill:     "Píldora",
  },
  background_treatment: {
    solid:     "Sólido",
    gradient:  "Degradado",
    geometric: "Geométrico",
    grid:      "Cuadrícula",
    orb:       "Orbe",
    texture:   "Textura",
  },
  accent_placement: {
    none:       "Sin acento",
    underline:  "Subrayado",
    corner:     "Esquina",
    sidebar:    "Lateral",
    dot:        "Punto",
  },
};

// ── Descripciones cortas por opción (en español) ───────────────────────────────
// El backend trae descripciones en inglés; preferimos estas y, si no hay,
// omitimos (nunca mostramos la cruda en inglés al usuario).

export const OPTION_DESCRIPTIONS: Record<string, Record<string, string>> = {
  isotype_style: {
    none:       "Sin símbolo gráfico, solo el nombre.",
    lettermark: "Un monograma con la inicial de tu marca.",
    geometric:  "Una figura geométrica simple.",
    abstract:   "Una forma abstracta y moderna.",
    enclosure:  "El símbolo dentro de un marco o emblema.",
  },
  palette_scheme: {
    brand:     "Usa todos los colores de tu marca.",
    mono:      "Un solo color, sin acentos.",
    light:     "Versión clara, sobre fondo blanco.",
    dark:      "Versión oscura, sobre fondo profundo.",
    accent_bg: "El color de acento como fondo.",
    gradient:  "Una transición suave entre colores.",
  },
  typography_pairing: {
    brand_default:  "Las fuentes propias de tu marca.",
    sans_serif:     "Tipografía limpia, sin remates.",
    serif_modern:   "Tipografía con remates, más clásica.",
    display:        "Tipografía de carácter, para titulares.",
    geometric_sans: "Tipografía geométrica y moderna.",
  },
  layout: {
    symbol_only:       "Solo el símbolo, sin el nombre.",
    wordmark_only:     "Solo el nombre, sin símbolo.",
    lockup_horizontal: "Símbolo y nombre, uno al lado del otro.",
    lockup_vertical:   "Símbolo arriba y nombre debajo.",
  },
  density_scale: {
    compact:  "Elementos juntos, aire ajustado.",
    normal:   "Espaciado equilibrado.",
    spacious: "Mucho aire alrededor de los elementos.",
  },
  corner_shape: {
    sharp:   "Esquinas rectas y definidas.",
    rounded: "Esquinas suavemente redondeadas.",
    pill:    "Bordes muy redondeados, tipo píldora.",
  },
  background_treatment: {
    solid:     "Un fondo de color plano.",
    gradient:  "Un degradado de color.",
    geometric: "Figuras geométricas de fondo.",
    grid:      "Una cuadrícula sutil de fondo.",
    orb:       "Un orbe de luz difuso.",
    texture:   "Una textura sutil de fondo.",
  },
  accent_placement: {
    none:      "Sin color de acento.",
    underline: "Un subrayado de acento.",
    corner:    "Un detalle de acento en la esquina.",
    sidebar:   "Una franja de acento lateral.",
    dot:       "Un punto de acento.",
  },
};

// ── Helpers ────────────────────────────────────────────────────────────────────

export function axisLabel(axisName: string, fallback?: string): string {
  return AXIS_LABELS[axisName] ?? fallback ?? axisName;
}

export function optionLabel(axisName: string, optionName: string, fallback?: string): string {
  return OPTION_LABELS[axisName]?.[optionName] ?? fallback ?? optionName;
}

/** Descripción humana en español de una opción; "" si no hay (no mostramos inglés). */
export function optionDescription(axisName: string, optionName: string): string {
  return OPTION_DESCRIPTIONS[axisName]?.[optionName] ?? "";
}

/**
 * Opciones "none" en isotype_style no deben ser el default cuando
 * el usuario quiere generar un logo con símbolo.
 */
export const ISOTYPE_STYLE_SKIP_DEFAULT = "none";

/** Primera opción real (no "none") de isotype_style. */
export const ISOTYPE_STYLE_FIRST_REAL = "lettermark";

// ── Labels de pasos del wizard ─────────────────────────────────────────────────

export const STEP_LABELS: Record<string, string> = {
  brand:   "Tu marca",
  assets:  "Qué generar",
  axes:    "Estilo",
  count:   "Variaciones",
  review:  "Revisar",
};

// ── Formatos (asset_types) ────────────────────────────────────────────────────

export const ASSET_TYPE_LABELS: Record<string, string> = {
  // Logos
  isotipo:              "Símbolo / Isotipo",
  lockup_horizontal:    "Logo horizontal",
  lockup_vertical:      "Logo vertical",
  wordmark:             "Wordmark (solo nombre)",
  favicon:              "Favicon",
  watermark:            "Marca de agua",
  // Banners
  linkedin_header:      "Portada de LinkedIn",
  twitter_header:       "Portada de X / Twitter",
  youtube_header:       "Arte de canal YouTube",
  web_hero_desktop:     "Hero web",
  ad_leaderboard:       "Anuncio horizontal",
  ad_rectangle:         "Anuncio rectangular",
  // Tarjetas
  business_card:        "Tarjeta de presentación",
  stat_card:            "Tarjeta de estadística",
  // OG / Meta
  og_general:           "Imagen OG / Meta",
  og_product:           "OG de producto",
  // Papelería
  letterhead:           "Papel membretado",
};

export function assetTypeLabel(key: string): string {
  return ASSET_TYPE_LABELS[key] ?? key.replace(/_/g, " ");
}
