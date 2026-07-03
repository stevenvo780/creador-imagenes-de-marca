/**
 * Marcas — punto de partida del flujo Eikón.
 *
 * Lista las marcas de la cuenta como tarjetas con cariño y permite crear una
 * nueva con solo un nombre (el identificador técnico se deriva solo). Desde
 * cada tarjeta se puede generar variaciones o eliminar la marca.
 *
 * Lenguaje 100% humano: nada de "brand", "slug", "tenant".
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

  // Formulario de creación
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [logoText, setLogoText] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");

  // Confirmación de borrado
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
      {/* Cabecera */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          gap: "var(--space-4)",
          flexWrap: "wrap",
          marginBottom: "var(--space-6)",
        }}
      >
        <div>
          <h1
            style={{
              margin: "0 0 var(--space-1)",
              fontFamily: "var(--font-display)",
              fontSize: "var(--font-size-2xl)",
              color: "var(--ink)",
            }}
          >
            Tus marcas
          </h1>
          <p
            style={{
              margin: 0,
              fontSize: "var(--font-size-sm)",
              color: "var(--slate-500)",
              lineHeight: 1.6,
            }}
          >
            Cada marca tiene un flujo de 2 pasos: <strong>Identidad</strong> (elegir logo) → <strong>Estudio</strong> (generar assets). También podés crear variaciones rápido o personalizar detalles.
          </p>
        </div>

        <Button
          variant={showForm ? "secondary" : "primary"}
          onClick={() => {
            setShowForm((v) => !v);
            setFormError("");
          }}
        >
          {showForm ? "Cancelar" : "+ Nueva marca"}
        </Button>
      </div>

      {/* Formulario de creación */}
      {showForm && (
        <form
          onSubmit={handleCreate}
          style={{
            background: "var(--white)",
            border: "1px solid var(--line)",
            borderRadius: "var(--radius-lg)",
            padding: "var(--space-6)",
            marginBottom: "var(--space-8)",
            display: "grid",
            gap: "var(--space-4)",
            boxShadow: "var(--shadow-sm)",
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
              <span style={{ color: "var(--slate-500)", fontWeight: 400 }}>
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

          <div style={{ display: "flex", gap: "var(--space-3)" }}>
            <Button type="submit" variant="primary" busy={busy}>
              {busy ? "Creando…" : "Crear marca"}
            </Button>
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
          </div>
        </form>
      )}

      {/* Cargando */}
      {loading && (
        <div
          role="status"
          aria-label="Cargando tus marcas"
          aria-busy="true"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
            gap: "var(--space-5)",
          }}
        >
          {Array.from({ length: 3 }, (_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {/* Error de carga */}
      {!loading && error && (
        <p style={errorStyle} role="alert">
          {error}
        </p>
      )}

      {/* Vacío */}
      {!loading && !error && items.length === 0 && !showForm && (
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

      {/* Grid de marcas */}
      {!loading && !error && items.length > 0 && (
        <ul
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
            gap: "var(--space-5)",
            listStyle: "none",
            margin: 0,
            padding: 0,
          }}
          aria-label="Lista de tus marcas"
        >
          {items.map((b) => (
            <li key={b.id}>
              <BrandCard
                brand={b}
                onGenerate={() => navigate("/batch")}
                onDelete={() => setToDelete(b)}
              />
            </li>
          ))}
        </ul>
      )}

      {/* Confirmación de borrado */}
      {toDelete && (
        <Modal
          open
          onClose={() => (deleting ? undefined : setToDelete(null))}
          title="Eliminar marca"
        >
          <div style={{ display: "grid", gap: "var(--space-5)" }}>
            <p style={{ margin: 0, color: "var(--slate-700)", lineHeight: 1.6 }}>
              ¿Seguro que querés eliminar{" "}
              <strong style={{ color: "var(--ink)" }}>{toDelete.name}</strong>?
              Esta acción no se puede deshacer.
            </p>
            <div style={{ display: "flex", gap: "var(--space-3)", justifyContent: "flex-end" }}>
              <Button
                variant="secondary"
                onClick={() => setToDelete(null)}
                disabled={deleting}
              >
                Cancelar
              </Button>
              <Button
                variant="primary"
                busy={deleting}
                onClick={() => void confirmDelete()}
                style={{ background: "var(--error)" }}
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

// ── Tarjeta de marca ────────────────────────────────────────────────────────────

function BrandCard({
  brand,
  onGenerate,
  onDelete,
}: {
  brand: Brand;
  onGenerate: () => void;
  onDelete: () => void;
}) {
  const initial = (brand.logo_symbol || brand.name || "?").trim().charAt(0).toUpperCase();

  return (
    <article
      style={{
        background: "var(--white)",
        border: "1px solid var(--line)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        animation: "eikon-fadein 220ms ease both",
      }}
    >
      {/* Encabezado con monograma */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-4)",
          padding: "var(--space-5)",
          background: "var(--mist)",
          borderBottom: "1px solid var(--line)",
        }}
      >
        <span
          aria-hidden="true"
          style={{
            width: 48,
            height: 48,
            flexShrink: 0,
            borderRadius: "var(--radius-md)",
            background: "var(--teal-600)",
            color: "#fff",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "var(--font-display)",
            fontWeight: 700,
            fontSize: "var(--font-size-xl)",
          }}
        >
          {initial}
        </span>
        <div style={{ minWidth: 0 }}>
          <h2
            style={{
              margin: 0,
              fontFamily: "var(--font-display)",
              fontSize: "var(--font-size-lg)",
              color: "var(--ink)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {brand.name}
          </h2>
          <p
            style={{
              margin: "2px 0 0",
              fontSize: "var(--font-size-xs)",
              color: "var(--slate-500)",
            }}
          >
            Creada el {formatDate(brand.created_at)}
          </p>
        </div>
      </div>

      {/* Acciones */}
      <div
        style={{
          padding: "var(--space-4) var(--space-5)",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-4)",
          marginTop: "auto",
        }}
      >
        {/* Botón principal: Generar variaciones */}
        <Button variant="primary" size="sm" onClick={onGenerate}>
          Generar variaciones
        </Button>

        {/* Flujo de 2 pasos: Identidad → Estudio */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "var(--space-2)",
          }}
        >
          <Link
            to={`/brands/${brand.id}/identity`}
            aria-label={`Identidad de ${brand.name}`}
            title="Paso 1: Elegir logo"
            style={{
              color: "var(--teal-600)",
              fontSize: "var(--font-size-sm)",
              fontWeight: 500,
              textDecoration: "none",
              padding: "var(--space-2) var(--space-3)",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--teal-200)",
              background: "var(--white)",
              textAlign: "center",
              transition: "all var(--transition-fast)",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--teal-50)";
              e.currentTarget.style.borderColor = "var(--teal-400)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "var(--white)";
              e.currentTarget.style.borderColor = "var(--teal-200)";
            }}
          >
            Identidad
          </Link>
          <Link
            to={`/studio?brand=${brand.id}`}
            aria-label={`Estudio de ${brand.name}`}
            title="Paso 2: Generar assets"
            style={{
              color: "var(--teal-600)",
              fontSize: "var(--font-size-sm)",
              fontWeight: 500,
              textDecoration: "none",
              padding: "var(--space-2) var(--space-3)",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--teal-200)",
              background: "var(--white)",
              textAlign: "center",
              transition: "all var(--transition-fast)",
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--teal-50)";
              e.currentTarget.style.borderColor = "var(--teal-400)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "var(--white)";
              e.currentTarget.style.borderColor = "var(--teal-200)";
            }}
          >
            Estudio
          </Link>
        </div>

        {/* Links secundarios */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "var(--space-2)",
          }}
        >
          <Link
            to={`/brands/${brand.id}/edit`}
            aria-label={`Personalizar la marca ${brand.name}`}
            style={{
              color: "var(--slate-500)",
              fontSize: "var(--font-size-sm)",
              textDecoration: "underline",
              padding: "var(--space-2) var(--space-3)",
              borderRadius: "var(--radius-sm)",
              minHeight: 44,
              minWidth: 44,
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "color var(--transition-fast), background var(--transition-fast)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "var(--ink)";
              e.currentTarget.style.background = "var(--mist)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--slate-500)";
              e.currentTarget.style.background = "transparent";
            }}
          >
            Personalizar
          </Link>
          <button
            type="button"
            onClick={onDelete}
            aria-label={`Eliminar la marca ${brand.name}`}
            style={{
              background: "none",
              border: "none",
              color: "var(--slate-500)",
              fontSize: "var(--font-size-sm)",
              cursor: "pointer",
              padding: "var(--space-2) var(--space-3)",
              borderRadius: "var(--radius-sm)",
              textDecoration: "underline",
              minHeight: 44,
              minWidth: 44,
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "color var(--transition-fast), background var(--transition-fast)",
              fontFamily: "inherit",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "var(--error)";
              e.currentTarget.style.background = "var(--mist)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--slate-500)";
              e.currentTarget.style.background = "transparent";
            }}
          >
            Eliminar
          </button>
        </div>
      </div>
    </article>
  );
}

// ── Estilos compartidos ─────────────────────────────────────────────────────────

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
