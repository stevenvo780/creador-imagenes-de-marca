import { ApiError, cancelApiRequests } from "./client";
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
  brief_id: number;
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
    const json = await res.json();
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
export async function privateImage(path: string, signal: AbortSignal) {
  // The API contract provides relative authenticated paths. Never transmit cookies to arbitrary links.
  if (
    !/^\/api\/v1\/(media\/\d+\/(download|thumbnail)|variations\/\d+\/file)(\?.*)?$/.test(
      path,
    )
  )
    throw new Error("Ruta de imagen privada inválida");
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
