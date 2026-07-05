/**
 * Marcas — punto de partida del flujo Eikon.
 *
 * Lista las marcas de la cuenta como tarjetas de identidad y permite crear una
 * nueva con nombre + texto de logo. La navegacion conserva el flujo:
 * Identidad -> Estudio, mas el acceso a creacion por lotes.
 */
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { brands as brandsApi, type Brand, ApiError } from "../api/client";
import { Button, EmptyState, Modal, SkeletonCard } from "../components";
import { formatDate, slugify } from "../utils/format";

export function BrandsPage() {
  const navigate = useNavigate();

  const [items, setItems] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [logoText, setLogoText] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");

  const [toDelete, setToDelete] = useState<Brand | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await brandsApi.list();
      setItems(res.items);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.detail : "No pudimos cargar tus marcas.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const derivedSlug = useMemo(() => slugify(name), [name]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setFormError("");
    if (!name.trim()) {
      setFormError("Escribí un nombre para tu marca.");
      return;
    }
    setBusy(true);
    try {
      const brand = await brandsApi.create({
        slug: derivedSlug || `marca-${Date.now()}`,
        name: name.trim(),
        logo_text: logoText.trim() || name.trim(),
      });
      setItems((prev) => [brand, ...prev]);
      setName("");
      setLogoText("");
      setShowForm(false);
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.detail : "No pudimos crear la marca.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function confirmDelete() {
    if (!toDelete) return;
    setDeleting(true);
    setFormError("");
    try {
      await brandsApi.delete(toDelete.id);
      setItems((prev) => prev.filter((b) => b.id !== toDelete.id));
      setToDelete(null);
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.detail : "No pudimos eliminar la marca.",
      );
    } finally {
      setDeleting(false);
    }
  }

  return (
    <section>
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          gap: "var(--space-4)",
          flexWrap: "wrap",
          marginBottom: "var(--space-8)",
        }}
      >
        <div className="eikon-page-intro" style={{ marginBottom: 0 }}>
          <h1>Tus marcas</h1>
          <p>
            Cada marca recorre dos pasos: identidad para fijar el logo y Estudio para generar piezas listas para usar.
          </p>
        </div>

        <Button
          variant="primary"
          onClick={() => {
            setShowForm(true);
            setFormError("");
          }}
        >
          + Nueva marca
        </Button>
      </div>

      <Modal
        open={showForm}
        onClose={() => {
          if (busy) return;
          setShowForm(false);
          setFormError("");
        }}
        title="Crear nueva marca"
      >
        <form
          onSubmit={handleCreate}
          style={{
            display: "grid",
            gap: "var(--space-4)",
          }}
          aria-label="Crear una marca nueva"
        >
          <div>
            <label htmlFor="brand-name" style={labelStyle}>
              Nombre de la marca
            </label>
            <input
              id="brand-name"
              type="text"
              required
              minLength={1}
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ej.: Café del Centro"
              style={inputStyle}
              autoFocus
            />
          </div>

          <div>
            <label htmlFor="brand-logo-text" style={labelStyle}>
              Texto del logo{" "}
              <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>
                (opcional)
              </span>
            </label>
            <input
              id="brand-logo-text"
              type="text"
              maxLength={120}
              value={logoText}
              onChange={(e) => setLogoText(e.target.value)}
              placeholder="Lo que se lee en el logo. Por defecto, el nombre."
              style={inputStyle}
            />
          </div>

          <div aria-live="assertive" aria-atomic="true">
            {formError && (
              <p style={errorStyle} role="alert">
                {formError}
              </p>
            )}
          </div>

          <div style={{ display: "flex", gap: "var(--space-3)", justifyContent: "flex-end" }}>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setShowForm(false);
                setFormError("");
              }}
              disabled={busy}
            >
              Cancelar
            </Button>
            <Button type="submit" variant="primary" busy={busy}>
              {busy ? "Creando…" : "Crear marca"}
            </Button>
          </div>
        </form>
      </Modal>

      {loading && (
        <div
          role="status"
          aria-label="Cargando tus marcas"
          aria-busy="true"
          className="eikon-brand-grid"
        >
          {Array.from({ length: 3 }, (_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {!loading && error && (
        <p style={errorStyle} role="alert">
          {error}
        </p>
      )}

      {!loading && !error && items.length === 0 && (
        <EmptyState
          title="Todavía no tenés marcas"
          description="Creá tu primera marca para empezar a generar su identidad visual."
          icon="🏷️"
          action={
            <Button variant="primary" onClick={() => setShowForm(true)}>
              + Crear mi primera marca
            </Button>
          }
        />
      )}

      {!loading && !error && items.length > 0 && (
        <ul className="eikon-brand-grid" style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {items.map((b) => (
            <li key={b.id}>
              <BrandCard
                brand={b}
                navigate={navigate}
                onGenerate={() => navigate("/batch")}
                onDelete={() => setToDelete(b)}
              />
            </li>
          ))}
          <li>
            <CreateBrandCard onClick={() => setShowForm(true)} />
          </li>
        </ul>
      )}

      {toDelete && (
        <Modal
          open
          onClose={() => (deleting ? undefined : setToDelete(null))}
          title="Eliminar marca"
        >
          <div style={{ display: "grid", gap: "var(--space-5)" }}>
            <p style={{ margin: 0, color: "var(--text-muted)", lineHeight: 1.6 }}>
              ¿Seguro que querés eliminar{" "}
              <strong style={{ color: "var(--text)" }}>{toDelete.name}</strong>?
              Esta acción no se puede deshacer.
            </p>
            {formError && (
              <p style={errorStyle} role="alert">
                {formError}
              </p>
            )}
            <div style={{ display: "flex", gap: "var(--space-3)", justifyContent: "flex-end" }}>
              <Button
                variant="secondary"
                onClick={() => setToDelete(null)}
                disabled={deleting}
              >
                Cancelar
              </Button>
              <Button
                variant="danger"
                busy={deleting}
                onClick={() => void confirmDelete()}
              >
                {deleting ? "Eliminando…" : "Sí, eliminar"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </section>
  );
}

function BrandCard({
  brand,
  navigate,
  onGenerate,
  onDelete,
}: {
  brand: Brand;
  navigate: ReturnType<typeof useNavigate>;
  onGenerate: () => void;
  onDelete: () => void;
}) {
  const initial = (brand.logo_symbol || brand.logo_text || brand.name || "?")
    .trim()
    .charAt(0)
    .toUpperCase();
  const paletteEntries = getPaletteEntries(brand.palette);
  const hasLogo = Boolean(brand.logo_style);

  return (
    <article
      style={{
        minHeight: "100%",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--r-lg)",
        boxShadow: "var(--shadow-1)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        animation: "eikon-fadein 220ms ease both",
      }}
    >
      <div
        style={{
          display: "grid",
          gap: "var(--space-5)",
          padding: "var(--space-6)",
          borderBottom: "1px solid var(--border)",
          background: "var(--surface-2)",
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: "var(--space-4)" }}>
          <span
            aria-hidden="true"
            style={{
              width: 56,
              height: 56,
              flexShrink: 0,
              borderRadius: "var(--r-md)",
              background: hasLogo ? "var(--teal)" : "transparent",
              color: hasLogo ? "var(--teal-ink)" : "var(--text)",
              border: hasLogo ? "1px solid var(--teal)" : "1px solid var(--border-strong)",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: "var(--font-display)",
              fontWeight: 700,
              fontSize: "var(--font-size-2xl)",
            }}
          >
            {initial}
          </span>
          <div style={{ minWidth: 0, flex: 1 }}>
            <h2
              style={{
                margin: 0,
                fontFamily: "var(--font-display)",
                fontSize: "1.8rem",
                fontWeight: 700,
                lineHeight: 1.1,
                color: "var(--text)",
                overflowWrap: "anywhere",
              }}
            >
              {brand.name}
            </h2>
            <p
              style={{
                margin: "var(--space-1) 0 0",
                fontSize: "var(--font-size-xs)",
                color: "var(--text-muted)",
                fontFamily: "var(--font-mono)",
              }}
            >
              Creada el {formatDate(brand.created_at)}
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "var(--space-3)" }}>
          <span
            style={{
              fontSize: "var(--font-size-xs)",
              color: hasLogo ? "var(--ok)" : "var(--amber)",
              border: `1px solid ${hasLogo ? "var(--ok)" : "var(--amber)"}`,
              borderRadius: "var(--r-md)",
              padding: "var(--space-1) var(--space-2)",
              fontWeight: 700,
            }}
          >
            {hasLogo ? "Identidad lista" : "Identidad pendiente"}
          </span>
          <span
            style={{
              color: "var(--text-faint)",
              fontSize: "var(--font-size-xs)",
              fontFamily: "var(--font-mono)",
            }}
          >
            {brand.slug}
          </span>
        </div>
      </div>

      <div
        style={{
          padding: "var(--space-5) var(--space-6)",
          display: "grid",
          gap: "var(--space-5)",
          flex: 1,
        }}
      >
        <div>
          <p style={eyebrowStyle}>Paleta</p>
          {paletteEntries.length > 0 ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
              {paletteEntries.map(([key, color]) => (
                <span
                  key={key}
                  title={`${formatPaletteKey(key)}: ${color}`}
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: "var(--r-sm)",
                    background: color,
                    border: "1px solid var(--border-strong)",
                    boxShadow: "var(--shadow-1)",
                  }}
                />
              ))}
            </div>
          ) : (
            <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "var(--font-size-sm)" }}>
              Sin paleta cargada.
            </p>
          )}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)", marginTop: "auto" }}>
          <Button
            variant="primary"
            size="sm"
            onClick={() => navigate(`/brands/${brand.id}/identity`)}
            title="Paso 1: Elegir logo"
            aria-label={`Identidad de ${brand.name}`}
          >
            Identidad
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => navigate(`/studio?brand=${brand.id}`)}
            title="Paso 2: Generar assets"
            aria-label={`Estudio de ${brand.name}`}
          >
            Estudio
          </Button>
        </div>

        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "var(--space-2)",
            alignItems: "center",
            justifyContent: "space-between",
            borderTop: "1px solid var(--border)",
            paddingTop: "var(--space-4)",
          }}
        >
          <Link
            to={`/brands/${brand.id}/edit`}
            aria-label={`Personalizar la marca ${brand.name}`}
            style={secondaryLinkStyle}
          >
            Personalizar
          </Link>
          <button type="button" onClick={onGenerate} style={secondaryButtonStyle}>
            Crear lote
          </button>
          <button
            type="button"
            onClick={onDelete}
            aria-label={`Eliminar la marca ${brand.name}`}
            style={{
              ...secondaryButtonStyle,
              color: "var(--danger)",
              borderColor: "var(--danger)",
            }}
          >
            Eliminar
          </button>
        </div>
      </div>
    </article>
  );
}

function CreateBrandCard({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        minHeight: "100%",
        width: "100%",
        background: "transparent",
        border: "1px dashed var(--border-strong)",
        borderRadius: "var(--r-lg)",
        color: "var(--text-muted)",
        padding: "var(--space-6)",
        display: "grid",
        placeItems: "center",
        gap: "var(--space-3)",
        textAlign: "center",
        cursor: "pointer",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: 52,
          height: 52,
          borderRadius: "var(--r-md)",
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          border: "1px solid var(--border)",
          color: "var(--teal)",
          fontSize: "var(--font-size-2xl)",
          lineHeight: 1,
        }}
      >
        +
      </span>
      <span style={{ color: "var(--text)", fontWeight: 700 }}>Crear nueva marca</span>
      <span style={{ fontSize: "var(--font-size-sm)" }}>
        Sumá otra identidad al atelier.
      </span>
    </button>
  );
}

function getPaletteEntries(palette: Record<string, unknown>): [string, string][] {
  return Object.entries(palette)
    .filter((entry): entry is [string, string] => typeof entry[1] === "string" && entry[1].length > 0)
    .slice(0, 8);
}

function formatPaletteKey(key: string): string {
  return key.replace(/_/g, " ");
}

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

const eyebrowStyle: React.CSSProperties = {
  margin: "0 0 var(--space-3)",
  color: "var(--text-muted)",
  fontSize: "var(--font-size-xs)",
  fontFamily: "var(--font-mono)",
  textTransform: "uppercase",
  letterSpacing: "0.08em",
};

const secondaryLinkStyle: React.CSSProperties = {
  color: "var(--text-muted)",
  fontSize: "var(--font-size-sm)",
  textDecoration: "none",
  padding: "var(--space-2) var(--space-3)",
  borderRadius: "var(--r-sm)",
  border: "1px solid var(--border)",
  minHeight: 38,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  fontWeight: 600,
};

const secondaryButtonStyle: React.CSSProperties = {
  background: "transparent",
  border: "1px solid var(--border)",
  color: "var(--text-muted)",
  fontSize: "var(--font-size-sm)",
  cursor: "pointer",
  padding: "var(--space-2) var(--space-3)",
  borderRadius: "var(--r-sm)",
  minHeight: 38,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  fontFamily: "var(--font-body)",
  fontWeight: 600,
};
