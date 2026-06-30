/**
 * Lightbox — vista de detalle de una variación.
 *
 * Usa el componente Modal del design system para mostrar la imagen
 * en tamaño grande con la calidad y opción de descarga.
 *
 * Se monta con `variation = null` cuando está cerrado (return null),
 * o con una Variation cuando está abierto.
 */
import { Modal, Stars } from '../../components';
import { downloads } from '../../api/client';
import type { Variation } from '../../api/client';
import { formatDate } from '../../utils/format';

export interface LightboxProps {
  variation: Variation | null;
  brandName?: string;
  /** Etiqueta de familia en español (ej. "Logos", "Banners"). */
  categoryLabel?: string;
  onClose: () => void;
  onDownload: () => Promise<void>;
  downloading?: boolean;
}

export function Lightbox({
  variation,
  brandName,
  categoryLabel,
  onClose,
  onDownload,
  downloading = false,
}: LightboxProps) {
  if (!variation) return null;

  const title = brandName
    ? `${brandName} — detalle`
    : 'Detalle de variación';

  const formattedDate = variation.created_at ? formatDate(variation.created_at) : null;

  return (
    <Modal open onClose={onClose} title={title} maxWidth="760px">
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-5)',
        }}
      >
        {/* Imagen grande en marco neutro */}
        <div
          style={{
            background: 'var(--mist)',
            borderRadius: 'var(--radius-md)',
            padding: 'var(--space-8)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 280,
          }}
        >
          <img
            src={downloads.fileUrl(variation.id)}
            alt={
              brandName
                ? `Vista de variación de ${brandName}`
                : `Vista de variación ${variation.id}`
            }
            style={{
              maxWidth: '100%',
              maxHeight: '60vh',
              objectFit: 'contain',
              borderRadius: 'var(--radius-sm)',
              boxShadow: 'var(--shadow-md)',
            }}
          />
        </div>

        {/* Calidad + fecha + botón descargar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 'var(--space-4)',
            flexWrap: 'wrap',
          }}
        >
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-1)',
            }}
          >
            <Stars score={variation.score} />
            {categoryLabel && (
              <span
                aria-label={`Familia: ${categoryLabel}`}
                style={{
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--teal-600)',
                  fontWeight: 600,
                  letterSpacing: '0.04em',
                  textTransform: 'uppercase',
                }}
              >
                {categoryLabel}
              </span>
            )}
            {formattedDate && (
              <span
                style={{
                  fontSize: 'var(--font-size-xs)',
                  color: 'var(--slate-500)',
                }}
              >
                {formattedDate}
              </span>
            )}
          </div>

          <button
            type="button"
            onClick={() => void onDownload()}
            disabled={downloading}
            style={{
              padding: 'var(--space-2) var(--space-6)',
              background: downloading ? 'var(--mist)' : 'var(--teal-600)',
              color: downloading ? 'var(--slate-500)' : '#fff',
              border: 'none',
              borderRadius: 'var(--radius-md)',
              fontSize: 'var(--font-size-sm)',
              fontWeight: 600,
              cursor: downloading ? 'not-allowed' : 'pointer',
              transition:
                'background var(--transition-fast), color var(--transition-fast)',
              whiteSpace: 'nowrap',
            }}
          >
            {downloading ? 'Descargando…' : '↓ Descargar imagen'}
          </button>
        </div>
      </div>
    </Modal>
  );
}
