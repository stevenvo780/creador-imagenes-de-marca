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

export interface AssetTypeInfo {
  name: string;
  label: string;
  description: string;
  width?: number;
  height?: number;
}

export interface AssetFamily {
  id: string;
  label: string;
  description: string;
  types: AssetTypeInfo[];
}

export interface BatchCreate {
  brand_id: number;
  asset_types?: string[];
  fixed?: Record<string, string>;
  permuted?: string[];
  count?: number;
  seed_salt?: string;
  /** "client": el navegador renderiza y sube los PNG (sin CPU de servidor). */
  render_mode?: "server" | "client";
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
  /** Familia de asset derivada del backend: logos | banners | cards | og | stationery */
  category: string | null;
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

/**
 * Mensaje claro en español por código de estado, usado cuando el backend no
 * envía un `detail` legible (p. ej. 503 de cold-start con body vacío, donde en
 * HTTP/2 `res.statusText` también viene vacío → antes el error quedaba invisible).
 */
function friendlyError(status: number): string {
  if (status === 401) return "Correo o contraseña incorrectos.";
  if (status === 403) return "No tenés permiso para esta acción.";
  if (status === 404) return "No encontramos lo que buscabas.";
  if (status === 409) return "Ya existe un elemento con esos datos.";
  if (status === 422) return "Revisá los datos: hay algún campo inválido.";
  if (status === 429) return "Demasiados intentos. Esperá un momento y reintentá.";
  if (status >= 500)
    return "El servidor está iniciando o saturado. Esperá unos segundos y reintentá.";
  return `Ocurrió un error (${status}). Intentá de nuevo.`;
}

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
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    // fetch rechaza ante problemas de red / conexión cortada (no por status HTTP).
    throw new ApiError(
      0,
      "No pudimos conectar con el servidor. Revisá tu conexión y reintentá.",
    );
  }
  if (res.status === 204) return undefined as unknown as T;
  const json = await res.json().catch(() => null);
  if (!res.ok) {
    const detail =
      json && typeof json === "object" && typeof json.detail === "string" && json.detail
        ? json.detail
        : friendlyError(res.status);
    throw new ApiError(res.status, detail);
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
  assetTypes: () => get<{ families: AssetFamily[] }>("/api/v1/wizard/asset-types"),
};

// ── Batches ──────────────────────────────────────────────────────────────────

export const batches = {
  create: (payload: BatchCreate) => post<Batch>("/api/v1/batches", payload),
  get: (id: number) => get<Batch>(`/api/v1/batches/${id}`),
  variations: (batchId: number) =>
    get<{ items: Variation[] }>(`/api/v1/batches/${batchId}/variations`),
};

// ── Gallery ──────────────────────────────────────────────────────────────────

export type GalleryOrder = "calidad" | "recientes";

export interface GalleryListParams {
  /** Filtrar por marca (server-side). */
  brandId?: number;
  /** Filtrar por generación / batch (server-side). */
  batchId?: number;
  /**
   * Ordenamiento server-side:
   *  - "calidad": score descendente, nulls al final.
   *  - "recientes": created_at descendente.
   */
  order?: GalleryOrder;
}

export const gallery = {
  list: (params: GalleryListParams = {}) => {
    const qs = new URLSearchParams();
    if (params.brandId !== undefined) qs.set("brand_id", String(params.brandId));
    if (params.batchId !== undefined) qs.set("batch_id", String(params.batchId));
    if (params.order) qs.set("order", params.order);
    const query = qs.toString();
    return get<{ items: Variation[] }>(`/api/v1/gallery${query ? `?${query}` : ""}`);
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

// ── Client-side Render ────────────────────────────────────────────────────────

/**
 * Render-spec devuelto por GET /api/v1/batches/{batchId}/plan
 */
export interface RenderSpec {
  batch_id: number;
  asset_type: string;
  category: string;
  template_name: string;
  viewport: { w: number; h: number };
  device_scale_factor: number;
  combinations: RenderCombination[];
}

export interface RenderCombination {
  idx: number;
  params: Record<string, unknown>;
  vars: Record<string, string>;
  data_attrs: Record<string, string>;
  isotype_data_uri: string;
  texts: Record<string, string>;
}

export const clientRender = {
  /** GET /api/v1/batches/{batchId}/plan */
  plan: (batchId: number) => get<RenderSpec>(`/api/v1/batches/${batchId}/plan`),

  /** POST /api/v1/batches/{batchId}/variations/upload (multipart form) */
  upload: async (batchId: number, formData: FormData): Promise<{ combo_idx: number; success: boolean }> => {
    const res = await fetch(`/api/v1/batches/${batchId}/variations/upload`, {
      method: "POST",
      credentials: "include",
      body: formData,
    });
    if (!res.ok) {
      const json = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(res.status, json?.detail ?? "upload error");
    }
    return res.json();
  },
};
