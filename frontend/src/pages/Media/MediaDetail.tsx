import { usePrivateOperation } from "./usePrivateOperation";
import { useEffect, useState } from "react";
import {
  getMedia,
  loadMediaReviewContext,
  releasePrivateUrl,
  type MediaReviewContext,
  isAbort,
  mediaError,
  mediaLabels,
  reviewMedia,
  type Media,
} from "../../api/media";
import { ApiError } from "../../api/client";
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
    [context, setContext] = useState<MediaReviewContext | null>(null),
    [contextLoading, setContextLoading] = useState(true),
    [error, setError] = useState(""),
    [reason, setReason] = useState(""),
    [busy, setBusy] = useState(false),
    [reload, setReload] = useState(0),
    [message, setMessage] = useState("");
  useEffect(() => {
    const c = new AbortController();
    let logoUrl: string | null = null;
    setItem(null);
    setContext(null);
    setContextLoading(true);
    setError("");
    async function load() {
      const media = await getMedia(id, c.signal);
      if (c.signal.aborted) return;
      setItem(media);
      const evidence = await loadMediaReviewContext(media, c.signal);
      logoUrl = evidence.logoUrl;
      if (c.signal.aborted) {
        if (logoUrl) releasePrivateUrl(logoUrl);
        return;
      }
      setContext(evidence);
    }
    void load()
      .catch((e) => {
        if (!c.signal.aborted && !isAbort(e)) setError(mediaError(e));
      })
      .finally(() => {
        if (!c.signal.aborted) setContextLoading(false);
      });
    return () => {
      c.abort();
      if (logoUrl) releasePrivateUrl(logoUrl);
    };
  }, [id, reload]);
  const operation = usePrivateOperation();

  async function review(decision: "approved" | "rejected") {
    const controller = operation.current;
    if (!item || !context?.ready || contextLoading || controller.signal.aborted)
      return;
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
        controller.signal,
      );
      if (controller.signal.aborted) return;
      setItem(await getMedia(id, controller.signal));
      setReason("");
      setMessage(
        decision === "approved" ? "Imagen aprobada." : "Imagen rechazada.",
      );
      onReviewed();
    } catch (e) {
      if (!isAbort(e) && !controller.signal.aborted) {
        setError(mediaError(e));
        if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
          if (context.logoUrl) releasePrivateUrl(context.logoUrl);
          setContext(null);
        } else {
          setContext((current) =>
            current
              ? {
                  ...current,
                  ready: false,
                  warning:
                    "La revisión no se completó. Actualizá el encargo y sus referencias antes de volver a revisar.",
                }
              : null,
          );
        }
      }
    } finally {
      if (!controller.signal.aborted) setBusy(false);
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
              {contextLoading && (
                <p role="status">Cargando encargo y referencias de marca…</p>
              )}
              {context?.warning && <p role="status">{context.warning}</p>}
              {context?.brief && (
                <section aria-label="Encargo original">
                  <h3>Encargo original</h3>
                  <p style={{ whiteSpace: "pre-wrap" }}>
                    {context.brief.prompt}
                  </p>
                  <p>
                    {context.brief.snapshot.project.name} · Versión de marca{" "}
                    {context.brief.snapshot.brand_version} ·{" "}
                    {context.brief.width} × {context.brief.height}
                  </p>
                  <h4>Identidad del encargo</h4>
                  <p>{context.brief.snapshot.identity.name}</p>
                  {context.logoUrl ? (
                    <img
                      className="media-image"
                      style={{ maxHeight: 180 }}
                      src={context.logoUrl}
                      alt="Logo original del encargo"
                    />
                  ) : (
                    <p>
                      Logo del generador:{" "}
                      {context.brief.snapshot.identity.logo_style ||
                        "Identidad sin referencia oficial"}{" "}
                      · Semilla{" "}
                      {context.brief.snapshot.identity.logo_seed ??
                        "no indicada"}
                    </p>
                  )}
                  <details>
                    <summary>Colores, tipografía y textos originales</summary>
                    <pre>
                      {JSON.stringify(
                        {
                          palette: context.brief.snapshot.identity.palette,
                          typography:
                            context.brief.snapshot.identity.typography,
                          texts: context.brief.snapshot.identity.texts,
                          logo_text: context.brief.snapshot.identity.logo_text,
                        },
                        null,
                        2,
                      )}
                    </pre>
                  </details>
                </section>
              )}
              {!contextLoading && !context && (
                <p>
                  No se pudo verificar el encargo y sus referencias. Actualizá
                  el detalle antes de revisar.
                </p>
              )}
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
                    <Button
                      busy={busy}
                      disabled={contextLoading || !context?.ready}
                      onClick={() => void review("approved")}
                    >
                      Aprobar
                    </Button>
                    <Button
                      variant="danger"
                      disabled={contextLoading || !context?.ready}
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
