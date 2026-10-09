import { usePrivateOperation } from "./usePrivateOperation";
import { useEffect, useState } from "react";
import {
  getMedia,
  isAbort,
  mediaError,
  mediaLabels,
  reviewMedia,
  type Media,
} from "../../api/media";
import { Button, Modal } from "../../components";
import { PrivateImage } from "./PrivateImage";
export function MediaDetail({
  id,
  owner,
  onClose,
  onReviewed,
}: {
  id: number;
  owner: boolean;
  onClose: () => void;
  onReviewed: () => void;
}) {
  const [item, setItem] = useState<Media | null>(null),
    [error, setError] = useState(""),
    [reason, setReason] = useState(""),
    [busy, setBusy] = useState(false),
    [reload, setReload] = useState(0),
    [message, setMessage] = useState("");
  useEffect(() => {
    const c = new AbortController();
    setItem(null);
    setError("");
    void getMedia(id, c.signal)
      .then(setItem)
      .catch((e) => {
        if (!isAbort(e)) setError(mediaError(e));
      });
    return () => c.abort();
  }, [id, reload]);
  const operation = usePrivateOperation();

  async function review(decision: "approved" | "rejected") {
    if (!item) return;
    if (decision === "rejected" && !reason.trim()) {
      setError("Escribí un motivo para rechazar la imagen.");
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await reviewMedia(
        id,
        {
          decision,
          expected_sha256: item.sha256,
          expected_brand_version: item.brand_version,
          reason: reason.trim(),
        },
        operation.current.signal,
      );
      if (operation.current.signal.aborted) return;
      setItem(await getMedia(id, operation.current.signal));
      setReason("");
      setMessage(
        decision === "approved" ? "Imagen aprobada." : "Imagen rechazada.",
      );
      onReviewed();
    } catch (e) {
      if (!isAbort(e)) setError(mediaError(e));
    } finally {
      if (!operation.current.signal.aborted) setBusy(false);
    }
  }
  return (
    <Modal open onClose={onClose} title={`Imagen ${id}`} maxWidth="1000px">
      <div className="media-detail">
        {item && (
          <PrivateImage
            path={item.download_url}
            alt={`Original de la imagen ${id}`}
          />
        )}
        <div>
          {!item && !error && <p role="status">Cargando detalle…</p>}
          {error && (
            <div role="alert">
              <p>{error}</p>
              <Button
                variant="secondary"
                onClick={() => {
                  setReload((v) => v + 1);
                  setMessage("");
                }}
              >
                Actualizar detalle
              </Button>
            </div>
          )}
          {message && <p role="status">{message}</p>}
          {item && (
            <>
              <span className={`media-status media-${item.status}`}>
                {mediaLabels[item.status]}
              </span>
              <p>
                Origen: {item.source === "codex" ? "Codex" : "Generador Eikón"}
              </p>
              <p>
                {item.width} × {item.height} · Versión de marca{" "}
                {item.brand_version}
              </p>
              <details>
                <summary>Original y procedencia</summary>
                <p className="media-hash">SHA256: {item.sha256}</p>
                <pre>{JSON.stringify(item.provenance, null, 2)}</pre>
              </details>
              <h3>Historial de revisión</h3>
              {item.reviews.length === 0 ? (
                <p>
                  Todavía no tiene revisiones. El ingreso de una imagen no
                  implica aprobación.
                </p>
              ) : (
                <ol className="media-reviews">
                  {item.reviews.map((r) => (
                    <li key={r.id}>
                      <strong>{mediaLabels[r.decision]}</strong>
                      <p>{r.reason || "Sin comentario"}</p>
                      <small>
                        {new Date(r.created_at * 1000).toLocaleString("es")} ·
                        Versión {r.brand_version}
                      </small>
                    </li>
                  ))}
                </ol>
              )}
              {owner && item.status !== "archived" && (
                <div className="media-review-form">
                  <label htmlFor="review-reason">
                    Motivo de revisión (obligatorio para rechazar)
                  </label>
                  <textarea
                    id="review-reason"
                    maxLength={4000}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                  <div className="media-actions">
                    <Button busy={busy} onClick={() => void review("approved")}>
                      Aprobar
                    </Button>
                    <Button
                      variant="danger"
                      busy={busy}
                      onClick={() => void review("rejected")}
                    >
                      Rechazar
                    </Button>
                  </div>
                </div>
              )}
              {!owner && (
                <p>La revisión corresponde al propietario de esta empresa.</p>
              )}
            </>
          )}
        </div>
      </div>
    </Modal>
  );
}
