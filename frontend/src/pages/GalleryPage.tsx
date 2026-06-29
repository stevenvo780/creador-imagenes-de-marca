/**
 * Galería de variaciones: muestra las imágenes renderizadas del tenant,
 * permite filtrar por brand, ordenar, seleccionar para ZIP y descargar
 * individualmente.
 */
import { useEffect, useMemo, useState } from "react";
import {
  brands as brandsApi,
  downloads,
  gallery,
  type Brand,
  type Variation,
  ApiError,
} from "../api/client";

type SortKey = "score_desc" | "score_asc" | "recent";

export function GalleryPage() {
  const [items, setItems] = useState<Variation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Selección para ZIP
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [zipping, setZipping] = useState(false);

  // Filtros y orden
  const [brandList, setBrandList] = useState<Brand[]>([]);
  const [selectedBrand, setSelectedBrand] = useState<number | "">("");
  const [sortBy, setSortBy] = useState<SortKey>("score_desc");

  // ── Carga inicial de variaciones ──────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    gallery
      .list()
      .then((res) => {
        if (!cancelled) setItems(res.items);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof ApiError ? err.detail : "Error al cargar galería.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // ── Carga de brands para el filtro ────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    brandsApi
      .list()
      .then((res) => {
        if (!cancelled) setBrandList(res.items);
      })
      .catch((err) => {
        // No es bloqueante: si falla, simplemente no mostramos el filtro de brands.
        console.warn("No se pudieron cargar los brands:", err);
        if (!cancelled) setBrandList([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // ── Filtrado + orden memoizado ────────────────────────────────────────────
  const visibleItems = useMemo<Variation[]>(() => {
    const filtered =
      selectedBrand === ""
        ? items
        : items.filter((v) => v.brand_id === selectedBrand);

    const sorted = [...filtered];
    switch (sortBy) {
      case "score_desc":
        sorted.sort((a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity));
        break;
      case "score_asc":
        sorted.sort((a, b) => (a.score ?? Infinity) - (b.score ?? Infinity));
        break;
      case "recent":
        sorted.sort((a, b) => {
          const ta = a.created_at ? Date.parse(a.created_at) : 0;
          const tb = b.created_at ? Date.parse(b.created_at) : 0;
          return tb - ta;
        });
        break;
    }
    return sorted;
  }, [items, selectedBrand, sortBy]);

  // ── Handlers ──────────────────────────────────────────────────────────────

  function toggleSelect(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleZip() {
    if (selected.size === 0) return;
    setZipping(true);
    try {
      const blob = await downloads.zip([...selected]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "eikon-variaciones.zip";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof ApiError ? err.detail : "Error al generar ZIP.");
    } finally {
      setZipping(false);
    }
  }

  /** Descarga individual: pide el PNG al backend, fuerza descarga como Blob. */
  async function handleDownloadOne(id: number) {
    try {
      const res = await fetch(downloads.fileUrl(id), {
        credentials: "include",
      });
      if (!res.ok) {
        const json = await res.json().catch(() => ({ detail: res.statusText }));
        throw new ApiError(res.status, json?.detail ?? "Error al descargar.");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `variacion-${id}.png`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof ApiError ? err.detail : "Error al descargar.");
    }
  }

  // ── Estados tempranos ─────────────────────────────────────────────────────

  if (loading)
    return (
      <p style={{ color: "var(--color-text-muted)" }} aria-live="polite">
        Cargando galería…
      </p>
    );

  if (error)
    return (
      <p
        style={{
          color: "var(--color-error)",
          fontSize: "var(--font-size-sm)",
          padding: "var(--space-3)",
          background: "var(--color-error-bg)",
          borderRadius: "var(--radius-sm)",
        }}
        role="alert"
      >
        {error}
      </p>
    );

  // ── Render principal ──────────────────────────────────────────────────────

  return (
    <section>
      {/* Cabecera */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "var(--space-4)",
        }}
      >
        <h2 style={{ margin: 0, fontSize: "var(--font-size-xl)", fontWeight: 700 }}>
          Galería
        </h2>
        {selected.size > 0 && (
          <button
            onClick={handleZip}
            disabled={zipping}
            aria-busy={zipping}
            style={{
              padding: "var(--space-2) var(--space-4)",
              background: "var(--color-accent)",
              color: "#fff",
              border: "none",
              borderRadius: "var(--radius-md)",
              fontWeight: 600,
              cursor: zipping ? "not-allowed" : "pointer",
              fontSize: "var(--font-size-sm)",
            }}
          >
            {zipping ? "Generando ZIP…" : `Descargar ZIP (${selected.size})`}
          </button>
        )}
      </div>

      {/* Barra de controles: filtro de brand + orden + contador */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "var(--space-4)",
          alignItems: "flex-end",
          marginBottom: "var(--space-6)",
        }}
      >
        <div>
          <label
            htmlFor="gallery-brand-filter"
            style={{
              display: "block",
              fontSize: "var(--font-size-xs)",
              color: "var(--color-text-muted)",
              marginBottom: "var(--space-1)",
              fontWeight: 500,
            }}
          >
            Brand
          </label>
          <select
            id="gallery-brand-filter"
            value={selectedBrand}
            onChange={(e) =>
              setSelectedBrand(e.target.value === "" ? "" : Number(e.target.value))
            }
            style={{
              padding: "var(--space-2) var(--space-3)",
              border: "1.5px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              fontSize: "var(--font-size-sm)",
              color: "var(--color-text)",
              background: "var(--color-surface)",
              minWidth: "180px",
            }}
          >
            <option value="">Todos</option>
            {brandList.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="gallery-sort"
            style={{
              display: "block",
              fontSize: "var(--font-size-xs)",
              color: "var(--color-text-muted)",
              marginBottom: "var(--space-1)",
              fontWeight: 500,
            }}
          >
            Ordenar por
          </label>
          <select
            id="gallery-sort"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortKey)}
            style={{
              padding: "var(--space-2) var(--space-3)",
              border: "1.5px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              fontSize: "var(--font-size-sm)",
              color: "var(--color-text)",
              background: "var(--color-surface)",
              minWidth: "180px",
            }}
          >
            <option value="score_desc">Score (mayor a menor)</option>
            <option value="score_asc">Score (menor a mayor)</option>
            <option value="recent">Más recientes</option>
          </select>
        </div>

        <p
          aria-live="polite"
          style={{
            margin: 0,
            fontSize: "var(--font-size-sm)",
            color: "var(--color-text-muted)",
            marginLeft: "auto",
            alignSelf: "center",
          }}
        >
          {visibleItems.length} variaciones
        </p>
      </div>

      {/* Grid */}
      {visibleItems.length === 0 ? (
        <p style={{ color: "var(--color-text-muted)" }}>
          {items.length === 0
            ? "No hay variaciones aún. Crea un batch desde la sección de Brands."
            : "Ninguna variación coincide con el filtro seleccionado."}
        </p>
      ) : (
        <ul
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
            gap: "var(--space-4)",
            listStyle: "none",
            margin: 0,
            padding: 0,
          }}
          aria-label="Variaciones de marca"
        >
          {visibleItems.map((v) => {
            const isSelected = selected.has(v.id);
            return (
              <li
                key={v.id}
                aria-label={`Variación ${v.id} — score ${v.score?.toFixed(2) ?? "N/A"}`}
                style={{
                  border: isSelected
                    ? "3px solid var(--color-primary)"
                    : "2px solid var(--color-border)",
                  borderRadius: "var(--radius-md)",
                  background: "var(--color-surface)",
                  overflow: "hidden",
                  boxShadow: isSelected
                    ? "0 0 0 2px var(--color-primary-muted)"
                    : "var(--shadow-md)",
                  transition: "border-color 0.15s, box-shadow 0.15s",
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <button
                  onClick={() => toggleSelect(v.id)}
                  aria-pressed={isSelected}
                  aria-label={`Seleccionar variación ${v.id}`}
                  style={{
                    display: "block",
                    width: "100%",
                    border: "none",
                    background: "none",
                    padding: 0,
                    cursor: "pointer",
                  }}
                >
                  <img
                    src={downloads.fileUrl(v.id)}
                    alt={`Variación ${v.id}`}
                    loading="lazy"
                    style={{
                      display: "block",
                      width: "100%",
                      height: "200px",
                      objectFit: "contain",
                      background: "var(--color-bg)",
                    }}
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = "none";
                    }}
                  />
                </button>

                <div
                  style={{
                    padding: "var(--space-2) var(--space-3)",
                    borderTop: "1px solid var(--color-border)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "var(--space-2)",
                  }}
                >
                  <p
                    style={{
                      margin: 0,
                      fontSize: "var(--font-size-xs)",
                      color: "var(--color-text-muted)",
                    }}
                  >
                    {isSelected ? (
                      <span
                        style={{
                          color: "var(--color-primary)",
                          fontWeight: 600,
                        }}
                      >
                        Seleccionada ·{" "}
                      </span>
                    ) : null}
                    Score: {v.score !== null ? v.score.toFixed(3) : "—"}
                  </p>
                  <button
                    type="button"
                    onClick={() => void handleDownloadOne(v.id)}
                    aria-label={`Descargar variación ${v.id}`}
                    style={{
                      padding: "var(--space-1) var(--space-2)",
                      background: "var(--color-accent)",
                      color: "#fff",
                      border: "none",
                      borderRadius: "var(--radius-sm)",
                      fontSize: "var(--font-size-xs)",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    Descargar
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}