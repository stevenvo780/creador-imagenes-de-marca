import { afterEach, describe, it, expect, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AttemptDetail } from "./AttemptDetail";
import { PublicationsPage } from "./PublicationsPage";
import { CampaignDetail } from "./CampaignDetail";
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
describe("Publicaciones", () => {
  it("un resultado incierto nunca muestra publicado ni enlace incluso con permalink", () => {
    render(
      <AttemptDetail
        attempt={{
          state: "uncertain",
          result: {
            state: "uncertain",
            permalink: "https://example.test/post",
            remote_id: "pending",
          },
        }}
      />,
    );
    expect(screen.getByText(/resultado incierto/i)).toBeTruthy();
    expect(screen.queryByRole("link", { name: /ver publicación/i })).toBeNull();
  });
  it("muestra enlace sólo con confirmación y fecha expirada separada", () => {
    const { rerender } = render(
      <AttemptDetail
        attempt={{
          state: "published",
          result: {
            state: "published",
            permalink: "https://example.test/post",
            remote_id: "post",
          },
        }}
      />,
    );
    expect(
      screen
        .getByRole("link", { name: /ver publicación/i })
        .getAttribute("href"),
    ).toBe("https://example.test/post");
    rerender(<AttemptDetail attempt={{ state: "expired", result: null }} />);
    expect(screen.getByText(/fecha expirada/i)).toBeTruthy();
  });
  it("empresa activa visible y miembro sin llamadas owner", () => {
    const fetcher = vi.spyOn(globalThis, "fetch");
    render(
      <MemoryRouter>
        <PublicationsPage owner={false} tenant="Empresa Beta" />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Empresa Beta/)).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: /detener autonomía/i }),
    ).toBeNull();
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("separa hold IA de revisión humana visual y deja privacidad vacía", () => {
    render(
      <MemoryRouter>
        <CampaignDetail
          owner
          campaign={{
            id: 1,
            project_id: 2,
            brand_id: 3,
            project_name: "Proyecto",
            product_name: "Producto",
            objective: "Campaña",
            archived: 0,
            revisions: [
              {
                id: 1,
                campaign_id: 1,
                contract_hash: "a".repeat(64),
                caption: "Texto",
                policy_version: 1,
                scheduled_at_utc: 100,
                expires_at_utc: 3700,
                timezone: "UTC",
                channel_metadata: {
                  sources: ["https://example.test/manual"],
                  rights: "owned",
                  privacy: null,
                },
                media: {
                  id: 1,
                  kind: "gallery_image",
                  sha256: "b".repeat(64),
                  mime: "image/png",
                  width: 100,
                  height: 100,
                },
                connection: {
                  id: 1,
                  platform: "tiktok",
                  remote_id: "account",
                  remote_name: "Mi cuenta",
                },
                visual_review: { approval_current: false },
                decision: {
                  id: 1,
                  outcome: "hold",
                  reason: "Fuente insuficiente",
                  provider: "test",
                  model: "test",
                },
                eligibility_reasons: ["needs_platform_consent"],
              },
            ],
          }}
          onRefresh={() => {}}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText(/retenida por IA/i)).toBeTruthy();
    expect(screen.getByText(/revisión humana visual/i)).toBeTruthy();
    expect(
      (screen.getByLabelText("Privacidad TikTok") as HTMLSelectElement).value,
    ).toBe("");
    expect(
      screen.getByText(/requiere consentimiento por contenido/i),
    ).toBeTruthy();
  });
});

it("descarta datos de la empresa anterior al cambiar de sesión", async () => {
  let resolveA!: (value: unknown) => void;
  const overview = (name: string) => ({
    tenant: { id: name === "A" ? 1 : 2, slug: name, name },
    policy: { version: 0, enabled: false },
    connections: [],
    campaigns: {
      items: [
        {
          id: 1,
          project_id: 1,
          brand_id: 1,
          project_name: name,
          product_name: `Producto ${name}`,
          objective: "Campaña",
          archived: 0,
          revisions: [],
        },
      ],
      next_cursor: null,
    },
  });
  let requests = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async (path) =>
      ({
        ok: true,
        status: 200,
        json: () =>
          String(path).endsWith("/overview")
            ? ++requests === 1
              ? new Promise((resolve) => {
                  resolveA = resolve;
                })
              : Promise.resolve(overview("B"))
            : Promise.resolve({ items: [], next_cursor: null }),
      }) as Response,
  );
  const { rerender } = render(
    <MemoryRouter>
      <PublicationsPage owner tenant="A" />
    </MemoryRouter>,
  );
  await vi.waitFor(() => expect(resolveA).toBeTruthy());
  rerender(
    <MemoryRouter>
      <PublicationsPage owner tenant="B" />
    </MemoryRouter>,
  );
  await screen.findByRole("link", { name: /Producto B/ });
  resolveA(overview("A"));
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(
    screen.queryByRole("link", { name: /Producto A/ }),
  ).toBeNull();
});

function previewCampaign(): import("../../api/publications").Campaign {
  return {
    id: 1, project_id: 2, brand_id: 3, project_name: "Proyecto", product_name: "Producto",
    objective: "Campaña", archived: 0,
    revisions: [1, 2].map(id => ({
      id, campaign_id: 1, contract_hash: "a".repeat(64), caption: `Texto ${id}`,
      policy_version: 1, scheduled_at_utc: 100, expires_at_utc: 3700, timezone: "UTC",
      channel_metadata: { sources: [], rights: "owned" },
      media: { id, kind: "gallery_image" as const, sha256: "b".repeat(64), mime: "image/jpeg", width: 100, height: 100 },
      connection: { id: 1, platform: "facebook" as const, remote_id: "account", remote_name: "Cuenta" },
      visual_review: { approval_current: false }, decision: null, eligibility_reasons: [],
    })),
  };
}

it("descarga sólo el preview solicitado y cancela/libera al cambiar o cerrar", async () => {
  const api = await import("../../api/publications");
  const { fireEvent, act } = await import("@testing-library/react");
  let resolveFirst!: (value: { url: string; release: () => void }) => void;
  const releases = [vi.fn(), vi.fn()];
  const preview = vi.spyOn(api, "privatePreview")
    .mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve; }))
    .mockResolvedValueOnce({ url: "blob:second", release: releases[1] });
  const { unmount } = render(<MemoryRouter><CampaignDetail owner campaign={previewCampaign()} onRefresh={() => {}} /></MemoryRouter>);
  expect(preview).not.toHaveBeenCalled();
  fireEvent.click(screen.getAllByRole("button", { name: "Ver archivo exacto" })[0]);
  expect(preview).toHaveBeenCalledTimes(1);
  const firstSignal = preview.mock.calls[0][1];
  fireEvent.click(screen.getByRole("button", { name: "Ver archivo exacto" }));
  await screen.findByAltText("Archivo exacto de esta revisión");
  expect(firstSignal.aborted).toBe(true);
  expect(screen.getAllByAltText("Archivo exacto de esta revisión")).toHaveLength(1);
  await act(async () => resolveFirst({ url: "blob:late", release: releases[0] }));
  expect(releases[0]).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Cerrar archivo exacto" }));
  expect(releases[1]).toHaveBeenCalledTimes(1);
  expect(preview.mock.calls[1][1].aborted).toBe(true);
  unmount();
});

it("envía el predecesor exacto al editar y su hash", async () => {
  const api = await import("../../api/publications");
  const fetcher = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, status: 201, json: async () => ({}) } as Response);
  const revision = previewCampaign().revisions[0];
  await api.revise(revision, "nuevo", revision.channel_metadata);
  const body = JSON.parse(fetcher.mock.calls[0][1]!.body as string);
  expect(body.supersedes_revision_id).toBe(revision.id);
  expect(body.supersedes_contract_hash).toBe(revision.contract_hash);
});

it("muestra retirada en estado y evento sin enlace ni republicación", () => {
  render(<AttemptDetail attempt={{ state: "withdrawn", result: null, events: [{ id: 1, kind: "withdrawn", created_at: 100 }] }} />);
  expect(screen.getAllByText(/Retirada/)).toHaveLength(2);
  expect(screen.queryByRole("link")).toBeNull();
  expect(screen.queryByRole("button")).toBeNull();
});

it("libera la URL privada real al cancelar y muestra el límite con un paso útil", async () => {
  const api = await import("../../api/publications");
  const realURL = globalThis.URL;
  const revoke = vi.fn();
  const create = vi.fn(() => "blob:exact-original");
  class TestURL extends realURL {
    static createObjectURL = create;
    static revokeObjectURL = revoke;
  }
  vi.stubGlobal("URL", TestURL);
  try {
    const revision = previewCampaign().revisions[0];
    revision.media.sha256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
    vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, arrayBuffer: async () => new TextEncoder().encode("abc").buffer } as Response);
    const controller = new AbortController();
    const preview = await api.privatePreview(revision, controller.signal);
    expect(create).toHaveBeenCalledTimes(1);
    controller.abort();
    expect(revoke).toHaveBeenCalledWith(preview.url);
    preview.release();
    expect(revoke).toHaveBeenCalledTimes(1);
    vi.mocked(globalThis.fetch).mockResolvedValue({ ok: false, status: 409, json: async () => ({ detail: "campaign_revision_limit" }) } as Response);
    await expect(api.revise(revision, "nuevo", revision.channel_metadata)).rejects.toThrow(/100 revisiones.*Crea otra campaña/);
  } finally {
    vi.unstubAllGlobals();
  }
});
