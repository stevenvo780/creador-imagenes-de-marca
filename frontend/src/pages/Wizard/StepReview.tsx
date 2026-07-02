/**
 * Paso 5: Revisar la configuración antes de generar.
 */
import { Brand } from "../../api/client";
import { WizardFormData } from "./useWizardState";
import { axisLabel, assetTypeLabel, optionLabel } from "./terms";

interface StepReviewProps {
  formData: WizardFormData;
  brand: Brand | null;
}

interface ReviewRow {
  label: string;
  value: string;
  highlight?: boolean;
}

export function StepReview({ formData, brand }: StepReviewProps) {
  const rows: ReviewRow[] = [
    {
      label: "Marca",
      value: brand ? brand.name : "—",
      highlight: true,
    },
    {
      label: "Formatos",
      value:
        formData.assetTypes.length > 0
          ? formData.assetTypes.map((t) => assetTypeLabel(t)).join(", ")
          : "—",
    },
    {
      label: "Variaciones",
      value: String(formData.count),
    },
  ];

  // Opciones fijas
  if (Object.keys(formData.fixed).length > 0) {
    Object.entries(formData.fixed).forEach(([axisName, value]) => {
      rows.push({
        label: axisLabel(axisName),
        value: optionLabel(axisName, value, value),
      });
    });
  }

  // Opciones que varían
  if (formData.permuted.length > 0) {
    rows.push({
      label: "Opciones que varían",
      value: formData.permuted.map((n) => axisLabel(n)).join(", "),
    });
  }

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
          Todo listo para generar
        </h2>
        <p
          style={{
            margin: 0,
            fontSize: "var(--font-size-base)",
            color: "var(--slate-500)",
            lineHeight: 1.6,
          }}
        >
          Revisa el resumen y cuando estés lista/o, haz clic en{" "}
          <strong style={{ color: "var(--teal-600)" }}>
            "Generar mis variaciones"
          </strong>
          .
        </p>
      </div>

      {/* Tabla de resumen */}
      <div
        style={{
          border: "1px solid var(--line)",
          borderRadius: "var(--radius-lg)",
          overflow: "hidden",
        }}
      >
        {rows.map((row, i) => (
          <div
            key={row.label + i}
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 2fr",
              gap: "var(--space-4)",
              padding: "var(--space-3) var(--space-5)",
              borderBottom:
                i < rows.length - 1 ? "1px solid var(--line)" : "none",
              background: row.highlight ? "var(--mist)" : "var(--white)",
            }}
          >
            <span
              style={{
                fontSize: "var(--font-size-sm)",
                fontWeight: 600,
                color: "var(--slate-700)",
                alignSelf: "center",
              }}
            >
              {row.label}
            </span>
            <span
              style={{
                fontSize: "var(--font-size-sm)",
                color: row.highlight ? "var(--ink)" : "var(--slate-500)",
                fontWeight: row.highlight ? 700 : 400,
                alignSelf: "center",
                wordBreak: "break-word",
              }}
            >
              {row.value}
            </span>
          </div>
        ))}
      </div>

      {/* Aviso */}
      <div
        style={{
          display: "flex",
          gap: "var(--space-3)",
          padding: "var(--space-4)",
          background: "var(--mist)",
          borderRadius: "var(--radius-md)",
          borderLeft: "4px solid var(--teal)",
          fontSize: "var(--font-size-sm)",
          color: "var(--slate-700)",
          lineHeight: 1.6,
        }}
      >
        <span aria-hidden="true" style={{ fontSize: "1.1em" }}>💡</span>
        <span>
          La generación ocurre en segundo plano. Puedes ver el progreso
          en la siguiente pantalla y revisar los resultados cuando estén listos.
        </span>
      </div>
    </section>
  );
}
