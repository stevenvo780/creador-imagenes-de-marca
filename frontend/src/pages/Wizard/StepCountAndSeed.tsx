/**
 * Paso 4: Cuántas variaciones generar.
 * La "seed" se muestra como opción avanzada plegada.
 *
 * GUARD: el máximo factible = producto de opciones visibles de los ejes en
 * "que varíe". Si nada varía, maxFeasible = 1 y se guía al usuario para que
 * vuelva al paso anterior. El slider y los botones rápidos nunca superan ese
 * máximo, y el contador se clampea automáticamente si baja.
 */
import { useState, useEffect } from "react";
import { WizardFormData } from "./useWizardState";

interface StepCountAndSeedProps {
  formData: WizardFormData;
  onUpdate: (update: Partial<WizardFormData>) => void;
}

const ALL_QUICK_OPTIONS = [8, 16, 32, 48];

/**
 * Calcula el número máximo de combinaciones factibles.
 * Es el producto de la cantidad de opciones visibles de cada eje en "que varíe".
 * Si ningún eje varía, devuelve 1 (solo hay una configuración posible).
 */
function calcMaxFeasible(
  permuted: string[],
  axisOptionCounts: Record<string, number>,
): number {
  if (permuted.length === 0) return 1;
  return permuted.reduce(
    (product, axisName) => product * (axisOptionCounts[axisName] ?? 1),
    1,
  );
}

export function StepCountAndSeed({ formData, onUpdate }: StepCountAndSeedProps) {
  const [showSeed, setShowSeed] = useState(false);

  const maxFeasible = calcMaxFeasible(
    formData.permuted,
    formData.axisOptionCounts,
  );

  const sliderMax = Math.min(64, maxFeasible);
  const nothingVaries = formData.permuted.length === 0;
  const feasibilityReached = !nothingVaries && maxFeasible < 64;

  // Clampear el contador si el máximo factible bajó por debajo del valor actual
  useEffect(() => {
    if (formData.count > maxFeasible) {
      onUpdate({ count: maxFeasible });
    }
    // Se ejecuta sólo cuando cambia maxFeasible; no incluir formData.count para
    // evitar bucle: onUpdate → formData → effect → onUpdate.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [maxFeasible]);

  // Botones rápidos que caben dentro del máximo factible
  const quickOptions = ALL_QUICK_OPTIONS.filter((n) => n <= maxFeasible);

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

      {/* ── Aviso: nada varía ── */}
      {nothingVaries && (
        <div
          role="note"
          aria-live="polite"
          style={{
            display: "flex",
            gap: "var(--space-3)",
            alignItems: "flex-start",
            padding: "var(--space-4) var(--space-4)",
            background: "var(--mist)",
            border: "1.5px solid var(--teal)",
            borderRadius: "var(--radius-md)",
          }}
        >
          <span aria-hidden="true" style={{ fontSize: "1.1rem", lineHeight: 1 }}>
            ℹ
          </span>
          <div
            style={{
              fontSize: "var(--font-size-sm)",
              color: "var(--ink)",
              lineHeight: 1.5,
            }}
          >
            <strong>Solo podés generar 1 variación</strong> porque todos los
            ejes de diseño están fijos.{" "}
            <span style={{ color: "var(--slate-500)" }}>
              Volvé al paso anterior y activá "Que varíe" en al menos una
              opción para explorar más combinaciones.
            </span>
          </div>
        </div>
      )}

      {/* ── Info: máximo acotado por los ejes elegidos ── */}
      {feasibilityReached && (
        <div
          role="note"
          style={{
            padding: "var(--space-3) var(--space-4)",
            background: "var(--mist)",
            border: "1px solid var(--line)",
            borderRadius: "var(--radius-md)",
            fontSize: "var(--font-size-sm)",
            color: "var(--slate-700)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
          }}
        >
          <span aria-hidden="true">⚙</span>
          Con los ejes configurados podés generar hasta{" "}
          <strong style={{ color: "var(--teal-600)" }}>{maxFeasible}</strong>{" "}
          combinaciones distintas.
        </div>
      )}

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

        {quickOptions.length > 0 ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: `repeat(${quickOptions.length}, 1fr)`,
              gap: "var(--space-2)",
            }}
          >
            {quickOptions.map((n) => {
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
        ) : null}

        {/* Ajuste manual con slider */}
        <div
          style={{
            background: "var(--mist)",
            borderRadius: "var(--radius-md)",
            padding: "var(--space-4)",
            opacity: nothingVaries ? 0.5 : 1,
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
              {Math.min(formData.count, sliderMax)}
            </span>
          </label>
          <input
            id="wizard-count-slider"
            type="range"
            min={1}
            max={sliderMax}
            value={Math.min(formData.count, sliderMax)}
            disabled={nothingVaries}
            onChange={(e) =>
              onUpdate({
                count: Math.min(Number(e.target.value), maxFeasible),
              })
            }
            style={{
              width: "100%",
              accentColor: "var(--teal-600)",
              cursor: nothingVaries ? "not-allowed" : "pointer",
            }}
            aria-valuemin={1}
            aria-valuemax={sliderMax}
            aria-valuenow={Math.min(formData.count, sliderMax)}
            aria-label={`Cantidad de variaciones: ${Math.min(formData.count, sliderMax)}`}
            aria-disabled={nothingVaries}
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
            <span>{sliderMax}</span>
          </div>
        </div>

        {/* Indicador de tiempo estimado */}
        {!nothingVaries && (
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
                    : "Generación larga — tómate un café"}
            </span>
          </div>
        )}
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
