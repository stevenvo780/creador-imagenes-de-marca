import { readFileSync } from "node:fs";
import { afterEach, expect, it } from "vitest";
import { createAndMountContainer } from "../render/clientRender";

afterEach(() => { document.body.innerHTML = ""; document.head.innerHTML = ""; delete document.documentElement.dataset.theme; });
it("conserva las variantes mono del template real y separa sus tokens de ambos temas", () => {
  const html = readFileSync("../templates/lockup_horizontal.html", "utf8");
  const system = readFileSync("../templates/eikon-system.css", "utf8");
  const appStyle = document.createElement("style");
  appStyle.textContent = ':root[data-theme="light"]{--bg:#f3f7f9;--surface:#fff} :root[data-theme="dark"]{--bg:#0e1416;--surface:#151c1f}';
  document.head.appendChild(appStyle);
  const vars = { bg: "#f5d9ba", texto: "#302014", primario: "#9c4834", font_titulo: "Manrope" };
  const before = JSON.stringify(vars);
  const node = createAndMountContainer(html, { vars, data_attrs: { "data-variant": "v2_mono" }, texts: {}, params: {}, idx: 0 }, { w: 1200, h: 400 }, system);
  const body = node.querySelector("body");
  for (const theme of ["light", "dark"]) {
    document.documentElement.dataset.theme = theme;
    expect(getComputedStyle(body).getPropertyValue("--bg").trim()).toBe("#f4f1ea");
    expect(getComputedStyle(body).getPropertyValue("--texto").trim()).toBe("#0b1417");
    expect(getComputedStyle(node).getPropertyValue("--bg").trim()).toBe(vars.bg);
    expect(getComputedStyle(node).getPropertyValue("--surface").trim()).toBe("#152028");
    expect(getComputedStyle(document.documentElement).getPropertyValue("--bg").trim()).toBe(theme === "light" ? "#f3f7f9" : "#0e1416");
    expect(body.style.getPropertyValue("--font-titulo")).toBe("Manrope");
    expect(body.style.getPropertyValue("--bg")).toBe("");
  }
  expect(JSON.stringify(vars)).toBe(before);
  expect(Array.from(node.querySelectorAll("style")).every(s => !/:root\b/.test(s.textContent))).toBe(true);
});

it("conserva los tokens derivados de la plantilla fb_cover en su propio lienzo", () => {
  const html = readFileSync("../templates/fb_cover.html", "utf8");
  const node = createAndMountContainer(html, { vars: { bg: "#f5d9ba", texto: "#302014" }, data_attrs: {}, texts: {}, params: {}, idx: 0 }, { w: 820, h: 312 }, "");
  for (const theme of ["light", "dark"]) {
    document.documentElement.dataset.theme = theme;
    expect(getComputedStyle(node).getPropertyValue("--surface").trim()).toBe("color-mix(in srgb, var(--bg) 86%, var(--texto))");
    expect(getComputedStyle(node).getPropertyValue("--bg").trim()).toBe("#f5d9ba");
    expect(getComputedStyle(node).getPropertyValue("--texto").trim()).toBe("#302014");
  }
});
