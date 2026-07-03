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
      { value: "fb_cover", label: "Facebook Cover (820×315)" },
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

  return (
    <section>
      {/* Cabecera */}
      <div
        style={{
          marginBottom: "var(--space-6)",
        }}
      >
        <h1
          style={{
            margin: "0 0 var(--space-1)",
            fontFamily: "var(--font-display)",
            fontSize: "var(--font-size-2xl)",
            color: "var(--ink)",
          }}
        >
          Estudio de activos
        </h1>
        <p
          style={{
            margin: 0,
            fontSize: "var(--font-size-sm)",
            color: "var(--slate-500)",
          }}
        >
          Generá banners, tarjetas, imágenes OG y más, heredando la identidad visual de tu marca.
        </p>
      </div>

      {/* ── Loading ────────────────────────────────────────────────────── */}

      {loadingBrands && (
        <div
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
          <p style={{ margin: 0, color: "var(--slate-500)", fontSize: "var(--font-size-sm)" }}>
            Cargando marcas…
          </p>
        </div>
      )}

      {/* ── Error de carga ─────────────────────────────────────────────── */}

      {!loadingBrands && loadError && (
        <p style={errorStyle} role="alert">
          {loadError}
        </p>
      )}

      {/* ── Vacío ──────────────────────────────────────────────────────── */}

      {!loadingBrands && !loadError && brands.length === 0 && (
        <EmptyState
          title="Todavía no tenés marcas"
          description="Creá tu primera marca para empezar a generar activos visuales."
          icon="🏷️"
          action={
            <Link to="/">
              <Button variant="primary">+ Crear mi primera marca</Button>
            </Link>
          }
        />
      )}

      {/* ── Contenido ──────────────────────────────────────────────────── */}

      {!loadingBrands && !loadError && brands.length > 0 && (
        <div
          style={{
            display: "grid",
            gap: "var(--space-8)",
            maxWidth: 720,
          }}
        >

          {/* ── Paso 1: Selector de marca ─────────────────────────────── */}

          <Card padding="lg">
            <h2
              style={{
                margin: "0 0 var(--space-4)",
                fontFamily: "var(--font-display)",
                fontSize: "var(--font-size-lg)",
                color: "var(--ink)",
              }}
            >
              1. Elegí tu marca
            </h2>

            <SelectField
              id="brand-select"
              label="Marca"
              hint="Seleccioná la marca cuya identidad visual querés usar."
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

            {/* Aviso: marca sin logo */}
            {selectedBrand && !brandHasLogo && (
              <div
                style={{
                  marginTop: "var(--space-4)",
                  background: "rgba(224, 168, 94, 0.12)",
                  border: "1px solid var(--gold-dark)",
                  borderRadius: "var(--radius-md)",
                  padding: "var(--space-3) var(--space-4)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--space-2)",
                }}
              >
                <p
                  style={{
                    margin: 0,
                    fontSize: "var(--font-size-sm)",
                    color: "var(--ink)",
                    fontWeight: 600,
                  }}
                >
                  Esta marca todavía no tiene logo fijo.
                </p>
                <p
                  style={{
                    margin: 0,
                    fontSize: "var(--font-size-sm)",
                    color: "var(--slate-700)",
                  }}
                >
                  Andá a la página de identidad y elegí un logo antes de generar activos.
                </p>
                <Link
                  to={`/brands/${selectedBrand.id}/identity`}
                  style={{
                    fontSize: "var(--font-size-sm)",
                    color: "var(--teal-600)",
                    fontWeight: 600,
                    alignSelf: "flex-start",
                  }}
                >
                  Fijar identidad →
                </Link>
              </div>
            )}
          </Card>

          {/* ── Paso 2: Tipo de asset ──────────────────────────────────── */}

          {selectedBrand && brandHasLogo && (
            <Card padding="lg">
              <h2
                style={{
                  margin: "0 0 var(--space-4)",
                  fontFamily: "var(--font-display)",
                  fontSize: "var(--font-size-lg)",
                  color: "var(--ink)",
                }}
              >
                2. ¿Qué querés generar?
              </h2>

              <SelectField
                id="asset-type-select"
                label="Tipo de activo"
                hint="Cada tipo tiene un formato y campos de texto distintos."
                value={selectedAssetType}
                onChange={(e) => handleAssetTypeChange(e.target.value)}
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
            </Card>
          )}

          {/* ── Paso 3: Form de contenido ─────────────────────────────── */}

          {selectedBrand && brandHasLogo && selectedAssetType && (
            <form onSubmit={handleGenerate}>
              <Card padding="lg" style={{ marginBottom: "var(--space-6)" }}>
                <h2
                  style={{
                    margin: "0 0 var(--space-4)",
                    fontFamily: "var(--font-display)",
                    fontSize: "var(--font-size-lg)",
                    color: "var(--ink)",
                  }}
                >
                  3. Contenido del {ASSET_LABEL[selectedAssetType] ?? selectedAssetType}
                </h2>

                <p
                  style={{
                    margin: "0 0 var(--space-4)",
                    fontSize: "var(--font-size-sm)",
                    color: "var(--slate-500)",
                  }}
                >
                  Completá los textos que aparecerán en el activo. Todos los campos son opcionales.
                </p>

                <div style={{ display: "grid", gap: "var(--space-4)" }}>
                  {currentFields.map((f) => (
                    <div key={f.key}>
                      <label
                        htmlFor={`content-${f.key}`}
                        style={labelStyle}
                      >
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
              </Card>

              {/* ── Botón Generar ─────────────────────────────────────── */}

              <div style={{ marginBottom: "var(--space-6)" }}>
                <Button
                  type="submit"
                  variant="primary"
                  busy={generating}
                  disabled={generating || !!resultVariation}
                >
                  {generating ? "Generando…" : resultVariation ? "Generado" : "Generar"}
                </Button>
              </div>
            </form>
          )}

          {/* ── Error de generación ───────────────────────────────────── */}

          {generateError && (
            <div
              role="alert"
              style={{
                background: "var(--error-bg)",
                border: "1px solid var(--error)",
                borderRadius: "var(--radius-md)",
                padding: "var(--space-4)",
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-3)",
              }}
            >
              <p style={{ margin: 0, color: "var(--error)", fontSize: "var(--font-size-sm)", fontWeight: 600 }}>
                {generateError}
              </p>
              <div>
                <Button
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
            </div>
          )}

          {/* ── Progreso ──────────────────────────────────────────────── */}

          {generating && progress && (
            <Card padding="md">
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "var(--space-4)",
                  textAlign: "center",
                }}
              >
                <Spinner size="md" />
                <p
                  style={{
                    margin: 0,
                    fontFamily: "var(--font-display)",
                    fontSize: "var(--font-size-lg)",
                    fontWeight: 700,
                    color: "var(--ink)",
                  }}
                  aria-live="polite"
                >
                  Generando en tu navegador…
                </p>
                <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--slate-500)" }}>
                  {progress.done} de {progress.total} listas
                </p>
                <div
                  style={{
                    height: 8,
                    background: "var(--line)",
                    borderRadius: 999,
                    overflow: "hidden",
                    width: "100%",
                    maxWidth: 360,
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width:
                        progress.total > 0
                          ? Math.round((progress.done / progress.total) * 100) + "%"
                          : "0%",
                      background: "var(--teal-600)",
                      transition: "width 0.2s",
                    }}
                  />
                </div>
              </div>
            </Card>
          )}

          {/* ── Preview + Descarga ────────────────────────────────────── */}

          {resultVariation && (
            <Card padding="lg">
              <h2
                style={{
                  margin: "0 0 var(--space-4)",
                  fontFamily: "var(--font-display)",
                  fontSize: "var(--font-size-lg)",
                  color: "var(--ink)",
                }}
              >
                Vista previa
              </h2>

              <div
                style={{
                  background: "var(--mist)",
                  borderRadius: "var(--radius-md)",
                  padding: "var(--space-6)",
                  marginBottom: "var(--space-5)",
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                  minHeight: 200,
                }}
              >
                <img
                  src={resultVariation.file_url}
                  alt="Vista previa del activo generado"
                  style={{
                    maxWidth: "100%",
                    maxHeight: 480,
                    borderRadius: "var(--radius-sm)",
                    boxShadow: "var(--shadow-md)",
                    display: "block",
                  }}
                />
              </div>

              <div
                style={{
                  display: "flex",
                  gap: "var(--space-3)",
                  flexWrap: "wrap",
                }}
              >
                <Button
                  variant="primary"
                  onClick={() => {
                    window.open(resultVariation.file_url, "_blank");
                  }}
                >
                  Descargar PNG
                </Button>
                <Button variant="secondary" onClick={handleReset}>
                  Generar otro activo
                </Button>
              </div>
            </Card>
          )}
        </div>
      )}
    </section>
  );
}

// ── Estilos compartidos ─────────────────────────────────────────────────────

const labelStyle: React.CSSProperties = {
  display: "block",
  marginBottom: "var(--space-1)",
  fontSize: "var(--font-size-sm)",
  fontWeight: 600,
  color: "var(--ink)",
};

const inputStyle: React.CSSProperties = {
  display: "block",
  width: "100%",
  padding: "var(--space-3) var(--space-4)",
  border: "1.5px solid var(--line)",
  borderRadius: "var(--radius-md)",
  fontSize: "var(--font-size-base)",
  color: "var(--ink)",
  background: "var(--paper)",
  boxSizing: "border-box",
  fontFamily: "var(--font-body)",
};

const errorStyle: React.CSSProperties = {
  color: "var(--error)",
  fontSize: "var(--font-size-sm)",
  padding: "var(--space-2) var(--space-3)",
  background: "var(--error-bg)",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--error)",
  margin: 0,
};
