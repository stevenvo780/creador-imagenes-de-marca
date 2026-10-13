import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { expect, it } from "vitest";

it("aplica el tema persistido antes de montar React y tolera almacenamiento bloqueado", () => {
  const source = readFileSync("public/theme-init.js", "utf8");
  for (const saved of ["dark", "light", "invalid"]) {
    const root = { dataset: {} };
    runInNewContext(source, { document: { documentElement: root }, localStorage: { getItem: () => saved }, matchMedia: () => ({ matches: true }) });
    expect(root.dataset.theme).toBe(saved === "light" ? "light" : "dark");
  }
  const root = { dataset: {} };
  runInNewContext(source, { document: { documentElement: root }, localStorage: { getItem: () => { throw new Error("blocked"); } }, matchMedia: () => ({ matches: false }) });
  expect(root.dataset.theme).toBe("light");
});
