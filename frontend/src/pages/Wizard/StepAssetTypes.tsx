/**
 * Paso 2: Seleccionar tipos de asset.
 * Presets: isotipo, isotipo+logo, custom.
 */
import { WizardFormData } from "./useWizardState";

interface StepAssetTypesProps {
  formData: WizardFormData;
  onUpdate: (update: Partial<WizardFormData>) => void;
}

const PRESETS = [
  {
    id: "isotipo",
    label: "Isotipo",
    description: "Solo isotipo (símbolo sin texto)",
    assets: ["isotipo"],
  },
  {
    id: "isotipo-logo",
    label: "Isotipo + Logo",
    description: "Símbolo y logo con texto",
    assets: ["isotipo", "logo_symbol_color"],
  },
  {
    id: "custom",
    label: "Personalizado",
    description: "Especifica tipos separados por coma",
    assets: [],
  },
];

export function StepAssetTypes({
  formData,
  onUpdate,
}: StepAssetTypesProps) {
  const selectedPreset =
    formData.assetTypes.join(",") === "isotipo"
      ? "isotipo"
      : formData.assetTypes.join(",") === "isotipo,logo_symbol_color"
        ? "isotipo-logo"
        : "custom";

  const handlePresetChange = (presetId: string) => {
    if (presetId === "custom") {
      // No cambiar assetTypes, dejar que edite manualmente
      return;
    }
    const preset = PRESETS.find((p) => p.id === presetId);
    if (preset) {
      onUpdate({ assetTypes: preset.assets });
    }
  };

  const handleCustomChange = (value: string) => {
    const types = value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    onUpdate({ assetTypes: types.length > 0 ? types : ["isotipo"] });
  };

  return (
    <section style={{ display: "grid", gap: "var(--space-4)" }}>
      <div>
        <h3
          style={{
            margin: "0 0 var(--space-3)",
            fontSize: "var(--font-size-base)",
            fontWeight: 600,
            color: "var(--color-text)",
          }}
        >
          Paso 2: Tipos de asset
        </h3>
        <p
          style={{
            margin: "0 0 var(--space-3)",
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-muted)",
          }}
        >
          Elige qué formatos de archivo generar.
        </p>
      </div>

      <fieldset
        style={{
          border: "none",
          padding: 0,
          margin: 0,
          display: "grid",
          gap: "var(--space-3)",
        }}
      >
        <legend
          style={{
            fontSize: "var(--font-size-sm)",
            fontWeight: 500,
            color: "var(--color-text)",
            marginBottom: "var(--space-2)",
          }}
        >
          Presets
        </legend>

        {PRESETS.slice(0, 2).map((preset) => (
          <label
            key={preset.id}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "var(--space-3)",
              padding: "var(--space-2) var(--space-3)",
              border: "1.5px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              cursor: "pointer",
              background:
                selectedPreset === preset.id
                  ? "rgba(26,122,110,0.04)"
                  : "transparent",
              transition: "background-color 0.2s",
            }}
          >
            <input
              type="radio"
              name="asset-preset"
              value={preset.id}
              checked={selectedPreset === preset.id}
              onChange={() => handlePresetChange(preset.id)}
              style={{ marginTop: "2px", cursor: "pointer" }}
            />
            <div style={{ flex: 1 }}>
              <div
                style={{
                  fontSize: "var(--font-size-sm)",
                  fontWeight: 500,
                  color: "var(--color-text)",
                }}
              >
                {preset.label}
              </div>
              <div
                style={{
                  marginTop: "2px",
                  fontSize: "var(--font-size-sm)",
                  color: "var(--color-text-muted)",
                }}
              >
                {preset.description}
              </div>
            </div>
          </label>
        ))}
      </fieldset>

      {selectedPreset === "custom" && (
        <div>
          <label
            htmlFor="asset-types-custom"
            style={{
              display: "block",
              marginBottom: "var(--space-2)",
              fontSize: "var(--font-size-sm)",
              fontWeight: 500,
              color: "var(--color-text)",
            }}
          >
            Tipos customizados (separados por coma)
          </label>
          <input
            id="asset-types-custom"
            type="text"
            value={formData.assetTypes.join(", ")}
            onChange={(e) => handleCustomChange(e.target.value)}
            placeholder="ej: isotipo, logo_symbol_color, stat_card"
            style={{
              display: "block",
              width: "100%",
              padding: "var(--space-2) var(--space-3)",
              border: "1.5px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              fontSize: "var(--font-size-sm)",
              color: "var(--color-text)",
              background: "var(--color-bg)",
              boxSizing: "border-box",
            }}
          />
        </div>
      )}

      <div
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-md)",
          padding: "var(--space-4)",
        }}
      >
        <p
          style={{
            margin: "0 0 var(--space-2)",
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-muted)",
          }}
        >
          <strong>Seleccionados:</strong>
        </p>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "var(--space-2)",
          }}
        >
          {formData.assetTypes.map((type) => (
            <code
              key={type}
              style={{
                background: "var(--color-bg)",
                padding: "var(--space-1) var(--space-2)",
                borderRadius: "var(--radius-sm)",
                fontSize: "var(--font-size-sm)",
              }}
            >
              {type}
            </code>
          ))}
        </div>
      </div>
    </section>
  );
}
