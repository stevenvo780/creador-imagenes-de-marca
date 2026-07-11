/**
 * Utilidades de formato compartidas.
 *
 * La API entrega las fechas como timestamp Unix en SEGUNDOS (número), p. ej.
 * 1782772485. `new Date(1782772485)` lo interpreta como milisegundos → 1970,
 * por eso normalizamos aquí en un solo lugar.
 */

export type TimeValue = number | string | null | undefined;

/** Convierte un valor de fecha de la API en un Date válido, o null. */
export function toDate(value: TimeValue): Date | null {
  if (value === null || value === undefined || value === "") return null;

  // Número: segundos epoch (heurística: < 1e12 ⇒ segundos, no ms).
  if (typeof value === "number") {
    const ms = value < 1e12 ? value * 1000 : value;
    const d = new Date(ms);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  // String numérico (segundos en texto).
  const asNum = Number(value);
  if (value.trim() !== "" && !Number.isNaN(asNum)) {
    const ms = asNum < 1e12 ? asNum * 1000 : asNum;
    const d = new Date(ms);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  // String ISO u otro formato reconocible.
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Fecha legible en español (p. ej. "29 de junio de 2026"), o guion. */
export function formatDate(
  value: TimeValue,
  opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "long", year: "numeric" },
): string {
  const d = toDate(value);
  return d ? d.toLocaleDateString("es-ES", opts) : "—";
}

/** Fecha + hora legibles en español, o guion. */
export function formatDateTime(value: TimeValue): string {
  const d = toDate(value);
  return d
    ? d.toLocaleString("es-ES", { dateStyle: "medium", timeStyle: "short" })
    : "—";
}

/**
 * Deriva un identificador (slug) a partir de un nombre humano.
 * Quita acentos, pasa a minúsculas y reemplaza no-alfanuméricos por guiones.
 */
export function slugify(input: string): string {
  return input
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // quitar diacríticos
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}
