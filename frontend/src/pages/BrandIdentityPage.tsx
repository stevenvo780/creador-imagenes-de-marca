import { type FormEvent, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { brands as brandsApi, type Brand, ApiError } from "../api/client";
import { Button, Card, Steps, Spinner, EmptyState } from "../components";
import type { StepItem } from "../components";

interface LogoOption {
  style: string;
  seed: number;
  svg_data_uri: string;
}

const FLOW_STEPS: StepItem[] = [
  { id: "logo", label: "Elegí tu logo" },
  { id: "studio", label: "Ir al Estudio" },
];

export default function BrandIdentityPage() {
  const navigate = useNavigate();
  const { brandId } = useParams<{ brandId: string }>();
  const numericId = Number(brandId);

  const [brand, setBrand] = useState<Brand | null>(null);
  const [brandLoading, setBrandLoading] = useState(true);
  const [brandError, setBrandError] = useState("");

  const [options, setOptions] = useState<LogoOption[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [optionsError, setOptionsError] = useState("");

  const [selectedLogo, setSelectedLogo] = useState<LogoOption | null>(null);

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saved, setSaved] = useState(false);

  async function loadLogoOptions() {
    if (!numericId) return;
    setOptionsLoading(true);
    setOptionsError("");
    try {
      const res = await brandsApi.logoOptions(numericId, 24);
      setOptions(res.options);
    } catch (err) {
      setOptionsError(
        err instanceof ApiError
          ? err.detail
          : "No pudimos cargar las variaciones de logo.",
      );
    } finally {
      setOptionsLoading(false);
    }
  }

  async function loadBrand() {
    setBrandLoading(true);
    setBrandError("");
    try {
      const b = await brandsApi.get(numericId);
      setBrand(b);
      setOptions([]);
      setSelectedLogo(null);
      setSaved(false);
      setSaveError("");
      await loadLogoOptions();
    } catch (err) {
      setBrandError(
        err instanceof ApiError
          ? err.detail
          : "No pudimos cargar la marca.",
      );
    } finally {
      setBrandLoading(false);
    }
  }

  useEffect(() => {
    if (numericId) {
      void loadBrand();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [numericId]);

  useEffect(() => {
    if (brand && options.length > 0 && brand.logo_style && brand.logo_seed) {
      const current = options.find(
        (o) => o.style === brand.logo_style && o.seed === brand.logo_seed,
      );
      if (current) {
        setSelectedLogo(current);
      }
    }
  }, [brand, options]);

  useEffect(() => {
    if (saved) {
      const timer = setTimeout(() => setSaved(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [saved]);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!selectedLogo || !brand) return;
    setSaving(true);
    setSaveError("");
    setSaved(false);
    try {
      const updated = await brandsApi.update(brand.id, {
        logo_style: selectedLogo.style,
        logo_seed: selectedLogo.seed,
      });
      setBrand(updated);
      setSaved(true);
    } catch (err) {
      setSaveError(
        err instanceof ApiError
          ? err.detail
          : "No pudimos guardar la identidad.",
      );
    } finally {
      setSaving(false);
    }
  }

  const paletteEntries = brand
    ? (Object.entries(brand.palette as Record<string, string>).filter(
        ([, v]) => typeof v === "string" && v.length > 0,
      ) as [string, string][])
    : [];

  const typographyEntries = brand
    ? (Object.entries(brand.typography as Record<string, string>).filter(
        ([, v]) => typeof v === "string" && v.length > 0,
      ) as [string, string][])
    : [];

  const hasIdentityInfo = paletteEntries.length > 0 || typographyEntries.length > 0;

  const isCurrentLogo = (option: LogoOption) =>
    brand?.logo_style === option.style && brand?.logo_seed === option.seed;

  const isSelected = (option: LogoOption) =>
    selectedLogo?.style === option.style && selectedLogo?.seed === option.seed;

  const logoBgColor = (brand?.palette as Record<string, string> | undefined)?.bg || "#F5F0EB";

  const hasSelection = selectedLogo !== null;

  return (
    <section>
      {/* ── Cargando marca ──────────────────────────────────────────── */}

      {brandLoading && (
        <div
          role="status"
          aria-label="Cargando marca"
          aria-busy="true"
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "var(--space-4)",
            padding: "var(--space-16) var(--space-4)",
          }}
        >
          <Spinner size="lg" />
          <p
            style={{
              margin: 0,
              color: "var(--slate-500)",
              fontSize: "var(--font-size-sm)",
            }}
          >
            Cargando marca…
          </p>
        </div>
      )}

      {/* ── Error al cargar ────────────────────────────────────────── */}

      {!brandLoading && brandError && (
        <EmptyState
          title="No encontramos la marca"
          description={brandError}
          icon="⚠️"
          action={
            <Button variant="primary" onClick={loadBrand}>
              Reintentar
            </Button>
          }
        />
      )}

      {/* ── Contenido ──────────────────────────────────────────────── */}

      {!brandLoading && !brandError && brand && (
        <>
          {/* Cabecera: nombre + flujo + navegación */}
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: "var(--space-4)",
              flexWrap: "wrap",
              marginBottom: "var(--space-8)",
            }}
          >
            <div style={{ flex: 1 }}>
              <h1
                style={{
                  margin: "0 0 var(--space-1)",
                  fontFamily: "var(--font-display)",
                  fontSize: "var(--font-size-2xl)",
                  color: "var(--ink)",
                }}
              >
                {brand.name}
              </h1>
              <p
                style={{
                  margin: "var(--space-1) 0 0",
                  fontSize: "var(--font-size-sm)",
                  color: "var(--slate-500)",
                }}
              >
                Elegí el logo que mejor represente tu marca.
              </p>

              <div style={{ marginTop: "var(--space-3)" }}>
                <Steps steps={FLOW_STEPS} currentIndex={0} />
              </div>
            </div>

            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate(`/brands/${brand.id}/edit`)}
            >
              Editar marca
            </Button>
          </div>

          {/* ── Identidad de marca (paleta + tipografía consolidado) ─── */}

          {hasIdentityInfo && (
            <Card padding="md" style={{ marginBottom: "var(--space-8)" }}>
              <p
                style={{
                  margin: "0 0 var(--space-4)",
                  fontSize: "var(--font-size-sm)",
                  fontWeight: 600,
                  color: "var(--slate-700)",
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                Identidad de marca
              </p>

              <div
                style={{
                  display: "flex",
                  gap: "var(--space-8)",
                  flexWrap: "wrap",
                  alignItems: "flex-start",
                }}
              >
                {paletteEntries.length > 0 && (
                  <div>
                    <p
                      style={{
                        margin: "0 0 var(--space-3)",
                        fontSize: "var(--font-size-xs)",
                        fontWeight: 600,
                        color: "var(--slate-500)",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                      }}
                    >
                      Paleta
                    </p>
                    <div
                      style={{
                        display: "flex",
                        gap: "var(--space-3)",
                        flexWrap: "wrap",
                      }}
                    >
                      {paletteEntries.map(([key, color]) => (
                        <div
                          key={key}
                          title={color}
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            gap: "var(--space-1)",
                          }}
                        >
                          <span
                            style={{
                              display: "block",
                              width: 40,
                              height: 40,
                              borderRadius: "var(--radius-sm)",
                              background: color,
                              border: "1px solid var(--line)",
                              boxShadow: "var(--shadow-sm)",
                              cursor: "default",
                              transition: "transform var(--transition-fast)",
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.transform = "scale(1.15)";
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.transform = "";
                            }}
                          />
                          <span
                            style={{
                              fontSize: "var(--font-size-xs)",
                              color: "var(--slate-500)",
                            }}
                          >
                            {key}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {typographyEntries.length > 0 && (
                  <div>
                    <p
                      style={{
                        margin: "0 0 var(--space-3)",
                        fontSize: "var(--font-size-xs)",
                        fontWeight: 600,
                        color: "var(--slate-500)",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                      }}
                    >
                      Tipografía
                    </p>
                    <div
                      style={{
                        display: "flex",
                        gap: "var(--space-6)",
                        flexWrap: "wrap",
                      }}
                    >
                      {typographyEntries.map(([key, value]) => (
                        <div key={key} title={value}>
                          <span
                            style={{
                              fontSize: "var(--font-size-xs)",
                              color: "var(--slate-500)",
                              display: "block",
                              marginBottom: "var(--space-1)",
                            }}
                          >
                            {key}
                          </span>
                          <span
                            style={{
                              fontSize: "var(--font-size-lg)",
                              fontFamily: value,
                              color: "var(--ink)",
                              fontWeight: 700,
                              cursor: "default",
                            }}
                          >
                            {value}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* Grid de logos */}
          <div
            style={{ marginBottom: "var(--space-6)" }}
            aria-label="Variaciones de logo"
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "var(--space-4)",
                marginBottom: "var(--space-4)",
                flexWrap: "wrap",
              }}
            >
              <div>
                <h2
                  style={{
                    margin: 0,
                    fontFamily: "var(--font-display)",
                    fontSize: "var(--font-size-lg)",
                    color: "var(--ink)",
                  }}
                >
                  Variaciones de logo
                </h2>
                <p
                  style={{
                    margin: "var(--space-1) 0 0",
                    fontSize: "var(--font-size-xs)",
                    color: "var(--slate-500)",
                  }}
                >
                  Trae nuevas variaciones de logo para elegir.
                </p>
              </div>

              <Button
                variant="secondary"
                size="sm"
                busy={optionsLoading}
                onClick={() => {
                  setSelectedLogo(null);
                  setSaved(false);
                  setSaveError("");
                  void loadLogoOptions();
                }}
              >
                ↻ Regenerar
              </Button>
            </div>

            {/* Error de carga de opciones */}
            {optionsError && (
              <div
                role="alert"
                style={{
                  background: "var(--error-bg)",
                  border: "1px solid var(--error)",
                  borderRadius: "var(--radius-md)",
                  padding: "var(--space-3) var(--space-4)",
                  marginBottom: "var(--space-4)",
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-3)",
                }}
              >
                <p
                  style={{
                    margin: 0,
                    color: "var(--error)",
                    fontSize: "var(--font-size-sm)",
                  }}
                >
                  {optionsError}
                </p>
                <Button variant="secondary" size="sm" onClick={loadLogoOptions}>
                  Reintentar
                </Button>
              </div>
            )}

            {/* Loading de opciones */}
            {optionsLoading && (
              <div
                role="status"
                aria-label="Cargando variaciones"
                aria-busy="true"
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
                  gap: "var(--space-5)",
                }}
              >
                {Array.from({ length: 8 }, (_, i) => (
                  <div
                    key={i}
                    aria-hidden="true"
                    style={{
                      aspectRatio: "1",
                      borderRadius: "var(--radius-lg)",
                      background: "var(--mist)",
                      animation: "eikon-pulse 1.8s ease-in-out infinite",
                      animationDelay: `${i * 120}ms`,
                    }}
                  />
                ))}
              </div>
            )}

            {/* Grid de logos */}
            {!optionsLoading && !optionsError && options.length > 0 && (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
                  gap: "var(--space-5)",
                }}
              >
                {options.map((option, i) => {
                  const selected = isSelected(option);
                  const current = isCurrentLogo(option);

                  const borderStyle: string = selected || current
                    ? "3px solid var(--teal-600)"
                    : "2px solid var(--line)";

                  return (
                    <button
                      key={`${option.style}-${option.seed}`}
                      type="button"
                      onClick={() => {
                        setSelectedLogo(option);
                        setSaved(false);
                        setSaveError("");
                      }}
                      aria-label={`Logo ${i + 1}${current && brand ? " (actual)" : ""} — estilo ${option.style}`}
                      aria-pressed={selected}
                      autoFocus={i === 0}
                      style={{
                        position: "relative",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        aspectRatio: "1",
                        background: logoBgColor,
                        border: borderStyle,
                        borderRadius: "var(--radius-lg)",
                        cursor: "pointer",
                        padding: "var(--space-4)",
                        boxShadow: selected || current
                          ? "var(--shadow-md)"
                          : undefined,
                        transition:
                          "border var(--transition-fast), box-shadow var(--transition-fast), transform var(--transition-fast)",
                        outline: "none",
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.boxShadow = "var(--shadow-md)";
                        e.currentTarget.style.borderColor = "var(--teal)";
                        e.currentTarget.style.transform = "scale(1.03)";
                      }}
                      onMouseLeave={(e) => {
                        if (selected || current) {
                          e.currentTarget.style.boxShadow = "var(--shadow-md)";
                          e.currentTarget.style.borderColor = "var(--teal-600)";
                        } else {
                          e.currentTarget.style.boxShadow = "";
                          e.currentTarget.style.borderColor = "var(--line)";
                        }
                        e.currentTarget.style.transform = "";
                      }}
                      onFocus={(e) => {
                        e.currentTarget.style.boxShadow = "var(--shadow-md)";
                        e.currentTarget.style.borderColor = "var(--teal)";
                      }}
                      onBlur={(e) => {
                        if (selected || current) {
                          e.currentTarget.style.boxShadow = "var(--shadow-md)";
                          e.currentTarget.style.borderColor = "var(--teal-600)";
                        } else {
                          e.currentTarget.style.boxShadow = "";
                          e.currentTarget.style.borderColor = "var(--line)";
                        }
                      }}
                    >
                      <img
                        src={option.svg_data_uri}
                        alt={`Logo variación ${i + 1}`}
                        style={{
                          maxWidth: "100%",
                          maxHeight: "100%",
                          display: "block",
                          objectFit: "contain",
                        }}
                      />

                      {current && (
                        <span
                          style={{
                            position: "absolute",
                            top: "8px",
                            right: "8px",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                            background: "var(--teal-600)",
                            color: "#fff",
                            fontSize: "var(--font-size-xs)",
                            fontWeight: 600,
                            padding: "3px 8px",
                            borderRadius: "var(--radius-sm)",
                            lineHeight: 1.4,
                            boxShadow: "0 2px 6px rgba(0,0,0,0.15)",
                          }}
                        >
                          ✓ Actual
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Barra de acciones */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-4)",
              flexWrap: "wrap",
              padding: "var(--space-6) 0",
              borderTop: "1px solid var(--line)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
              <Button
                variant="primary"
                busy={saving}
                disabled={!hasSelection || saving}
                onClick={handleSave}
                style={{
                  fontSize: "var(--font-size-base)",
                  fontWeight: 700,
                  padding: "var(--space-3) var(--space-6)",
                  minHeight: 48,
                }}
              >
                {saving ? "Guardando…" : "Guardar identidad"}
              </Button>

              <span
                style={{
                  fontSize: "var(--font-size-xs)",
                  color: "var(--slate-500)",
                }}
              >
                Paso 1 de 2
              </span>
            </div>

            {saved && (
              <Button
                variant="secondary"
                onClick={() => navigate(`/studio?brand=${brand.id}`)}
                style={{
                  borderColor: "var(--teal)",
                  color: "var(--teal-600)",
                }}
              >
                Ir al Estudio →
              </Button>
            )}

            {!saved && (
              <span
                style={{
                  fontSize: "var(--font-size-xs)",
                  color: "var(--slate-400)",
                  fontStyle: "italic",
                  padding: "var(--space-2) var(--space-3)",
                  background: "var(--mist)",
                  borderRadius: "var(--radius-sm)",
                }}
              >
                Guardá tu logo para continuar al Estudio
              </span>
            )}
          </div>

          {/* Mensajes */}
          <div aria-live="assertive" aria-atomic="true">
            {saveError && (
              <p
                role="alert"
                style={{
                  margin: "var(--space-4) 0 0",
                  color: "var(--error)",
                  fontSize: "var(--font-size-sm)",
                  padding: "var(--space-2) var(--space-3)",
                  background: "var(--error-bg)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--error)",
                }}
              >
                {saveError}
              </p>
            )}

            {saved && !saveError && (
              <p
                style={{
                  margin: "var(--space-4) 0 0",
                  color: "var(--teal-600)",
                  fontSize: "var(--font-size-sm)",
                  fontWeight: 600,
                  padding: "var(--space-2) var(--space-3)",
                  background: "var(--mist)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--teal)",
                }}
              >
                Identidad guardada ✓
              </p>
            )}
          </div>
        </>
      )}
    </section>
  );
}
