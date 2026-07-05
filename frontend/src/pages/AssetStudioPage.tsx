import { type FormEvent, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  brands as brandsApi,
  batches,
  type Brand,
  type Variation,
  ApiError,
} from "../api/client";
import { Button, Card, EmptyState, SelectField, Spinner } from "../components";

// ── Tipos de asset curados ──────────────────────────────────────────────────

interface AssetTypeOption {
  value: string;
  label: string;
}

interface AssetTypeGroup {
  category: string;
  types: AssetTypeOption[];
}

const ASSET_TYPES_GROUPED: AssetTypeGroup[] = [
  {
    category: "Redes sociales",
    types: [
      { value: "ig_post", label: "Instagram Post (1080×1080)" },
      { value: "ig_story", label: "Instagram Story (1080×1920)" },
      { value: "ig_carousel", label: "Instagram Carousel (1080×1350)" },
      { value: "ig_reel_cover", label: "Instagram Reel Cover (1080×1920)" },
      { value: "x_header", label: "X/Twitter Header (1500×500)" },
      { value: "x_post", label: "X/Twitter Post (1200×675)" },
      { value: "linkedin_banner", label: "LinkedIn Banner (1584×396)" },
      { value: "linkedin_post", label: "LinkedIn Post (1200×627)" },
      { value: "yt_banner", label: "YouTube Banner (2560×1440)" },
      { value: "yt_thumbnail", label: "YouTube Thumbnail (1280×720)" },
      { value: "tiktok_cover", label: "TikTok Cover (1080×1920)" },
      { value: "fb_cover", label: "Facebook Cover (1640×624)" },
    ],
  },
  {
    category: "Web",
    types: [
      { value: "web_hero_mobile", label: "Banner web (móvil, 750×1334)" },
      { value: "email_header", label: "Email Header (600×300)" },
    ],
  },
  {
    category: "Anuncios",
    types: [
      { value: "ad_rectangle", label: "Anuncio rectangular (300×250)" },
    ],
  },
  {
    category: "Marca e impresión",
    types: [
      { value: "business_card", label: "Tarjeta de negocio (1050×600)" },
      { value: "og_general", label: "OG General (1200×630)" },
      { value: "og_product", label: "OG Producto (1200×630)" },
      { value: "poster_a4", label: "Póster A4 (1240×1754)" },
    ],
  },
];

const ASSET_LABEL: Record<string, string> = Object.fromEntries(
  ASSET_TYPES_GROUPED.flatMap((group) =>
    group.types.map((t) => [t.value, t.label]),
  ),
);

function extractAssetDimensions(label: string | undefined): string {
  const match = label?.match(/\d{3,4}\s*×\s*\d{3,4}/);
  return match ? match[0].replace(/\s+/g, " ") : "Dimensiones variables";
}

// ── Campos de contenido por tipo ────────────────────────────────────────────

interface ContentField {
  key: string;
  label: string;
  placeholder: string;
}

const CONTENT_FIELDS: Record<string, ContentField[]> = {
  business_card: [
    { key: "empresa", label: "Empresa", placeholder: "Ej.: Elenxos S.A." },
    { key: "cargo", label: "Cargo", placeholder: "Ej.: Director de arte" },
    { key: "email", label: "Email", placeholder: "Ej.: hola@elenxos.com" },
    { key: "telefono", label: "Teléfono", placeholder: "Ej.: +54 11 5555-0000" },
  ],
  og_general: [
    { key: "titulo", label: "Título", placeholder: "Ej.: El arte de preguntar" },
    { key: "subtitulo", label: "Subtítulo", placeholder: "Ej.: Una guía para educadores" },
    { key: "url", label: "URL", placeholder: "Ej.: elenxos.com" },
  ],
  og_product: [
    { key: "producto", label: "Producto", placeholder: "Ej.: Curso de lógica" },
    { key: "precio", label: "Precio", placeholder: "Ej.: USD 49" },
    { key: "url", label: "URL", placeholder: "Ej.: elenxos.com/cursos/logica" },
  ],
  ad_rectangle: [
    { key: "titulo", label: "Título", placeholder: "Ej.: Aprendé a debatir" },
    { key: "cta", label: "Llamado a la acción", placeholder: "Ej.: Inscribite ahora" },
    { key: "url", label: "URL", placeholder: "Ej.: elenxos.com" },
  ],
  web_hero_desktop: [
    { key: "headline", label: "Titular", placeholder: "Ej.: Transformá tu manera de pensar" },
    { key: "tagline", label: "Bajada", placeholder: "Ej.: Cursos de filosofía, lógica y retórica" },
    { key: "cta", label: "Llamado a la acción", placeholder: "Ej.: Explorar cursos" },
  ],
  ig_post: [
    { key: "titulo", label: "Título/Headline", placeholder: "Ej.: Nuevo artículo publicado" },
    { key: "copy", label: "Copy/Caption", placeholder: "Ej.: Lee nuestro último análisis..." },
    { key: "etiqueta", label: "Hashtag principal", placeholder: "Ej.: #filosofia" },
  ],
  ig_story: [
    { key: "titulo", label: "Titular", placeholder: "Ej.: Pregunta del día" },
    { key: "copy", label: "Texto adicional", placeholder: "Ej.: ¿Cuál es tu respuesta?" },
  ],
  ig_carousel: [
    { key: "titulo", label: "Título", placeholder: "Ej.: 5 preguntas esenciales" },
    { key: "copy", label: "Descripción", placeholder: "Ej.: Deslizá para ver más..." },
  ],
  ig_reel_cover: [
    { key: "titulo", label: "Titular", placeholder: "Ej.: Pregunta del día" },
    { key: "copy", label: "Texto adicional", placeholder: "Ej.: ¿Cuál es tu respuesta?" },
    { key: "url", label: "URL", placeholder: "Ej.: elenxos.com" },
  ],
  x_header: [
    { key: "titulo", label: "Texto principal", placeholder: "Ej.: Ideas para pensar mejor" },
    { key: "copy", label: "Copy", placeholder: "Ej.: Filosofía aplicada para equipos" },
    { key: "url", label: "URL", placeholder: "Ej.: elenxos.com" },
  ],
  x_post: [
    { key: "titulo", label: "Texto del post", placeholder: "Ej.: Reflexión sobre la democracia..." },
    { key: "url", label: "URL", placeholder: "Ej.: elenxos.com/articulo" },
  ],
  linkedin_banner: [
    { key: "titulo", label: "Titular", placeholder: "Ej.: Liderando el cambio en educación" },
    { key: "subtitulo", label: "Subtítulo", placeholder: "Ej.: Comunidad profesional" },
    { key: "copy", label: "Descripción", placeholder: "Ej.: En esta publicación comparto..." },
    { key: "url", label: "URL", placeholder: "Ej.: elenxos.com" },
  ],
  linkedin_post: [
    { key: "titulo", label: "Titular", placeholder: "Ej.: Liderando el cambio en educación" },
    { key: "copy", label: "Descripción", placeholder: "Ej.: En esta publicación comparto..." },
    { key: "url", label: "URL", placeholder: "Ej.: elenxos.com" },
  ],
  fb_cover: [
    { key: "titulo", label: "Título", placeholder: "Ej.: Comunidad Elenxos" },
    { key: "subtitulo", label: "Subtítulo", placeholder: "Ej.: Filosofía aplicada" },
  ],
  yt_thumbnail: [
    { key: "titulo", label: "Texto principal", placeholder: "Ej.: ¿Qué es la lógica?" },
    { key: "numero", label: "Número/Episodio (opcional)", placeholder: "Ej.: EP 12" },
  ],
  yt_banner: [
    { key: "titulo", label: "Texto principal", placeholder: "Ej.: ¿Qué es la lógica?" },
  ],
  tiktok_cover: [
    { key: "titulo", label: "Titular", placeholder: "Ej.: Pregunta del día" },
    { key: "copy", label: "Texto adicional", placeholder: "Ej.: ¿Cuál es tu respuesta?" },
  ],
  poster_a4: [
    { key: "titulo", label: "Título del evento/producto", placeholder: "Ej.: Congreso de Filosofía 2026" },
    { key: "subtitulo", label: "Subtítulo", placeholder: "Ej.: Reflexiones sobre la era digital" },
    { key: "copy", label: "Descripción", placeholder: "Ej.: 12-14 de marzo | Auditorio Nacional" },
    { key: "url", label: "Sitio web / CTA", placeholder: "Ej.: congreso.elenxos.com" },
  ],
  email_header: [
    { key: "titulo", label: "Titular del email", placeholder: "Ej.: Novedades de esta semana" },
    { key: "copy", label: "Subtítulo", placeholder: "Ej.: Los temas más relevantes para vos" },
  ],
  web_hero_mobile: [
    { key: "titulo", label: "Titular", placeholder: "Ej.: Transformá tu manera de pensar" },
    { key: "subtitulo", label: "Bajada", placeholder: "Ej.: Cursos de filosofía, lógica y retórica" },
    { key: "url", label: "URL", placeholder: "Ej.: elenxos.com/cursos" },
  ],
};

// ── Página principal ────────────────────────────────────────────────────────

export function AssetStudioPage() {
  const [searchParams] = useSearchParams();
  const preselectedBrandId = searchParams.get("brand");

  // Marcas
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loadingBrands, setLoadingBrands] = useState(true);
  const [loadError, setLoadError] = useState("");

  // Selección
  const [selectedBrandId, setSelectedBrandId] = useState<number | null>(
    preselectedBrandId ? Number(preselectedBrandId) : null,
  );
  const [selectedAssetType, setSelectedAssetType] = useState("");
  const [contentValues, setContentValues] = useState<Record<string, string>>({});

  // Generación
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [generateError, setGenerateError] = useState("");

  // Resultado
  const [resultVariation, setResultVariation] = useState<Variation | null>(null);

  // ── Cargar marcas ───────────────────────────────────────────────────────

  async function loadBrands() {
    setLoadingBrands(true);
    setLoadError("");
    try {
      const res = await brandsApi.list();
      setBrands(res.items);
    } catch (err) {
      setLoadError(
        err instanceof ApiError ? err.detail : "No pudimos cargar tus marcas.",
      );
    } finally {
      setLoadingBrands(false);
    }
  }

  useEffect(() => {
    void loadBrands();
  }, []);

  const selectedBrand = brands.find((b) => b.id === selectedBrandId) ?? null;
  const brandHasLogo = selectedBrand
    ? (selectedBrand.logo_style && selectedBrand.logo_style.length > 0)
    : false;

  // ── Handlers ────────────────────────────────────────────────────────────

  function handleBrandChange(id: number) {
    setSelectedBrandId(id);
    setGenerateError("");
    setResultVariation(null);
    setProgress(null);
  }

  function handleAssetTypeChange(type: string) {
    setSelectedAssetType(type);
    setContentValues({});
    setGenerateError("");
    setResultVariation(null);
    setProgress(null);
  }

  function handleContentChange(key: string, value: string) {
    setContentValues((prev) => ({ ...prev, [key]: value }));
  }

  // ── Generar ─────────────────────────────────────────────────────────────

  async function handleGenerate(e: FormEvent) {
    e.preventDefault();
    if (!selectedBrandId || !selectedAssetType) return;

    setGenerateError("");
    setGenerating(true);
    setProgress(null);
    setResultVariation(null);

    try {
      const batch = await batches.create({
        brand_id: selectedBrandId,
        asset_types: [selectedAssetType],
        fixed: {},
        permuted: [],
        count: 1,
        render_mode: "client",
        content: Object.keys(contentValues).length > 0 ? contentValues : undefined,
      });

      const { renderBatchClientSide } = await import("../render");
      const res = await renderBatchClientSide(batch.id, (done, total) => {
        setProgress({ done, total });
      });

      if (res.uploaded === 0) {
        setGenerateError("No se pudo generar ninguna imagen en tu navegador. Intentá de nuevo.");
        setGenerating(false);
        return;
      }

      const vars = await batches.variations(batch.id);
      if (vars.items.length > 0) {
        setResultVariation(vars.items[0]);
      } else {
        setGenerateError("La generación terminó pero no se encontraron variaciones.");
      }
    } catch (err) {
      setGenerateError(
        err instanceof ApiError ? err.detail : "Hubo un problema al generar el asset.",
      );
    } finally {
      setGenerating(false);
      setProgress(null);
    }
  }

  function handleReset() {
    setSelectedAssetType("");
    setContentValues({});
    setGenerateError("");
    setResultVariation(null);
    setProgress(null);
  }

  // ── Render ──────────────────────────────────────────────────────────────

  const currentFields = CONTENT_FIELDS[selectedAssetType] ?? [];
  const selectedAssetLabel = selectedAssetType
    ? ASSET_LABEL[selectedAssetType] ?? selectedAssetType
    : "";
  const selectedDimensions = extractAssetDimensions(selectedAssetLabel);
  const selectedBrandInitial = (selectedBrand?.logo_symbol || selectedBrand?.name || "E")
    .trim()
    .charAt(0)
    .toUpperCase();
  const canGenerate =
    !!selectedBrand && brandHasLogo && !!selectedAssetType && !generating && !resultVariation;

  return (
    <section>
      <div className="eikon-page-intro">
        <h1>Estudio de activos</h1>
        <p>
          Generá banners, tarjetas, imágenes OG y más, heredando la identidad visual de tu marca.
        </p>
      </div>

      {loadingBrands && (
        <Card
          padding="lg"
          role="status"
          aria-label="Cargando marcas"
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
          <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "var(--font-size-sm)" }}>
            Cargando marcas…
          </p>
        </Card>
      )}

      {!loadingBrands && loadError && (
        <p style={errorStyle} role="alert">
          {loadError}
        </p>
      )}

      {!loadingBrands && !loadError && brands.length === 0 && (
        <EmptyState
          title="Todavía no tenés marcas"
          description="Creá tu primera marca para empezar a generar activos visuales."
          icon="🏷️"
          action={
            <Link to="/brands">
              <Button variant="primary">+ Crear mi primera marca</Button>
            </Link>
          }
        />
      )}

      {!loadingBrands && !loadError && brands.length > 0 && (
        <div className="eikon-studio-grid">
          <form onSubmit={handleGenerate} className="eikon-studio-panel">
            <Card
              padding="lg"
              style={{
                display: "grid",
                gap: "var(--space-6)",
                borderColor: "var(--border-strong)",
              }}
            >
              <section aria-labelledby="studio-brand-heading">
                <h2 style={sectionTitleStyle} id="studio-brand-heading">
                  1. Marca
                </h2>
                <SelectField
                  id="brand-select"
                  label="Marca"
                  hint="Seleccioná la identidad visual que querés usar."
                  value={selectedBrandId ?? ""}
                  onChange={(e) => handleBrandChange(Number(e.target.value))}
                >
                  <option value="" disabled>
                    Seleccioná una marca
                  </option>
                  {brands.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </SelectField>

                {selectedBrand && !brandHasLogo && (
                  <div
                    style={{
                      marginTop: "var(--space-4)",
                      background: "color-mix(in srgb, var(--amber) 14%, transparent)",
                      border: "1px solid color-mix(in srgb, var(--amber) 55%, var(--border))",
                      borderRadius: "var(--r-md)",
                      padding: "var(--space-3) var(--space-4)",
                      display: "grid",
                      gap: "var(--space-2)",
                    }}
                  >
                    <p
                      style={{
                        margin: 0,
                        fontSize: "var(--font-size-sm)",
                        color: "var(--text)",
                        fontWeight: 700,
                      }}
                    >
                      Esta marca todavía no tiene logo fijo.
                    </p>
                    <p
                      style={{
                        margin: 0,
                        fontSize: "var(--font-size-sm)",
                        color: "var(--text-muted)",
                      }}
                    >
                      Andá a la página de identidad y elegí un logo antes de generar activos.
                    </p>
                    <Link
                      to={`/brands/${selectedBrand.id}/identity`}
                      style={{
                        fontSize: "var(--font-size-sm)",
                        color: "var(--teal)",
                        fontWeight: 700,
                        justifySelf: "start",
                      }}
                    >
                      Fijar identidad
                    </Link>
                  </div>
                )}
              </section>

              <section aria-labelledby="studio-type-heading">
                <h2 style={sectionTitleStyle} id="studio-type-heading">
                  2. Tipo
                </h2>
                <SelectField
                  id="asset-type-select"
                  label="Tipo de activo"
                  hint="Cada tipo define formato y campos de contenido."
                  value={selectedAssetType}
                  onChange={(e) => handleAssetTypeChange(e.target.value)}
                  disabled={!selectedBrand || !brandHasLogo}
                >
                  <option value="" disabled>
                    Seleccioná un tipo
                  </option>
                  {ASSET_TYPES_GROUPED.map((group) => (
                    <optgroup key={group.category} label={group.category}>
                      {group.types.map((t) => (
                        <option key={t.value} value={t.value}>
                          {t.label}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </SelectField>
              </section>

              <section aria-labelledby="studio-content-heading">
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: "var(--space-3)",
                    alignItems: "baseline",
                    marginBottom: "var(--space-3)",
                  }}
                >
                  <h2 style={{ ...sectionTitleStyle, marginBottom: 0 }} id="studio-content-heading">
                    3. Contenido
                  </h2>
                  {selectedAssetType && (
                    <span
                      style={{
                        color: "var(--text-muted)",
                        fontFamily: "var(--font-mono)",
                        fontSize: "var(--font-size-xs)",
                      }}
                    >
                      {selectedDimensions}
                    </span>
                  )}
                </div>

                {!selectedAssetType && (
                  <p style={mutedTextStyle}>
                    Elegí un tipo de activo para ver los campos disponibles.
                  </p>
                )}

                {selectedAssetType && (
                  <>
                    <p style={mutedTextStyle}>
                      Completá los textos que aparecerán en el activo. Todos los campos son opcionales.
                    </p>
                    <div style={{ display: "grid", gap: "var(--space-4)" }}>
                      {currentFields.map((f) => (
                        <div key={f.key}>
                          <label htmlFor={`content-${f.key}`} style={labelStyle}>
                            {f.label}
                          </label>
                          <input
                            id={`content-${f.key}`}
                            type="text"
                            value={contentValues[f.key] ?? ""}
                            onChange={(e) => handleContentChange(f.key, e.target.value)}
                            placeholder={f.placeholder}
                            style={inputStyle}
                          />
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </section>

              {generateError && (
                <div role="alert" style={errorPanelStyle}>
                  <p style={{ margin: 0, color: "var(--danger)", fontSize: "var(--font-size-sm)", fontWeight: 700 }}>
                    {generateError}
                  </p>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setGenerateError("");
                      setResultVariation(null);
                      setProgress(null);
                    }}
                  >
                    Reintentar
                  </Button>
                </div>
              )}

              <Button
                type="submit"
                variant="primary"
                busy={generating}
                disabled={!canGenerate}
                style={{
                  width: "100%",
                  minHeight: 52,
                  fontSize: "var(--font-size-lg)",
                }}
              >
                {generating ? "Generando…" : resultVariation ? "Generado" : "Generar"}
              </Button>
            </Card>
          </form>

          <Card
            padding="lg"
            className="eikon-studio-easel"
            style={{
              display: "grid",
              gap: "var(--space-5)",
              background: "var(--surface)",
              borderColor: "var(--border-strong)",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: "var(--space-4)",
                alignItems: "flex-start",
                flexWrap: "wrap",
              }}
            >
              <div>
                <h2
                  style={{
                    margin: "0 0 var(--space-1)",
                    fontFamily: "var(--font-display)",
                    fontSize: "var(--font-size-2xl)",
                    color: "var(--text)",
                  }}
                >
                  Lienzo
                </h2>
                <p style={{ ...mutedTextStyle, margin: 0 }}>
                  {selectedAssetLabel || "Elegí un formato para preparar la vista previa."}
                </p>
              </div>
              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "var(--font-size-xs)",
                  color: "var(--text-muted)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--r-sm)",
                  padding: "var(--space-1) var(--space-2)",
                  background: "var(--surface-2)",
                }}
              >
                {selectedAssetType ? selectedDimensions : "0000 × 0000"}
              </span>
            </div>

            <div
              className="eikon-preview-shell"
              style={{
                position: "relative",
                display: "grid",
                placeItems: "center",
                overflow: "hidden",
                border: "1px solid var(--border-strong)",
                borderRadius: "var(--r-lg)",
                background: "var(--bg)",
                boxShadow: "inset 0 0 0 1px var(--border), var(--shadow-2)",
                padding: "var(--space-6)",
              }}
            >
              {resultVariation ? (
                <img
                  src={resultVariation.file_url}
                  alt="Vista previa del activo generado"
                  style={{
                    maxWidth: "100%",
                    maxHeight: "100%",
                    borderRadius: "var(--r-sm)",
                    boxShadow: "var(--shadow-2)",
                    objectFit: "contain",
                  }}
                />
              ) : (
                <div
                  style={{
                    width: "min(100%, 360px)",
                    aspectRatio: "1 / 1",
                    border: "1px dashed var(--border-strong)",
                    borderRadius: "var(--r-lg)",
                    display: "grid",
                    placeItems: "center",
                    padding: "var(--space-6)",
                    textAlign: "center",
                    background: "var(--surface)",
                  }}
                >
                  {generating ? (
                    <div
                      style={{
                        display: "grid",
                        gap: "var(--space-4)",
                        justifyItems: "center",
                        width: "100%",
                      }}
                    >
                      <Spinner size="lg" />
                      <div>
                        <p
                          style={{
                            margin: 0,
                            fontFamily: "var(--font-display)",
                            fontSize: "var(--font-size-xl)",
                            fontWeight: 700,
                            color: "var(--text)",
                          }}
                          aria-live="polite"
                        >
                          Generando en tu navegador…
                        </p>
                        {progress && (
                          <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--text-muted)" }}>
                            {progress.done} de {progress.total} listas
                          </p>
                        )}
                      </div>
                      <div
                        style={{
                          height: 8,
                          background: "var(--border)",
                          borderRadius: 999,
                          overflow: "hidden",
                          width: "100%",
                        }}
                      >
                        <div
                          style={{
                            height: "100%",
                            width:
                              progress && progress.total > 0
                                ? Math.round((progress.done / progress.total) * 100) + "%"
                                : "0%",
                            background: "var(--teal)",
                            transition: "width 0.2s",
                          }}
                        />
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: "grid", gap: "var(--space-4)", justifyItems: "center" }}>
                      <span
                        aria-hidden="true"
                        style={{
                          width: 72,
                          height: 72,
                          borderRadius: "var(--r-md)",
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          background: "var(--surface-2)",
                          border: "1px solid var(--border)",
                          color: "var(--text)",
                          fontFamily: "var(--font-display)",
                          fontSize: "2rem",
                          fontWeight: 700,
                        }}
                      >
                        {selectedBrandInitial}
                      </span>
                      <div>
                        <p
                          style={{
                            margin: "0 0 var(--space-1)",
                            fontFamily: "var(--font-display)",
                            fontSize: "var(--font-size-xl)",
                            fontWeight: 700,
                            color: "var(--text)",
                          }}
                        >
                          Tu asset aparecerá acá
                        </p>
                        <p style={{ ...mutedTextStyle, margin: 0 }}>
                          {selectedBrand
                            ? `${selectedBrand.name}${selectedAssetLabel ? ` · ${selectedAssetLabel}` : ""}`
                            : "Seleccioná una marca para comenzar."}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div
              style={{
                display: "flex",
                gap: "var(--space-3)",
                flexWrap: "wrap",
                justifyContent: "flex-end",
              }}
            >
              <Button
                variant="primary"
                disabled={!resultVariation}
                onClick={() => {
                  if (resultVariation) window.open(resultVariation.file_url, "_blank");
                }}
              >
                Descargar PNG
              </Button>
              <Button variant="secondary" onClick={handleReset} disabled={generating}>
                Generar otro activo
              </Button>
            </div>
          </Card>
        </div>
      )}
    </section>
  );
}

// ── Estilos compartidos ─────────────────────────────────────────────────────

const sectionTitleStyle: React.CSSProperties = {
  margin: "0 0 var(--space-3)",
  fontFamily: "var(--font-display)",
  fontSize: "var(--font-size-xl)",
  color: "var(--text)",
};

const mutedTextStyle: React.CSSProperties = {
  margin: "0 0 var(--space-4)",
  fontSize: "var(--font-size-sm)",
  color: "var(--text-muted)",
};

const labelStyle: React.CSSProperties = {
  display: "block",
  marginBottom: "var(--space-1)",
  fontSize: "var(--font-size-sm)",
  fontWeight: 600,
  color: "var(--text)",
};

const inputStyle: React.CSSProperties = {
  display: "block",
  width: "100%",
  padding: "var(--space-3) var(--space-4)",
  border: "1.5px solid var(--border)",
  borderRadius: "var(--r-md)",
  fontSize: "var(--font-size-base)",
  color: "var(--text)",
  background: "var(--surface-2)",
  boxSizing: "border-box",
  fontFamily: "var(--font-body)",
};

const errorStyle: React.CSSProperties = {
  color: "var(--danger)",
  fontSize: "var(--font-size-sm)",
  padding: "var(--space-3) var(--space-4)",
  background: "var(--error-bg)",
  borderRadius: "var(--r-md)",
  border: "1px solid var(--danger)",
  margin: 0,
};

const errorPanelStyle: React.CSSProperties = {
  background: "var(--error-bg)",
  border: "1px solid var(--danger)",
  borderRadius: "var(--r-md)",
  padding: "var(--space-4)",
  display: "grid",
  gap: "var(--space-3)",
};
