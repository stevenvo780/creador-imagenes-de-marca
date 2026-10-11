import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";
import postcss from "postcss";

// Ejecuta la función real de montaje. El DOM mínimo modela solo la cascada de
// tamaño para detectar fugas de 100vh/min-width desde la aplicación anfitriona.
const source = ts.createSourceFile("clientRender.ts",
  readFileSync(new URL("../src/render/clientRender.ts", import.meta.url), "utf8"),
  ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
let mountNode;
function visit(node) {
  if (ts.isFunctionDeclaration(node) && node.name?.text === "createAndMountContainer") mountNode = node;
  ts.forEachChild(node, visit);
}
visit(source);
assert.ok(mountNode);
const compiled = ts.transpile(mountNode.getText(source), { target: ts.ScriptTarget.ES2022 });
const hostBodyStyles = {};
postcss.parse(readFileSync(new URL("../src/styles/theme.css", import.meta.url), "utf8"))
  .walkRules("body", (rule) => rule.walkDecls((decl) => {
    hostBodyStyles[decl.prop.replace(/-([a-z])/g, (_, char) => char.toUpperCase())] = decl.value;
  }));

function fixture(viewport) {
  function element(tag) {
    return {
      tag, style: { setProperty(key, value) { this[key] = value; } }, dataset: {}, children: [],
      appendChild(node) { this.children.push(node); }, setAttribute() {},
      querySelector() { return null; }, querySelectorAll() { return []; },
    };
  }
  const bodyContent = element("body");
  const document = { createElement: element, body: element("body") };
  const DOMParser = class {
    parseFromString() { return { body: bodyContent, querySelectorAll() { return []; } }; }
  };
  const mount = new Function("document", "DOMParser", `${compiled}; return createAndMountContainer;`)(document, DOMParser);
  const container = mount("<body>Plantilla sintética</body>",
    { vars: {}, data_attrs: {}, texts: {}, isotype_data_uri: null }, viewport, "");
  assert.equal(container.children.at(-1), bodyContent, "Se mide el body realmente montado");
  return { container, bodyContent };
}
function pixels(value, browserHeight) {
  if (value?.endsWith("vh")) return parseFloat(value) * browserHeight / 100;
  return parseFloat(value) || 0;
}
for (const [name, viewport, browserHeight] of [
  ["publicación vertical en ventana alta", { w: 1080, h: 1350 }, 1746],
  ["anuncio más estrecho que el mínimo de la app", { w: 300, h: 250 }, 1746],
  ["tarjeta horizontal en ventana alta", { w: 1050, h: 600 }, 1746],
  ["historia en ventana baja", { w: 1080, h: 1920 }, 740],
]) {
  test(`El lienzo tiene tamaño propio: ${name}`, () => {
    const { container, bodyContent } = fixture(viewport);
    // La plantilla aporta width/height; los estilos inline deben imponerse a
    // los mínimos globales incluso al copiar un body dentro de otro documento.
    const styles = { ...hostBodyStyles, width: `${viewport.w}px`, height: `${viewport.h}px`, ...bodyContent.style };
    const width = Math.max(pixels(styles.width, browserHeight), pixels(styles.minWidth, browserHeight));
    const height = Math.max(pixels(styles.height, browserHeight), pixels(styles.minHeight, browserHeight));
    assert.equal(width, viewport.w, "El ancho no depende del mínimo de la SPA");
    assert.equal(height, viewport.h, "El footer no sale del PNG por min-height:100vh");
    assert.equal(width, pixels(container.style.width, browserHeight));
    assert.equal(height, pixels(container.style.height, browserHeight));
  });
}
