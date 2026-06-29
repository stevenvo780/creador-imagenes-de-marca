/**
 * GalleryPage — héroe del producto Eikón.
 *
 * Muestra las variaciones generadas en un grid de "láminas enmarcadas".
 * Permite:
 *   - Filtrar por Marca y por Generación.
 *   - Ordenar por Calidad (mejores primero) o Más recientes.
 *   - Selección múltiple + descarga en .zip desde la barra flotante.
 *   - Click en imagen → lightbox de detalle con descarga individual.
 *
 * Vocabulario visible al usuario (sin jerga técnica):
 *   score      → Calidad (estrellas / "Recomendado")
 *   batch_id   → Generación
 *   brand_id   → Marca
 *   variation  → variación
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  brands as brandsApi,
  downloads,
  gallery,
  ApiError,
  type Brand,
  type Variation,
} from '../../api/client';
import { Button, EmptyState, SkeletonCard } from '../../components';
import { toMillis } from '../../utils/format';
import { VariationCard } from './VariationCard';
import { Lightbox } from './Lightbox';

type SortKey = 'score_desc' | 'recent';

export function GalleryPage() {
  // ── Datos ─────────────────────────────────────────────────────────────────
  const [items, setItems] = useState<Variation[]>([]);
  const [brandList, setBrandList] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // ── Filtros y orden ───────────────────────────────────────────────────────
  // Si venimos del wizard (…/gallery?batch=ID), arrancamos filtrando esa generación.
  const [searchParams] = useSearchParams();
  const initialBatch = (() => {
    const raw = searchParams.get('batch');
    const n = raw === null ? NaN : Number(raw);
    return Number.isFinite(n) && n > 0 ? n : '';
  })();

  const [filterBrand, setFilterBrand] = useState<number | ''>('');
  const [filterBatch, setFilterBatch] = useState<number | ''>(initialBatch);
  const [sortBy, setSortBy] = useState<SortKey>('score_desc');

  // ── Selección y ZIP ───────────────────────────────────────────────────────
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [zipping, setZipping] = useState(false);

  // ── Lightbox ──────────────────────────────────────────────────────────────
  const [lightboxId, setLightboxId] = useState<number | null>(null);

  // Por variación: indica si está descargándose individualmente
  const [downloading, setDownloading] = useState<Set<number>>(new Set());

  // ── Carga inicial (paralela) ───────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    Promise.all([gallery.list(), brandsApi.list()])
      .then(([galleryRes, brandsRes]) => {
        if (cancelled) return;
        setItems(galleryRes.items);
        setBrandList(brandsRes.items);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          err instanceof ApiError
            ? err.detail
            : 'No se pudo cargar la galería. Intentá de nuevo.',
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // ── Lotes únicos (para filtro "Generación") ───────────────────────────────
  const batchIds = useMemo<number[]>(() => {
    const ids = new Set<number>();
    for (const v of items) {
      if (v.batch_id !== null) ids.add(v.batch_id);
    }
    return [...ids].sort((a, b) => b - a); // más reciente primero
  }, [items]);

  // ── Mapa id → nombre de marca ─────────────────────────────────────────────
  const brandMap = useMemo<Map<number, string>>(() => {
    const m = new Map<number, string>();
    for (const b of brandList) m.set(b.id, b.name);
    return m;
  }, [brandList]);

  // ── Filtrado + orden memoizado ────────────────────────────────────────────
  const visibleItems = useMemo<Variation[]>(() => {
    let result = items;

    if (filterBrand !== '')
      result = result.filter((v) => v.brand_id === filterBrand);

    if (filterBatch !== '')
      result = result.filter((v) => v.batch_id === filterBatch);

    const sorted = [...result];

    if (sortBy === 'score_desc') {
      sorted.sort(
        (a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity),
      );
    } else {
      sorted.sort((a, b) => toMillis(b.created_at) - toMillis(a.created_at));
    }

    return sorted;
  }, [items, filterBrand, filterBatch, sortBy]);

  // ── Variación del lightbox ─────────────────────────────────────────────────
  const lightboxVariation = useMemo<Variation | null>(
    () => (lightboxId !== null ? (items.find((v) => v.id === lightboxId) ?? null) : null),
    [lightboxId, items],
  );

  // ── Handlers ──────────────────────────────────────────────────────────────

  const toggleSelect = useCallback((id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllVisible = useCallback(() => {
    setSelected(new Set(visibleItems.map((v) => v.id)));
  }, [visibleItems]);

  const clearSelection = useCallback(() => setSelected(new Set()), []);

  const handleZip = useCallback(async () => {
    if (selected.size === 0) return;
    setZipping(true);
    try {
      const blob = await downloads.zip([...selected]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'eikon-variaciones.zip';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof ApiError ? err.detail : 'Error al generar el ZIP.');
    } finally {
      setZipping(false);
    }
  }, [selected]);

  const handleDownloadOne = useCallback(async (id: number) => {
    setDownloading((prev) => new Set(prev).add(id));
    try {
      const res = await fetch(downloads.fileUrl(id), {
        credentials: 'include',
      });
      if (!res.ok) {
        const json = await res.json().catch(() => ({
          detail: res.statusText,
        }));
        throw new ApiError(
          res.status,
          (json as { detail?: string })?.detail ?? 'Error al descargar.',
        );
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `variacion-${id}.png`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof ApiError ? err.detail : 'Error al descargar.');
    } finally {
      setDownloading((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }, []);

  // ── Render: cargando ──────────────────────────────────────────────────────

  if (loading) {
    return (
      <div>
        <h1
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 'var(--font-size-2xl)',
            marginBottom: 'var(--space-8)',
          }}
        >
          Galería
        </h1>
        <div
          role="status"
          aria-label="Cargando galería"
          aria-busy="true"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
            gap: 'var(--space-6)',
          }}
        >
          {Array.from({ length: 8 }, (_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    );
  }

  // ── Render: error ─────────────────────────────────────────────────────────

  if (error) {
    return (
      <p
        role="alert"
        style={{
          color: 'var(--error)',
          fontSize: 'var(--font-size-sm)',
          padding: 'var(--space-3) var(--space-4)',
          background: 'var(--error-bg)',
          borderRadius: 'var(--radius-md)',
        }}
      >
        {error}
      </p>
    );
  }

  // ── Render principal ──────────────────────────────────────────────────────

  const allVisibleSelected =
    visibleItems.length > 0 && visibleItems.every((v) => selected.has(v.id));

  return (
    <>
      {/* Padding inferior para que la barra flotante no tape el último card */}
      <section
        style={{
          paddingBottom: selected.size > 0 ? 80 : 0,
          transition: 'padding-bottom var(--transition-normal)',
        }}
      >
        {/* Cabecera de página */}
        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: 'var(--space-3)',
            marginBottom: 'var(--space-6)',
          }}
        >
          <h1
            style={{
              margin: 0,
              fontFamily: 'var(--font-display)',
              fontSize: 'var(--font-size-2xl)',
              color: 'var(--ink)',
            }}
          >
            Galería
          </h1>

          {items.length > 0 && (
            <span
              aria-live="polite"
              aria-atomic="true"
              style={{
                fontSize: 'var(--font-size-sm)',
                color: 'var(--slate-500)',
              }}
            >
              {visibleItems.length}{' '}
              {visibleItems.length === 1 ? 'variación' : 'variaciones'}
            </span>
          )}
        </div>

        {/* Barra de controles */}
        {items.length > 0 && (
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'flex-end',
              gap: 'var(--space-3)',
              marginBottom: 'var(--space-8)',
              padding: 'var(--space-4) var(--space-5)',
              background: 'var(--white)',
              border: '1px solid var(--line)',
              borderRadius: 'var(--radius-lg)',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            {/* Filtro: Marca */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-1)',
              }}
            >
              <label
                htmlFor="gallery-brand"
                style={{
                  fontSize: 'var(--font-size-xs)',
                  fontWeight: 600,
                  color: 'var(--slate-500)',
                }}
              >
                Marca
              </label>
              <select
                id="gallery-brand"
                value={filterBrand}
                onChange={(e) =>
                  setFilterBrand(
                    e.target.value === '' ? '' : Number(e.target.value),
                  )
                }
                style={selectStyle}
              >
                <option value="">Todas las marcas</option>
                {brandList.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Filtro: Generación (solo si hay más de uno) */}
            {batchIds.length > 1 && (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 'var(--space-1)',
                }}
              >
                <label
                  htmlFor="gallery-batch"
                  style={{
                    fontSize: 'var(--font-size-xs)',
                    fontWeight: 600,
                    color: 'var(--slate-500)',
                  }}
                >
                  Generación
                </label>
                <select
                  id="gallery-batch"
                  value={filterBatch}
                  onChange={(e) =>
                    setFilterBatch(
                      e.target.value === '' ? '' : Number(e.target.value),
                    )
                  }
                  style={selectStyle}
                >
                  <option value="">Todas las generaciones</option>
                  {batchIds.map((id) => (
                    <option key={id} value={id}>
                      Generación #{id}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Ordenar por */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-1)',
              }}
            >
              <label
                htmlFor="gallery-sort"
                style={{
                  fontSize: 'var(--font-size-xs)',
                  fontWeight: 600,
                  color: 'var(--slate-500)',
                }}
              >
                Ordenar por
              </label>
              <select
                id="gallery-sort"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortKey)}
                style={selectStyle}
              >
                <option value="score_desc">Calidad (mejores primero)</option>
                <option value="recent">Más recientes</option>
              </select>
            </div>

            {/* Seleccionar / Deseleccionar todo */}
            {visibleItems.length > 0 && (
              <button
                type="button"
                onClick={allVisibleSelected ? clearSelection : selectAllVisible}
                style={{
                  marginLeft: 'auto',
                  alignSelf: 'flex-end',
                  padding: 'var(--space-2) var(--space-3)',
                  background: 'transparent',
                  border: '1.5px solid var(--line)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: 'var(--font-size-sm)',
                  color: 'var(--slate-700)',
                  fontWeight: 500,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  transition: 'border-color var(--transition-fast)',
                }}
              >
                {allVisibleSelected ? 'Quitar selección' : 'Seleccionar todo'}
              </button>
            )}
          </div>
        )}

        {/* Estado vacío global */}
        {items.length === 0 && (
          <EmptyState
            title="Todavía no generaste nada"
            description="Creá tu primera marca y generá variaciones desde la sección Crear."
            icon="🎨"
            action={
              <Link
                to="/batch"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  padding: 'var(--space-2) var(--space-5)',
                  background: 'var(--teal-600)',
                  color: '#fff',
                  borderRadius: 'var(--radius-md)',
                  fontSize: 'var(--font-size-sm)',
                  fontWeight: 600,
                  textDecoration: 'none',
                }}
              >
                Crear variaciones
              </Link>
            }
          />
        )}

        {/* Estado vacío por filtro */}
        {items.length > 0 && visibleItems.length === 0 && (
          <EmptyState
            title="Sin resultados"
            description="Ninguna variación coincide con los filtros seleccionados. Probá con otras opciones."
            icon="🔍"
          />
        )}

        {/* Grid de variaciones */}
        {visibleItems.length > 0 && (
          <ul
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
              gap: 'var(--space-6)',
              listStyle: 'none',
              margin: 0,
              padding: 0,
            }}
            aria-label="Variaciones de marca"
          >
            {visibleItems.map((v) => (
              <li key={v.id}>
                <VariationCard
                  variation={v}
                  brandName={brandMap.get(v.brand_id)}
                  isSelected={selected.has(v.id)}
                  onToggleSelect={() => toggleSelect(v.id)}
                  onOpenLightbox={() => setLightboxId(v.id)}
                  onDownload={() => handleDownloadOne(v.id)}
                  downloading={downloading.has(v.id)}
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Barra de acciones flotante (aparece cuando hay selección) */}
      {selected.size > 0 && (
        <div
          role="region"
          aria-label="Acciones sobre la selección"
          style={{
            position: 'fixed',
            bottom: 'var(--space-6)',
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 150,
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-4)',
            padding: 'var(--space-3) var(--space-5)',
            background: 'var(--white)',
            border: '1px solid var(--line)',
            borderRadius: 'var(--radius-pill)',
            boxShadow: 'var(--shadow-lg)',
            animation: 'eikon-fadein 180ms ease',
            whiteSpace: 'nowrap',
          }}
        >
          <span
            style={{
              fontSize: 'var(--font-size-sm)',
              fontWeight: 600,
              color: 'var(--ink)',
            }}
          >
            {selected.size}{' '}
            {selected.size === 1
              ? 'variación seleccionada'
              : 'variaciones seleccionadas'}
          </span>

          <Button
            variant="primary"
            size="sm"
            onClick={() => void handleZip()}
            busy={zipping}
          >
            {zipping ? 'Generando ZIP…' : '↓ Descargar .zip'}
          </Button>

          <button
            type="button"
            onClick={clearSelection}
            aria-label="Cancelar selección"
            title="Cancelar selección"
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--slate-500)',
              cursor: 'pointer',
              fontSize: 'var(--font-size-lg)',
              lineHeight: 1,
              padding: 'var(--space-1)',
              borderRadius: 'var(--radius-sm)',
              transition: 'color var(--transition-fast)',
            }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Lightbox de detalle */}
      <Lightbox
        variation={lightboxVariation}
        brandName={
          lightboxVariation ? brandMap.get(lightboxVariation.brand_id) : undefined
        }
        onClose={() => setLightboxId(null)}
        onDownload={() =>
          lightboxId !== null
            ? handleDownloadOne(lightboxId)
            : Promise.resolve()
        }
        downloading={lightboxId !== null && downloading.has(lightboxId)}
      />
    </>
  );
}

// ── Estilos compartidos ────────────────────────────────────────────────────────

const selectStyle: CSSProperties = {
  padding: 'var(--space-2) var(--space-3)',
  border: '1.5px solid var(--line)',
  borderRadius: 'var(--radius-md)',
  fontSize: 'var(--font-size-sm)',
  color: 'var(--ink)',
  background: 'var(--paper)',
  minWidth: 160,
  cursor: 'pointer',
  fontFamily: 'var(--font-body)',
};
