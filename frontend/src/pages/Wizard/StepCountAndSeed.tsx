/**
 * Paso 4: Cuántas variaciones generar.
 * La "seed" se muestra como opción avanzada plegada.
 */
import { useState } from "react";
import { WizardFormData } from "./useWizardState";

interface StepCountAndSeedProps {
  formData: WizardFormData;
  onUpdate: (update: Partial<WizardFormData>) => void;
}

const QUICK_OPTIONS = [8, 16, 32, 48];

export function StepCountAndSeed({ formData, onUpdate }: StepCountAndSeedProps) {
  const [showSeed, setShowSeed] = useState(false);

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
          ¿Cuántas variaciones quieres?
        </h2>
        <p
          style={{
            margin: 0,
            fontSize: "var(--font-size-base)",
            color: "var(--slate-500)",
            lineHeight: 1.6,
          }}
        >
          Más variaciones = más opciones para elegir, pero tarda un poco
          más en generarse.
        </p>
      </div>

      {/* Opciones rápidas */}
      <div style={{ display: "grid", gap: "var(--space-3)" }}>
        <span
          style={{
            fontSize: "var(--font-size-sm)",
            fontWeight: 600,
            color: "var(--ink)",
          }}
        >
          Cantidad
        </span>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: "var(--space-2)",
          }}
        >
          {QUICK_OPTIONS.map((n) => {
            const isSelected = formData.count === n;
            return (
              <button
                key={n}
                type="button"
                onClick={() => onUpdate({ count: n })}
                style={{
                  padding: "var(--space-3) var(--space-2)",
                  border: isSelected
                    ? "2px solid var(--teal-600)"
                    : "1.5px solid var(--line)",
                  borderRadius: "var(--radius-md)",
                  background: isSelected ? "var(--mist)" : "var(--white)",
                  color: isSelected ? "var(--teal-600)" : "var(--ink)",
                  fontWeight: isSelected ? 700 : 500,
                  fontFamily: "var(--font-display)",
                  fontSize: "var(--font-size-lg)",
                  cursor: "pointer",
                  transition:
                    "border-color var(--transition-fast), background var(--transition-fast)",
                  textAlign: "center",
                }}
                aria-pressed={isSelected}
              >
                {n}
              </button>
            );
          })}
        </div>

        {/* Ajuste manual con slider */}
        <div
          style={{
            background: "var(--mist)",
            borderRadius: "var(--radius-md)",
            padding: "var(--space-4)",
          }}
        >
          <label
            htmlFor="wizard-count-slider"
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: "var(--font-size-sm)",
              fontWeight: 600,
              color: "var(--ink)",
              marginBottom: "var(--space-3)",
            }}
          >
            <span>Ajuste fino</span>
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "var(--font-size-base)",
                color: "var(--teal-600)",
              }}
            >
              {formData.count}
            </span>
          </label>
          <input
            id="wizard-count-slider"
            type="range"
            min={1}
            max={64}
            value={formData.count}
            onChange={(e) => onUpdate({ count: Number(e.target.value) })}
            style={{
              width: "100%",
              accentColor: "var(--teal-600)",
            }}
            aria-valuemin={1}
            aria-valuemax={64}
            aria-valuenow={formData.count}
            aria-label={`Cantidad de variaciones: ${formData.count}`}
          />
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginTop: "var(--space-1)",
              fontSize: "var(--font-size-xs)",
              color: "var(--slate-500)",
            }}
          >
            <span>1</span>
            <span>64</span>
          </div>
        </div>

        {/* Indicador de tiempo estimado */}
        <div
          style={{
            padding: "var(--space-2) var(--space-3)",
            background: "var(--mist)",
            borderRadius: "var(--radius-md)",
            fontSize: "var(--font-size-sm)",
            color: "var(--slate-700)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
          }}
        >
          <span aria-hidden="true">⏱</span>
          <span>
            {formData.count <= 8
              ? "Rápido — listo en segundos"
              : formData.count <= 24
                ? "Normal — menos de un minuto"
                : formData.count <= 48
                  ? "Puede tomar un par de minutos"
                  : "Generación larga — tómate un café ☕"}
          </span>
        </div>
      </div>

      {/* Sección avanzada: reproducibilidad */}
      <div style={{ display: "grid", gap: "var(--space-3)" }}>
        <button
          type="button"
          onClick={() => setShowSeed((v) => !v)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
            background: "none",
            border: "none",
            padding: 0,
            cursor: "pointer",
            fontSize: "var(--font-size-sm)",
            color: "var(--slate-500)",
            fontWeight: 500,
            textAlign: "left",
          }}
          aria-expanded={showSeed}
        >
          <span aria-hidden="true">{showSeed ? "▾" : "▸"}</span>
          Opciones avanzadas: reproducir los mismos resultados
        </button>

        {showSeed && (
          <div
            style={{
              display: "grid",
              gap: "var(--space-3)",
              padding: "var(--space-4)",
              background: "var(--mist)",
              borderRadius: "var(--radius-md)",
            }}
          >
            <p
              style={{
                margin: 0,
                fontSize: "var(--font-size-sm)",
                color: "var(--slate-500)",
              }}
            >
              Si ingresas una clave, puedes reproducir exactamente los mismos
              resultados en el futuro. Déjala vacía para resultados aleatorios.
            </p>
            <div>
              <label
                htmlFor="wizard-seed-salt"
                style={{
                  display: "block",
                  marginBottom: "var(--space-2)",
                  fontSize: "var(--font-size-sm)",
                  fontWeight: 600,
                  color: "var(--ink)",
                }}
              >
                Clave de reproducción
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
                  border: "1.5px solid var(--line)",
                  borderRadius: "var(--radius-md)",
                  fontSize: "var(--font-size-sm)",
                  color: "var(--ink)",
                  background: "var(--paper)",
                  boxSizing: "border-box",
                }}
              />
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
