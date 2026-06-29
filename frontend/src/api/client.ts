/**
 * Typed fetch client — usa cookies httpOnly de sesión (same-origin).
 * Todas las llamadas incluyen credentials: "include" para enviar la cookie JWT.
 */

// ── Tipos de dominio ────────────────────────────────────────────────────────

export interface UserInfo {
  id?: number;
  email: string;
  role: string;
}

export interface TenantInfo {
  id?: number;
  slug: string;
}

export interface AuthPayload {
  user: UserInfo;
  tenant: TenantInfo;
}

export interface Brand {
  id: number;
  tenant_id: number;
  slug: string;
  name: string;
  palette: Record<string, unknown>;
  typography: Record<string, unknown>;
  logo_text: string;
  logo_symbol: string;
  texts: Record<string, unknown>;
  /** Timestamp Unix en segundos (o ISO si el backend cambia). */
  created_at: number | string | null;
}

export interface BrandCreate {
  slug: string;
  name: string;
  palette?: Record<string, unknown>;
  typography?: Record<string, unknown>;
  logo_text?: string;
  logo_symbol?: string;
  texts?: Record<string, unknown>;
}

export interface BrandUpdate {
  name?: string;
  palette?: Record<string, unknown>;
  typography?: Record<string, unknown>;
  logo_text?: string;
  logo_symbol?: string;
  texts?: Record<string, unknown>;
}

export interface AxisOption {
  name: string;
  label: string;
  description: string | null;
}

export interface Axis {
  name: string;
  label: string;
  type: string;
  options: AxisOption[];
}

export interface BatchCreate {
  brand_id: number;
  asset_types?: string[];
  fixed?: Record<string, string>;
  permuted?: string[];
  count?: number;
  seed_salt?: string;
}

/**
 * Estados reales que emite el backend (webapp/storage + worker).
 * Nota: el backend usa "completed"/"failed"/"cancelled" (no "done"/"error").
 */
export type BatchStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface Batch {
  id: number;
  tenant_id: number;
  brand_id: number;
  spec: Record<string, unknown>;
  status: BatchStatus;
  counts: Record<string, unknown>;
  created_at: number | string | null;
  started_at: number | string | null;
  finished_at: number | string | null;
}

export interface Variation {
  id: number;
  batch_id: number | null;
  tenant_id: number;
  brand_id: number;
  axis_params: Record<string, unknown>;
  seed: string | null;
  score: number | null;
  output_path: string | null;
  wcag: Record<string, unknown> | null;
  layout_status: string | null;
  selected: boolean;
  created_at: number | string | null;
  file_url: string;
}

// ── Error tipado ─────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

// ── Fetch base ───────────────────────────────────────────────────────────────

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const init: RequestInit = {
    method,
    credentials: "include",
    headers: { "Content-Type": "application/json" },
  };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }
  const res = await fetch(path, init);
  if (res.status === 204) return undefined as unknown as T;
  const json = await res.json().catch(() => ({ detail: res.statusText }));
  if (!res.ok) {
    throw new ApiError(res.status, json?.detail ?? String(json));
  }
  return json as T;
}

function get<T>(path: string) {
  return request<T>("GET", path);
}
function post<T>(path: string, body?: unknown) {
  return request<T>("POST", path, body);
}
function put<T>(path: string, body?: unknown) {
  return request<T>("PUT", path, body);
}
function del<T>(path: string) {
  return request<T>("DELETE", path);
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export const auth = {
  register: (payload: {
    tenant_slug: string;
    tenant_name: string;
    email: string;
    password: string;
  }) => post<AuthPayload>("/auth/register", payload),

  login: (payload: { email: string; password: string }) =>
    post<AuthPayload>("/auth/login", payload),

  logout: () => post<void>("/auth/logout"),

  me: () => get<AuthPayload>("/auth/me"),
};

// ── Brands ───────────────────────────────────────────────────────────────────

export const brands = {
  list: () => get<{ items: Brand[] }>("/api/v1/brands"),
  create: (payload: BrandCreate) => post<Brand>("/api/v1/brands", payload),
  get: (id: number) => get<Brand>(`/api/v1/brands/${id}`),
  update: (id: number, payload: BrandUpdate) =>
    put<Brand>(`/api/v1/brands/${id}`, payload),
  delete: (id: number) => del<void>(`/api/v1/brands/${id}`),
};

// ── Wizard ───────────────────────────────────────────────────────────────────

export const wizard = {
  axes: () => get<{ axes: Axis[] }>("/api/v1/wizard/axes"),
  brands: () => get<{ items: Brand[] }>("/api/v1/wizard/brands"),
};

// ── Batches ──────────────────────────────────────────────────────────────────

export const batches = {
  create: (payload: BatchCreate) => post<Batch>("/api/v1/batches", payload),
  get: (id: number) => get<Batch>(`/api/v1/batches/${id}`),
  variations: (batchId: number) =>
    get<{ items: Variation[] }>(`/api/v1/batches/${batchId}/variations`),
};

// ── Gallery ──────────────────────────────────────────────────────────────────

export const gallery = {
  list: (brandId?: number) => {
    const qs = brandId !== undefined ? `?brand_id=${brandId}` : "";
    return get<{ items: Variation[] }>(`/api/v1/gallery${qs}`);
  },
  select: (variation_id: number, selected: boolean) =>
    post<{ variation_id: number; selected: boolean }>("/api/v1/gallery/select", {
      variation_id,
      selected,
    }),
};

// ── Downloads ────────────────────────────────────────────────────────────────

export const downloads = {
  /** URL directa para img src — incluye cookie automáticamente al ser same-origin. */
  fileUrl: (variationId: number) => `/api/v1/variations/${variationId}/file`,

  zip: async (ids: number[]): Promise<Blob> => {
    const res = await fetch("/api/v1/downloads/zip", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    if (!res.ok) {
      const json = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(res.status, json?.detail ?? "zip error");
    }
    return res.blob();
  },
};
