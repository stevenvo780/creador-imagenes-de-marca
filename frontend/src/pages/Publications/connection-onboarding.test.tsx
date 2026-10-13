import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { cancelApiRequests } from "../../api/client";
import type { Connection } from "../../api/publications";
import { ConnectionPanel } from "./ConnectionPanel";

const authorizationUrl = "https://www.tiktok.com/v2/auth/authorize/?state=fixture-state";
const oauthResponse = { authorization_url: authorizationUrl, state: "fixture-state", expires_at: 1800000000 };
const requests: { path: string; body: unknown; signal?: AbortSignal | null }[] = [];
let destinations: string[];
const realWindow = window;

beforeEach(() => {
  destinations = [];
  requests.length = 0;
  // jsdom no navega entre documentos: se observa únicamente ese borde del navegador.
  vi.stubGlobal("window", new Proxy(realWindow, {
    get(target, property) {
      if (property === "location") return { origin: "http://localhost:3000", assign: (url: string) => destinations.push(url) };
      return Reflect.get(target, property);
    },
  }));
  respond(oauthResponse);
});
afterEach(() => {
  cleanup();
  cancelApiRequests();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
function respond(body: unknown, status = 200) {
  vi.stubGlobal("fetch", async (path: string, init: RequestInit) => {
    requests.push({ path, body: JSON.parse(String(init.body)), signal: init.signal });
    return { ok: status < 400, status, json: async () => body };
  });
}
async function form(platform = "tiktok", projects = "11") {
  const view = render(<ConnectionPanel connections={[]} />);
  const user = userEvent.setup();
  await user.click(screen.getByText("Añadir cuenta para varios proyectos"));
  await user.selectOptions(screen.getByLabelText("Red"), platform);
  if (projects) await user.type(screen.getByLabelText(/Proyectos autorizados/), projects);
  return { ...view, user, submit: () => fireEvent.submit(screen.getByLabelText("Red").closest("form")!) };
}
const existing: Connection = {
  id: 42, platform: "tiktok", api_mode: "oauth2", remote_id: "open-42", remote_name: "Cuenta TikTok",
  status: "active", version: 3, project_ids: [11], scopes: ["user.info.basic", "video.publish"],
  expires_at: null, hold_reason: null, scope_evidence: "verified", expiry_state: "valid",
};

it("da de alta TikTok sin ID remoto y navega usando sólo el contrato de onboarding", async () => {
  const { user } = await form("tiktok", "11, 12");
  expect(screen.queryByLabelText("ID remoto de cuenta")).toBeNull();
  await user.click(screen.getByRole("button", { name: "Añadir cuenta" }));
  await vi.waitFor(() => expect(destinations).toEqual([authorizationUrl]));
  expect(requests.map(({ path, body }) => ({ path, body }))).toEqual([{
    path: "/api/v1/publications/oauth/onboarding/start",
    body: { platform: "tiktok", api_mode: "oauth2", project_ids: [11, 12], redirect_uri: "http://localhost:3000/api/v1/publications/oauth/callback" },
  }]);
});

it.each(["", "0", "11,0", "11,", "11,,12", "-1", "1.5", "abc", "9007199254740992"])(
  "rechaza proyectos inválidos %j antes de HTTP aunque se envíe el formulario directamente", async projects => {
    const { submit } = await form("tiktok", projects);
    submit();
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(requests).toEqual([]);
    expect(destinations).toEqual([]);
  },
);

it.each([
  "http://www.tiktok.com/authorize",
  "https://evil.test/authorize",
  "https://www.tiktok.com.evil.test/authorize",
  "https://fixture-user:fixture-password@www.tiktok.com/authorize",
  "javascript:alert('fixture')",
  "not-a-url",
])("rechaza un destino OAuth inseguro %j sin mostrarlo", async authorization_url => {
  respond({ ...oauthResponse, authorization_url });
  const { submit } = await form();
  submit();
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).not.toContain(authorization_url);
  expect(alert.textContent).not.toContain("fixture-password");
  expect(destinations).toEqual([]);
  expect(requests.map(r => r.path)).toEqual(["/api/v1/publications/oauth/onboarding/start"]);
});

it("muestra un error HTTP seguro y permite volver a intentar", async () => {
  respond({ detail: "provider-secret=fixture-secret" }, 502);
  const { submit } = await form();
  submit();
  expect((await screen.findByRole("alert")).textContent).not.toContain("fixture-secret");
  expect(destinations).toEqual([]);
  expect((screen.getByRole("button", { name: "Añadir cuenta" }) as HTMLButtonElement).disabled).toBe(false);
});

it.each(["logout", "company-switch"])("descarta OAuth tardío tras %s aunque HTTP ignore abort", async kind => {
  let resolveBody!: (body: unknown) => void;
  vi.stubGlobal("fetch", async (path: string, init: RequestInit) => {
    requests.push({ path, body: JSON.parse(String(init.body)), signal: init.signal });
    return { ok: true, status: 200, json: () => new Promise(resolve => { resolveBody = resolve; }) };
  });
  const { submit, rerender } = await form();
  submit();
  await vi.waitFor(() => expect(resolveBody).toBeTruthy());
  if (kind === "logout") act(() => cancelApiRequests());
  else rerender(<ConnectionPanel key="company-two" connections={[]} />);
  expect(requests[0].signal?.aborted).toBe(true);
  await act(async () => resolveBody(oauthResponse));
  expect(destinations).toEqual([]);
  expect(screen.queryByRole("alert")).toBeNull();
});

it("no navega si la sesión cambia entre la respuesta y el destino OAuth", async () => {
  respond({ ...oauthResponse, get authorization_url() { cancelApiRequests(); return authorizationUrl; } });
  const { submit } = await form();
  submit();
  await vi.waitFor(() => expect(requests).toHaveLength(1));
  await act(async () => {});
  expect(destinations).toEqual([]);
  expect(screen.queryByRole("alert")).toBeNull();
});

it("renueva TikTok usando el ID de conexión existente y el endpoint original", async () => {
  render(<ConnectionPanel connections={[existing]} />);
  await userEvent.setup().click(screen.getByRole("button", { name: "Conectar o renovar permisos" }));
  await vi.waitFor(() => expect(destinations).toEqual([authorizationUrl]));
  expect(requests.map(({ path, body }) => ({ path, body }))).toEqual([{
    path: "/api/v1/publications/oauth/start",
    body: { platform: "tiktok", connection_id: 42, redirect_uri: "http://localhost:3000/api/v1/publications/oauth/callback" },
  }]);
});

it.each([
  ["facebook", "page"], ["instagram", "instagram_login"], ["x", "oauth2"],
])("conserva alta de %s con ID remoto obligatorio y creación de metadatos", async (platform, api_mode) => {
  const { user } = await form(platform);
  const remote = screen.getByLabelText("ID remoto de cuenta") as HTMLInputElement;
  expect(remote.required).toBe(true);
  await user.click(screen.getByRole("button", { name: "Añadir cuenta" }));
  expect(requests).toEqual([]);
  await user.type(remote, "remote-42");
  await user.click(screen.getByRole("button", { name: "Añadir cuenta" }));
  await vi.waitFor(() => expect(requests).toHaveLength(1));
  expect(requests[0].path).toBe("/api/v1/publications/connections");
  expect(requests[0].body).toEqual({ platform, api_mode, remote_id: "remote-42", project_ids: [11] });
  expect(destinations).toEqual([]);
});
