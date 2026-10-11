import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import ts from "typescript";

const identityHelper = await import("data:text/javascript;base64," + Buffer.from(ts.transpile(
  readFileSync(new URL("../src/utils/brandIdentity.ts", import.meta.url), "utf8"),
  { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
)).toString("base64"));

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
    if (["brandHasLogo", "canGenerate", "ASSET_TYPES_GROUPED", "CONTENT_FIELDS", "ASSET_LABEL",
         "currentFields", "selectedAssetLabel", "selectedDimensions"].includes(name))
      expressions.set(name, node.initializer);
  }
  if (ts.isFunctionDeclaration(node) && ["extractAssetDimensions", "handleBrandChange", "handleContentChange"].includes(node.name?.text))
    expressions.set(node.name.text, node);
  if (ts.isJsxOpeningElement(node) && node.tagName.getText(source) === "SelectField") {
    const attributes = node.attributes.properties;
    const id = attributes.find((attr) => attr.name?.getText(source) === "id");
    if (id?.initializer && ts.isStringLiteral(id.initializer) && ["brand-select", "asset-type-select"].includes(id.initializer.text)) {
      const disabled = attributes.find((attr) => attr.name?.getText(source) === "disabled");
      expressions.set(id.initializer.text === "brand-select" ? "brandDisabled" : "typeDisabled", disabled?.initializer?.expression);
    }
  }
  if (ts.isJsxSelfClosingElement(node) && node.tagName.getText(source) === "input") {
    const disabled = node.attributes.properties.find(attr => attr.name?.getText(source) === "disabled");
    expressions.set("contentDisabled", disabled?.initializer?.expression);
  }
  ts.forEachChild(node, visit);
}
visit(source);
function evaluate(name, bindings) {
  bindings = { ...identityHelper, ...bindings };
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
    assert.equal(evaluate("typeDisabled", { selectedBrand, brandHasLogo, generating: false }), !ready);
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
  assert.equal(evaluate("typeDisabled", { selectedBrand, brandHasLogo, generating: false }), true);
  assert.equal(evaluate("canGenerate", {
    selectedBrand, brandHasLogo, selectedAssetType: "ig_post",
    generating: false, resultVariation: null,
  }), false);
});

test("Cambiar producto elimina copy y URL anteriores e invalida su vista previa", () => {
  const state = {brandId: 115, content: {titulo: "Aletheia", url: "aletheia.humanizar.tech"}, result: {id: 1}, progress: {done: 1, total: 1}, error: "anterior"};
  evaluate("handleBrandChange", {
    setSelectedBrandId: value => state.brandId = value,
    setContentValues: value => state.content = value,
    setResultVariation: value => state.result = value,
    setProgress: value => state.progress = value,
    setGenerateError: value => state.error = value,
  })(120);
  assert.equal(state.brandId, 120);
  assert.deepEqual(state.content, {}, "Prizma no puede heredar la URL ni el copy de Aletheia");
  assert.equal(state.result, null);
  assert.equal(state.error, "");
  assert.equal(state.progress, null);
});

test("Editar el contenido invalida el PNG anterior antes de poder descargarlo", () => {
  const state = {content: {titulo: "Anterior", url: "producto.example.test"}, result: {id: 1}, error: "anterior", progress: {done: 1, total: 1}};
  evaluate("handleContentChange", {
    setContentValues: update => state.content = update(state.content),
    setResultVariation: value => state.result = value,
    setGenerateError: value => state.error = value,
    setProgress: value => state.progress = value,
  })("titulo", "Nuevo");
  assert.deepEqual(state.content, {titulo: "Nuevo", url: "producto.example.test"});
  assert.equal(state.result, null, "La vista previa descargable debe corresponder al contenido actual");
  assert.equal(state.error, "");
  assert.equal(state.progress, null);
});

test("La generación pendiente mantiene estable la marca, formato y contenido", () => {
  const bindings = {selectedBrand: baseBrand, brandHasLogo: true, generating: true};
  for (const consumer of ["brandDisabled", "typeDisabled", "contentDisabled"])
    assert.equal(evaluate(consumer, bindings), true, `${consumer}: no cambiar el contrato del render en curso`);
  assert.equal(evaluate("brandDisabled", {...bindings, generating: false}), false);
  assert.equal(evaluate("contentDisabled", {...bindings, generating: false}), false);
});

test("Studio ofrece la publicación vertical con dimensiones visibles y campos de la plantilla", () => {
  const ASSET_TYPES_GROUPED = evaluate("ASSET_TYPES_GROUPED", {});
  const ASSET_LABEL = evaluate("ASSET_LABEL", { ASSET_TYPES_GROUPED });
  const CONTENT_FIELDS = evaluate("CONTENT_FIELDS", {});
  const selectedAssetType = "social_4x5";
  assert.ok(ASSET_TYPES_GROUPED.flatMap((group) => group.types)
    .some((type) => type.value === selectedAssetType), "El usuario puede seleccionar social_4x5");
  const selectedAssetLabel = evaluate("selectedAssetLabel", { ASSET_LABEL, selectedAssetType });
  assert.match(selectedAssetLabel, /Publicación vertical/);
  const extractAssetDimensions = evaluate("extractAssetDimensions", {});
  assert.equal(evaluate("selectedDimensions", { extractAssetDimensions, selectedAssetLabel }), "1080×1350");
  const currentFields = evaluate("currentFields", { CONTENT_FIELDS, selectedAssetType });
  assert.deepEqual(currentFields.map((field) => field.key), ["titulo", "subtitulo", "copy", "etiqueta", "url"]);
  assert.ok(currentFields.every((field) => field.label && field.placeholder), "Los campos tienen ayudas visibles");
});
