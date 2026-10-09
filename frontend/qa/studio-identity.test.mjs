import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import ts from "typescript";

// Ejecuta el guard y sus consumidores reales, como el harness AST de task7-fix1.
const source = ts.createSourceFile(
  "AssetStudioPage.tsx",
  process.env.EIKON_STUDIO_BASE
    ? execFileSync("git", ["show", `${process.env.EIKON_STUDIO_BASE}:frontend/src/pages/AssetStudioPage.tsx`], { encoding: "utf8" })
    : readFileSync(new URL("../src/pages/AssetStudioPage.tsx", import.meta.url), "utf8"),
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TSX,
);
const expressions = new Map();
function visit(node) {
  if (ts.isVariableDeclaration(node) && node.initializer) {
    const name = node.name.getText(source);
    if (name === "brandHasLogo" || name === "canGenerate")
      expressions.set(name, node.initializer);
  }
  if (ts.isJsxOpeningElement(node) && node.tagName.getText(source) === "SelectField") {
    const attributes = node.attributes.properties;
    const id = attributes.find((attr) => attr.name?.getText(source) === "id");
    if (id?.initializer && ts.isStringLiteral(id.initializer) && id.initializer.text === "asset-type-select") {
      const disabled = attributes.find((attr) => attr.name?.getText(source) === "disabled");
      expressions.set("typeDisabled", disabled?.initializer?.expression);
    }
  }
  ts.forEachChild(node, visit);
}
visit(source);
function evaluate(name, bindings) {
  const expression = expressions.get(name);
  assert.ok(expression, `Studio debe exponer el consumidor ${name}`);
  const compiled = ts.transpile(`const observed = ${expression.getText(source)};`, {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ES2022,
  });
  return new Function(...Object.keys(bindings), `${compiled}; return observed;`)(...Object.values(bindings));
}

const baseBrand = {
  id: 1, slug: "qa-brand", name: "Marca sintética", project_id: 1,
  brand_version: 1, reference_logo_sha256: null, logo_asset: null,
  palette: {}, typography: {}, logo_text: "", logo_symbol: "",
  logo_style: "", logo_seed: 0, texts: {}, created_at: 0,
};
for (const [name, identity, ready] of [
  ["referencia original sin estilo procedural", { reference_logo_sha256: "a".repeat(64) }, true],
  ["archivo legado exclusivo en DB sin ruta resuelta", { logo_asset: "marcas/qa/logo.svg" }, false],
  ["procedural con seed positivo", { logo_style: "orbital", logo_seed: 7 }, true],
  ["procedural con seed cero válido", { logo_style: "orbital", logo_seed: 0 }, true],
  ["marca sin identidad", {}, false],
  ["seed sin estilo", { logo_seed: 7 }, false],
  ["estilo sin seed", { logo_style: "orbital", logo_seed: null }, false],
  ["estilo none sin isotipo", { logo_style: "none", logo_seed: 7 }, false],
]) {
  test(`Studio ${name}: habilitación del tipo y de generación`, () => {
    const selectedBrand = { ...baseBrand, ...identity };
    const brandHasLogo = evaluate("brandHasLogo", { selectedBrand });
    assert.equal(brandHasLogo, ready, "El guard debe reconocer únicamente identidad disponible");
    assert.equal(evaluate("typeDisabled", { selectedBrand, brandHasLogo }), !ready);
    assert.equal(evaluate("canGenerate", {
      selectedBrand, brandHasLogo, selectedAssetType: "ig_post",
      generating: false, resultVariation: null,
    }), ready);
  });
}
test("Studio sin marca seleccionada mantiene ambos controles deshabilitados", () => {
  const selectedBrand = null;
  const brandHasLogo = evaluate("brandHasLogo", { selectedBrand });
  assert.equal(brandHasLogo, false);
  assert.equal(evaluate("typeDisabled", { selectedBrand, brandHasLogo }), true);
  assert.equal(evaluate("canGenerate", {
    selectedBrand, brandHasLogo, selectedAssetType: "ig_post",
    generating: false, resultVariation: null,
  }), false);
});
