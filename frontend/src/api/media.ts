import { ApiError, beginSessionWork, cancelApiRequests } from "./client";
export type MediaStatus =
  | "pending_review"
  | "approved"
  | "rejected"
  | "archived";
export const mediaLabels: Record<MediaStatus, string> = {
  pending_review: "Pendiente de revisión",
  approved: "Aprobado",
  rejected: "Rechazado",
  archived: "Archivado",
};
export interface Project {
  id: number;
  slug: string;
  name: string;
  description: string;
  archived: number | boolean;
}
export interface Review {
  id: number;
  decision: "approved" | "rejected";
  reason: string;
  created_at: number;
  brand_version: number;
  sha256: string;
}
export interface Media {
  id: number;
  brief_id: number | null;
  snapshot_hash: string;
  project_id: number;
  brand_id: number;
  brand_version: number;
  sha256: string;
  mime: string;
  width: number;
  height: number;
  byte_size: number;
  source: "codex" | "legacy";
  status: MediaStatus;
  approval_current: boolean;
  download_url: string;
  thumbnail_url: string;
  provenance: Record<string, unknown>;
  reviews: Review[];
}
export interface Page<T> {
  items: T[];
  next_cursor: number | null;
}
export interface MediaFilters {
  brand_id?: number;
  project_id?: number;
  source?: "codex" | "legacy";
  status?: MediaStatus;
  cursor?: number;
}
export interface ApiKey {
  id: number;
  name: string;
  scopes: string[];
  expires_at: number;
  revoked?: boolean;
}
// Closed grant list: none of these permissions can approve, administer keys or write identity.
export const codexScopes = [
  "projects:read",
  "projects:write",
  "brands:read",
  "briefs:write",
  "media:read",
  "media:write",
] as const;
const pending = new Set<AbortController>();
const objectUrls = new Set<string>();
export function clearPrivateMedia() {
  cancelApiRequests();
  for (const c of pending) c.abort();
  pending.clear();
  for (const u of objectUrls) URL.revokeObjectURL(u);
  objectUrls.clear();
}
export function releasePrivateUrl(url: string) {
  URL.revokeObjectURL(url);
  objectUrls.delete(url);
}
export function mediaError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401)
      return "Tu sesión venció. Salí y volvé a iniciar sesión.";
    if (error.status === 409)
      return "La identidad o la pieza cambió. Actualizá el detalle antes de revisar.";
    if (error.status === 403)
      return "Tu cuenta no tiene permiso para esta acción.";
    return error.detail;
  }
  return "No se pudo conectar. Reintentá la operación.";
}
export function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}
async function privateRequest<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const controller = new AbortController();
  pending.add(controller);
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  if (signal?.aborted) controller.abort();
  try {
    const res = await fetch(path, {
      method,
      signal: controller.signal,
      credentials: "include",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    if (res.status === 204) return undefined as T;
    controller.signal.throwIfAborted();
    const json = await res.json();
    controller.signal.throwIfAborted();
    if (!res.ok)
      throw new ApiError(
        res.status,
        typeof json.detail === "string"
          ? json.detail
          : "Revisá los datos e intentá de nuevo.",
      );
    return json as T;
  } finally {
    pending.delete(controller);
    signal?.removeEventListener("abort", abort);
  }
}
export async function privateImage(
  path: string,
  signal: AbortSignal,
  expectedSha256?: string,
) {
  // The API contract provides relative authenticated paths. Never transmit cookies to arbitrary links.
  const mediaPath =
    /^\/api\/v1\/(media\/\d+\/(download|thumbnail)|variations\/\d+\/file)(\?.*)?$/.test(
      path,
    );
  const referencePath =
    /^\/api\/v1\/brands\/\d+\/reference-logo\?sha256=[a-f0-9]{64}$/.test(path);
  if (!mediaPath && !referencePath)
    throw new Error("Ruta de imagen privada inválida");
  if (
    referencePath &&
    (!expectedSha256 || !path.endsWith(`sha256=${expectedSha256}`))
  )
    throw new Error("Referencia de logo inválida");
  const c = new AbortController();
  pending.add(c);
  const abort = () => c.abort();
  signal.addEventListener("abort", abort, { once: true });
  if (signal.aborted) c.abort();
  try {
    const res = await fetch(path, {
      credentials: "include",
      cache: "no-store",
      signal: c.signal,
    });
    if (!res.ok) throw new ApiError(res.status, "No se pudo cargar la imagen.");
    const blob = await res.blob();
    if (c.signal.aborted) throw new DOMException("Aborted", "AbortError");
    if (expectedSha256) {
      const hash = Array.from(
        new Uint8Array(
          await crypto.subtle.digest("SHA-256", await blob.arrayBuffer()),
        ),
      )
        .map((value) => value.toString(16).padStart(2, "0"))
        .join("");
      c.signal.throwIfAborted();
      if (hash !== expectedSha256)
        throw new ApiError(
          422,
          "El logo de referencia no coincide con el encargo original.",
        );
    }
    const url = URL.createObjectURL(blob);
    objectUrls.add(url);
    return url;
  } finally {
    pending.delete(c);
    signal.removeEventListener("abort", abort);
  }
}
export const listProjects = (signal?: AbortSignal, cursor?: number) =>
  privateRequest<Page<Project>>(
    `/api/v1/projects?limit=100${cursor ? `&cursor=${cursor}` : ""}`,
    "GET",
    undefined,
    signal,
  );
export const createProject = (
  payload: {
    name: string;
    slug: string;
    description: string;
  },
  signal?: AbortSignal,
) => privateRequest<Project>("/api/v1/projects", "POST", payload, signal);
export const listMedia = (filters: MediaFilters = {}, signal?: AbortSignal) => {
  const query = new URLSearchParams();
  for (const [k, v] of Object.entries(filters))
    if (v !== undefined) query.set(k, String(v));
  return privateRequest<Page<Media>>(
    `/api/v1/media?${query}`,
    "GET",
    undefined,
    signal,
  );
};
export const getMedia = (id: number, signal?: AbortSignal) =>
  privateRequest<Media>(`/api/v1/media/${id}`, "GET", undefined, signal);
export const reviewMedia = (
  id: number,
  payload: {
    decision: "approved" | "rejected";
    expected_sha256: string;
    expected_brand_version: number;
    reason: string;
  },
  signal?: AbortSignal,
) =>
  privateRequest<Review>(
    `/api/v1/media/${id}/reviews`,
    "POST",
    payload,
    signal,
  );
export const promoteVariation = (variation_id: number, signal?: AbortSignal) =>
  privateRequest<Media>(
    "/api/v1/media/from-variation",
    "POST",
    { variation_id },
    signal,
  );
export const listCodexKeys = (signal?: AbortSignal) =>
  privateRequest<{
    keys: ApiKey[];
  }>("/api/v1/auth/api-keys", "GET", undefined, signal);
export const createCodexKey = (
  payload: {
    name: string;
    scopes: string[];
    expires_in_days: number;
  },
  signal?: AbortSignal,
) =>
  privateRequest<
    ApiKey & {
      key: string;
    }
  >("/api/v1/auth/api-keys", "POST", payload, signal);
export const revokeCodexKey = (id: number, signal?: AbortSignal) =>
  privateRequest<void>(
    `/api/v1/auth/api-keys/${id}`,
    "DELETE",
    undefined,
    signal,
  );

export interface BrandSnapshot {
  brand_id: number;
  brand_version: number;
  project: {
    id: number;
    name: string;
    description: string;
    archived: number | boolean;
  };
  identity: {
    name: string;
    palette: Record<string, unknown>;
    typography: Record<string, unknown>;
    texts: Record<string, unknown>;
    logo_style?: string;
    logo_seed?: number;
    logo_text?: string;
  };
  reference_logo: { sha256: string; url: string } | null;
}
export interface GenerationBrief {
  id: number;
  brand_id: number;
  project_id: number;
  brand_version: number;
  snapshot_hash: string;
  prompt: string;
  width: number;
  height: number;
  expires_at: number;
  snapshot: BrandSnapshot;
}
export interface MediaReviewContext {
  brief: GenerationBrief | null;
  logoUrl: string | null;
  ready: boolean;
  warning: string;
}
export const getGenerationBrief = (id: number, signal?: AbortSignal) =>
  privateRequest<GenerationBrief>(
    `/api/v1/generation-briefs/${id}`,
    "GET",
    undefined,
    signal,
  );
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object")
    return `{${Object.keys(value)
      .sort()
      .map(
        (key) =>
          `${JSON.stringify(key)}:${canonical((value as Record<string, unknown>)[key])}`,
      )
      .join(",")}}`;
  return JSON.stringify(value);
}
/** Freeze review evidence from its original brief; current identity is only a readiness check. */
export async function loadMediaReviewContext(
  item: Media,
  signal: AbortSignal,
): Promise<MediaReviewContext> {
  const work = beginSessionWork(signal);
  let logoUrl: string | null = null;
  try {
    work.check();
    if (!item.brief_id) {
      if (item.source !== "legacy")
        throw new ApiError(409, "La imagen no tiene un encargo asociado.");
      return {
        brief: null,
        logoUrl: null,
        ready: false,
        warning:
          "Esta pieza del generador no tiene un encargo de revisión. Incorporala mediante Enviar a revisión antes de aprobar.",
      };
    }
    const brief = await getGenerationBrief(item.brief_id, work.signal);
    work.check();
    if (
      brief.id !== item.brief_id ||
      brief.brand_id !== item.brand_id ||
      brief.project_id !== item.project_id ||
      brief.brand_version !== item.brand_version ||
      brief.snapshot_hash !== item.snapshot_hash ||
      brief.width !== item.width ||
      brief.height !== item.height ||
      brief.snapshot.brand_id !== item.brand_id ||
      brief.snapshot.brand_version !== item.brand_version
    )
      throw new ApiError(
        409,
        "El encargo no coincide con la versión original de la imagen.",
      );
    const current = await privateRequest<BrandSnapshot>(
      `/api/v1/brands/${item.brand_id}/brief`,
      "GET",
      undefined,
      work.signal,
    );
    work.check();
    const reference = brief.snapshot.reference_logo;
    if (reference) {
      if (
        !/^[a-f0-9]{64}$/.test(reference.sha256) ||
        reference.url !==
          `/api/v1/brands/${item.brand_id}/reference-logo?sha256=${reference.sha256}`
      )
        throw new ApiError(422, "La referencia del encargo es inválida.");
      logoUrl = await privateImage(
        reference.url,
        work.signal,
        reference.sha256,
      );
      work.check();
    }
    const ready =
      canonical(current) === canonical(brief.snapshot) &&
      !current.project.archived;
    return {
      brief,
      logoUrl,
      ready,
      warning: ready
        ? ""
        : "La identidad o el proyecto cambió desde este encargo. Se conserva la referencia original; necesitás una pieza con un encargo vigente antes de aprobar.",
    };
  } catch (error) {
    if (logoUrl) releasePrivateUrl(logoUrl);
    throw error;
  } finally {
    work.finish();
  }
}
