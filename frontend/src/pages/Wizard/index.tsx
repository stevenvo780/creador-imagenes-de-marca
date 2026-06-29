/**
 * WizardFlow: Componente principal que orquesta todos los pasos del wizard.
 * Maneja navegación, validación y envío del batch.
 */
import { useEffect, useState } from "react";
import { batches, type Brand, ApiError } from "../../api/client";
import { useWizardState, WIZARD_STEPS } from "./useWizardState";
import { StepSelectBrand } from "./StepSelectBrand";
import { StepAssetTypes } from "./StepAssetTypes";
import { StepConfigureAxes } from "./StepConfigureAxes";
import { StepCountAndSeed } from "./StepCountAndSeed";
import { StepReview } from "./StepReview";
import { StepBatchProgress } from "./StepBatchProgress";

// Simulación local de GET /api/v1/wizard/brands para obtener brand por ID
// (ya que el state de formData solo tiene el ID, necesitamos obtener el objeto Brand)
async function getBrandById(id: number): Promise<Brand | null> {
  try {
    // Idealmente esto vendría del servidor, pero usamos el endpoint de brands
    const res = await fetch(`/api/v1/brands/${id}`, {
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export function WizardFlow() {
  const wizard = useWizardState();
  const [selectedBrand, setSelectedBrand] = useState<Brand | null>(null);

  // Cargar brand object cuando cambia brandId
  useEffect(() => {
    if (wizard.formData.brandId === "") {
      setSelectedBrand(null);
      return;
    }
    let cancelled = false;
    getBrandById(wizard.formData.brandId as number)
      .then((brand) => {
        if (!cancelled) setSelectedBrand(brand);
      });
    return () => {
      cancelled = true;
    };
  }, [wizard.formData.brandId]);

  const handleSubmit = async () => {
    if (wizard.formData.brandId === "") {
      wizard.setError("Selecciona un brand.");
      return;
    }

    wizard.setLoading(true);
    wizard.setError("");

    try {
      const batch = await batches.create({
        brand_id: wizard.formData.brandId as number,
        asset_types: wizard.formData.assetTypes,
        fixed: wizard.formData.fixed,
        permuted: wizard.formData.permuted,
        count: wizard.formData.count,
        seed_salt: wizard.formData.seedSalt,
      });
      wizard.setBatchId(batch.id);
    } catch (err) {
      wizard.setError(
        err instanceof ApiError
          ? err.detail
          : "Error al crear batch.",
      );
    } finally {
      wizard.setLoading(false);
    }
  };

  // Si hay un batch en progreso, mostrar ese paso
  if (wizard.batchId !== null) {
    return (
      <StepBatchProgress
        batchId={wizard.batchId}
        onCreateAnother={() => {
          wizard.resetWizard();
        }}
      />
    );
  }

  const stepIndex = WIZARD_STEPS.indexOf(wizard.currentStep);
  const canPrev = stepIndex > 0;
  const canNext =
    stepIndex < WIZARD_STEPS.length - 1 &&
    wizard.formData.brandId !== "";

  const isReviewStep = wizard.currentStep === "review";

  return (
    <div style={{ display: "grid", gap: "var(--space-6)" }}>
      {/* Progress indicator */}
      <div
        style={{
          display: "grid",
          gap: "var(--space-3)",
        }}
      >
        <div
          style={{
            display: "flex",
            gap: "var(--space-2)",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          {WIZARD_STEPS.map((step, i) => (
            <div
              key={step}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-2)",
                flex: 1,
              }}
            >
              <div
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "50%",
                  background:
                    i <= stepIndex
                      ? "var(--color-primary)"
                      : "var(--color-border)",
                  color: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "var(--font-size-sm)",
                  fontWeight: 600,
                }}
              >
                {i + 1}
              </div>
              {i < WIZARD_STEPS.length - 1 && (
                <div
                  style={{
                    height: "2px",
                    background:
                      i < stepIndex
                        ? "var(--color-primary)"
                        : "var(--color-border)",
                    flex: 1,
                  }}
                />
              )}
            </div>
          ))}
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: "var(--font-size-xs)",
            color: "var(--color-text-muted)",
          }}
        >
          {WIZARD_STEPS.map((step) => (
            <span key={step} style={{ flex: 1, textAlign: "center" }}>
              {step === "brand"
                ? "Brand"
                : step === "assets"
                  ? "Assets"
                  : step === "axes"
                    ? "Ejes"
                    : step === "count"
                      ? "Cantidad"
                      : "Revisar"}
            </span>
          ))}
        </div>
      </div>

      {/* Contenido del paso actual */}
      <div
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-lg)",
          padding: "var(--space-6)",
        }}
      >
        {wizard.currentStep === "brand" && (
          <StepSelectBrand
            formData={wizard.formData}
            onUpdate={wizard.setFormData}
            onError={wizard.setError}
          />
        )}
        {wizard.currentStep === "assets" && (
          <StepAssetTypes
            formData={wizard.formData}
            onUpdate={wizard.setFormData}
          />
        )}
        {wizard.currentStep === "axes" && (
          <StepConfigureAxes
            formData={wizard.formData}
            onUpdate={wizard.setFormData}
            onError={wizard.setError}
          />
        )}
        {wizard.currentStep === "count" && (
          <StepCountAndSeed
            formData={wizard.formData}
            onUpdate={wizard.setFormData}
          />
        )}
        {wizard.currentStep === "review" && (
          <StepReview formData={wizard.formData} brand={selectedBrand} />
        )}
      </div>

      {/* Error alert */}
      {wizard.error && (
        <div
          aria-live="assertive"
          aria-atomic="true"
          style={{
            background: "var(--color-error-bg)",
            border: "1px solid var(--color-error)",
            borderRadius: "var(--radius-md)",
            padding: "var(--space-3) var(--space-4)",
            color: "var(--color-error)",
            fontSize: "var(--font-size-sm)",
          }}
          role="alert"
        >
          {wizard.error}
        </div>
      )}

      {/* Botones de navegación */}
      <div
        style={{
          display: "grid",
          gap: "var(--space-3)",
          gridTemplateColumns: canPrev ? "1fr 1fr" : "1fr",
        }}
      >
        {canPrev && (
          <button
            onClick={wizard.prevStep}
            disabled={wizard.loading}
            style={{
              padding: "var(--space-3) var(--space-4)",
              background: "var(--color-surface)",
              border: "1.5px solid var(--color-border)",
              borderRadius: "var(--radius-md)",
              fontSize: "var(--font-size-base)",
              fontWeight: 600,
              cursor: wizard.loading ? "not-allowed" : "pointer",
              color: "var(--color-text)",
              opacity: wizard.loading ? 0.6 : 1,
            }}
          >
            ← Anterior
          </button>
        )}

        {!isReviewStep ? (
          <button
            onClick={wizard.nextStep}
            disabled={!canNext || wizard.loading}
            style={{
              padding: "var(--space-3) var(--space-4)",
              background: canNext ? "var(--color-primary)" : "var(--color-primary-muted)",
              color: "#fff",
              border: "none",
              borderRadius: "var(--radius-md)",
              fontSize: "var(--font-size-base)",
              fontWeight: 600,
              cursor: !canNext || wizard.loading ? "not-allowed" : "pointer",
              opacity: !canNext ? 0.6 : 1,
            }}
          >
            Siguiente →
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={wizard.loading}
            aria-busy={wizard.loading}
            style={{
              padding: "var(--space-3) var(--space-4)",
              background: wizard.loading
                ? "var(--color-primary-muted)"
                : "var(--color-primary)",
              color: "#fff",
              border: "none",
              borderRadius: "var(--radius-md)",
              fontSize: "var(--font-size-base)",
              fontWeight: 600,
              cursor: wizard.loading ? "not-allowed" : "pointer",
            }}
          >
            {wizard.loading ? "Encolando…" : "Crear batch"}
          </button>
        )}
      </div>
    </div>
  );
}
