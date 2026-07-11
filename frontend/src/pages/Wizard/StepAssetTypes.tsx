/**
 * Paso 2 del wizard: elegir qué formatos generar.
 *
 * Muestra todas las familias de asset (Logos, Banners, Tarjetas, OG/Meta,
 * Papelería) con selección múltiple por tipo. Los datos se cargan desde
 * GET /api/v1/wizard/asset-types; si la carga falla se usan labels de terms.ts.
 */
import { useEffect, useId, useRef, useState } from "react";
import { wizard, type AssetFamily } from "../../api/client";
import { Spinner } from "../../components";
import { WizardFormData } from "./useWizardState";
import { assetTypeLabel } from "./terms";

interface StepAssetTypesProps {
  formData: WizardFormData;
  onUpdate: (update: Partial<WizardFormData>) => void;
}

// ── Datos estáticos de respaldo (mismos que el endpoint, sin necesidad de red) ─

const FALLBACK_FAMILIES: AssetFamily[] = [
  {
    id: "logos",
    label: "Logos",
    description: "Identificador principal de la marca: isotipo, lockup y wordmark",
    types: [
      { name: "isotipo",           label: "Símbolo / Isotipo",       description: "El ícono gráfico de la marca, sin texto" },
      { name: "lockup_horizontal", label: "Logo horizontal",          description: "Símbolo y nombre dispuestos en horizontal" },
      { name: "lockup_vertical",   label: "Logo vertical",            description: "Símbolo arriba y nombre debajo" },
      { name: "wordmark",          label: "Wordmark (solo nombre)",   description: "El nombre de la marca como elemento tipográfico" },
      { name: "favicon",           label: "Favicon",                  description: "Versión mínima del ícono para pestaña de navegador" },
      { name: "watermark",         label: "Marca de agua",            description: "Versión translúcida para aplicar sobre imágenes" },
    ],
  },
  {
    id: "banners",
    label: "Banners",
    description: "Imágenes de portada para redes sociales y sitio web",
    types: [
      { name: "linkedin_header",  label: "Portada de LinkedIn",        description: "Portada para perfil o página de empresa en LinkedIn (1584×396 px)" },
      { name: "twitter_header",   label: "Portada de X / Twitter",     description: "Portada para perfil en X (1500×500 px)" },
      { name: "youtube_header",   label: "Arte de canal YouTube",      description: "Imagen de cabecera del canal de YouTube (2560×1440 px)" },
      { name: "web_hero_desktop", label: "Hero web",                   description: "Imagen de cabecera para sitio web (1920×600 px)" },
      { name: "ad_leaderboard",   label: "Anuncio horizontal",         description: "Banner publicitario estándar IAB (728×90 px)" },
      { name: "ad_rectangle",     label: "Anuncio rectangular",        description: "Banner publicitario mediano (300×250 px)" },
    ],
  },
  {
    id: "cards",
    label: "Tarjetas",
    description: "Formatos cuadrados y rectangulares para posts e impresión",
    types: [
      { name: "business_card", label: "Tarjeta de presentación", description: "Tarjeta de visita, anverso y reverso (1050×600 px)" },
      { name: "stat_card",     label: "Tarjeta de estadística",  description: "Post cuadrado con un dato o métrica destacada (1080×1080 px)" },
    ],
  },
  {
    id: "og",
    label: "OG / Meta",
    description: "Imagen de previsualización al compartir el enlace en redes",
    types: [
      { name: "og_general", label: "Imagen OG / Meta", description: "Imagen al compartir el enlace en redes (1200×630 px)" },
    ],
  },
  {
    id: "stationery",
    label: "Papelería",
    description: "Formatos de oficina: papel membretado, sobres y documentos",
    types: [
      { name: "letterhead", label: "Papel membretado", description: "Hoja A4 con cabecera de la marca (2480×3508 px)" },
    ],
  },
];

// ── Íconos por familia (SVG inline, aria-hidden) ───────────────────────────────

function FamilyIcon({ id }: { id: string }) {
  const icons: Record<string, string> = {
    logos:      "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5",
    banners:    "M4 6h16M4 10h16M4 14h10",
    cards:      "M3 5h18a1 1 0 011 1v12a1 1 0 01-1 1H3a1 1 0 01-1-1V6a1 1 0 011-1z",
    og:         "M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101M10.172 13.828a4 4 0 015.656 0l4 4a4 4 0 01-5.656 5.656l-1.1-1.1",
    stationery: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
  };
  const d = icons[id] ?? "M12 4v16m8-8H4";
  return (
    <svg
      aria-hidden="true"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0 }}
    >
      <path d={d} />
    </svg>
  );
}

export function StepAssetTypes({ formData, onUpdate }: StepAssetTypesProps) {
  const [families, setFamilies] = useState<AssetFamily[]>(FALLBACK_FAMILIES);
  const [loadState, setLoadState] = useState<"loading" | "ok" | "error">("loading");
  const headingId = useId();
  const firstCheckRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    wizard
      .assetTypes()
      .then((res) => {
        if (!cancelled && res.families.length > 0) {
          setFamilies(res.families);
        }
        if (!cancelled) setLoadState("ok");
      })
      .catch(() => {
        if (!cancelled) setLoadState("error");
      });
    return () => { cancelled = true; };
  }, []);

  // Focus primer checkbox al montar (accesibilidad)
  useEffect(() => {
    if (loadState === "ok" && firstCheckRef.current) {
      firstCheckRef.current.focus();
    }
  }, [loadState]);

  const selected = new Set(formData.assetTypes);

  const toggle = (name: string) => {
    const next = new Set(selected);
    if (next.has(name)) {
      next.delete(name);
    } else {
      next.add(name);
    }
    onUpdate({ assetTypes: Array.from(next) });
  };

  // Label legible de los tipos seleccionados (en orden de aparición en families)
  const selectedLabels = families
    .flatMap((f) => f.types)
    .filter((t) => selected.has(t.name))
    .map((t) => t.label || assetTypeLabel(t.name));

  return (
    <section
      aria-labelledby={headingId}
      style={{ display: "grid", gap: "var(--space-6)" }}
    >
      {/* Encabezado */}
      <div>
        <h2
          id={headingId}
          style={{
            margin: "0 0 var(--space-2)",
            fontFamily: "var(--font-display)",
            fontSize: "var(--font-size-2xl)",
            fontWeight: 700,
            color: "var(--ink)",
          }}
        >
          ¿Qué quieres generar?
        </h2>
        <p
          style={{
            margin: 0,
            fontSize: "var(--font-size-base)",
            color: "var(--slate-500)",
            lineHeight: 1.6,
          }}
        >
          Elige uno o varios formatos de identidad visual. Puedes combinar
          familias distintas en el mismo lote.
        </p>
      </div>

      {/* Spinner de carga inicial */}
      {loadState === "loading" && (
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            padding: "var(--space-8) 0",
          }}
        >
          <Spinner label="Cargando formatos…" size="lg" />
        </div>
      )}

      {/* Aviso si falla la carga (mostramos igual los datos estáticos) */}
      {loadState === "error" && (
        <div
          role="alert"
          style={{
            padding: "var(--space-3) var(--space-4)",
            background: "var(--mist)",
            borderRadius: "var(--radius-md)",
            fontSize: "var(--font-size-sm)",
            color: "var(--slate-700)",
          }}
        >
          No se pudo conectar con el servidor. Se muestran los formatos disponibles.
        </div>
      )}

      {/* Familias */}
      {(loadState === "ok" || loadState === "error") && (
        <div
          role="group"
          aria-label="Familias de formato"
          style={{ display: "grid", gap: "var(--space-5)" }}
        >
          {families.map((family, fi) => (
            <fieldset
              key={family.id}
              style={{ border: "none", padding: 0, margin: 0 }}
            >
              {/* Cabecera de familia */}
              <legend
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-2)",
                  width: "100%",
                  paddingBottom: "var(--space-2)",
                  marginBottom: "var(--space-2)",
                  borderBottom: "1.5px solid var(--line)",
                  fontFamily: "var(--font-display)",
                  fontSize: "var(--font-size-base)",
                  fontWeight: 700,
                  color: "var(--ink)",
                  letterSpacing: "0.01em",
                }}
              >
                <FamilyIcon id={family.id} />
                {family.label}
                {family.description && (
                  <span
                    style={{
                      fontWeight: 400,
                      fontSize: "var(--font-size-sm)",
                      color: "var(--slate-500)",
                      marginLeft: "var(--space-1)",
                    }}
                  >
                    — {family.description}
                  </span>
                )}
              </legend>

              {/* Tipos de la familia */}
              <div
                style={{
                  display: "grid",
                  gap: "var(--space-2)",
                  gridTemplateColumns:
                    "repeat(auto-fill, minmax(min(100%, 320px), 1fr))",
                }}
              >
                {family.types.map((type, ti) => {
                  const isChecked = selected.has(type.name);
                  const inputId = `asset-${family.id}-${type.name}`;
                  const isFirst = fi === 0 && ti === 0;
                  return (
                    <label
                      key={type.name}
                      htmlFor={inputId}
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: "var(--space-3)",
                        padding: "var(--space-3) var(--space-4)",
                        border: isChecked
                          ? "2px solid var(--teal-600)"
                          : "1.5px solid var(--line)",
                        borderRadius: "var(--radius-md)",
                        cursor: "pointer",
                        background: isChecked ? "var(--mist)" : "var(--white)",
                        transition:
                          "border-color var(--transition-fast), background var(--transition-fast)",
                        userSelect: "none",
                      }}
                    >
                      <input
                        ref={isFirst ? firstCheckRef : undefined}
                        id={inputId}
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggle(type.name)}
                        style={{
                          marginTop: "2px",
                          accentColor: "var(--teal-600)",
                          cursor: "pointer",
                          flexShrink: 0,
                          width: "16px",
                          height: "16px",
                        }}
                        aria-describedby={
                          type.description ? `${inputId}-desc` : undefined
                        }
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div
                          style={{
                            fontSize: "var(--font-size-sm)",
                            fontWeight: 600,
                            color: isChecked ? "var(--teal-600)" : "var(--ink)",
                            marginBottom: type.description ? "var(--space-1)" : 0,
                          }}
                        >
                          {type.label || assetTypeLabel(type.name)}
                        </div>
                        {type.description && (
                          <div
                            id={`${inputId}-desc`}
                            style={{
                              fontSize: "var(--font-size-xs)",
                              color: "var(--slate-500)",
                              lineHeight: 1.5,
                            }}
                          >
                            {type.description}
                          </div>
                        )}
                      </div>
                    </label>
                  );
                })}
              </div>
            </fieldset>
          ))}
        </div>
      )}

      {/* Resumen de selección */}
      <div
        aria-live="polite"
        aria-atomic="true"
        style={{
          padding: "var(--space-3) var(--space-4)",
          background: "var(--mist)",
          borderRadius: "var(--radius-md)",
          fontSize: "var(--font-size-sm)",
          color: selected.size === 0 ? "var(--error)" : "var(--slate-700)",
          borderLeft: selected.size === 0
            ? "4px solid var(--error)"
            : "4px solid var(--teal)",
        }}
      >
        {selected.size === 0 ? (
          <span>
            <strong>Selecciona al menos un formato</strong> para continuar.
          </span>
        ) : (
          <span>
            <strong>
              {selected.size === 1
                ? "1 formato seleccionado:"
                : `${selected.size} formatos seleccionados:`}
            </strong>{" "}
            {selectedLabels.join(" · ")}
          </span>
        )}
      </div>
    </section>
  );
}
