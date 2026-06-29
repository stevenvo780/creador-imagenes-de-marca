/**
 * Paso 3: Configurar ejes (FIXED vs PERMUTE).
 * Para cada eje, elegir entre fijar a un valor o permitir que varíe.
 */
import { useEffect, useState } from "react";
import { wizard, type Axis, ApiError } from "../../api/client";
import { WizardFormData } from "./useWizardState";

interface StepConfigureAxesProps {
  formData: WizardFormData;
  onUpdate: (update: Partial<WizardFormData>) => void;
  onError: (error: string) => void;
}

export function StepConfigureAxes({
  formData,
  onUpdate,
  onError,
}: StepConfigureAxesProps) {
  const [axes, setAxes] = useState<Axis[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    wizard
      .axes()
      .then((res) => {
        if (!cancelled) {
          setAxes(res.axes);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          onError(
            err instanceof ApiError
              ? err.detail
              : "Error al cargar ejes.",
          );
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [onError]);

  const handleTogglePermute = (axisName: string) => {
    const isPermuted = formData.permuted.includes(axisName);
    if (isPermuted) {
      // Pasar a FIXED con primer valor
      const axis = axes.find((a) => a.name === axisName);
      if (axis && axis.options.length > 0) {
        onUpdate({
          permuted: formData.permuted.filter((n) => n !== axisName),
          fixed: {
            ...formData.fixed,
            [axisName]: axis.options[0].name,
          },
        });
      }
    } else {
      // Pasar a PERMUTE, remover de fixed
      const newFixed = { ...formData.fixed };
      delete newFixed[axisName];
      onUpdate({
        permuted: [...formData.permuted, axisName],
        fixed: newFixed,
      });
    }
  };

  const handleFixedChange = (axisName: string, value: string) => {
    onUpdate({
      fixed: {
        ...formData.fixed,
        [axisName]: value,
      },
    });
  };

  if (loading) {
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
            Paso 3: Configurar ejes
          </h3>
        </div>
        <p
          style={{
            color: "var(--color-text-muted)",
            fontSize: "var(--font-size-sm)",
          }}
          aria-live="polite"
        >
          Cargando ejes…
        </p>
      </section>
    );
  }

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
          Paso 3: Configurar ejes
        </h3>
        <p
          style={{
            margin: "0",
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-muted)",
          }}
        >
          Para cada eje: elige un valor fijo o permite que varíe en las
          generaciones.
        </p>
      </div>

      <div style={{ display: "grid", gap: "var(--space-4)" }}>
        {axes.map((axis) => {
          const isPermuted = formData.permuted.includes(axis.name);
          const fixedValue = formData.fixed[axis.name];

          return (
            <fieldset
              key={axis.name}
              style={{
                border: "1.5px solid var(--color-border)",
                borderRadius: "var(--radius-md)",
                padding: "var(--space-4)",
                margin: 0,
                display: "grid",
                gap: "var(--space-3)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "var(--space-3)",
                }}
              >
                <div>
                  <legend
                    style={{
                      fontSize: "var(--font-size-sm)",
                      fontWeight: 600,
                      color: "var(--color-text)",
                    }}
                  >
                    {axis.label}
                  </legend>
                  <p
                    style={{
                      margin: "var(--space-1) 0 0",
                      fontSize: "var(--font-size-xs)",
                      color: "var(--color-text-muted)",
                    }}
                  >
                    {axis.options.length} opciones disponibles
                  </p>
                </div>

                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-2)",
                    fontSize: "var(--font-size-sm)",
                    fontWeight: 500,
                    cursor: "pointer",
                    whiteSpace: "nowrap",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={isPermuted}
                    onChange={() => handleTogglePermute(axis.name)}
                    title="Marcar para permitir que este eje varíe"
                  />
                  Permutar
                </label>
              </div>

              {isPermuted ? (
                <div
                  style={{
                    background: "rgba(26,122,110,0.04)",
                    padding: "var(--space-2) var(--space-3)",
                    borderRadius: "var(--radius-sm)",
                    fontSize: "var(--font-size-sm)",
                    color: "var(--color-text-muted)",
                  }}
                >
                  Todas las opciones ({axis.options.length}) serán generadas.
                </div>
              ) : (
                <div>
                  <label
                    htmlFor={`axis-${axis.name}`}
                    style={{
                      display: "block",
                      marginBottom: "var(--space-2)",
                      fontSize: "var(--font-size-sm)",
                      fontWeight: 500,
                      color: "var(--color-text)",
                    }}
                  >
                    Valor fijo
                  </label>
                  <select
                    id={`axis-${axis.name}`}
                    value={fixedValue || ""}
                    onChange={(e) =>
                      handleFixedChange(axis.name, e.target.value)
                    }
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
                  >
                    <option value="">— Seleccionar opción —</option>
                    {axis.options.map((opt) => (
                      <option key={opt.name} value={opt.name}>
                        {opt.label}
                      </option>
                    ))}
                  </select>

                  {fixedValue && (
                    <p
                      style={{
                        margin: "var(--space-2) 0 0",
                        fontSize: "var(--font-size-xs)",
                        color: "var(--color-text-muted)",
                      }}
                    >
                      {axis.options.find((o) => o.name === fixedValue)
                        ?.description || ""}
                    </p>
                  )}
                </div>
              )}
            </fieldset>
          );
        })}
      </div>

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
            fontWeight: 600,
            color: "var(--color-text)",
          }}
        >
          Resumen de configuración
        </p>

        {Object.keys(formData.fixed).length > 0 && (
          <div style={{ marginBottom: "var(--space-2)" }}>
            <p
              style={{
                margin: "var(--space-1) 0",
                fontSize: "var(--font-size-sm)",
                color: "var(--color-text-muted)",
              }}
            >
              <strong>Fijos:</strong>{" "}
              {Object.entries(formData.fixed)
                .map(([k, v]) => `${k}=${v}`)
                .join(", ")}
            </p>
          </div>
        )}

        {formData.permuted.length > 0 && (
          <p
            style={{
              margin: "var(--space-1) 0",
              fontSize: "var(--font-size-sm)",
              color: "var(--color-text-muted)",
            }}
          >
            <strong>Permutados:</strong> {formData.permuted.join(", ")}
          </p>
        )}
      </div>
    </section>
  );
}
