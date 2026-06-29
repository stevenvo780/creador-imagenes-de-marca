/**
 * VariationCard — tarjeta "lámina enmarcada" para la galería.
 *
 * Muestra la imagen de una variación en un marco con fondo neutro,
 * padding generoso y sombra sutil. Permite:
 *   - Seleccionar (checkbox) para descarga en lote.
 *   - Click en imagen → abre el lightbox de detalle.
 *   - Descargar individualmente.
 *
 * La calidad (score) se muestra como estrellas o badge "Recomendado"
 * usando el componente Stars — nunca el número crudo.
 */
import { Stars } from '../../components';
import { downloads } from '../../api/client';
import type { Variation } from '../../api/client';

export interface VariationCardProps {
  variation: Variation;
  /** Nombre legible de la marca a la que pertenece. */
  brandName?: string;
  isSelected: boolean;
  onToggleSelect: () => void;
  onOpenLightbox: () => void;
  onDownload: () => Promise<void>;
  downloading?: boolean;
}

export function VariationCard({
  variation,
  brandName,
  isSelected,
  onToggleSelect,
  onOpenLightbox,
  onDownload,
  downloading = false,
}: VariationCardProps) {
  const imageUrl = downloads.fileUrl(variation.id);

  return (
    <article
      aria-label={
        brandName
          ? `Variación de ${brandName}`
          : `Variación ${variation.id}`
      }
      style={{
        background: 'var(--white)',
        border: isSelected
          ? '2px solid var(--teal-600)'
          : '1px solid var(--line)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: isSelected
          ? '0 0 0 3px rgba(47,168,154,0.18), var(--shadow-md)'
          : 'var(--shadow-sm)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        transition:
          'border-color var(--transition-normal), box-shadow var(--transition-normal)',
        animation: 'eikon-fadein 220ms ease both',
      }}
    >
      {/* Zona de imagen */}
      <div style={{ position: 'relative' }}>
        {/* Checkbox de selección — esquina superior izquierda */}
        <label
          title={isSelected ? 'Deseleccionar' : 'Seleccionar'}
          style={{
            position: 'absolute',
            top: 'var(--space-2)',
            left: 'var(--space-2)',
            zIndex: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 24,
            height: 24,
            background: isSelected ? 'var(--teal-600)' : 'rgba(255,255,255,0.9)',
            border: `2px solid ${isSelected ? 'var(--teal-600)' : 'var(--line)'}`,
            borderRadius: 'var(--radius-sm)',
            cursor: 'pointer',
            boxShadow: 'var(--shadow-sm)',
            transition: 'background var(--transition-fast), border-color var(--transition-fast)',
          }}
        >
          <input
            type="checkbox"
            checked={isSelected}
            onChange={onToggleSelect}
            aria-label={`Seleccionar variación${brandName ? ` de ${brandName}` : ''}`}
            style={{
              position: 'absolute',
              opacity: 0,
              width: '100%',
              height: '100%',
              cursor: 'pointer',
              margin: 0,
            }}
          />
          {isSelected && (
            <span
              aria-hidden="true"
              style={{ color: '#fff', fontSize: 14, lineHeight: 1, fontWeight: 700 }}
            >
              ✓
            </span>
          )}
        </label>

        {/* Imagen clickeable → abre lightbox */}
        <button
          type="button"
          onClick={onOpenLightbox}
          aria-label={`Ver detalle${brandName ? ` de ${brandName}` : ''}`}
          style={{
            display: 'block',
            width: '100%',
            border: 'none',
            background: 'var(--mist)',
            padding: 'var(--space-5)',
            cursor: 'zoom-in',
            lineHeight: 0,
          }}
        >
          <img
            src={imageUrl}
            alt={
              brandName
                ? `Vista previa de variación de ${brandName}`
                : `Vista previa de variación ${variation.id}`
            }
            loading="lazy"
            style={{
              display: 'block',
              width: '100%',
              height: 200,
              objectFit: 'contain',
            }}
            onError={(e) => {
              const img = e.currentTarget;
              img.style.opacity = '0.25';
              img.style.filter = 'grayscale(1)';
            }}
          />
        </button>
      </div>

      {/* Footer: marca, calidad, botón descargar */}
      <div
        style={{
          padding: 'var(--space-3) var(--space-4)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 'var(--space-2)',
          borderTop: '1px solid var(--line)',
        }}
      >
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
            minWidth: 0,
          }}
        >
          {brandName && (
            <span
              style={{
                fontSize: 'var(--font-size-xs)',
                color: 'var(--slate-500)',
                fontWeight: 600,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {brandName}
            </span>
          )}
          <Stars score={variation.score} />
        </div>

        <button
          type="button"
          onClick={() => void onDownload()}
          disabled={downloading}
          aria-label={`Descargar variación${brandName ? ` de ${brandName}` : ''}`}
          title="Descargar imagen"
          style={{
            flexShrink: 0,
            padding: 'var(--space-1) var(--space-3)',
            background: downloading ? 'var(--mist)' : 'var(--teal-600)',
            color: downloading ? 'var(--slate-500)' : '#fff',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            fontSize: 'var(--font-size-xs)',
            fontWeight: 600,
            cursor: downloading ? 'not-allowed' : 'pointer',
            transition:
              'background var(--transition-fast), color var(--transition-fast)',
            whiteSpace: 'nowrap',
          }}
        >
          {downloading ? '…' : '↓ Descargar'}
        </button>
      </div>
    </article>
  );
}
