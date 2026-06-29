/**
 * Paso 2: Elegir qué formatos generar.
 * Opciones en lenguaje humano, sin jerga técnica.
 */
import { WizardFormData } from "./useWizardState";
import { assetTypeLabel } from "./terms";

interface StepAssetTypesProps {
  formData: WizardFormData;
  onUpdate: (update: Partial<WizardFormData>) => void;
}

interface FormatPreset {
  id: string;
  label: string;
  description: string;
  assets: string[];
}

const PRESETS: FormatPreset[] = [
  {
    id: "symbol-and-logo",
    label: "Símbolo y logo",
    description: "El símbolo de tu marca junto al nombre. El resultado más completo.",
    assets: ["isotipo", "logo_symbol_color"],
  },
  {
    id: "symbol-only",
    label: "Solo símbolo",
    description: "Únicamente el ícono gráfico, sin texto. Ideal para avatares y favicons.",
    assets: ["isotipo"],
  },
];

export function StepAssetTypes({ formData, onUpdate }: StepAssetTypesProps) {
  const currentKey = formData.assetTypes.join(",");

  const selectedPreset =
    currentKey === "isotipo,logo_symbol_color"
      ? "symbol-and-logo"
      : currentKey === "isotipo"
        ? "symbol-only"
        : "custom";

  const handlePresetSelect = (preset: FormatPreset) => {
    onUpdate({ assetTypes: preset.assets });
  };

  return (
    <section style={{ display: "grid", gap: "var(--space-6)" }}>

      {/* Encabezado */}
      <div>
        <h2
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
          Elige los formatos de identidad visual que quieres crear.
        </p>
      </div>

      {/* Opciones */}
      <fieldset style={{ border: "none", padding: 0, margin: 0 }}>
        <legend className="sr-only">Formatos a generar</legend>

        <div style={{ display: "grid", gap: "var(--space-3)" }}>
          {PRESETS.map((preset) => {
            const isSelected = selectedPreset === preset.id;
            return (
              <label
                key={preset.id}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "var(--space-4)",
                  padding: "var(--space-4) var(--space-5)",
                  border: isSelected
                    ? "2px solid var(--teal-600)"
                    : "1.5px solid var(--line)",
                  borderRadius: "var(--radius-lg)",
                  cursor: "pointer",
                  background: isSelected ? "var(--mist)" : "var(--white)",
                  transition:
                    "border-color var(--transition-fast), background var(--transition-fast)",
                }}
              >
                <input
                  type="radio"
                  name="format-preset"
                  value={preset.id}
                  checked={isSelected}
                  onChange={() => handlePresetSelect(preset)}
                  style={{
                    marginTop: "3px",
                    accentColor: "var(--teal-600)",
                    cursor: "pointer",
                    flexShrink: 0,
                  }}
                />
                <div style={{ flex: 1 }}>
                  <div
                    style={{
                      fontSize: "var(--font-size-base)",
                      fontWeight: 700,
                      color: isSelected ? "var(--teal-600)" : "var(--ink)",
                      marginBottom: "var(--space-1)",
                    }}
                  >
                    {preset.label}
                  </div>
                  <div
                    style={{
                      fontSize: "var(--font-size-sm)",
                      color: "var(--slate-500)",
                      lineHeight: 1.5,
                    }}
                  >
                    {preset.description}
                  </div>
                  {/* Detalle de los formatos incluidos */}
                  <div
                    style={{
                      marginTop: "var(--space-2)",
                      display: "flex",
                      flexWrap: "wrap",
                      gap: "var(--space-2)",
                    }}
                  >
                    {preset.assets.map((a) => (
                      <span
                        key={a}
                        style={{
                          display: "inline-block",
                          padding: "2px var(--space-2)",
                          background: isSelected
                            ? "rgba(47, 168, 154, 0.15)"
                            : "var(--mist)",
                          borderRadius: "var(--radius-sm)",
                          fontSize: "var(--font-size-xs)",
                          color: isSelected ? "var(--teal-600)" : "var(--slate-500)",
                          fontWeight: 500,
                        }}
                      >
                        {assetTypeLabel(a)}
                      </span>
                    ))}
                  </div>
                </div>
              </label>
            );
          })}
        </div>
      </fieldset>

      {/* Formatos seleccionados — resumen */}
      <div
        style={{
          padding: "var(--space-3) var(--space-4)",
          background: "var(--mist)",
          borderRadius: "var(--radius-md)",
          fontSize: "var(--font-size-sm)",
          color: "var(--slate-700)",
        }}
      >
        <strong>Vas a generar:</strong>{" "}
        {formData.assetTypes.map((t) => assetTypeLabel(t)).join(" · ")}
      </div>
    </section>
  );
}
