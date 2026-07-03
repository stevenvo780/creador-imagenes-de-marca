/**
 * GalleryPage — héroe del producto Eikón.
 *
 * Muestra las variaciones generadas en un grid de "láminas enmarcadas".
 * Permite:
 *   - Filtrar por Marca, Generación y Familia de formato — los dos primeros
 *     pasan como parámetros al backend (server-side); la familia se aplica
 *     en cliente sobre el resultado ya ordenado.
 *   - Ordenar por Calidad o Más recientes — enviado al backend como
 *     order=calidad | order=recientes.
 *   - Selección múltiple + descarga en .zip desde la barra flotante.
 *   - Click en imagen → lightbox de detalle con descarga individual.
 *
 * Vocabulario visible al usuario (sin jerga técnica):
 *   score      → Calidad (estrellas / "Recomendado")
 *   batch_id   → Generación
 *   brand_id   → Marca
 *   category   → Familia (logos / banners / tarjetas / redes / papelería)
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  brands as brandsApi,
  downloads,
  gallery,
  variations,
  ApiError,
  type Brand,
  type GalleryOrder,
  type Variation,
} from '../../api/client';
import { Button, EmptyState, SkeletonCard } from '../../components';
import { VariationCard } from './VariationCard';
import { Lightbox } from './Lightbox';

// ── Constantes de dominio ─────────────────────────────────────────────────────

type SortKey = GalleryOrder; // 'calidad' | 'recientes'

/** Etiquetas en español para las familias de formato que devuelve el backend. */
const CATEGORY_LABELS: Record<string, string> = {
  logos: 'Logos',
  banners: 'Banners',
  cards: 'Tarjetas',
  og: 'Redes / OG',
  stationery: 'Papelería',
};

// ── Componente principal ──────────────────────────────────────────────────────

export function GalleryPage() {
  // ── Datos ─────────────────────────────────────────────────────────────────
  const [items, setItems] = useState<Variation[]>([]);
  const [brandList, setBrandList] = useState<Brand[]>([]);
  /** true durante la primera carga o cualquier refetch por cambio de filtro. */
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // ── Filtros y orden ───────────────────────────────────────────────────────
  // Si venimos del wizard (…/gallery?batch=ID), arrancamos filtrando esa generación.
  const [searchParams] = useSearchParams();
  const initialBatch = (() => {
    const raw = searchParams.get('batch');
    const n = raw === null ? NaN : Number(raw);
    return Number.isFinite(n) && n > 0 ? n : ('' as const);
  })();

  const [filterBrand, setFilterBrand] = useState<number | ''>('');
  const [filterBatch, setFilterBatch] = useState<number | ''>(initialBatch);
  /**
   * filterCategory es client-side: no lo pasamos al backend porque el endpoint
   * no lo soporta; se aplica como .filter() sobre los items ya devueltos.
   */
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [sortBy, setSortBy] = useState<SortKey>('calidad');

  // ── Selección, ZIP y eliminación ──────────────────────────────────────────
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [zipping, setZipping] = useState(false);
  const [deleting, setDeleting] = useState<Set<number>>(new Set());
  const [deleteConfirm, setDeleteConfirm] = useState<{
    ids: number[];
    open: boolean;
  }>({ ids: [], open: false });

  // ── Lightbox ──────────────────────────────────────────────────────────────
  const [lightboxId, setLightboxId] = useState<number | null>(null);
  const [downloading, setDownloading] = useState<Set<number>>(new Set());

  // ── Carga de marcas (una sola vez) ────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    brandsApi
      .list()
      .then((res) => {
        if (!cancelled) setBrandList(res.items);
      })
      .catch(() => {
        // Las marcas son opcionales para mostrar nombres; no bloqueamos si fallan.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // ── Carga de variaciones (server-side: marca, generación y orden) ─────────
  // Se re-ejecuta cada vez que cambia filterBrand, filterBatch o sortBy.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');

    gallery
      .list({
        brandId: filterBrand !== '' ? filterBrand : undefined,
        batchId: filterBatch !== '' ? filterBatch : undefined,
        order: sortBy,
      })
      .then((res) => {
        if (cancelled) return;
        setItems(res.items);
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
  }, [filterBrand, filterBatch, sortBy]);

  // ── Lotes únicos (para el filtro "Generación") ────────────────────────────
  // Se derivan de los items actuales (ya filtrados por marca/batch en el backend).
  const batchIds = useMemo<number[]>(() => {
    const ids = new Set<number>();
    for (const v of items) {
      if (v.batch_id !== null) ids.add(v.batch_id);
    }
    return [...ids].sort((a, b) => b - a); // más reciente primero
  }, [items]);

  // ── Categorías disponibles (para el filtro "Familia") ────────────────────
  const availableCategories = useMemo<string[]>(() => {
    const cats = new Set<string>();
    for (const v of items) {
      if (v.category) cats.add(v.category);
    }
    // Orden canónico fijo para que el dropdown sea predecible
    const ORDER = ['logos', 'banners', 'cards', 'og', 'stationery'];
    return ORDER.filter((c) => cats.has(c));
  }, [items]);

  // ── Mapa id → nombre de marca ─────────────────────────────────────────────
  const brandMap = useMemo<Map<number, string>>(() => {
    const m = new Map<number, string>();
    for (const b of brandList) m.set(b.id, b.name);
    return m;
  }, [brandList]);

  // ── Filtrado client-side por familia ──────────────────────────────────────
  // brand/batch/order ya vienen filtrados/ordenados del servidor;
  // aquí sólo aplicamos el filtro de categoría adicional.
  const visibleItems = useMemo<Variation[]>(() => {
    if (filterCategory === '') return items;
    return items.filter((v) => v.category === filterCategory);
  }, [items, filterCategory]);

  // ── Variación del lightbox ─────────────────────────────────────────────────
  const lightboxVariation = useMemo<Variation | null>(
    () =>
      lightboxId !== null ? (items.find((v) => v.id === lightboxId) ?? null) : null,
    [lightboxId, items],
  );

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleBrandChange = useCallback((value: number | '') => {
    setFilterBrand(value);
    // Al cambiar marca, el batch activo puede no pertenecer a ella → se limpia.
    setFilterBatch('');
    setFilterCategory('');
    setSelected(new Set());
  }, []);

  const handleBatchChange = useCallback((value: number | '') => {
    setFilterBatch(value);
    setFilterCategory('');
    setSelected(new Set());
  }, []);

  const handleCategoryChange = useCallback((value: string) => {
    setFilterCategory(value);
    setSelected(new Set());
  }, []);

  const handleSortChange = useCallback((value: SortKey) => {
    setSortBy(value);
    setSelected(new Set());
  }, []);

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

  const handleDeleteBulk = useCallback((ids: number[]) => {
    if (ids.length === 0) return;
    setDeleteConfirm({ ids, open: true });
  }, []);

  const confirmDelete = useCallback(async () => {
    const ids = deleteConfirm.ids;
    setDeleteConfirm({ ids: [], open: false });
    const set = new Set(ids);
    setDeleting((prev) => new Set([...prev, ...set]));
    try {
      if (ids.length === 1) {
        await variations.delete(ids[0]);
      } else {
        await variations.deleteBulk(ids);
      }
      setSelected(new Set());
      const res = await gallery.list({
        brandId: filterBrand !== '' ? filterBrand : undefined,
        batchId: filterBatch !== '' ? filterBatch : undefined,
        order: sortBy,
      });
      setItems(res.items);
    } catch (err) {
      alert(err instanceof ApiError ? err.detail : 'Error al eliminar.');
    } finally {
      setDeleting((prev) => {
        const next = new Set(prev);
        for (const id of ids) next.delete(id);
        return next;
      });
    }
  }, [deleteConfirm.ids, filterBrand, filterBatch, sortBy]);

  const handleDeleteSingle = useCallback(async (id: number) => {
    setDeleting((prev) => new Set([...prev, id]));
    try {
      await variations.delete(id);
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      const res = await gallery.list({
        brandId: filterBrand !== '' ? filterBrand : undefined,
        batchId: filterBatch !== '' ? filterBatch : undefined,
        order: sortBy,
      });
      setItems(res.items);
    } catch (err) {
      alert(err instanceof ApiError ? err.detail : 'Error al eliminar.');
    } finally {
      setDeleting((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }, [filterBrand, filterBatch, sortBy]);

  const handleDownloadOne = useCallback(async (id: number) => {
    setDownloading((prev) => new Set(prev).add(id));
    try {
      const res = await fetch(downloads.fileUrl(id), { credentials: 'include' });
      if (!res.ok) {
        const json = await res.json().catch(() => ({ detail: res.statusText }));
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

  const hasItems = items.length > 0;

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

          {hasItems && (
            <span
              aria-live="polite"
              aria-atomic="true"
              style={{ fontSize: 'var(--font-size-sm)', color: 'var(--slate-500)' }}
            >
              {visibleItems.length}{' '}
              {visibleItems.length === 1 ? 'variación' : 'variaciones'}
            </span>
          )}
        </div>

        {/* Barra de controles (visible cuando hay datos o filtros activos) */}
        {(hasItems || filterBrand !== '' || filterBatch !== '') && (
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
            {/* ── Filtro: Marca (server-side) ── */}
            <FilterGroup id="gallery-brand" label="Marca">
              <select
                id="gallery-brand"
                value={filterBrand}
                onChange={(e) =>
                  handleBrandChange(e.target.value === '' ? '' : Number(e.target.value))
                }
                aria-label="Filtrar por marca"
                style={selectStyle}
              >
                <option value="">Todas las marcas</option>
                {brandList.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </FilterGroup>

            {/* ── Filtro: Generación (server-side, sólo si hay más de uno) ── */}
            {batchIds.length > 1 && (
              <FilterGroup id="gallery-batch" label="Generación">
                <select
                  id="gallery-batch"
                  value={filterBatch}
                  onChange={(e) =>
                    handleBatchChange(
                      e.target.value === '' ? '' : Number(e.target.value),
                    )
                  }
                  aria-label="Filtrar por generación"
                  style={selectStyle}
                >
                  <option value="">Todas las generaciones</option>
                  {batchIds.map((id) => (
                    <option key={id} value={id}>
                      Generación #{id}
                    </option>
                  ))}
                </select>
              </FilterGroup>
            )}

            {/* ── Filtro: Familia / Formato (client-side sobre resultado del servidor) ── */}
            {availableCategories.length > 1 && (
              <FilterGroup id="gallery-category" label="Familia">
                <select
                  id="gallery-category"
                  value={filterCategory}
                  onChange={(e) => handleCategoryChange(e.target.value)}
                  aria-label="Filtrar por familia de formato"
                  style={selectStyle}
                >
                  <option value="">Todas las familias</option>
                  {availableCategories.map((cat) => (
                    <option key={cat} value={cat}>
                      {CATEGORY_LABELS[cat] ?? cat}
                    </option>
                  ))}
                </select>
              </FilterGroup>
            )}

            {/* ── Ordenar por (server-side) ── */}
            <FilterGroup id="gallery-sort" label="Ordenar por">
              <select
                id="gallery-sort"
                value={sortBy}
                onChange={(e) => handleSortChange(e.target.value as SortKey)}
                aria-label="Ordenar variaciones"
                style={selectStyle}
              >
                <option value="calidad">Calidad (mejores primero)</option>
                <option value="recientes">Más recientes</option>
              </select>
            </FilterGroup>

            {/* ── Seleccionar / Deseleccionar todo (visible) ── */}
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

        {/* ── Chips de filtros activos ── */}
        {(filterBrand !== '' || filterBatch !== '' || filterCategory !== '') && (
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 'var(--space-2)',
              marginBottom: 'var(--space-4)',
            }}
            aria-label="Filtros activos"
          >
            {filterBrand !== '' && (
              <FilterChip
                label={`Marca: ${brandMap.get(filterBrand as number) ?? `#${filterBrand as number}`}`}
                onRemove={() => handleBrandChange('')}
              />
            )}
            {filterBatch !== '' && (
              <FilterChip
                label={`Generación #${filterBatch as number}`}
                onRemove={() => handleBatchChange('')}
              />
            )}
            {filterCategory !== '' && (
              <FilterChip
                label={`Familia: ${CATEGORY_LABELS[filterCategory] ?? filterCategory}`}
                onRemove={() => handleCategoryChange('')}
              />
            )}
          </div>
        )}

        {/* ── Estado vacío global ── */}
        {!hasItems && filterBrand === '' && filterBatch === '' && (
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

        {/* ── Estado vacío por filtro de servidor ── */}
        {!hasItems && (filterBrand !== '' || filterBatch !== '') && (
          <EmptyState
            title="Sin resultados"
            description="Ninguna variación coincide con los filtros seleccionados. Probá con otras opciones."
            icon="🔍"
          />
        )}

        {/* ── Estado vacío por filtro de familia (client-side) ── */}
        {hasItems && visibleItems.length === 0 && (
          <EmptyState
            title="Sin resultados en esta familia"
            description={`No hay variaciones de tipo "${CATEGORY_LABELS[filterCategory] ?? filterCategory}" con los filtros actuales.`}
            icon="🔍"
          />
        )}

        {/* ── Grid de variaciones ── */}
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
                  categoryLabel={v.category ? (CATEGORY_LABELS[v.category] ?? v.category) : undefined}
                  isSelected={selected.has(v.id)}
                  onToggleSelect={() => toggleSelect(v.id)}
                  onOpenLightbox={() => setLightboxId(v.id)}
                  onDownload={() => handleDownloadOne(v.id)}
                  downloading={downloading.has(v.id)}
                  onDelete={() => handleDeleteSingle(v.id)}
                  deleting={deleting.has(v.id)}
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ── Barra de acciones flotante (aparece cuando hay selección) ── */}
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
            {selected.size === 1 ? 'variación seleccionada' : 'variaciones seleccionadas'}
          </span>

          <Button
            variant="primary"
            size="sm"
            onClick={() => void handleZip()}
            busy={zipping}
          >
            {zipping ? 'Generando ZIP…' : '↓ Descargar .zip'}
          </Button>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => handleDeleteBulk([...selected])}
            disabled={deleting.size > 0}
            style={{
              color: 'var(--error)',
              borderColor: 'var(--error)',
            }}
          >
            🗑 Eliminar {selected.size}{' '}
            {selected.size === 1 ? 'variación' : 'variaciones'}
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

      {/* ── Diálogo de confirmación de borrado ── */}
      {deleteConfirm.open && (
        <div
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="delete-dialog-title"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 300,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(14, 27, 26, 0.5)',
            backdropFilter: 'blur(2px)',
          }}
        >
          <div
            style={{
              background: 'var(--white)',
              borderRadius: 'var(--radius-xl)',
              boxShadow: 'var(--shadow-lg)',
              padding: 'var(--space-6)',
              maxWidth: 420,
              width: '100%',
              animation: 'eikon-fadein 180ms ease',
            }}
          >
            <h3
              id="delete-dialog-title"
              style={{
                margin: '0 0 var(--space-3)',
                fontFamily: 'var(--font-display)',
                fontSize: 'var(--font-size-lg)',
                color: 'var(--ink)',
              }}
            >
              Confirmar eliminación
            </h3>
            <p
              style={{
                fontSize: 'var(--font-size-sm)',
                color: 'var(--slate-600)',
                margin: '0 0 var(--space-5)',
              }}
            >
              ¿Estás seguro de que querés borrar {deleteConfirm.ids.length}{' '}
              {deleteConfirm.ids.length === 1 ? 'variación' : 'variaciones'}? No se puede
              deshacer.
            </p>
            <div
              style={{
                display: 'flex',
                gap: 'var(--space-3)',
                justifyContent: 'flex-end',
              }}
            >
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setDeleteConfirm({ ids: [], open: false })}
              >
                Cancelar
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => void confirmDelete()}
                busy={deleting.size > 0}
                style={{
                  background: 'var(--error)',
                  borderColor: 'transparent',
                  color: '#fff',
                }}
              >
                Eliminar
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Lightbox de detalle ── */}
      <Lightbox
        variation={lightboxVariation}
        brandName={
          lightboxVariation ? brandMap.get(lightboxVariation.brand_id) : undefined
        }
        categoryLabel={
          lightboxVariation?.category
            ? (CATEGORY_LABELS[lightboxVariation.category] ?? lightboxVariation.category)
            : undefined
        }
        onClose={() => setLightboxId(null)}
        onDownload={() =>
          lightboxId !== null ? handleDownloadOne(lightboxId) : Promise.resolve()
        }
        downloading={lightboxId !== null && downloading.has(lightboxId)}
        onDelete={async () => {
          if (lightboxId !== null) {
            await handleDeleteSingle(lightboxId);
            setLightboxId(null);
          }
        }}
        deleting={lightboxId !== null && deleting.has(lightboxId)}
      />
    </>
  );
}

// ── Sub-componentes de UI ──────────────────────────────────────────────────────

/**
 * FilterGroup — envuelve un label + su control en un div flex column.
 * Reutilizado por todos los filtros del toolbar.
 */
function FilterGroup({
  id,
  label,
  children,
}: {
  id: string;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
      <label
        htmlFor={id}
        style={{
          fontSize: 'var(--font-size-xs)',
          fontWeight: 600,
          color: 'var(--slate-500)',
        }}
      >
        {label}
      </label>
      {children}
    </div>
  );
}

/**
 * FilterChip — pastilla removible que indica un filtro activo.
 * Accesible: botón con aria-label descriptivo.
 */
function FilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '2px 6px 2px 8px',
        borderRadius: 'var(--radius-pill)',
        fontSize: 'var(--font-size-xs)',
        fontWeight: 600,
        lineHeight: 1.5,
        whiteSpace: 'nowrap',
        background: 'var(--mist)',
        color: 'var(--slate-700)',
        border: '1px solid var(--line)',
      }}
    >
      {label}
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Quitar filtro: ${label}`}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 16,
          height: 16,
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--slate-500)',
          fontSize: 10,
          fontWeight: 700,
          borderRadius: '50%',
          padding: 0,
          lineHeight: 1,
          transition: 'color var(--transition-fast)',
        }}
      >
        ✕
      </button>
    </span>
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
