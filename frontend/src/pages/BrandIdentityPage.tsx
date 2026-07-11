import { type FormEvent, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { brands as brandsApi, type Brand, ApiError } from "../api/client";
import { Badge, Button, Card, EmptyState, Spinner, Steps } from "../components";
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

  async function handleSave(e?: FormEvent) {
    e?.preventDefault();
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

  const isCurrentLogo = (option: LogoOption) =>
    brand?.logo_style === option.style && brand?.logo_seed === option.seed;

  const isSelected = (option: LogoOption) =>
    selectedLogo?.style === option.style && selectedLogo?.seed === option.seed;

  const hasSelection = selectedLogo !== null;

  return (
    <section>
      {brandLoading && (
        <Card
          padding="lg"
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
              color: "var(--text-muted)",
              fontSize: "var(--font-size-sm)",
            }}
          >
            Cargando marca…
          </p>
        </Card>
      )}

      {!brandLoading && brandError && (
        <EmptyState
          title="No encontramos la marca"
          description={brandError}
          icon="⚠️"
          action={
            <Button variant="primary" onClick={() => void loadBrand()}>
              Reintentar
            </Button>
          }
        />
      )}

      {!brandLoading && !brandError && brand && (
        <>
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
            <div className="eikon-page-intro" style={{ marginBottom: 0, flex: 1 }}>
              <p
                style={{
                  margin: "0 0 var(--space-2)",
                  color: "var(--teal)",
                  fontSize: "var(--font-size-xs)",
                  fontFamily: "var(--font-mono)",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                }}
              >
                Paso 1 de 2
              </p>
              <h1>{brand.name}</h1>
              <p>Elegí el logo que mejor represente tu marca antes de pasar al Estudio.</p>
              <div style={{ marginTop: "var(--space-4)", maxWidth: 520 }}>
                <Steps steps={FLOW_STEPS} currentIndex={0} />
              </div>
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => navigate(`/brands/${brand.id}/edit`)}
            >
              Editar marca
            </Button>
          </div>

          <div className="eikon-identity-layout">
            <main>
              <Card padding="lg" style={{ background: "var(--surface)", borderColor: "var(--border-strong)" }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "var(--space-4)",
                    marginBottom: "var(--space-5)",
                    flexWrap: "wrap",
                  }}
                >
                  <div>
                    <h2
                      style={{
                        margin: 0,
                        fontFamily: "var(--font-display)",
                        fontSize: "var(--font-size-2xl)",
                        color: "var(--text)",
                      }}
                    >
                      Variaciones de logo
                    </h2>
                    <p
                      style={{
                        margin: "var(--space-1) 0 0",
                        fontSize: "var(--font-size-sm)",
                        color: "var(--text-muted)",
                      }}
                    >
                      Seleccioná una pieza. El borde teal indica la elección activa.
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
                    Regenerar
                  </Button>
                </div>

                {optionsError && (
                  <div role="alert" style={errorPanelStyle}>
                    <p
                      style={{
                        margin: 0,
                        color: "var(--danger)",
                        fontSize: "var(--font-size-sm)",
                      }}
                    >
                      {optionsError}
                    </p>
                    <Button variant="secondary" size="sm" onClick={() => void loadLogoOptions()}>
                      Reintentar
                    </Button>
                  </div>
                )}

                {optionsLoading && (
                  <div
                    role="status"
                    aria-label="Cargando variaciones"
                    aria-busy="true"
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))",
                      gap: "var(--space-5)",
                    }}
                  >
                    {Array.from({ length: 8 }, (_, i) => (
                      <div
                        key={i}
                        aria-hidden="true"
                        style={{
                          aspectRatio: "1",
                          borderRadius: "var(--r-lg)",
                          background: "var(--surface-2)",
                          border: "1px solid var(--border)",
                          animation: "eikon-pulse 1.8s ease-in-out infinite",
                          animationDelay: `${i * 120}ms`,
                        }}
                      />
                    ))}
                  </div>
                )}

                {!optionsLoading && !optionsError && options.length > 0 && (
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))",
                      gap: "var(--space-5)",
                    }}
                    aria-label="Variaciones de logo"
                  >
                    {options.map((option, i) => {
                      const selected = isSelected(option);
                      const current = isCurrentLogo(option);

                      return (
                        <button
                          key={`${option.style}-${option.seed}`}
                          type="button"
                          onClick={() => {
                            setSelectedLogo(option);
                            setSaved(false);
                            setSaveError("");
                          }}
                          aria-label={`Logo ${i + 1}${current ? " (logo actual)" : ""} — estilo ${option.style}`}
                          aria-pressed={selected}
                          style={{
                            position: "relative",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            aspectRatio: "1",
                            background: "var(--bg)",
                            border: selected
                              ? "3px solid var(--teal)"
                              : current
                                ? "2px solid var(--amber)"
                                : "1px solid var(--border)",
                            borderRadius: "var(--r-lg)",
                            cursor: "pointer",
                            padding: "var(--space-5)",
                            boxShadow: selected ? "0 0 0 4px color-mix(in srgb, var(--teal) 16%, transparent), var(--shadow-2)" : "var(--shadow-1)",
                            transition:
                              "border var(--transition-fast), box-shadow var(--transition-fast), transform var(--transition-fast)",
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.transform = "translateY(-2px)";
                            e.currentTarget.style.boxShadow = "var(--shadow-2)";
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.transform = "";
                            e.currentTarget.style.boxShadow = selected
                              ? "0 0 0 4px color-mix(in srgb, var(--teal) 16%, transparent), var(--shadow-2)"
                              : "var(--shadow-1)";
                          }}
                        >
                          <img
                            src={option.svg_data_uri}
                            alt={`Logo variación ${i + 1}`}
                            style={{
                              maxWidth: "100%",
                              maxHeight: "100%",
                              objectFit: "contain",
                            }}
                          />

                          {selected && (
                            <span
                              aria-hidden="true"
                              style={{
                                position: "absolute",
                                top: "var(--space-2)",
                                left: "var(--space-2)",
                                width: 28,
                                height: 28,
                                borderRadius: "var(--radius-pill)",
                                background: "var(--teal)",
                                color: "var(--teal-ink)",
                                display: "inline-flex",
                                alignItems: "center",
                                justifyContent: "center",
                                fontWeight: 700,
                              }}
                            >
                              ✓
                            </span>
                          )}

                          {current && (
                            <Badge
                              label="Logo actual"
                              variant="current"
                              style={{
                                position: "absolute",
                                top: "var(--space-2)",
                                right: "var(--space-2)",
                              }}
                            />
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}
              </Card>
            </main>

            <aside className="eikon-identity-side">
              <Card
                padding="lg"
                style={{
                  display: "grid",
                  gap: "var(--space-6)",
                  borderColor: "var(--border-strong)",
                }}
              >
                <div>
                  <p style={eyebrowStyle}>Identidad de marca</p>
                  <h2
                    style={{
                      margin: 0,
                      fontFamily: "var(--font-display)",
                      fontSize: "var(--font-size-2xl)",
                      color: "var(--text)",
                    }}
                  >
                    Material activo
                  </h2>
                </div>

                <section>
                  <p style={sectionLabelStyle}>Paleta</p>
                  {paletteEntries.length > 0 ? (
                    <div style={{ display: "grid", gap: "var(--space-3)" }}>
                      {paletteEntries.map(([key, color]) => (
                        <div
                          key={key}
                          title={color}
                          style={{
                            display: "grid",
                            gridTemplateColumns: "32px 1fr",
                            alignItems: "center",
                            gap: "var(--space-3)",
                          }}
                        >
                          <span
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: "var(--r-sm)",
                              background: color,
                              border: "1px solid var(--border-strong)",
                              boxShadow: "var(--shadow-1)",
                            }}
                          />
                          <span
                            style={{
                              color: "var(--text-muted)",
                              fontSize: "var(--font-size-xs)",
                              fontFamily: "var(--font-mono)",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                            }}
                          >
                            {key}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p style={mutedTextStyle}>Sin paleta cargada.</p>
                  )}
                </section>

                <section>
                  <p style={sectionLabelStyle}>Tipografía</p>
                  {typographyEntries.length > 0 ? (
                    <div style={{ display: "grid", gap: "var(--space-3)" }}>
                      {typographyEntries.map(([key, value]) => (
                        <div key={key} title={value}>
                          <span
                            style={{
                              display: "block",
                              marginBottom: "var(--space-1)",
                              fontSize: "var(--font-size-xs)",
                              color: "var(--text-faint)",
                              fontFamily: "var(--font-mono)",
                            }}
                          >
                            {key}
                          </span>
                          <span
                            style={{
                              fontSize: "var(--font-size-lg)",
                              fontFamily: value,
                              color: "var(--text)",
                              fontWeight: 700,
                              lineHeight: 1.2,
                            }}
                          >
                            {value}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p style={mutedTextStyle}>Sin tipografías cargadas.</p>
                  )}
                </section>

                <div style={{ display: "grid", gap: "var(--space-3)" }}>
                  <Button
                    variant="primary"
                    busy={saving}
                    disabled={!hasSelection || saving}
                    onClick={() => void handleSave()}
                    style={{ width: "100%" }}
                  >
                    {saving ? "Guardando…" : "Guardar identidad"}
                  </Button>

                  <Button
                    variant="secondary"
                    disabled={!saved}
                    onClick={() => navigate(`/studio?brand=${brand.id}`)}
                    style={{
                      width: "100%",
                      borderColor: saved ? "var(--teal)" : "var(--border)",
                      color: saved ? "var(--teal)" : "var(--text-faint)",
                    }}
                  >
                    Ir al Estudio
                  </Button>
                </div>

                <div aria-live="assertive" aria-atomic="true">
                  {saveError && (
                    <p role="alert" style={errorMessageStyle}>
                      {saveError}
                    </p>
                  )}

                  {saved && !saveError && (
                    <p
                      style={{
                        margin: 0,
                        color: "var(--ok)",
                        fontSize: "var(--font-size-sm)",
                        fontWeight: 700,
                        padding: "var(--space-3)",
                        background: "color-mix(in srgb, var(--ok) 14%, transparent)",
                        borderRadius: "var(--r-md)",
                        border: "1px solid color-mix(in srgb, var(--ok) 48%, var(--border))",
                      }}
                    >
                      Identidad guardada ✓
                    </p>
                  )}

                  {!saved && !saveError && (
                    <p
                      style={{
                        margin: 0,
                        fontSize: "var(--font-size-xs)",
                        color: "var(--text-faint)",
                      }}
                    >
                      Guardá tu logo para habilitar el paso al Estudio.
                    </p>
                  )}
                </div>
              </Card>
            </aside>
          </div>
        </>
      )}
    </section>
  );
}

const eyebrowStyle: React.CSSProperties = {
  margin: "0 0 var(--space-2)",
  color: "var(--teal)",
  fontSize: "var(--font-size-xs)",
  fontFamily: "var(--font-mono)",
  textTransform: "uppercase",
  letterSpacing: "0.08em",
};

const sectionLabelStyle: React.CSSProperties = {
  margin: "0 0 var(--space-3)",
  color: "var(--text-muted)",
  fontSize: "var(--font-size-xs)",
  fontFamily: "var(--font-mono)",
  textTransform: "uppercase",
  letterSpacing: "0.08em",
};

const mutedTextStyle: React.CSSProperties = {
  margin: 0,
  color: "var(--text-muted)",
  fontSize: "var(--font-size-sm)",
};

const errorPanelStyle: React.CSSProperties = {
  background: "var(--error-bg)",
  border: "1px solid var(--danger)",
  borderRadius: "var(--r-md)",
  padding: "var(--space-4)",
  marginBottom: "var(--space-5)",
  display: "flex",
  alignItems: "center",
  gap: "var(--space-3)",
  flexWrap: "wrap",
};

const errorMessageStyle: React.CSSProperties = {
  margin: 0,
  color: "var(--danger)",
  fontSize: "var(--font-size-sm)",
  padding: "var(--space-3)",
  background: "var(--error-bg)",
  borderRadius: "var(--r-md)",
  border: "1px solid var(--danger)",
};
