import { Button } from "../../components";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Campaign,
  Revision,
  CreatorInfo,
  Privacy,
  ChannelMetadata,
  consent,
  creatorInfo,
  errorMessage,
  getConsent,
  isAbort,
  privatePreview,
  publicationRequest,
  revise,
} from "../../api/publications";
import { usePrivateOperation } from "../Media/usePrivateOperation";

function ExactPreview({
  revision,
  onReady,
}: {
  revision: Revision;
  onReady: (value: boolean) => void;
}) {
  const [url, setUrl] = useState(""),
    [error, setError] = useState("");
  useEffect(() => {
    const c = new AbortController();
    let release: (() => void) | undefined;
    setUrl("");
    onReady(false);
    privatePreview(revision, c.signal)
      .then((result) => {
        release = result.release;
        if (c.signal.aborted) {
          release();
          return;
        }
        setUrl(result.url);
        onReady(true);
      })
      .catch((e) => {
        if (!isAbort(e)) setError(errorMessage(e));
      });
    return () => {
      c.abort();
      release?.();
    };
  }, [revision.id, revision.contract_hash]);
  return (
    <div className="pub-preview">
      {url ? (
        revision.media.kind === "publication_video" ? (
          <video
            controls
            preload="metadata"
            src={url}
            aria-label="Video exacto de la revisión"
          />
        ) : (
          <img src={url} alt="Archivo exacto de esta revisión" />
        )
      ) : (
        <p>{error || "Cargando archivo exacto…"}</p>
      )}
      <p className="pub-hash">SHA256 {revision.media.sha256}</p>
    </div>
  );
}
function Candidate({
  revision: r,
  owner,
  onRefresh,
  policyVersion,
  previewOpen,
  onPreview,
}: {
  previewOpen: boolean;
  onPreview: () => void;
  revision: Revision;
  owner: boolean;
  onRefresh: () => void;
  policyVersion?: number;
}) {
  const [scheduled, setScheduled] = useState(
    new Date(r.scheduled_at_utc * 1000).toISOString(),
  );
  const [ready, setReady] = useState(false),
    [caption, setCaption] = useState(r.caption),
    [privacy, setPrivacy] = useState<Privacy | "">(""),
    [commercial, setCommercial] = useState(
      r.channel_metadata.commercial_content === true,
    ),
    [branded, setBranded] = useState(
      r.channel_metadata.branded_content === true,
    ),
    [creator, setCreator] = useState<CreatorInfo | null>(null),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [music, setMusic] = useState(false),
    [confirmed, setConfirmed] = useState(false),
    [aigc, setAigc] = useState(r.channel_metadata.is_aigc === true),
    [comments, setComments] = useState(
      r.channel_metadata.disable_comment === true,
    ),
    [duet, setDuet] = useState(r.channel_metadata.disable_duet === true),
    [stitch, setStitch] = useState(r.channel_metadata.disable_stitch === true),
    [receiptId, setReceiptId] = useState<number | null>(null);
  const operation = usePrivateOperation();
  const tiktok = r.connection.platform === "tiktok";
  useEffect(() => {
    if (!previewOpen) setReady(false);
  }, [previewOpen]);
  useEffect(() => {
    if (!tiktok) return;
    const c = new AbortController();
    getConsent(r.id, c.signal)
      .then((s) => {
        if (s.receipt_id) setReceiptId(s.receipt_id);
        if (s.consent)
          setMessage(
            `Consentimiento registrado: ${s.consent.privacy_level}. Vence ${new Date(s.consent.expires_at * 1000).toLocaleString()}`,
          );
      })
      .catch((e) => {
        if (!isAbort(e)) setError(errorMessage(e));
      });
    return () => c.abort();
  }, [r.id, tiktok]);
  const act = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      if (!isAbort(e)) setError(errorMessage(e));
    } finally {
      if (!operation.current.signal.aborted) setBusy(false);
    }
  };
  const loadCreator = () =>
    act(async () => {
      const c = await creatorInfo(r, operation.current.signal);
      setCreator(c);
      setPrivacy("");
      setComments((old) => old || c.comment_disabled);
      setDuet((old) => old || c.duet_disabled);
      setStitch((old) => old || c.stitch_disabled);
    });
  const changed =
    aigc !== r.channel_metadata.is_aigc ||
    comments !== r.channel_metadata.disable_comment ||
    duet !== r.channel_metadata.disable_duet ||
    stitch !== r.channel_metadata.disable_stitch ||
    scheduled !== new Date(r.scheduled_at_utc * 1000).toISOString() ||
    caption !== r.caption ||
    (privacy !== "" && privacy !== r.channel_metadata.privacy) ||
    commercial !== r.channel_metadata.commercial_content ||
    branded !== r.channel_metadata.branded_content;
  const saveRevision = () =>
    act(async () => {
      const metadata: ChannelMetadata = {
        ...r.channel_metadata,
        ...(tiktok
          ? {
              privacy: privacy || null,
              disable_comment: comments,
              disable_duet: duet,
              disable_stitch: stitch,
              is_aigc: aigc,
              commercial_content: commercial,
              branded_content: branded,
              platform_consent_receipt: null,
            }
          : {}),
      };
      await revise(
        r,
        caption,
        metadata,
        operation.current.signal,
        scheduled,
        policyVersion,
      );
      setMessage(
        "Nueva revisión creada. Necesita una nueva evaluación IA y consentimiento propio.",
      );
      onRefresh();
    });
  const confirm = () =>
    act(async () => {
      if (
        !creator || !privacy || !music || !confirmed || !ready || !previewOpen || changed
      )
        return;
      const result = await consent(
        r,
        {
          contract_hash: r.contract_hash,
          creator_id: creator.creator_id,
          privacy_level: privacy,
          disable_comment: comments,
          disable_duet: duet,
          disable_stitch: stitch,
          brand_content_toggle: branded,
          brand_organic_toggle: commercial,
          is_aigc: aigc,
          music_acknowledged: true,
          consent_confirmed: true,
        },
        operation.current.signal,
      );
      setReceiptId(result.receipt_id);
      setMessage(
        "Consentimiento registrado para esta revisión exacta. La IA y los requisitos de la cuenta siguen determinando el envío.",
      );
    });
  const isReel =
    r.media.kind === "publication_video" &&
    r.connection.platform === "instagram";
  return (
    <article className="pub-candidate">
      <header>
        <h3>
          Revisión {r.id} · {r.connection.remote_name || r.connection.remote_id}
        </h3>
        <p>
          {r.connection.platform} / {r.connection.remote_id}
        </p>
        {isReel && (
          <p>
            Instagram REELS ·{" "}
            {r.channel_metadata.publication_format === "reel"
              ? "Sin compartir en feed"
              : "Compartir en feed"}
          </p>
        )}
      </header>
      <div className="pub-candidate-grid">
        <div>
          <Button aria-expanded={previewOpen} onClick={onPreview}>
            {previewOpen ? "Cerrar archivo exacto" : "Ver archivo exacto"}
          </Button>
          {previewOpen && <ExactPreview revision={r} onReady={setReady} />}
        </div>
        <div>
          <h4>Evaluación IA</h4>
          <strong>
            {!r.decision
              ? "Pendiente de evaluación"
              : {
                  approve: "Autorizada por IA",
                  reject: "Rechazada por IA",
                  hold: "Retenida por IA",
                }[r.decision.outcome]}
          </strong>
          {r.decision && (
            <>
              <p>{r.decision.reason}</p>
              <p>
                {r.decision.provider} / {r.decision.model}
              </p>
            </>
          )}
          <p>
            Revisión humana visual:{" "}
            {r.visual_review.approval_current
              ? "aprobada al congelar"
              : "sin aprobación visual al congelar"}
            .
          </p>
          <p>
            Fecha:{" "}
            {new Date(r.scheduled_at_utc * 1000).toLocaleString("es", {
              timeZone: r.timezone,
            })}{" "}
            ({r.timezone})
          </p>
          {r.expires_at_utc <= Date.now() / 1000 && (
            <p>
              Fecha expirada. Prepara otra fecha con una nueva revisión y
              evaluación IA.
            </p>
          )}
          <details>
            <summary>Fuentes y contrato exacto</summary>
            <ul>
              {r.channel_metadata.sources.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
            <p>{r.channel_metadata.context}</p>
            <p>Derechos: {r.channel_metadata.rights || "Sin evidencia"}</p>
            <p className="pub-hash">Contrato {r.contract_hash}</p>
          </details>
          {!!r.eligibility_reasons.length && (
            <div className="pub-hold">
              <p>Requisitos pendientes:</p>
              <ul>
                {r.eligibility_reasons.map((reason) => (
                  <li key={reason}>
                    {reason === "needs_platform_consent"
                      ? "Requiere consentimiento por contenido"
                      : reason === "needs_platform_audit"
                        ? "Falta acreditar revisión, dominio o auditoría TikTok"
                        : reason}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <label>
            Fecha de envío (ISO con zona)
            <input
              disabled={!owner || busy}
              value={scheduled}
              onChange={(e) => {
                setScheduled(e.target.value);
                setConfirmed(false);
              }}
            />
          </label>
          <label>
            Texto de la publicación
            <textarea
              value={caption}
              disabled={!owner || busy}
              onChange={(e) => {
                setCaption(e.target.value);
                setConfirmed(false);
              }}
            />
          </label>
          {tiktok && (
            <fieldset disabled={!owner || busy}>
              <legend>Consentimiento TikTok por contenido</legend>
              <p>
                Revisa el archivo y la cuenta antes de consentir. La privacidad
                debe elegirse explícitamente.
              </p>
              <Button type="button" onClick={loadCreator}>
                Consultar opciones actuales de TikTok
              </Button>
              <label>
                Privacidad TikTok
                <select
                  value={privacy}
                  onChange={(e) => {
                    setPrivacy(e.target.value as Privacy | "");
                    setConfirmed(false);
                  }}
                >
                  <option value="">Selecciona privacidad</option>
                  {(creator?.privacy_level_options || []).map((p) => (
                    <option key={p} value={p}>
                      {p === "SELF_ONLY" ? "Sólo yo (privada)" : p}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={commercial}
                  onChange={(e) => {
                    setCommercial(e.target.checked);
                    setConfirmed(false);
                  }}
                />{" "}
                Promociona mi marca o negocio
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={branded}
                  onChange={(e) => {
                    setBranded(e.target.checked);
                    setConfirmed(false);
                  }}
                />{" "}
                Contenido de marca para un tercero
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={comments}
                  disabled={!creator || creator.comment_disabled}
                  onChange={(e) => setComments(e.target.checked)}
                />{" "}
                Desactivar comentarios
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={duet}
                  disabled={!creator || creator.duet_disabled}
                  onChange={(e) => setDuet(e.target.checked)}
                />{" "}
                Desactivar dúos
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={stitch}
                  disabled={!creator || creator.stitch_disabled}
                  onChange={(e) => setStitch(e.target.checked)}
                />{" "}
                Desactivar pegar
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={aigc}
                  onChange={(e) => setAigc(e.target.checked)}
                />{" "}
                Declarar contenido generado por IA
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={music}
                  onChange={(e) => setMusic(e.target.checked)}
                />{" "}
                Acepto la confirmación de uso de música y tengo los derechos
                necesarios
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                />{" "}
                Consiento enviar este archivo y texto exactos a esta cuenta con
                estas opciones
              </label>
              <Button
                style={{ whiteSpace: "normal", overflowWrap: "anywhere" }}
                type="button"
                disabled={
                  !creator ||
                  !privacy ||
                  !ready ||
                  !previewOpen ||
                  !music ||
                  !confirmed ||
                  changed ||
                  creator.expires_at <= Date.now() / 1000
                }
                onClick={confirm}
              >
                Registrar consentimiento exacto
              </Button>
              {receiptId && (
                <Button
                  type="button"
                  onClick={() =>
                    act(async () => {
                      await publicationRequest(
                        `/consents/${receiptId}`,
                        "DELETE",
                        undefined,
                        operation.current.signal,
                      );
                      setReceiptId(null);
                      setMessage("Consentimiento revocado.");
                    })
                  }
                >
                  Revocar consentimiento
                </Button>
              )}
            </fieldset>
          )}
          {owner && (
            <>
              <Button
                style={{ whiteSpace: "normal", overflowWrap: "anywhere" }}
                disabled={
                  busy ||
                  !(
                    caption !== r.caption ||
                    scheduled !==
                      new Date(r.scheduled_at_utc * 1000).toISOString() ||
                    (tiktok && changed)
                  ) ||
                  (tiktok && !privacy)
                }
                onClick={saveRevision}
              >
                Crear nueva revisión y solicitar evaluación IA
              </Button>
              <p>
                Editar texto o privacidad crea un contrato nuevo. El cliente
                Codex deberá evaluarlo de nuevo.
              </p>
            </>
          )}
          {error && <p role="alert">{error}</p>}
          {message && <p role="status">{message}</p>}
        </div>
      </div>
    </article>
  );
}
export function CampaignDetail({
  campaign,
  owner,
  onRefresh,
  policyVersion,
}: {
  campaign: Campaign;
  owner: boolean;
  onRefresh: () => void;
  policyVersion?: number;
}) {
  const [previewId, setPreviewId] = useState<number | null>(null);
  useEffect(() => setPreviewId(null), [campaign.id]);
  return (
    <section>
      <h2>
        {campaign.product_name}: {campaign.objective}
      </h2>
      <p>
        Proyecto {campaign.project_name} ({campaign.project_id}) · Producto{" "}
        {campaign.brand_id}
      </p>
      <nav aria-label="Producto">
        <Link to={`/brands/${campaign.brand_id}/identity`}>Identidad</Link>{" "}
        <Link to={`/gallery?project=${campaign.project_id}`}>
          Galería del producto
        </Link>
      </nav>
      <p>
        Límite: 100 revisiones por campaña, incluido el historial. Al alcanzarlo,
        crea otra campaña.
      </p>
      {!campaign.revisions.length && (
        <p>
          Esta campaña aún no tiene candidatos. El cliente Codex prepara las
          piezas y sus revisiones.
        </p>
      )}
      {campaign.revisions.map((r) => (
        <Candidate
          key={`${r.id}:${r.contract_hash}`}
          revision={r}
          previewOpen={previewId === r.id}
          onPreview={() => setPreviewId(previewId === r.id ? null : r.id)}
          policyVersion={policyVersion}
          owner={owner}
          onRefresh={onRefresh}
        />
      ))}
    </section>
  );
}
