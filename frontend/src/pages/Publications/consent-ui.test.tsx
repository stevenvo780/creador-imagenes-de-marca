import { afterEach, it, expect, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import * as api from "../../api/publications";
import { CampaignDetail } from "./CampaignDetail";
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
const revision: api.Revision = {
  id: 7,
  campaign_id: 3,
  contract_hash: "a".repeat(64),
  caption: "Texto exacto",
  policy_version: 1,
  scheduled_at_utc: 1900000000,
  expires_at_utc: 1900003600,
  timezone: "UTC",
  channel_metadata: {
    sources: ["https://example.test/source"],
    rights: "owned",
    privacy: "SELF_ONLY",
    commercial_content: false,
    branded_content: false,
    disable_comment: false,
    disable_duet: false,
    disable_stitch: false,
    is_aigc: false,
  },
  media: {
    id: 1,
    kind: "gallery_image",
    sha256: "b".repeat(64),
    mime: "image/jpeg",
    width: 1080,
    height: 1080,
  },
  connection: {
    id: 5,
    platform: "tiktok",
    remote_id: "creator",
    remote_name: "Cuenta exacta",
  },
  visual_review: { approval_current: false },
  decision: {
    id: 1,
    outcome: "approve",
    reason: "Pertinente",
    provider: "double",
    model: "double",
  },
  eligibility_reasons: [],
};
it.each([
  ["disable_comment", "Desactivar comentarios"],
  ["disable_duet", "Desactivar dúos"],
  ["disable_stitch", "Desactivar pegar"],
  ["is_aigc", "Declarar contenido generado por IA"],
])("cambiar %s crea revisión antes de consentir", async (flag, label) => {
  vi.spyOn(api, "privatePreview").mockResolvedValue({
    url: "blob:exact",
    release: vi.fn(),
  });
  vi.spyOn(api, "getConsent").mockResolvedValue({
    consent: null,
    reasons: ["needs_platform_consent"],
  });
  vi.spyOn(api, "creatorInfo").mockResolvedValue({
    creator_id: 1,
    privacy_level_options: ["SELF_ONLY"],
    comment_disabled: false,
    duet_disabled: false,
    stitch_disabled: false,
    expires_at: 1900003600,
    creator_receipt_sha256: "c".repeat(64),
  });
  const revise = vi.spyOn(api, "revise").mockResolvedValue({ id: 8 });
  const consent = vi.spyOn(api, "consent");
  const refresh = vi.fn();
  render(
    <MemoryRouter>
      <CampaignDetail
        owner
        campaign={{
          id: 3,
          project_id: 1,
          brand_id: 1,
          project_name: "Proyecto",
          product_name: "Producto",
          objective: "Lanzamiento",
          archived: 0,
          revisions: [revision],
        }}
        onRefresh={refresh}
      />
    </MemoryRouter>,
  );
  const user = userEvent.setup();
  await user.click(
    screen.getByRole("button", {
      name: "Consultar opciones actuales de TikTok",
    }),
  );
  await user.selectOptions(
    screen.getByLabelText("Privacidad TikTok"),
    "SELF_ONLY",
  );
  await user.click(screen.getByLabelText(label));
  expect(
    (
      screen.getByRole("button", {
        name: "Registrar consentimiento exacto",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
  await user.click(
    screen.getByRole("button", {
      name: "Crear nueva revisión y solicitar evaluación IA",
    }),
  );
  expect(revise).toHaveBeenCalledWith(
    revision,
    "Texto exacto",
    expect.objectContaining({ [flag]: true }),
    expect.any(AbortSignal),
    expect.any(String),
    undefined,
  );
  expect(consent).not.toHaveBeenCalled();
  expect(refresh).toHaveBeenCalledOnce();
});
