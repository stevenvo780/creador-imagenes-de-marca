import { afterEach, it, expect, vi } from "vitest";
import { cancelApiRequests } from "../../api/client";
import {
  publicationRequest,
  privatePreview,
  Revision,
} from "../../api/publications";
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  cancelApiRequests();
});
it("descarta un cuerpo tardío tras logout incluso si fetch ignora abort", async () => {
  let resolveBody!: (value: unknown) => void;
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      status: 200,
      json: () =>
        new Promise((resolve) => {
          resolveBody = resolve;
        }),
    })),
  );
  const request = publicationRequest("/overview");
  await vi.waitFor(() => expect(resolveBody).toBeTruthy());
  cancelApiRequests();
  resolveBody({ tenant: { id: 1 } });
  await expect(request).rejects.toHaveProperty("name", "AbortError");
});
it("cookie sólo a rutas propias sin caché y abort de campaña descarta body", async () => {
  let resolveBody!: (value: unknown) => void;
  const fetcher = vi.fn(async () => ({
    ok: true,
    status: 200,
    json: () =>
      new Promise((resolve) => {
        resolveBody = resolve;
      }),
  }));
  vi.stubGlobal("fetch", fetcher);
  const c = new AbortController();
  const request = publicationRequest("/campaigns", "GET", undefined, c.signal);
  await vi.waitFor(() => expect(resolveBody).toBeTruthy());
  c.abort();
  resolveBody({ items: [] });
  await expect(request).rejects.toHaveProperty("name", "AbortError");
  expect(fetcher).toHaveBeenCalledWith(
    "/api/v1/publications/campaigns",
    expect.objectContaining({ credentials: "include", cache: "no-store" }),
  );
  await expect(publicationRequest("https://evil.test")).rejects.toThrow();
});
it("preview rechaza referencia ajena antes de enviar cookies", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  await expect(
    privatePreview(
      {
        id: 1,
        contract_hash: "https://evil.test",
        media: { sha256: "a".repeat(64), mime: "image/png" },
      } as Revision,
      new AbortController().signal,
    ),
  ).rejects.toThrow();
  expect(fetcher).not.toHaveBeenCalled();
});
