/**
 * Página de brands: lista + creación rápida de brands del tenant.
 */
import { type FormEvent, useEffect, useState } from "react";
import { brands as brandsApi, type Brand, ApiError } from "../api/client";

export function BrandsPage() {
  const [items, setItems] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Formulario de creación
  const [showForm, setShowForm] = useState(false);
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState("");

  async function load() {
    setLoading(true);
    try {
      const res = await brandsApi.list();
      setItems(res.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Error al cargar brands.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setFormError("");
    setBusy(true);
    try {
      const brand = await brandsApi.create({ slug, name });
      setItems((prev) => [brand, ...prev]);
      setSlug("");
      setName("");
      setShowForm(false);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.detail : "Error al crear.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("¿Eliminar este brand?")) return;
    try {
      await brandsApi.delete(id);
      setItems((prev) => prev.filter((b) => b.id !== id));
    } catch (err) {
      alert(err instanceof ApiError ? err.detail : "Error al eliminar.");
    }
  }

  return (
    <section>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "var(--space-6)",
        }}
      >
        <h2 style={{ margin: 0, fontSize: "var(--font-size-xl)", fontWeight: 700 }}>
          Brands
        </h2>
        <button
          onClick={() => setShowForm((v) => !v)}
          style={primaryButtonStyle}
        >
          {showForm ? "Cancelar" : "+ Nuevo brand"}
        </button>
      </div>

      {/* Formulario de creación */}
      {showForm && (
        <form
          onSubmit={handleCreate}
          style={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-md)",
            padding: "var(--space-4)",
            marginBottom: "var(--space-6)",
            display: "grid",
            gap: "var(--space-3)",
          }}
          aria-label="Crear brand"
        >
          <div style={{ display: "grid", gap: "var(--space-3)", gridTemplateColumns: "1fr 1fr" }}>
            <div>
              <label htmlFor="brand-slug" style={labelStyle}>
                Slug
              </label>
              <input
                id="brand-slug"
                type="text"
                required
                minLength={2}
                maxLength={80}
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                placeholder="mi-marca"
                style={inputStyle}
              />
            </div>
            <div>
              <label htmlFor="brand-name" style={labelStyle}>
                Nombre
              </label>
              <input
                id="brand-name"
                type="text"
                required
                minLength={1}
                maxLength={120}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Mi Marca"
                style={inputStyle}
              />
            </div>
          </div>

          <div aria-live="assertive" aria-atomic="true">
            {formError && (
              <p style={errorStyle} role="alert">
                {formError}
              </p>
            )}
          </div>

          <button type="submit" disabled={busy} style={primaryButtonStyle} aria-busy={busy}>
            {busy ? "Creando…" : "Crear brand"}
          </button>
        </form>
      )}

      {/* Estado de carga y error */}
      {loading && (
        <p style={{ color: "var(--color-text-muted)" }} aria-live="polite">
          Cargando…
        </p>
      )}
      {!loading && error && (
        <p style={errorStyle} role="alert">
          {error}
        </p>
      )}

      {/* Tabla de brands */}
      {!loading && !error && (
        <div style={{ overflowX: "auto" }}>
          {items.length === 0 ? (
            <p style={{ color: "var(--color-text-muted)" }}>
              No hay brands aún. Crea el primero con el botón superior.
            </p>
          ) : (
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontSize: "var(--font-size-sm)",
              }}
              aria-label="Lista de brands"
            >
              <thead>
                <tr
                  style={{
                    borderBottom: "2px solid var(--color-border)",
                    textAlign: "left",
                    color: "var(--color-text-muted)",
                  }}
                >
                  <th style={{ padding: "var(--space-2) var(--space-3)" }}>ID</th>
                  <th style={{ padding: "var(--space-2) var(--space-3)" }}>Slug</th>
                  <th style={{ padding: "var(--space-2) var(--space-3)" }}>Nombre</th>
                  <th style={{ padding: "var(--space-2) var(--space-3)" }}>Creado</th>
                  <th style={{ padding: "var(--space-2) var(--space-3)" }}>
                    <span className="sr-only">Acciones</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((b) => (
                  <tr
                    key={b.id}
                    style={{ borderBottom: "1px solid var(--color-border)" }}
                  >
                    <td style={{ padding: "var(--space-2) var(--space-3)", color: "var(--color-text-muted)" }}>
                      {b.id}
                    </td>
                    <td style={{ padding: "var(--space-2) var(--space-3)", fontFamily: "monospace" }}>
                      {b.slug}
                    </td>
                    <td style={{ padding: "var(--space-2) var(--space-3)", fontWeight: 500 }}>
                      {b.name}
                    </td>
                    <td style={{ padding: "var(--space-2) var(--space-3)", color: "var(--color-text-muted)" }}>
                      {b.created_at ? new Date(b.created_at).toLocaleDateString("es") : "—"}
                    </td>
                    <td style={{ padding: "var(--space-2) var(--space-3)" }}>
                      <button
                        onClick={() => handleDelete(b.id)}
                        style={{
                          background: "none",
                          border: "1px solid var(--color-error)",
                          color: "var(--color-error)",
                          borderRadius: "var(--radius-sm)",
                          padding: "2px var(--space-2)",
                          cursor: "pointer",
                          fontSize: "var(--font-size-xs)",
                        }}
                        aria-label={`Eliminar brand ${b.name}`}
                      >
                        Eliminar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </section>
  );
}

const labelStyle: React.CSSProperties = {
  display: "block",
  marginBottom: "var(--space-1)",
  fontSize: "var(--font-size-sm)",
  fontWeight: 500,
  color: "var(--color-text)",
};

const inputStyle: React.CSSProperties = {
  display: "block",
  width: "100%",
  padding: "var(--space-2) var(--space-3)",
  border: "1.5px solid var(--color-border)",
  borderRadius: "var(--radius-sm)",
  fontSize: "var(--font-size-base)",
  color: "var(--color-text)",
  background: "var(--color-bg)",
  boxSizing: "border-box",
};

const primaryButtonStyle: React.CSSProperties = {
  padding: "var(--space-2) var(--space-4)",
  background: "var(--color-primary)",
  color: "#fff",
  border: "none",
  borderRadius: "var(--radius-md)",
  fontWeight: 600,
  cursor: "pointer",
  fontSize: "var(--font-size-sm)",
};

const errorStyle: React.CSSProperties = {
  color: "var(--color-error)",
  fontSize: "var(--font-size-sm)",
  padding: "var(--space-2) var(--space-3)",
  background: "var(--color-error-bg)",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--color-error)",
};
