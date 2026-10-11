import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";
import postcss from "postcss";

// Consume los estilos reales; la geometría sigue las reglas de replaced elements
// (flujo con altura automática frente a caja absoluta con object-fit).
const source = ts.createSourceFile("AssetStudioPage.tsx",
  readFileSync(new URL("../src/pages/AssetStudioPage.tsx", import.meta.url), "utf8"),
  ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const css = postcss.parse(readFileSync(new URL("../src/styles/theme.css", import.meta.url), "utf8"));
let image;
function visit(node) {
  if (ts.isJsxSelfClosingElement(node) && node.tagName.getText(source) === "img") image = node;
  ts.forEachChild(node, visit);
}
visit(source);
assert.ok(image);
const styleAttr = image.attributes.properties.find((attr) => attr.name?.getText(source) === "style");
const classAttr = image.attributes.properties.find((attr) => attr.name?.getText(source) === "className");
const inline = new Function(ts.transpile(`return (${styleAttr.initializer.expression.getText(source)});`))();
const imageStyles = {};
if (classAttr?.initializer && ts.isStringLiteral(classAttr.initializer)) {
  const selector = "." + classAttr.initializer.text;
  css.walkRules(selector, (rule) => {
    rule.walkDecls((decl) => {
      const camel = decl.prop.replace(/-([a-z])/g, (_, char) => char.toUpperCase());
      imageStyles[camel] = decl.value;
    });
  });
}
Object.assign(imageStyles, inline);

function cssSize(value, available, padding) {
  if (value === "100%") return available;
  if (value === "calc(100% - 2 * var(--space-6))") return available - 2 * padding;
  return undefined;
}
function drawnBounds(naturalWidth, naturalHeight, shellSize, padding) {
  const s = imageStyles;
  const width = cssSize(s.width, shellSize, padding) ?? shellSize - 2 * padding;
  // El flujo automático no resuelve max-height porcentual: reproduce el recorte observado.
  const height = cssSize(s.height, shellSize, padding) ?? width * naturalHeight / naturalWidth;
  const scale = s.objectFit === "contain"
    ? Math.min(width / naturalWidth, height / naturalHeight)
    : width / naturalWidth;
  return {
    width: naturalWidth * scale,
    height: naturalHeight * scale,
    bounded: s.position === "absolute" || height <= shellSize - 2 * padding,
  };
}
for (const [name, width, height, shellSize] of [
  ["publicación vertical en escritorio", 2160, 2700, 503.8],
  ["historia vertical en móvil", 1080, 1920, 260],
  ["tarjeta horizontal en escritorio", 1050, 600, 503.8],
  ["publicación cuadrada en móvil", 1080, 1080, 260],
]) {
  test(`Preview completo: ${name}`, () => {
    const inner = shellSize - 48;
    const drawn = drawnBounds(width, height, shellSize, 24);
    assert.ok(drawn.width <= inner + 0.01, "La imagen no supera el ancho interior");
    assert.ok(drawn.height <= inner + 0.01, "El pie de la imagen queda dentro del lienzo");
    assert.ok(drawn.bounded, "La caja no depende de una altura porcentual automática");
    assert.ok(Math.abs(drawn.width / drawn.height - width / height) < 0.0001,
      "La imagen conserva su proporción");
  });
}
