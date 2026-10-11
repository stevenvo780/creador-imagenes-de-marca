import type { Brand } from "../api/client";

type IdentityBrand = Pick<Brand, "reference_logo_sha256" | "logo_style" | "logo_seed">;
type IdentityKind = "original" | "procedural" | "unconfigured";

/** Indica un logo fijado; no sustituye la revisión de las piezas de la galería. */
export function getBrandIdentity(brand: IdentityBrand | null | undefined): {
  kind: IdentityKind;
  configured: boolean;
  label: string;
} {
  if (brand?.reference_logo_sha256 && /^[a-f0-9]{64}$/i.test(brand.reference_logo_sha256)) {
    return { kind: "original", configured: true, label: "Logo original fijado" };
  }
  const style = brand?.logo_style?.trim();
  if (style && style !== "none" && Number.isInteger(brand?.logo_seed)) {
    return { kind: "procedural", configured: true, label: "Logo procedural fijado" };
  }
  return { kind: "unconfigured", configured: false, label: "Identidad pendiente" };
}
