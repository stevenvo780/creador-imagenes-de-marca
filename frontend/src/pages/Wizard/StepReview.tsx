/**
 * Paso 5: Revisar configuración antes de enviar.
 */
import { Brand } from "../../api/client";
import { WizardFormData } from "./useWizardState";

interface StepReviewProps {
  formData: WizardFormData;
  brand: Brand | null;
}

export function StepReview({ formData, brand }: StepReviewProps) {
  const summaryItems = [
    {
      label: "Brand",
      value: brand ? `${brand.name} (${brand.slug})` : "—",
    },
    {
      label: "Tipos de asset",
      value: formData.assetTypes.join(", "),
    },
    {
      label: "Cantidad de variaciones",
      value: String(formData.count),
    },
    {
      label: "Ejes fijos",
      value:
        Object.keys(formData.fixed).length > 0
          ? Object.entries(formData.fixed)
              .map(([k, v]) => `${k} = ${v}`)
              .join(", ")
          : "Ninguno",
    },
    {
      label: "Ejes permutados",
      value: formData.permuted.length > 0 ? formData.permuted.join(", ") : "Ninguno",
    },
    {
      label: "Seed salt",
      value: formData.seedSalt || "(aleatorio)",
    },
  ];

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
          Paso 5: Revisar y enviar
        </h3>
        <p
          style={{
            margin: "0",
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-muted)",
          }}
        >
          Verifica la configuración antes de crear el batch.
        </p>
      </div>

      <div
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-md)",
          padding: "var(--space-4)",
          display: "grid",
          gap: "var(--space-3)",
        }}
      >
        {summaryItems.map((item) => (
          <div key={item.label} style={{ borderBottom: "1px solid var(--color-border)", paddingBottom: "var(--space-2)" }}>
            <p
              style={{
                margin: "0 0 var(--space-1)",
                fontSize: "var(--font-size-sm)",
                fontWeight: 600,
                color: "var(--color-text)",
              }}
            >
              {item.label}
            </p>
            <p
              style={{
                margin: 0,
                fontSize: "var(--font-size-base)",
                color: "var(--color-text-muted)",
              }}
            >
              <code
                style={{
                  background: "var(--color-bg)",
                  padding: "var(--space-1) var(--space-2)",
                  borderRadius: "var(--radius-sm)",
                  fontFamily: "monospace",
                }}
              >
                {item.value}
              </code>
            </p>
          </div>
        ))}
      </div>

      <div
        style={{
          background: "rgba(26,122,110,0.04)",
          border: "1px solid var(--color-primary-muted)",
          borderRadius: "var(--radius-md)",
          padding: "var(--space-4)",
        }}
      >
        <p
          style={{
            margin: 0,
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text)",
          }}
        >
          Al hacer clic en <strong>"Crear batch"</strong>, se encolará la tarea
          de generación. El procesamiento ocurre en segundo plano.
        </p>
      </div>
    </section>
  );
}
