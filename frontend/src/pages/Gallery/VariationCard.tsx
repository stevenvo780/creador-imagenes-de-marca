import { usePrivateOperation } from "../Media/usePrivateOperation";
/**
 * VariationCard — tarjeta "lámina enmarcada" para la galería.
 *
 * Muestra la imagen de una variación en un marco con fondo neutro,
 * padding generoso y sombra sutil. Permite:
 *   - Seleccionar (checkbox) para descarga en lote.
 *   - Click en imagen → abre el lightbox de detalle.
 *   - Descargar individualmente.
 *   - Eliminar individualmente.
 *
 * La calidad (score) se muestra como estrellas o badge "Recomendado"
 * usando el componente Stars — nunca el número crudo.
 */
import { useState } from "react";
import { promoteVariation, mediaError, isAbort } from "../../api/media";
import { PrivateImage } from "../Media/PrivateImage";
import { Stars } from "../../components";
import { downloads } from "../../api/client";
import type { Variation } from "../../api/client";

export interface VariationCardProps {
  variation: Variation;
  /** Nombre legible de la marca a la que pertenece. */
  brandName?: string;
  /** Etiqueta de familia en español (ej. "Logos", "Banners", "Tarjetas"). */
  categoryLabel?: string;
  isSelected: boolean;
  onToggleSelect: () => void;
  onOpenLightbox: () => void;
  onDownload: () => Promise<void>;
  downloading?: boolean;
  /** Handler para eliminar esta variación. */
  onDelete?: () => Promise<void>;
  /** true mientras se está eliminando esta variación. */
  deleting?: boolean;
}

export function VariationCard({
  variation,
  brandName,
  categoryLabel,
  isSelected,
  onToggleSelect,
  onOpenLightbox,
  onDownload,
  downloading = false,
  onDelete,
  deleting = false,
}: VariationCardProps) {
  const [promotion, setPromotion] = useState("");
  const [promoting, setPromoting] = useState(false);
  const controller = usePrivateOperation();

  async function promote() {
    setPromoting(true);
    try {
      await promoteVariation(variation.id, controller.current.signal);
      if (!controller.current.signal.aborted)
        setPromotion(
          "Pendiente de revisión. Abrí Imágenes para revisión para revisarla.",
        );
    } catch (e) {
      if (!isAbort(e)) setPromotion(mediaError(e));
    } finally {
      if (!controller.current.signal.aborted) setPromoting(false);
    }
  }
  const imageUrl = downloads.fileUrl(variation.id);

  return (
    <article
      className="eikon-gallery-card"
      aria-label={
        brandName ? `Variación de ${brandName}` : `Variación ${variation.id}`
      }
      style={{
        background: "var(--surface)",
        border: isSelected
          ? "2px solid var(--teal)"
          : "1px solid var(--border)",
        borderRadius: "var(--r-lg)",
        boxShadow: isSelected
          ? "0 0 0 3px color-mix(in srgb, var(--teal) 18%, transparent), var(--shadow-2)"
          : "var(--shadow-1)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        transition:
          "border-color var(--transition-normal), box-shadow var(--transition-normal)",
        animation: "eikon-fadein 220ms ease both",
      }}
    >
      {/* Zona de imagen */}
      <div style={{ position: "relative" }}>
        {/* Checkbox de selección — esquina superior izquierda */}
        <label
          title={isSelected ? "Deseleccionar" : "Seleccionar"}
          style={{
            position: "absolute",
            top: "var(--space-2)",
            left: "var(--space-2)",
            zIndex: 2,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 24,
            height: 24,
            background: isSelected ? "var(--teal)" : "var(--surface-2)",
            border: `2px solid ${isSelected ? "var(--teal)" : "var(--border-strong)"}`,
            borderRadius: "var(--r-sm)",
            cursor: "pointer",
            boxShadow: "var(--shadow-sm)",
            transition:
              "background var(--transition-fast), border-color var(--transition-fast)",
          }}
        >
          <input
            type="checkbox"
            checked={isSelected}
            onChange={onToggleSelect}
            aria-label={`Seleccionar variación${brandName ? ` de ${brandName}` : ""}`}
            style={{
              position: "absolute",
              opacity: 0,
              width: "100%",
              height: "100%",
              cursor: "pointer",
              margin: 0,
            }}
          />
          {isSelected && (
            <span
              aria-hidden="true"
              style={{
                color: "var(--teal-ink)",
                fontSize: 14,
                lineHeight: 1,
                fontWeight: 700,
              }}
            >
              ✓
            </span>
          )}
        </label>

        {/* Imagen clickeable → abre lightbox */}
        <button
          type="button"
          onClick={onOpenLightbox}
          aria-label={`Ver detalle${brandName ? ` de ${brandName}` : ""}`}
          style={{
            display: "block",
            width: "100%",
            border: "none",
            background: "var(--bg)",
            padding: "var(--space-5)",
            cursor: "zoom-in",
            lineHeight: 0,
          }}
        >
          <PrivateImage
            path={imageUrl}
            alt={`Vista previa de variación de ${brandName ?? variation.id}`}
          />
        </button>
      </div>

      <div style={{ padding: ".75rem 1rem" }}>
        <span className="media-status">Generador Eikón</span>
        <p>Sin revisión humana</p>
        <button
          className="media-text-button"
          disabled={promoting || promotion.startsWith("Pendiente")}
          onClick={() => void promote()}
        >
          Enviar a revisión
        </button>
        {promotion && <p role="status">{promotion}</p>}
      </div>
      {/* Footer: marca, calidad, botón descargar */}
      <div
        style={{
          padding: "var(--space-3) var(--space-4)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "var(--space-2)",
          borderTop: "1px solid var(--border)",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 2,
            minWidth: 0,
          }}
        >
          {brandName && (
            <span
              style={{
                fontSize: "var(--font-size-sm)",
                color: "var(--text-muted)",
                fontWeight: 600,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {brandName}
            </span>
          )}
          {categoryLabel && (
            <span
              aria-label={`Familia: ${categoryLabel}`}
              style={{
                fontSize: 12,
                color: "var(--teal)",
                fontWeight: 600,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
              }}
            >
              {categoryLabel}
            </span>
          )}
          <Stars score={variation.score} />
        </div>

        <div
          className="eikon-gallery-actions"
          style={{
            display: "flex",
            gap: "var(--space-2)",
            flexShrink: 0,
            transition:
              "opacity var(--transition-fast), transform var(--transition-fast)",
          }}
        >
          {onDelete && (
            <button
              type="button"
              onClick={() => {
                if (window.confirm("¿Borrar esta variación?")) {
                  void onDelete();
                }
              }}
              disabled={deleting}
              aria-label={`Eliminar variación${brandName ? ` de ${brandName}` : ""}`}
              title="Eliminar variación"
              style={{
                padding: "var(--space-2) var(--space-4)",
                background: deleting ? "var(--surface-2)" : "transparent",
                color: deleting ? "var(--text-faint)" : "var(--danger)",
                border: `1px solid ${deleting ? "var(--border)" : "var(--danger)"}`,
                borderRadius: "var(--r-md)",
                fontSize: "var(--font-size-sm)",
                fontWeight: 600,
                cursor: deleting ? "not-allowed" : "pointer",
                transition:
                  "background var(--transition-fast), color var(--transition-fast)",
                whiteSpace: "nowrap",
              }}
            >
              {deleting ? "…" : "🗑 Borrar"}
            </button>
          )}
          <button
            type="button"
            onClick={() => void onDownload()}
            disabled={downloading}
            aria-label={`Descargar variación${brandName ? ` de ${brandName}` : ""}`}
            title="Descargar imagen"
            style={{
              padding: "var(--space-2) var(--space-4)",
              background: downloading ? "var(--surface-2)" : "var(--teal)",
              color: downloading ? "var(--text-faint)" : "var(--teal-ink)",
              border: "none",
              borderRadius: "var(--r-md)",
              fontSize: "var(--font-size-sm)",
              fontWeight: 600,
              cursor: downloading ? "not-allowed" : "pointer",
              transition:
                "background var(--transition-fast), color var(--transition-fast)",
              whiteSpace: "nowrap",
            }}
          >
            {downloading ? "…" : "↓ Descargar"}
          </button>
        </div>
      </div>
    </article>
  );
}
