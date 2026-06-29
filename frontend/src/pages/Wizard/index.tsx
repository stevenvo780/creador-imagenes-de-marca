/**
 * WizardFlow: Componente principal que orquesta todos los pasos del wizard.
 * Guía al usuario paso a paso para generar variaciones de identidad de marca.
 */
import { useEffect, useState } from "react";
import { batches, type Brand, ApiError } from "../../api/client";
import { Button, Steps } from "../../components";
import { useWizardState, WIZARD_STEPS } from "./useWizardState";
import { STEP_LABELS } from "./terms";
import { StepSelectBrand } from "./StepSelectBrand";
import { StepAssetTypes } from "./StepAssetTypes";
import { StepConfigureAxes } from "./StepConfigureAxes";
import { StepCountAndSeed } from "./StepCountAndSeed";
import { StepReview } from "./StepReview";
import { StepBatchProgress } from "./StepBatchProgress";

async function getBrandById(id: number): Promise<Brand | null> {
  try {
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

  useEffect(() => {
    if (wizard.formData.brandId === "") {
      setSelectedBrand(null);
      return;
    }
    let cancelled = false;
    getBrandById(wizard.formData.brandId as number).then((brand) => {
      if (!cancelled) setSelectedBrand(brand);
    });
    return () => { cancelled = true; };
  }, [wizard.formData.brandId]);

  const handleSubmit = async () => {
    if (wizard.formData.brandId === "") {
      wizard.setError("Selecciona una marca para continuar.");
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
          : "Hubo un error al iniciar la generación. Intenta de nuevo.",
      );
    } finally {
      wizard.setLoading(false);
    }
  };

  // Si hay un batch en progreso, mostrar pantalla de progreso
  if (wizard.batchId !== null) {
    return (
      <StepBatchProgress
        batchId={wizard.batchId}
        onCreateAnother={() => wizard.resetWizard()}
      />
    );
  }

  const stepIndex = WIZARD_STEPS.indexOf(wizard.currentStep);
  const isReviewStep = wizard.currentStep === "review";

  // Validación por paso: solo el paso de marca requiere selección antes de avanzar
  const canGoNext =
    stepIndex < WIZARD_STEPS.length - 1 &&
    (wizard.currentStep !== "brand" || wizard.formData.brandId !== "");

  const stepsConfig = WIZARD_STEPS.map((id) => ({
    id,
    label: STEP_LABELS[id] ?? id,
  }));

  return (
    <div style={{ display: "grid", gap: "var(--space-6)" }}>
      <h1 className="sr-only">Crear la identidad de tu marca</h1>

      {/* ── Indicador de pasos ─────────────────────────────────── */}
      <Steps steps={stepsConfig} currentIndex={stepIndex} />

      {/* ── Contenido del paso actual ──────────────────────────── */}
      <div
        style={{
          background: "var(--white)",
          border: "1px solid var(--line)",
          borderRadius: "var(--radius-lg)",
          padding: "var(--space-8) var(--space-6)",
          boxShadow: "var(--shadow-sm)",
          animation: "eikon-fadein 180ms ease",
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

      {/* ── Error ─────────────────────────────────────────────── */}
      {wizard.error && (
        <div
          role="alert"
          aria-live="assertive"
          aria-atomic="true"
          style={{
            background: "var(--error-bg)",
            border: "1px solid var(--error)",
            borderRadius: "var(--radius-md)",
            padding: "var(--space-3) var(--space-4)",
            color: "var(--error)",
            fontSize: "var(--font-size-sm)",
          }}
        >
          {wizard.error}
        </div>
      )}

      {/* ── Botones de navegación ─────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gap: "var(--space-3)",
          gridTemplateColumns: stepIndex > 0 ? "1fr 1fr" : "1fr",
        }}
      >
        {stepIndex > 0 && (
          <Button
            variant="secondary"
            onClick={wizard.prevStep}
            disabled={wizard.loading}
          >
            ← Anterior
          </Button>
        )}

        {!isReviewStep ? (
          <Button
            variant="primary"
            onClick={wizard.nextStep}
            disabled={!canGoNext || wizard.loading}
          >
            Siguiente →
          </Button>
        ) : (
          <Button
            variant="primary"
            busy={wizard.loading}
            onClick={handleSubmit}
          >
            {wizard.loading ? "Iniciando generación…" : "Generar mis variaciones"}
          </Button>
        )}
      </div>
    </div>
  );
}
