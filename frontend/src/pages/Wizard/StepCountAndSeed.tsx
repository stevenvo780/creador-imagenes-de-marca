/**
 * Paso 4: Cantidad de variaciones y seed salt (opcional).
 */
import { WizardFormData } from "./useWizardState";

interface StepCountAndSeedProps {
  formData: WizardFormData;
  onUpdate: (update: Partial<WizardFormData>) => void;
}

export function StepCountAndSeed({
  formData,
  onUpdate,
}: StepCountAndSeedProps) {
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
          Paso 4: Cantidad y reproducibilidad
        </h3>
        <p
          style={{
            margin: "0",
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-muted)",
          }}
        >
          Elige cuantas variaciones generar y si quieres resultados reproducibles.
        </p>
      </div>

      <div
        style={{
          background: "var(--color-surface)",
          border: "1.5px solid var(--color-border)",
          borderRadius: "var(--radius-md)",
          padding: "var(--space-4)",
        }}
      >
        <label htmlFor="wizard-count" style={labelStyle}>
          Cantidad de variaciones: <strong>{formData.count}</strong>
        </label>
        <input
          id="wizard-count"
          type="range"
          min={1}
          max={64}
          value={formData.count}
          onChange={(e) => onUpdate({ count: Number(e.target.value) })}
          style={{
            width: "100%",
            marginTop: "var(--space-3)",
            marginBottom: "var(--space-2)",
            height: "6px",
            borderRadius: "3px",
            background: "var(--color-border)",
            outline: "none",
            WebkitAppearance: "none",
          }}
          aria-valuemin={1}
          aria-valuemax={64}
          aria-valuenow={formData.count}
          aria-label="Cantidad de variaciones"
        />
        <style>{`
          input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 18px;
            height: 18px;
            borderRadius: 50%;
            background: var(--color-primary);
            cursor: pointer;
            border: 2px solid white;
            boxShadow: 0 2px 4px rgba(0,0,0,0.1);
          }
          input[type="range"]::-moz-range-thumb {
            width: 18px;
            height: 18px;
            borderRadius: 50%;
            background: var(--color-primary);
            cursor: pointer;
            border: 2px solid white;
            boxShadow: 0 2px 4px rgba(0,0,0,0.1);
          }
        `}</style>
        <p
          style={{
            margin: "var(--space-1) 0 0",
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-muted)",
          }}
        >
          A mayor cantidad, más tiempo de procesamiento.
        </p>
      </div>

      <div>
        <label htmlFor="wizard-seed-salt" style={labelStyle}>
          Seed salt (opcional)
        </label>
        <input
          id="wizard-seed-salt"
          type="text"
          value={formData.seedSalt}
          onChange={(e) => onUpdate({ seedSalt: e.target.value })}
          placeholder="Dejar vacío para aleatorio"
          maxLength={80}
          style={{
            display: "block",
            width: "100%",
            padding: "var(--space-2) var(--space-3)",
            border: "1.5px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            fontSize: "var(--font-size-base)",
            color: "var(--color-text)",
            background: "var(--color-bg)",
            boxSizing: "border-box",
          }}
        />
        <p
          style={{
            margin: "var(--space-2) 0 0",
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-muted)",
          }}
        >
          Usa el mismo seed para reproducir exactamente los mismos resultados.
        </p>
      </div>
    </section>
  );
}

const labelStyle: React.CSSProperties = {
  display: "block",
  marginBottom: "var(--space-2)",
  fontSize: "var(--font-size-sm)",
  fontWeight: 500,
  color: "var(--color-text)",
};
