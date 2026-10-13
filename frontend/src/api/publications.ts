/** Contratos públicos de publicaciones; ninguna credencial social llega al navegador. */
import { ApiError, beginSessionWork } from "./client";
export type Platform = "facebook" | "instagram" | "tiktok" | "x";
export type Privacy =
  | "PUBLIC_TO_EVERYONE"
  | "MUTUAL_FOLLOW_FRIENDS"
  | "FOLLOWER_OF_CREATOR"
  | "SELF_ONLY";
export interface ChannelMetadata {
  sources: string[];
  rights: string;
  links?: string[];
  context?: string;
  privacy?: string | null;
  disable_comment?: boolean | null;
  disable_duet?: boolean | null;
  disable_stitch?: boolean | null;
  is_aigc?: boolean | null;
  commercial_content?: boolean | null;
  branded_content?: boolean | null;
  publication_format?: "feed" | "reel";
  platform_consent_receipt?: string | null;
}
export interface Revision {
  id: number;
  campaign_id: number;
  contract_hash: string;
  caption: string;
  policy_version: number;
  scheduled_at_utc: number;
  expires_at_utc: number;
  timezone: string;
  channel_metadata: ChannelMetadata;
  media: {
    id: number;
    kind: "gallery_image" | "publication_video";
    sha256: string;
    mime: string;
    width: number;
    height: number;
  };
  connection: {
    id: number;
    platform: Platform;
    remote_id: string;
    remote_name: string | null;
  };
  visual_review: { approval_current: boolean };
  decision: {
    id: number;
    outcome: "approve" | "hold" | "reject";
    reason: string;
    provider: string;
    model: string;
    created_at?: number;
  } | null;
  eligibility_reasons: string[];
}
export interface Campaign {
  id: number;
  project_id: number;
  brand_id: number;
  project_name: string;
  product_name: string;
  objective: string;
  archived: number;
  revisions: Revision[];
}
export interface Connection {
  id: number;
  platform: Platform;
  api_mode: string;
  remote_id: string;
  remote_name: string | null;
  status: string;
  version: number;
  project_ids: number[];
  scopes: string[];
  expires_at: number | null;
  hold_reason: string | null;
  scope_evidence: string;
  expiry_state: string;
}
export interface Policy {
  version: number;
  enabled: boolean;
  project_ids?: number[];
  product_ids?: number[];
  connection_ids?: number[];
  allowed_sources?: string[];
  timezone?: string;
  frequency_minutes?: number;
  max_daily_per_destination?: number;
  window_minutes?: number;
  valid_from?: number | null;
  expires_at?: number | null;
  spend_allowed?: boolean;
}
export interface Attempt {
  state: string;
  visibility?: "private" | "platform" | "unknown";
  result?: {
    state: string;
    remote_id: string | null;
    permalink: string | null;
  } | null;
}
export interface Delivery extends Attempt {
  id: number;
  revision_id: number;
  contract_hash: string;
  normalized_destination: string;
  media_sha256: string;
  due_at: number;
  expires_at: number;
  started_at: number | null;
  hold_reasons: string[];
  events?: { id: number; kind: string; created_at: number }[];
}
export interface Page<T> {
  items: T[];
  next_cursor: number | null;
}
export interface Overview {
  tenant: { id: number; slug: string; name: string };
  policy: Policy;
  campaigns: Page<Campaign>;
  connections: Connection[];
}
export interface CreatorInfo {
  creator_id: number;
  privacy_level_options: Privacy[];
  comment_disabled: boolean;
  duet_disabled: boolean;
  stitch_disabled: boolean;
  expires_at: number;
  creator_receipt_sha256: string;
}
export interface ConsentChoices {
  creator_id: number;
  contract_hash: string;
  privacy_level: Privacy;
  disable_comment: boolean;
  disable_duet: boolean;
  disable_stitch: boolean;
  brand_content_toggle: boolean;
  brand_organic_toggle: boolean;
  is_aigc: boolean;
  music_acknowledged: true;
  consent_confirmed: true;
}
export interface ConsentStatus {
  receipt_id?: number;
  consent: {
    consent_id: string;
    privacy_level: Privacy;
    expires_at: number;
  } | null;
  reasons: string[];
}
const root = "/api/v1/publications";
export function errorMessage(error: unknown) {
  return error instanceof ApiError
    ? error.detail
    : "No se pudo completar la operación. Vuelve a intentarlo.";
}
export function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}
export async function publicationRequest<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  if (
    !/^\/(overview|campaigns(?:\?.*|\/\d+\/revisions)?|calendar(?:\?.*|\/deliveries\/\d+\/cancel)?|connections|policy|deliveries\/\d+|revisions\/\d+\/(?:creator-info|consent)|consents\/\d+|oauth\/start)$/.test(
      path,
    )
  )
    throw new ApiError(422, "Ruta de publicación inválida.");
  const work = beginSessionWork(signal);
  try {
    work.check();
    const res = await fetch(root + path, {
      method,
      credentials: "include",
      cache: "no-store",
      signal: work.signal,
      headers: { "Content-Type": "application/json" },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    }).catch((error: unknown) => {
      work.check();
      if (error instanceof TypeError)
        throw new ApiError(0, "No se pudo conectar con el servidor. Revisa tu conexión y vuelve a intentarlo.");
      throw error;
    });
    work.check();
    if (res.status === 204) return undefined as T;
    const value = await res.json().catch(() => null);
    work.check();
    if (!res.ok) {
      const messages: Record<number, string> = {
        401: "Tu sesión venció. Vuelve a ingresar.",
        403: "Sólo el owner de esta empresa puede administrar publicaciones.",
        404: "No encontramos este registro en la empresa activa.",
        409: "La autorización o revisión cambió. Actualiza y revisa los requisitos pendientes.",
        422: "Revisa los campos y selecciona una privacidad válida.",
        429: "El proveedor limitó las solicitudes. Intenta más tarde.",
      };
      const causes: Record<string, string> = {
        campaign_revision_limit:
          "Esta campaña alcanzó 100 revisiones. Crea otra campaña para continuar; el historial se conserva.",
        revision_superseded:
          "Esta revisión ya fue sustituida. Actualiza y edita su revisión vigente.",
        needs_platform_audit:
          "Falta evidencia privada de dominio, revisión de contenido o auditoría de TikTok.",
        creator_info_required:
          "Consulta primero las opciones actuales de TikTok.",
        new_revision_required:
          "Las opciones cambiaron. Crea una nueva revisión y solicita otra evaluación IA.",
        aigc_disclosure_required:
          "La procedencia registrada indica generación IA. Declara contenido generado por IA en una nueva revisión.",
        oauth_not_configured:
          "La conexión OAuth de esta red aún no está configurada por el operador.",
        vault_key_unavailable:
          "El servicio de credenciales no está disponible. El operador debe completar su configuración.",
        consent_receipt_changed:
          "El consentimiento cambió después de reservar. Se necesita una nueva revisión y evaluación IA.",
      };
      throw new ApiError(
        res.status,
        causes[value?.detail] ||
          messages[res.status] ||
          "El servicio no está disponible. Intenta más tarde.",
      );
    }
    if (value === null)
      throw new ApiError(502, "Respuesta incompleta del servidor.");
    return value as T;
  } catch (error) {
    work.check();
    throw error;
  } finally {
    work.finish();
  }
}
export const getOverview = (signal?: AbortSignal) =>
  publicationRequest<Overview>("/overview", "GET", undefined, signal);
export const getCalendar = (cursor = 0, signal?: AbortSignal) =>
  publicationRequest<Page<Delivery>>(
    `/calendar?cursor=${cursor}`,
    "GET",
    undefined,
    signal,
  );
export const getCampaigns = (cursor = 0, signal?: AbortSignal) =>
  publicationRequest<Page<Campaign>>(
    `/campaigns?cursor=${cursor}`,
    "GET",
    undefined,
    signal,
  );
export const getDelivery = (id: number, signal?: AbortSignal) =>
  publicationRequest<Delivery>(`/deliveries/${id}`, "GET", undefined, signal);
export const getConsent = (id: number, signal?: AbortSignal) =>
  publicationRequest<ConsentStatus>(
    `/revisions/${id}/consent`,
    "GET",
    undefined,
    signal,
  );
export const creatorInfo = (revision: Revision, signal?: AbortSignal) =>
  publicationRequest<CreatorInfo>(
    `/revisions/${revision.id}/creator-info`,
    "POST",
    { contract_hash: revision.contract_hash },
    signal,
  );
export const consent = (
  revision: Revision,
  choices: ConsentChoices,
  signal?: AbortSignal,
) =>
  publicationRequest<{ receipt_id: number; consent: ConsentStatus["consent"] }>(
    `/revisions/${revision.id}/consent`,
    "POST",
    choices,
    signal,
  );
export const revise = (
  revision: Revision,
  caption: string,
  metadata: ChannelMetadata,
  signal?: AbortSignal,
  scheduledAt = new Date(revision.scheduled_at_utc * 1000).toISOString(),
  policyVersion = revision.policy_version,
) =>
  publicationRequest<unknown>(
    `/campaigns/${revision.campaign_id}/revisions`,
    "POST",
    {
      supersedes_revision_id: revision.id,
      supersedes_contract_hash: revision.contract_hash,
      media_id: revision.media.id,
      media_kind: revision.media.kind,
      caption,
      connection_id: revision.connection.id,
      scheduled_at: scheduledAt,
      policy_version: policyVersion,
      channel_metadata: metadata,
    },
    signal,
  );
export function policyInput(policy: Policy) {
  return {
    enabled: policy.enabled,
    project_ids: policy.project_ids || [],
    product_ids: policy.product_ids || [],
    connection_ids: policy.connection_ids || [],
    allowed_sources: policy.allowed_sources || [],
    timezone: policy.timezone || "UTC",
    frequency_minutes: policy.frequency_minutes || 60,
    max_daily_per_destination: policy.max_daily_per_destination || 1,
    window_minutes: policy.window_minutes || 60,
    valid_from: policy.valid_from
      ? new Date(policy.valid_from * 1000).toISOString()
      : null,
    expires_at: policy.expires_at
      ? new Date(policy.expires_at * 1000).toISOString()
      : null,
    spend_allowed: false,
  };
}
/** Sólo una referencia tipada; nunca URLs arbitrarias ni cookies hacia un host externo. */
export async function privatePreview(
  revision: Revision,
  signal: AbortSignal,
): Promise<{ url: string; release: () => void }> {
  if (
    !Number.isSafeInteger(revision.id) ||
    revision.id < 1 ||
    !/^[a-f0-9]{64}$/.test(revision.contract_hash) ||
    !/^[a-f0-9]{64}$/.test(revision.media.sha256) ||
    !["image/png", "image/jpeg", "video/mp4"].includes(revision.media.mime)
  )
    throw new ApiError(422, "Referencia de archivo inválida.");
  const work = beginSessionWork(signal);
  let url: string | null = null;
  const release = () => {
    if (url) {
      URL.revokeObjectURL(url);
      url = null;
    }
    work.finish();
  };
  work.onCancel(release);
  try {
    work.check();
    const response = await fetch(
      `${root}/revisions/${revision.id}/preview?contract_hash=${revision.contract_hash}`,
      { credentials: "include", cache: "no-store", signal: work.signal },
    );
    work.check();
    if (!response.ok)
      throw new ApiError(
        response.status,
        "No se puede mostrar el archivo exacto.",
      );
    const bytes = await response.arrayBuffer();
    work.check();
    const hash = Array.from(
      new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
      (x) => x.toString(16).padStart(2, "0"),
    ).join("");
    work.check();
    if (hash !== revision.media.sha256)
      throw new ApiError(
        409,
        "El archivo recibido no coincide con esta revisión.",
      );
    url = URL.createObjectURL(new Blob([bytes], { type: revision.media.mime }));
    work.check();
    return { url, release };
  } catch (error) {
    release();
    throw error;
  }
}
export function safePermalink(value: string | null | undefined) {
  try {
    const p = new URL(value || "");
    return p.protocol === "https:" && !p.username && !p.password
      ? p.href
      : null;
  } catch {
    return null;
  }
}
