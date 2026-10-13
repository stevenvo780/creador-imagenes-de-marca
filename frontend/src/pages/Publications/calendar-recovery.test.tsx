import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError, cancelApiRequests } from "../../api/client";
import { getCalendar, publicationRequest, type Delivery } from "../../api/publications";
import { CalendarPanel } from "./CalendarPanel";

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); cancelApiRequests(); });
const connectionMessage = "No se pudo conectar con el servidor. Revisa tu conexión y vuelve a intentarlo.";
const delivery: Delivery = {
  id: 1, revision_id: 2, contract_hash: "a".repeat(64), media_sha256: "b".repeat(64),
  normalized_destination: "Cuenta de prueba", due_at: 2000000000, expires_at: 2000001000,
  started_at: null, hold_reasons: [], state: "scheduled",
};
function response(value: unknown, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => value } as Response;
}

it.each([
  { reasons: ["frequency_limit"] },
  { reasons: ["daily_quota_reached"] },
  { reasons: ["daily_quota_reached", "frequency_limit"] },
])("conserva la pieza retenida por límites temporales sin pedir otra revisión ($reasons)", async ({ reasons }) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
    items: [{ ...delivery, state: "held", hold_reasons: reasons }], next_cursor: null,
  })));
  render(<CalendarPanel owner />);
  await screen.findByText("Cuenta de prueba");
  expect(screen.getByText("Retenida")).toBeTruthy();
  expect(screen.getByText(/los límites se vuelven a comprobar antes del envío/i)).toBeTruthy();
  expect(screen.queryByText(/requiere una nueva revisión/i)).toBeNull();
});

it("no promete reintento automático para una retención que también necesita autenticación", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
    items: [{ ...delivery, state: "held", hold_reasons: ["frequency_limit", "requires_auth"] }], next_cursor: null,
  })));
  render(<CalendarPanel owner />);
  await screen.findByText("Cuenta de prueba");
  expect(screen.queryByText(/los límites se vuelven a comprobar antes del envío/i)).toBeNull();
  expect(screen.getByText(/si el intento fue retenido por el trabajador/i)).toBeTruthy();
  expect(screen.getByText("requires_auth")).toBeTruthy();
});

it("una retención expirada muestra la nueva fecha requerida sin instrucciones temporales contradictorias", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
    items: [{ ...delivery, state: "held", expires_at: 1, hold_reasons: ["frequency_limit"] }], next_cursor: null,
  })));
  render(<CalendarPanel owner />);
  await screen.findByText("Cuenta de prueba");
  expect(screen.getByText("Fecha expirada")).toBeTruthy();
  expect(screen.getByText(/otra fecha y una nueva evaluación IA/i)).toBeTruthy();
  expect(screen.queryByText(/retención del trabajador/i)).toBeNull();
  expect(screen.queryByText(/los límites se vuelven a comprobar antes del envío/i)).toBeNull();
});

it.each([{ label: "vacía", items: [] as Delivery[] }, { label: "con entregas", items: [delivery] }])("recupera la agenda tras un GET fallido y retira la alerta ($label)", async ({ items }) => {
  const fetcher = vi.fn().mockRejectedValueOnce(new TypeError("Failed to fetch"))
    .mockResolvedValueOnce(response({ items, next_cursor: null }));
  vi.stubGlobal("fetch", fetcher);
  render(<CalendarPanel owner />);
  expect((await screen.findByRole("alert")).textContent).toBe(connectionMessage);
  expect(screen.queryByText("Aún no hay entregas programadas")).toBeNull();
  expect(fetcher).toHaveBeenCalledTimes(1);
  await userEvent.setup().click(screen.getByRole("button", { name: "Cargar más entregas" }));
  await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  expect(items.length ? screen.getByText("Cuenta de prueba") : screen.getByText("Aún no hay entregas programadas")).toBeTruthy();
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(fetcher.mock.calls.every(([path]) => path === "/api/v1/publications/calendar?cursor=0")).toBe(true);
});

it("una cancelación exitosa y su recarga retiran el error previo sin repetir el POST", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(response({ items: [delivery], next_cursor: null }))
    .mockRejectedValueOnce(new TypeError("Failed to fetch"))
    .mockResolvedValueOnce(response(undefined, 204))
    .mockResolvedValueOnce(response({ items: [], next_cursor: null }));
  vi.stubGlobal("fetch", fetcher);
  render(<CalendarPanel owner />);
  await screen.findByText("Cuenta de prueba");
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Ver intento y recibo" }));
  await screen.findByRole("alert");
  await user.click(screen.getByRole("button", { name: "Cancelar antes del intento" }));
  await screen.findByText("Aún no hay entregas programadas");
  expect(screen.queryByRole("alert")).toBeNull();
  expect(fetcher.mock.calls.filter(([, options]) => options.method === "POST")).toHaveLength(1);
});

it("un aborto de agenda permanece silencioso", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("aborted", "AbortError")));
  render(<CalendarPanel owner />);
  await waitFor(() => expect(screen.queryByText("Cargando agenda…")).toBeNull());
  expect(screen.queryByRole("alert")).toBeNull();
});

it("la cancelación de sesión prevalece sobre un TypeError tardío de transporte", async () => {
  let reject!: (error: unknown) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise((_, fail) => { reject = fail; })));
  const request = getCalendar();
  cancelApiRequests();
  reject(new TypeError("Failed to fetch"));
  await expect(request).rejects.toHaveProperty("name", "AbortError");
});

it("mantiene los errores HTTP distintos de una conexión fallida", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ detail: "internal" }, 500)));
  await expect(getCalendar()).rejects.toMatchObject({ status: 500, detail: "El servicio no está disponible. Intenta más tarde." });
});

it("mantiene el error de JSON incompleto distinto del transporte", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => { throw new SyntaxError("invalid JSON"); } }));
  await expect(getCalendar()).rejects.toMatchObject({ status: 502, detail: "Respuesta incompleta del servidor." });
});

it("no clasifica un TypeError de serialización como transporte ni envía el POST", async () => {
  const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
  const circular: Record<string, unknown> = {}; circular.self = circular;
  const error = await publicationRequest("/policy", "POST", circular).catch(error => error);
  expect(error).toBeInstanceOf(TypeError);
  expect(error).not.toBeInstanceOf(ApiError);
  expect(fetcher).not.toHaveBeenCalled();
});
