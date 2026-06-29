/**
 * Hook para gestionar estado multi-paso del wizard.
 * Mantiene: paso actual, valores del formulario, errores, y estado de carga.
 */
import { useState, useCallback } from "react";

export interface WizardFormData {
  brandId: number | "";
  assetTypes: string[];
  fixed: Record<string, string>; // eje_name → valor elegido
  permuted: string[]; // lista de ejes a permutar
  count: number;
  seedSalt: string;
}

export const WIZARD_STEPS = ["brand", "assets", "axes", "count", "review"] as const;
export type WizardStep = (typeof WIZARD_STEPS)[number];

interface WizardState {
  currentStep: WizardStep;
  formData: WizardFormData;
  error: string;
  loading: boolean;
  batchId: number | null;
}

export function useWizardState() {
  const [state, setState] = useState<WizardState>({
    currentStep: "brand",
    formData: {
      brandId: "",
      // Default: símbolo + logo con símbolo (más útil que solo isotipo)
      assetTypes: ["isotipo", "logo_symbol_color"],
      // isotype_style arranca en "lettermark" (excluir "none" por defecto)
      fixed: { isotype_style: "lettermark" },
      permuted: [],
      count: 16,
      seedSalt: "",
    },
    error: "",
    loading: false,
    batchId: null,
  });

  const goToStep = useCallback((step: WizardStep) => {
    setState((prev) => ({ ...prev, currentStep: step, error: "" }));
  }, []);

  const nextStep = useCallback(() => {
    const currentIndex = WIZARD_STEPS.indexOf(state.currentStep);
    if (currentIndex < WIZARD_STEPS.length - 1) {
      goToStep(WIZARD_STEPS[currentIndex + 1]);
    }
  }, [state.currentStep, goToStep]);

  const prevStep = useCallback(() => {
    const currentIndex = WIZARD_STEPS.indexOf(state.currentStep);
    if (currentIndex > 0) {
      goToStep(WIZARD_STEPS[currentIndex - 1]);
    }
  }, [state.currentStep, goToStep]);

  const setFormData = useCallback(
    (update: Partial<WizardFormData>) => {
      setState((prev) => ({
        ...prev,
        formData: { ...prev.formData, ...update },
      }));
    },
    [],
  );

  const setError = useCallback((error: string) => {
    setState((prev) => ({ ...prev, error }));
  }, []);

  const setLoading = useCallback((loading: boolean) => {
    setState((prev) => ({ ...prev, loading }));
  }, []);

  const setBatchId = useCallback((batchId: number | null) => {
    setState((prev) => ({ ...prev, batchId }));
  }, []);

  const resetWizard = useCallback(() => {
    setState({
      currentStep: "brand",
      formData: {
        brandId: "",
        assetTypes: ["isotipo", "logo_symbol_color"],
        fixed: { isotype_style: "lettermark" },
        permuted: [],
        count: 16,
        seedSalt: "",
      },
      error: "",
      loading: false,
      batchId: null,
    });
  }, []);

  return {
    currentStep: state.currentStep,
    formData: state.formData,
    error: state.error,
    loading: state.loading,
    batchId: state.batchId,
    goToStep,
    nextStep,
    prevStep,
    setFormData,
    setError,
    setLoading,
    setBatchId,
    resetWizard,
  };
}
