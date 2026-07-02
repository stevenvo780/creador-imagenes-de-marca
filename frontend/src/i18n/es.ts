// Central i18n module for eikon backend axis labels + option descriptions

export const es = {
  palette_keys: {
    bg: "Fondo",
    texto: "Texto",
    primario: "Primario",
    acento: "Acento",
    acento_2: "Acento 2",
  },
  brand_editor: {
    title: "Editar marca",
    subtitle: "Ajustá el nombre, el texto del logo y la paleta de colores.",
    section_name: "Datos básicos",
    section_palette: "Paleta de colores",
    name_label: "Nombre de la marca",
    name_hint: "Lo ven tus usuarios en todas las pantallas.",
    logo_text_label: "Texto del logo",
    logo_text_hint: "Lo que se lee dentro del logo. Si lo dejás vacío, usamos el nombre.",
    palette_hint: "Tocá el cuadrado para abrir el selector, o escribí el valor en hexadecimal (por ejemplo #1F8276).",
    save: "Guardar cambios",
    saving: "Guardando…",
    cancel: "Cancelar",
    back: "Volver a mis marcas",
    load_error: "No pudimos cargar la marca. Volvé a intentarlo.",
    save_error_invalid: "Revisá los colores: tienen que ser valores hexadecimales válidos (#RRGGBB).",
    save_error_generic: "No pudimos guardar los cambios. Intentá de nuevo.",
    save_success: "Cambios guardados.",
  },

  palette_scheme: {
    label: "Paleta de color",
    options: {
      brand: "Paleta completa de la marca (por defecto)",
      mono: "Monocromo: texto/fondo invertidos, sin acento",
      light: "Modo claro: fondo/texto invertidos",
      dark: "Modo oscuro: primario como fondo",
      accent_bg: "Acento como fondo",
      gradient: "Fondo degradado (gradiente hero)",
    },
  },
  typography_pairing: {
    label: "Tipografía",
    options: {
      brand_default: "Tipografía por defecto de la marca",
      sans_serif: "Sans-serif moderno (Inter/System)",
      serif_modern: "Título serif con cuerpo sans",
      display: "Tipografías display",
      geometric_sans: "Título grotesco geométrico (Space Grotesk) con cuerpo sans",
    },
  },
  layout: {
    label: "Composición",
    options: {
      symbol_only: "Solo símbolo (sin texto)",
      wordmark_only: "Solo texto (wordmark)",
      lockup_horizontal: "Bloque horizontal (símbolo + texto lado a lado)",
      lockup_vertical: "Bloque vertical (símbolo arriba del texto)",
    },
  },
  background_treatment: {
    label: "Fondo",
    options: {
      solid: "Fondo de color sólido",
      gradient: "Fondo degradado",
      geometric: "Patrón geométrico",
      grid: "Superposición de cuadrícula",
      orb: "Efecto de orbe radial",
      texture: "Textura sutil",
    },
  },
  density_scale: {
    label: "Espaciado",
    options: {
      compact: "Compacto: escala 85%",
      normal: "Normal: escala 100% (por defecto)",
      spacious: "Amplio: escala 115%",
    },
  },
  corner_shape: {
    label: "Esquinas",
    options: {
      sharp: "Esquinas rectas (0px)",
      rounded: "Esquinas redondeadas (14px)",
      pill: "Forma de píldora (999px)",
    },
  },
  isotype_style: {
    label: "Estilo de símbolo",
    options: {
      none: "Sin estilo adicional (preservar apariencia actual)",
      lettermark: "Variante de monograma (una letra)",
      geometric: "Forma geométrica abstracta",
      abstract: "Forma orgánica abstracta",
      enclosure: "Marca encerrada en una forma",
    },
  },
  accent_placement: {
    label: "Acento",
    options: {
      none: "Sin acento (por defecto)",
      underline: "Barra de acento subrayada",
      corner: "Marcador de acento en esquina",
      sidebar: "Franja de acento lateral",
      dot: "Elemento de acento en punto",
    },
  },
} as const;

export function tLabel(axisId: string): string {
  const axis = (es as unknown as Record<string, { label: string }>)[axisId];
  return axis?.label ?? axisId;
}

export function tOption(axisId: string, optionId: string): string {
  const axis = (es as unknown as Record<string, { options: Record<string, string> }>)[axisId];
  return axis?.options[optionId] ?? optionId;
}