/**
 * Paso 1: Elegir la marca con la que trabajar.
 */
import { useEffect, useState } from "react";
import { wizard, type Brand, ApiError } from "../../api/client";
import { Spinner } from "../../components";
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
              : "No se pudieron cargar las marcas. Intenta de nuevo.",
          );
          setLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [onError]);

  const selectedBrand = brands.find(
    (b) => formData.brandId !== "" && b.id === formData.brandId,
  );

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
          ¿Con qué marca vas a trabajar?
        </h2>
        <p
          style={{
            margin: 0,
            fontSize: "var(--font-size-base)",
            color: "var(--slate-500)",
            lineHeight: 1.6,
          }}
        >
          Elige la marca base. Eikón va a generar variaciones de identidad
          usando sus colores, tipografía y símbolo.
        </p>
      </div>

      {/* Selector */}
      {loading ? (
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
          Cargando marcas…
        </div>
      ) : brands.length === 0 ? (
        <div
          style={{
            padding: "var(--space-6)",
            border: "1.5px dashed var(--line)",
            borderRadius: "var(--radius-lg)",
            textAlign: "center",
            color: "var(--slate-500)",
            fontSize: "var(--font-size-sm)",
          }}
        >
          Todavía no tienes marcas creadas.{" "}
          <a href="/brands" style={{ color: "var(--teal-600)" }}>
            Crear una marca
          </a>
        </div>
      ) : (
        <div style={{ display: "grid", gap: "var(--space-3)" }}>
          <label
            htmlFor="wizard-brand-select"
            style={{
              display: "block",
              fontSize: "var(--font-size-sm)",
              fontWeight: 600,
              color: "var(--ink)",
              marginBottom: "var(--space-1)",
            }}
          >
            Tu marca
          </label>
          <select
            id="wizard-brand-select"
            value={formData.brandId}
            onChange={(e) =>
              onUpdate({
                brandId: e.target.value === "" ? "" : Number(e.target.value),
              })
            }
            style={{
              display: "block",
              width: "100%",
              padding: "var(--space-3) var(--space-4)",
              border: "1.5px solid var(--line)",
              borderRadius: "var(--radius-md)",
              fontSize: "var(--font-size-base)",
              color: "var(--ink)",
              background: "var(--paper)",
              boxSizing: "border-box",
              cursor: "pointer",
            }}
          >
            <option value="">— Elige tu marca —</option>
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Vista previa de la marca seleccionada */}
      {selectedBrand && (
        <div
          style={{
            background: "var(--mist)",
            border: "1px solid var(--line)",
            borderRadius: "var(--radius-lg)",
            padding: "var(--space-4) var(--space-5)",
            display: "grid",
            gap: "var(--space-2)",
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: "var(--font-size-xs)",
              fontWeight: 600,
              color: "var(--teal-600)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            Marca seleccionada
          </p>
          <p
            style={{
              margin: 0,
              fontFamily: "var(--font-display)",
              fontSize: "var(--font-size-xl)",
              fontWeight: 700,
              color: "var(--ink)",
            }}
          >
            {selectedBrand.name}
          </p>
          {selectedBrand.logo_text && (
            <p
              style={{
                margin: 0,
                fontSize: "var(--font-size-sm)",
                color: "var(--slate-500)",
              }}
            >
              Texto del logo: <em>{selectedBrand.logo_text}</em>
            </p>
          )}
        </div>
      )}
    </section>
  );
}
