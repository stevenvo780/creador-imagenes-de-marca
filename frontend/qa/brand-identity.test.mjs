import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";

// Ejecuta los guards y el badge reales: no replica su lógica en el test.
const helperPath = new URL("../src/utils/brandIdentity.ts", import.meta.url);
const helper = await import("data:text/javascript;base64," + Buffer.from(ts.transpile(
      readFileSync(helperPath, "utf8"),
      { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
    )).toString("base64"));

function evaluateConsumer(file, name, bindings) {
  const source = ts.createSourceFile(file, readFileSync(new URL(file, import.meta.url), "utf8"),
    ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let expression;
  function visit(node) {
    if (ts.isVariableDeclaration(node) && node.name.getText(source) === name)
      expression = node.initializer;
    if (name === "badge" && ts.isJsxExpression(node) && node.expression &&
        node.parent?.openingElement?.attributes.getText(source).includes('color: hasLogo ? "var(--ok)"'))
      expression = node.expression;
    ts.forEachChild(node, visit);
  }
  visit(source);
  assert.ok(expression, `Consumidor ${name} disponible`);
  const compiled = ts.transpile(`const observed = ${expression.getText(source)};`, {
    target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022,
  });
  const scope = { ...helper, ...bindings };
  return new Function(...Object.keys(scope), `${compiled}; return observed;`)(...Object.values(scope));
}

const brandPage = "../src/pages/BrandsPage.tsx";
const studioPage = "../src/pages/AssetStudioPage.tsx";
const baseBrand = {
  id: 1, tenant_id: 1, slug: "qa-brand", name: "Marca sintética", project_id: 1,
  brand_version: 1, reference_logo_sha256: null, palette: {}, typography: {},
  logo_text: "QA", logo_symbol: "", logo_style: "", logo_seed: 0, texts: {}, created_at: 0,
};
for (const [name, identity, ready] of [
  ["original sin estilo procedural", { reference_logo_sha256: "a".repeat(64) }, true],
  ["original tiene prioridad sobre none", { reference_logo_sha256: "B".repeat(64), logo_style: "none" }, true],
  ["hash original malformado", { reference_logo_sha256: "no-es-un-sha256" }, false],
  ["hash original de longitud incorrecta", { reference_logo_sha256: "a".repeat(63) }, false],
  ["hash original no hexadecimal", { reference_logo_sha256: "z".repeat(64) }, false],
  ["hash original con salto de línea final", { reference_logo_sha256: "a".repeat(64) + "\n" }, false],
  ["procedural con seed cero", { logo_style: "orbital", logo_seed: 0 }, true],
  ["procedural con seed positivo", { logo_style: "orbital", logo_seed: 7 }, true],
  ["none no fija identidad", { logo_style: "none", logo_seed: 7 }, false],
  ["estilo vacío", { logo_style: "", logo_seed: 7 }, false],
  ["estilo de espacios", { logo_style: "   ", logo_seed: 7 }, false],
  ["estilo sin seed", { logo_style: "orbital", logo_seed: null }, false],
  ["seed decimal", { logo_style: "orbital", logo_seed: 0.5 }, false],
  ["seed string", { logo_style: "orbital", logo_seed: "7" }, false],
  ["seed infinito", { logo_style: "orbital", logo_seed: Infinity }, false],
  ["archivo legado no resuelto", { logo_asset: "marcas/qa/logo.svg" }, false],
]) {
  test(`Marcas y Studio coinciden: ${name}`, () => {
    const brand = { ...baseBrand, ...identity };
    const extra = { identity: evaluateConsumer(brandPage, "identity", { brand }) };
    assert.equal(evaluateConsumer(brandPage, "hasLogo", { brand, ...extra }), ready);
    assert.equal(evaluateConsumer(studioPage, "brandHasLogo", { selectedBrand: brand, ...extra }), ready);
  });
}

for (const [name, identity, expected, ready] of [
  ["original", { reference_logo_sha256: "a".repeat(64) }, "Logo original fijado", true],
  ["procedural", { logo_style: "orbital", logo_seed: 0 }, "Logo procedural fijado", true],
  ["sin configurar", {}, "Identidad pendiente", false],
]) {
  test(`El badge distingue ${name} sin confundirlo con aprobación de piezas`, () => {
    const brand = { ...baseBrand, ...identity };
    const extra = { identity: evaluateConsumer(brandPage, "identity", { brand }) };
    assert.equal(evaluateConsumer(brandPage, "badge", { brand, hasLogo: ready, ...extra }), expected);
  });
}
