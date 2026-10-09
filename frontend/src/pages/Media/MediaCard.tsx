import { mediaLabels, type Media } from "../../api/media";
import { PrivateImage } from "./PrivateImage";
export function MediaCard({
  item,
  brandName,
  projectName,
  onOpen,
}: {
  item: Media;
  brandName: string;
  projectName: string;
  onOpen: () => void;
}) {
  return (
    <article className="media-card">
      <button
        className="media-preview"
        onClick={onOpen}
        aria-label={`Abrir imagen ${item.id} de ${brandName}`}
      >
        <PrivateImage
          path={item.thumbnail_url}
          alt={`Imagen ${item.id} de ${brandName}`}
        />
      </button>
      <div className="media-card-info">
        <span className={`media-status media-${item.status}`}>
          {mediaLabels[item.status]}
        </span>
        <h2>{brandName}</h2>
        <p>{projectName}</p>
        <p>
          {item.source === "codex" ? "Codex" : "Generador Eikón"} · {item.width}{" "}
          × {item.height}
        </p>
        <button className="media-text-button" onClick={onOpen}>
          Ver detalle y revisión
        </button>
      </div>
    </article>
  );
}
