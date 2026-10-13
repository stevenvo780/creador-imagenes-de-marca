import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, within, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as api from "../../api/publications";
import { PublicationsPage } from "./PublicationsPage";
import { policyStatus } from "./PolicyPanel";
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const objective = "Objetivo completo con fuentes y alcance que se conserva íntegro en el detalle de la campaña.";
function overview(): api.Overview {
  return {
    tenant: { id: 1, slug: "empresa", name: "Empresa" },
    policy: { version: 3, enabled: true, valid_from: 100, expires_at: 200 },
    connections: [{ id: 1, platform: "facebook", api_mode: "page", remote_id: "private-id", remote_name: "Cuenta de la empresa", status: "active", version: 1, project_ids: [1], scopes: ["pages_manage_posts"], expires_at: null, hold_reason: null, scope_evidence: "", expiry_state: "" }],
    campaigns: { items: [
      { id: 1, project_id: 1, brand_id: 2, project_name: "Proyecto uno", product_name: "Producto Alfa", objective, archived: 0, revisions: [] },
      { id: 2, project_id: 2, brand_id: 3, project_name: "Proyecto dos", product_name: "Producto Beta", objective: "Segundo objetivo", archived: 0, revisions: [] },
    ], next_cursor: null },
  };
}
function start(path = "/publications") {
  const getOverview = vi.spyOn(api, "getOverview").mockResolvedValue(overview());
  const getCalendar = vi.spyOn(api, "getCalendar").mockResolvedValue({ items: [], next_cursor: null });
  render(<MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/publications" element={<PublicationsPage owner tenant="empresa" />} />
    <Route path="/publications/campaigns/:campaignId" element={<PublicationsPage owner tenant="empresa" />} />
  </Routes></MemoryRouter>);
  return { getOverview, getCalendar, user: userEvent.setup() };
}
it("abre Agenda, permite buscar y entra por teclado al detalle con objetivo íntegro", async () => {
  const { user } = start();
  await screen.findByRole("heading", { name: "Agenda de envíos" });
  expect(screen.getByRole("button", { name: "Agenda" }).getAttribute("aria-pressed")).toBe("true");
  expect(screen.queryByText(objective)).toBeNull();
  await user.type(screen.getByRole("searchbox"), "beta");
  expect(screen.queryByRole("link", { name: /Producto Alfa/ })).toBeNull();
  expect(screen.getByRole("link", { name: /Producto Beta/ })).toBeTruthy();
  await user.clear(screen.getByRole("searchbox"));
  const link = screen.getByRole("link", { name: /Producto Alfa/ });
  link.focus(); await user.keyboard("{Enter}");
  expect(await screen.findByText(objective)).toBeTruthy();
  expect(link.getAttribute("href")).toBe("/publications/campaigns/1");
  expect(screen.getByRole("button", { name: "Contenido" }).getAttribute("aria-pressed")).toBe("true");
  expect(within(screen.getByRole("complementary", { name: "Productos y campañas" })).queryByText(objective)).toBeNull();
  await user.click(screen.getByRole("button", { name: "Agenda" }));
  await screen.findByRole("heading", { name: "Agenda de envíos" });
  expect(screen.queryByText(objective)).toBeNull();
});
it("preserva el deep link y ofrece contenido desde una agenda vacía", async () => {
  const { user } = start("/publications/campaigns/1");
  expect(await screen.findByText(objective)).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Agenda" }));
  await screen.findByRole("heading", { name: "Aún no hay entregas programadas" });
  await user.click(screen.getByRole("button", { name: "Ir a Contenido" }));
  expect(screen.getByRole("heading", { name: "Contenido por producto" })).toBeTruthy();
});
it("diferencia conexión de publicación, deja datos técnicos en details y no atribuye bloqueos a redes sin conectar", async () => {
  const { user } = start();
  await screen.findByRole("button", { name: "Cuentas" });
  expect(screen.getByText("1 cuenta conectada")).toBeTruthy();
  expect(screen.getByText("Autorización: Vencida")).toBeTruthy();
  expect(screen.queryByText(/publicadas/i)).toBeNull();
  await user.click(screen.getByRole("button", { name: "Cuentas" }));
  expect(screen.getByText("Facebook · Conectada")).toBeTruthy();
  expect(screen.getAllByText("Sin conectar")).toHaveLength(3);
  expect(screen.queryByText(/X permanece bloqueado/)).toBeNull();
  const scopes = screen.getByText(/pages_manage_posts/);
  expect(scopes.closest("details")?.open).toBe(false);
  expect(screen.getByRole("button", { name: "Detener autonomía" })).toBeTruthy();
});
it("Actualizar vuelve a consultar los datos y agenda; no ofrece vacío antes de terminar la carga", async () => {
  const { getOverview, getCalendar, user } = start();
  await screen.findByRole("heading", { name: "Aún no hay entregas programadas" });
  await user.click(screen.getByRole("button", { name: "Actualizar" }));
  await screen.findByRole("heading", { name: "Aún no hay entregas programadas" });
  expect(getOverview).toHaveBeenCalledTimes(2);
  expect(getCalendar).toHaveBeenCalledTimes(2);
});
it("muestra una lista parcial sin inventar el total y busca también en objetivos sin mostrarlos", async () => {
  const data = overview(); data.campaigns.next_cursor = 2;
  vi.spyOn(api, "getOverview").mockResolvedValue(data);
  vi.spyOn(api, "getCalendar").mockResolvedValue({ items: [], next_cursor: null });
  vi.spyOn(api, "getCampaigns").mockResolvedValue({ items: [], next_cursor: null });
  render(<MemoryRouter><PublicationsPage owner tenant="empresa" /></MemoryRouter>);
  await screen.findByText(/Lista parcial/);
  const user = userEvent.setup();
  await user.type(screen.getByRole("searchbox"), "fuentes y alcance");
  expect(screen.getByRole("link", { name: /Producto Alfa/ })).toBeTruthy();
  expect(screen.queryByText(objective)).toBeNull();
  await user.click(screen.getByRole("button", { name: "Cargar más campañas" }));
  expect(api.getCampaigns).toHaveBeenCalledWith(2, expect.any(AbortSignal));
});
it("cancela agenda al salir de su vista y descarta su respuesta tardía", async () => {
  vi.spyOn(api, "getOverview").mockResolvedValue(overview());
  let resolve!: (value: api.Page<api.Delivery>) => void;
  const calendar = vi.spyOn(api, "getCalendar").mockImplementation(() => new Promise(r => { resolve = r; }));
  render(<MemoryRouter><PublicationsPage owner tenant="empresa" /></MemoryRouter>);
  await screen.findByText("Cargando agenda…");
  expect(screen.queryByText("Aún no hay entregas programadas")).toBeNull();
  await userEvent.setup().click(screen.getByRole("button", { name: "Cuentas" }));
  expect(calendar.mock.calls[0][1]?.aborted).toBe(true);
  await act(async () => resolve({ items: [], next_cursor: null }));
  expect(screen.queryByText("Aún no hay entregas programadas")).toBeNull();
});
it("clasifica autorización por tiempo y nunca asume vigencia sin fechas", () => {
  expect(policyStatus({ version: 1, enabled: true }, 150)).toBe("Vigencia sin comprobar");
  expect(policyStatus({ version: 1, enabled: true, valid_from: 200, expires_at: 300 }, 150)).toBe("Aún no vigente");
  expect(policyStatus({ version: 1, enabled: true, valid_from: 100, expires_at: 200 }, 150)).toBe("Vigente");
  expect(policyStatus({ version: 1, enabled: true, valid_from: 100, expires_at: 200 }, 250)).toBe("Vencida");
});
it("al perder owner retira los datos y cancela operaciones sin consultar rutas privadas", async () => {
  const request = vi.spyOn(api, "getOverview").mockResolvedValue(overview());
  const calendar = vi.spyOn(api, "getCalendar").mockResolvedValue({ items: [], next_cursor: null });
  const { rerender } = render(<MemoryRouter><PublicationsPage owner tenant="empresa" /></MemoryRouter>);
  await screen.findByRole("heading", { name: "Agenda de envíos" });
  rerender(<MemoryRouter><PublicationsPage owner={false} tenant="empresa" /></MemoryRouter>);
  expect(screen.queryByRole("link", { name: /Producto Alfa/ })).toBeNull();
  expect(screen.queryByRole("button", { name: "Detener autonomía" })).toBeNull();
  expect(request.mock.calls[0][0]?.aborted).toBe(true);
  expect(calendar.mock.calls[0][1]?.aborted).toBe(true);
  expect(request).toHaveBeenCalledTimes(1);
});
it("un error de agenda no se presenta como ausencia de envíos", async () => {
  vi.spyOn(api, "getOverview").mockResolvedValue(overview());
  vi.spyOn(api, "getCalendar").mockRejectedValue(new Error("unavailable"));
  render(<MemoryRouter><PublicationsPage owner tenant="empresa" /></MemoryRouter>);
  await screen.findByRole("alert");
  expect(screen.queryByText("Aún no hay entregas programadas")).toBeNull();
});
it("mantiene detener accesible y envía sólo el cierre con la versión exacta de la política", async () => {
  const { user } = start();
  const mutation = vi.spyOn(api, "publicationRequest").mockResolvedValue({});
  await screen.findByRole("button", { name: "Detener autonomía" });
  await user.click(screen.getByRole("button", { name: "Detener autonomía" }));
  expect(mutation).toHaveBeenCalledWith("/policy", "POST", { enabled: false, expected_version: 3 }, expect.any(AbortSignal));
});
