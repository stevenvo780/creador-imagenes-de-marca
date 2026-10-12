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
  await screen.findByRole("link", { name: "Producto B: Campaña" });
  resolveA(overview("A"));
  await new Promise((resolve) => setTimeout(resolve, 0));
  expect(
    screen.queryByRole("link", { name: "Producto A: Campaña" }),
  ).toBeNull();
});
