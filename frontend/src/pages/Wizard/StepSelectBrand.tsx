/**
 * Paso 1: Seleccionar brand.
 * Carga lista de brands y permite elegir uno.
 */
import { useEffect, useState } from "react";
import { wizard, type Brand, ApiError } from "../../api/client";
import { WizardFormData } from "./useWizardState";

interface StepSelectBrandProps {
  formData: WizardFormData;
  onUpdate: (update: Partial<WizardFormData>) => void;
  onError: (error: string) => void;
}

export function StepSelectBrand({
  formData,
  onUpdate,
  onError,
}: StepSelectBrandProps) {
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    wizard
      .brands()
      .then((res) => {
        if (!cancelled) {
          setBrands(res.items);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          onError(
            err instanceof ApiError
              ? err.detail
              : "Error al cargar brands.",
          );
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [onError]);

  const selectedBrand = brands.find(
    (b) => formData.brandId !== "" && b.id === formData.brandId,
  );

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
          Paso 1: Seleccionar brand
        </h3>
        <p
          style={{
            margin: "0 0 var(--space-3)",
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-muted)",
          }}
        >
          Elige el brand base para generar variaciones.
        </p>
      </div>

      {loading ? (
        <p
          style={{
            color: "var(--color-text-muted)",
            fontSize: "var(--font-size-sm)",
          }}
          aria-live="polite"
        >
          Cargando brands…
        </p>
      ) : (
        <div>
          <label
            htmlFor="wizard-brand-select"
            style={{
              display: "block",
              marginBottom: "var(--space-2)",
              fontSize: "var(--font-size-sm)",
              fontWeight: 500,
              color: "var(--color-text)",
            }}
          >
            Brand
          </label>
          <select
            id="wizard-brand-select"
            value={formData.brandId}
            onChange={(e) =>
              onUpdate({
                brandId:
                  e.target.value === "" ? "" : Number(e.target.value),
              })
            }
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
          >
            <option value="">— Seleccionar brand —</option>
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name} ({b.slug})
              </option>
            ))}
          </select>
        </div>
      )}

      {selectedBrand && (
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
            <strong>Seleccionado:</strong>
          </p>
          <p style={{ margin: "0", fontSize: "var(--font-size-base)", fontWeight: 600 }}>
            {selectedBrand.name}
          </p>
          <p
            style={{
              margin: "var(--space-1) 0 0",
              fontSize: "var(--font-size-sm)",
              color: "var(--color-text-muted)",
            }}
          >
            <code style={{ background: "var(--color-bg)", padding: "2px 4px" }}>
              {selectedBrand.slug}
            </code>
          </p>
        </div>
      )}
    </section>
  );
}
