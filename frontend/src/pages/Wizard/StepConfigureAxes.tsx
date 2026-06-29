/**
 * Paso 3: Elegir el estilo de las variaciones.
 * Para cada opción de diseño: fijar un valor o "que varíe".
 * Todo en español humano; sin términos técnicos crudos.
 */
import { useEffect, useState } from "react";
import { wizard, type Axis, type AxisOption, ApiError } from "../../api/client";
import { Spinner } from "../../components";
import { WizardFormData } from "./useWizardState";
import {
  axisLabel,
  optionLabel,
  optionDescription,
  AXIS_DESCRIPTIONS,
  ISOTYPE_STYLE_SKIP_DEFAULT,
  ISOTYPE_STYLE_FIRST_REAL,
} from "./terms";

interface StepConfigureAxesProps {
  formData: WizardFormData;
  onUpdate: (update: Partial<WizardFormData>) => void;
  onError: (error: string) => void;
}

/** Filtra las opciones de "isotype_style" para ocultar "none" al usuario. */
function visibleOptions(axis: Axis): AxisOption[] {
  if (axis.name === "isotype_style") {
    return axis.options.filter((o) => o.name !== ISOTYPE_STYLE_SKIP_DEFAULT);
  }
  return axis.options;
}

/** Primer valor visible para un eje (respeta filtro de "none"). */
function firstVisibleOption(axis: Axis): string {
  if (axis.name === "isotype_style") return ISOTYPE_STYLE_FIRST_REAL;
  return axis.options[0]?.name ?? "";
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
              : "No se pudieron cargar las opciones de diseño.",
          );
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [onError]);

  const handleToggleVary = (axisName: string, axis: Axis) => {
    const isPermuted = formData.permuted.includes(axisName);
    if (isPermuted) {
      // Pasar a FIJO con el primer valor visible
      onUpdate({
        permuted: formData.permuted.filter((n) => n !== axisName),
        fixed: {
          ...formData.fixed,
          [axisName]: firstVisibleOption(axis),
        },
      });
    } else {
      // Pasar a VARÍA: quitar de fixed
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
      fixed: { ...formData.fixed, [axisName]: value },
    });
  };

  if (loading) {
    return (
      <section style={{ display: "grid", gap: "var(--space-6)" }}>
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
            Elige el estilo
          </h2>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-3)",
            color: "var(--slate-500)",
            fontSize: "var(--font-size-sm)",
          }}
          aria-live="polite"
        >
          <Spinner size="sm" />
          Cargando opciones de diseño…
        </div>
      </section>
    );
  }

  // Conteo de opciones fijas y variables para el resumen
  const fixedCount = Object.keys(formData.fixed).length;
  const varyCount = formData.permuted.length;

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
          Elige el estilo
        </h2>
        <p
          style={{
            margin: 0,
            fontSize: "var(--font-size-base)",
            color: "var(--slate-500)",
            lineHeight: 1.6,
          }}
        >
          Para cada opción, fija un valor o deja que varíe entre las
          generaciones. Más variaciones = más diversidad.
        </p>
      </div>

      {/* Lista de ejes */}
      <div style={{ display: "grid", gap: "var(--space-4)" }}>
        {axes.map((axis) => {
          const isPermuted = formData.permuted.includes(axis.name);
          const fixedValue = formData.fixed[axis.name];
          const opts = visibleOptions(axis);
          const humanLabel = axisLabel(axis.name, axis.label);
          const description = AXIS_DESCRIPTIONS[axis.name] ?? null;

          return (
            <fieldset
              key={axis.name}
              style={{
                border: isPermuted
                  ? "1.5px solid var(--teal)"
                  : "1.5px solid var(--line)",
                borderRadius: "var(--radius-lg)",
                padding: "var(--space-4) var(--space-5)",
                margin: 0,
                display: "grid",
                gap: "var(--space-3)",
                background: isPermuted ? "var(--mist)" : "var(--white)",
                transition: "border-color var(--transition-fast), background var(--transition-fast)",
              }}
            >
              {/* Cabecera del eje */}
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  justifyContent: "space-between",
                  gap: "var(--space-4)",
                }}
              >
                <div style={{ flex: 1 }}>
                  <legend
                    style={{
                      fontSize: "var(--font-size-base)",
                      fontWeight: 700,
                      color: "var(--ink)",
                      padding: 0,
                      float: "none",
                    }}
                  >
                    {humanLabel}
                  </legend>
                  {description && (
                    <p
                      style={{
                        margin: "var(--space-1) 0 0",
                        fontSize: "var(--font-size-xs)",
                        color: "var(--slate-500)",
                      }}
                    >
                      {description}
                    </p>
                  )}
                </div>

                {/* Toggle: fijo / que varíe */}
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-2)",
                    cursor: "pointer",
                    flexShrink: 0,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={isPermuted}
                    onChange={() => handleToggleVary(axis.name, axis)}
                    style={{ accentColor: "var(--teal-600)", cursor: "pointer" }}
                    aria-label={`${humanLabel}: que varíe entre generaciones`}
                  />
                  <span
                    style={{
                      fontSize: "var(--font-size-sm)",
                      fontWeight: 600,
                      color: isPermuted ? "var(--teal-600)" : "var(--slate-500)",
                      whiteSpace: "nowrap",
                    }}
                  >
                    Que varíe
                  </span>
                </label>
              </div>

              {/* Valor fijo o indicador de variación */}
              {isPermuted ? (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-2)",
                    padding: "var(--space-2) var(--space-3)",
                    background: "rgba(47, 168, 154, 0.12)",
                    borderRadius: "var(--radius-md)",
                    fontSize: "var(--font-size-sm)",
                    color: "var(--teal-600)",
                    fontWeight: 500,
                  }}
                >
                  <span aria-hidden="true">↕</span>
                  Este valor va a variar entre las generaciones
                  <span
                    style={{
                      marginLeft: "auto",
                      fontSize: "var(--font-size-xs)",
                      color: "var(--slate-500)",
                      fontWeight: 400,
                    }}
                  >
                    {opts.length} opciones
                  </span>
                </div>
              ) : (
                <div style={{ display: "grid", gap: "var(--space-2)" }}>
                  <label
                    htmlFor={`axis-${axis.name}`}
                    style={{
                      fontSize: "var(--font-size-sm)",
                      fontWeight: 500,
                      color: "var(--slate-700)",
                    }}
                  >
                    Valor elegido
                  </label>
                  <select
                    id={`axis-${axis.name}`}
                    value={fixedValue || ""}
                    onChange={(e) => handleFixedChange(axis.name, e.target.value)}
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
                      cursor: "pointer",
                    }}
                  >
                    <option value="">— Elige una opción —</option>
                    {opts.map((opt) => (
                      <option key={opt.name} value={opt.name}>
                        {optionLabel(axis.name, opt.name, opt.label)}
                      </option>
                    ))}
                  </select>

                  {/* Descripción de la opción seleccionada (en español) */}
                  {fixedValue && optionDescription(axis.name, fixedValue) && (
                    <p
                      style={{
                        margin: 0,
                        fontSize: "var(--font-size-xs)",
                        color: "var(--slate-500)",
                      }}
                    >
                      {optionDescription(axis.name, fixedValue)}
                    </p>
                  )}
                </div>
              )}
            </fieldset>
          );
        })}
      </div>

      {/* Resumen compacto */}
      {(fixedCount > 0 || varyCount > 0) && (
        <div
          style={{
            padding: "var(--space-3) var(--space-4)",
            background: "var(--mist)",
            borderRadius: "var(--radius-md)",
            display: "flex",
            gap: "var(--space-6)",
            fontSize: "var(--font-size-sm)",
            color: "var(--slate-700)",
            flexWrap: "wrap",
          }}
        >
          {fixedCount > 0 && (
            <span>
              <strong>{fixedCount}</strong>{" "}
              {fixedCount === 1 ? "opción fija" : "opciones fijas"}
            </span>
          )}
          {varyCount > 0 && (
            <span style={{ color: "var(--teal-600)" }}>
              <strong>{varyCount}</strong>{" "}
              {varyCount === 1 ? "opción varía" : "opciones varían"}
            </span>
          )}
        </div>
      )}
    </section>
  );
}
