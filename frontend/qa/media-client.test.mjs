/** API behavior checks using Node's built-in runner, with no new dependencies. */
import { test, afterEach } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";
const moduleUrl = (source) =>
  "data:text/javascript;base64," +
  Buffer.from(
    ts.transpile(source, {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ES2022,
    }),
  ).toString("base64");
const clientUrl = moduleUrl(
  readFileSync(new URL("../src/api/client.ts", import.meta.url), "utf8"),
);
const source = readFileSync(
  new URL("../src/api/media.ts", import.meta.url),
  "utf8",
).replace(/['"]\.\/client['"]/, JSON.stringify(clientUrl));
const api = await import(moduleUrl(source));
const originalFetch = globalThis.fetch;
afterEach(() => {
  api.clearPrivateMedia();
  globalThis.fetch = originalFetch;
});
function response(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
test("filters reach authenticated no-store endpoint without tenant body", async () => {
  let request;
  globalThis.fetch = async (url, options) => {
    request = { url, options };
    return response({ items: [], next_cursor: null });
  };
  await api.listMedia({
    brand_id: 2,
    project_id: 4,
    source: "codex",
    status: "pending_review",
  });
  assert.equal(
    request.url,
    "/api/v1/media?brand_id=2&project_id=4&source=codex&status=pending_review",
  );
  assert.equal(request.options.credentials, "include");
  assert.equal(request.options.cache, "no-store");
  assert.equal(request.options.body, undefined);
});
test("review sends original hash and frozen identity version", async () => {
  let sent;
  globalThis.fetch = async (url, options) => {
    sent = { url, options };
    return response({ id: 1 }, 201);
  };
  const payload = {
    decision: "rejected",
    expected_sha256: "a".repeat(64),
    expected_brand_version: 7,
    reason: "Corregir texto",
  };
  await api.reviewMedia(8, payload);
  assert.equal(sent.url, "/api/v1/media/8/reviews");
  assert.deepEqual(JSON.parse(sent.options.body), payload);
});
test("key scopes are closed and secret is returned to caller only", async () => {
  assert.deepEqual(api.codexScopes, [
    "projects:read",
    "projects:write",
    "brands:read",
    "briefs:write",
    "media:read",
    "media:write",
  ]);
  globalThis.fetch = async () =>
    response(
      { id: 1, key: "synthetic-only", name: "test", scopes: [], expires_at: 1 },
      201,
    );
  const key = await api.createCodexKey({
    name: "test",
    scopes: [],
    expires_in_days: 1,
  });
  assert.equal(key.key, "synthetic-only");
});
test("401 and version409 provide actions in Spanish", async () => {
  for (const [status, expected] of [
    [401, /sesión venció/],
    [409, /Actualizá el detalle/],
  ]) {
    globalThis.fetch = async () =>
      response({ detail: { code: "obsolete" } }, status);
    await assert.rejects(api.getMedia(1), (e) =>
      expected.test(api.mediaError(e)),
    );
  }
});
test("logout aborts in-flight requests and private images", async () => {
  const signals = [];
  globalThis.fetch = (_url, { signal }) =>
    new Promise((_, reject) => {
      signals.push(signal);
      signal.addEventListener("abort", () =>
        reject(new DOMException("Aborted", "AbortError")),
      );
    });
  const a = api.listMedia().catch((e) => e),
    b = api
      .privateImage("/api/v1/media/1/thumbnail", new AbortController().signal)
      .catch((e) => e);
  api.clearPrivateMedia();
  assert.equal(signals.length, 2);
  assert.ok(signals.every((s) => s.aborted));
  assert.ok(api.isAbort(await a));
  assert.ok(api.isAbort(await b));
});
test("private image rejects external paths and revokes retained blob on logout", async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    return new Response(new Blob(["image"], { type: "image/png" }));
  };
  await assert.rejects(
    api.privateImage(
      "https://example.test/asset",
      new AbortController().signal,
    ),
  );
  assert.equal(calls, 0);
  const original = URL.revokeObjectURL,
    revoked = [];
  URL.revokeObjectURL = (u) => {
    revoked.push(u);
    original(u);
  };
  try {
    const u = await api.privateImage(
      "/api/v1/media/1/thumbnail",
      new AbortController().signal,
    );
    assert.ok(u.startsWith("blob:"));
    api.clearPrivateMedia();
    assert.deepEqual(revoked, [u]);
  } finally {
    URL.revokeObjectURL = original;
  }
});
test("legacy promotion is an explicit variation-only request", async () => {
  let sent;
  globalThis.fetch = async (url, options) => {
    sent = { url, body: JSON.parse(options.body) };
    return response({ id: 2, status: "pending_review" }, 201);
  };
  const result = await api.promoteVariation(91);
  assert.deepEqual(sent, {
    url: "/api/v1/media/from-variation",
    body: { variation_id: 91 },
  });
  assert.equal(result.status, "pending_review");
});

const client = await import(clientUrl);
test("logout cancels legacy requests even after response headers", async () => {
  let deliver;
  globalThis.fetch = async () => ({
    status: 200,
    ok: true,
    json: () =>
      new Promise((resolve) => {
        deliver = resolve;
      }),
  });
  const request = client.gallery.list().catch((e) => e);
  await new Promise((resolve) => setImmediate(resolve));
  api.clearPrivateMedia();
  deliver({ items: [{ id: 1, brand_id: 1 }] });
  assert.ok(api.isAbort(await request));
});

// Controlled DOM/rasterizer dependencies exercise the real render/upload orchestration.
// This is a cancellation regression, not proof of browser pixels or FontFace loading.
const screenshotUrl =
  "data:text/javascript;base64," +
  Buffer.from(
    "export const domToPng=(node)=>globalThis.qaRasterize(node);",
  ).toString("base64");
const rendererSource = readFileSync(
  new URL("../src/render/clientRender.ts", import.meta.url),
  "utf8",
)
  .replace(/["']\.\.\/api\/client["']/, JSON.stringify(clientUrl))
  .replace(
    'import("modern-screenshot")',
    `import(${JSON.stringify(screenshotUrl)})`,
  );
const renderer = await import(moduleUrl(rendererSource));
function rendererFixture(logo = "") {
  const saved = {
    document: globalThis.document,
    DOMParser: globalThis.DOMParser,
    FontFace: globalThis.FontFace,
    requestAnimationFrame: globalThis.requestAnimationFrame,
    qaRasterize: globalThis.qaRasterize,
  };
  class Node {
    constructor() {
      this.children = [];
      this.style = {
        setProperty: (key, value) => {
          this.style[key] = value;
        },
      };
      this.dataset = {};
    }
    appendChild(child) {
      child.parentNode = this;
      this.children.push(child);
      return child;
    }
    removeChild(child) {
      this.children = this.children.filter((c) => c !== child);
      child.parentNode = null;
    }
    remove() {
      this.parentNode?.removeChild(this);
    }
    querySelector(selector) {
      return selector === "[data-isotype-container]" ? logoSlot : null;
    }
    querySelectorAll() {
      return [];
    }
    setAttribute() {}
  }
  const logoSlot = new Node();
  logoSlot.style.width = "100px";
  logoSlot.style.height = "100px";
  const body = new Node(),
    fonts = [];
  globalThis.document = {
    body,
    createElement: () => new Node(),
    fonts: { ready: Promise.resolve(), add: (font) => fonts.push(font) },
  };
  globalThis.DOMParser = class {
    parseFromString() {
      return { body: new Node(), querySelectorAll: () => [] };
    }
  };
  globalThis.FontFace = class {
    constructor(family) {
      this.family = family;
    }
    async load() {
      return this;
    }
  };
  globalThis.requestAnimationFrame = (callback) => queueMicrotask(callback);
  const uploads = [];
  globalThis.fetch = async (path, options = {}) => {
    if (path.endsWith("/plan"))
      return response({
        template_name: "ig_post",
        asset_type: "ig_post",
        viewport: { w: 512, h: 512 },
        device_scale_factor: 1,
        combinations: [
          {
            idx: 0,
            params: {},
            vars: { font_titulo: "Manrope", font_cuerpo: "Manrope" },
            data_attrs: {},
            texts: {},
            isotype_data_uri: logo,
          },
        ],
      });
    if (path.endsWith("/upload")) {
      uploads.push(path);
      return response({ combo_idx: 0, success: true });
    }
    return new Response(
      path.includes("/templates/") ? "<body>Alpha</body>" : "",
    );
  };
  return {
    body,
    logoSlot,
    fonts,
    uploads,
    restore() {
      for (const [key, value] of Object.entries(saved)) {
        if (value === undefined) delete globalThis[key];
        else globalThis[key] = value;
      }
    },
  };
}
test("logout during rasterization removes private DOM and never uploads into next session", async () => {
  const fixture = rendererFixture();
  let finishRaster, started;
  const rasterStarted = new Promise((resolve) => {
    started = resolve;
  });
  globalThis.qaRasterize = () => {
    started();
    return new Promise((resolve) => {
      finishRaster = resolve;
    });
  };
  try {
    const task = renderer.renderBatchClientSide(9);
    await rasterStarted;
    assert.equal(fixture.body.children.length, 1);
    api.clearPrivateMedia();
    assert.equal(fixture.body.children.length, 0);
    finishRaster("data:image/png;base64,aW1hZ2U=");
    await task;
    assert.deepEqual(fixture.uploads, []);
  } finally {
    fixture.restore();
  }
});
test("normal client render still uploads and removes staging DOM", async () => {
  const fixture = rendererFixture();
  globalThis.qaRasterize = async (node) => {
    assert.equal(node.children.at(-1).style["--font-titulo"], "Manrope");
    assert.equal(node.children.at(-1).style["--font-cuerpo"], "Manrope");
    return "data:image/png;base64,aW1hZ2U=";
  };
  try {
    const result = await renderer.renderBatchClientSide(10);
    assert.deepEqual(result, { uploaded: 1, failed: 0 });
    assert.deepEqual(fixture.uploads, ["/api/v1/batches/10/variations/upload"]);
    assert.equal(fixture.body.children.length, 0);
    assert.ok(fixture.fonts.some((font) => font.family === "Manrope"));
  } finally {
    fixture.restore();
  }
});


const rasterLogos = {
  "300x80": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAASwAAABQCAIAAAAsiN8sAAAA+UlEQVR4nO3VMREAMAwDsbTIAz0wfpEIePrzm90BOj/cBkQIPU8IMRFCTIQQEyHERAgxEUJMhBATIcRECDERQkyEEBMhxEQIMRFCTIQQEyHERAgxEUJMhBATIcRECDERQkyEEBMhxEQIMRFCTIQQEyHERAgxEUJMhBATIcRECDERQkyEEBMhxEQIMRFCTIQQEyHERAgxEUJMhBATIcRECDERQkyEEBMhxEQIMRFCTIQQEyHERAgxEUJMhBATIcRECDERQkyEEBMhxEQIMRFCTIQQEyHERAgxEUJMhBATIcRECDERQkyEEBMhxEQIMRFCTIQQEyHERAjTOrm+AaBspO5yAAAAAElFTkSuQmCC",
  "80x300": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFAAAAEsCAIAAADb5KP0AAAB30lEQVR4nO3PAQ0AIBCAQCT5R7eFbuIlgMUMJRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMX/4dRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMRIjMd4OOG0DnnYDWB18dlMAAAAASUVORK5CYII=",
  "100x100": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAIAAAD/gAIDAAAA5klEQVR4nO3SsREAIAwDscDkjM4K+V6qXf35zHvDzl3uEKvxrECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArECsQKxArNn7/nEByH6uSUQAAAAASUVORK5CYII="
};
for (const [width, height] of [[300, 80], [80, 300], [100, 100]]) {
  test(`official raster ${width}x${height} stays contained and centered in a square slot`, async () => {
    // Synthetic raster bytes; the actual renderer injects this exact source.
    const logo = rasterLogos[`${width}x${height}`];
    const png = Buffer.from(logo.split(",")[1], "base64");
    assert.equal(png.readUInt32BE(16), width);
    assert.equal(png.readUInt32BE(20), height);
    const fixture = rendererFixture(logo);
    globalThis.qaRasterize = async () => {
      const img = fixture.logoSlot.children.at(-1);
      assert.equal(img.src, logo);
      assert.equal(img.style.objectFit, "contain");
      assert.equal(img.style.objectPosition, "center");
      assert.equal(img.style.width, "100%");
      assert.equal(img.style.height, "100%");
      return "data:image/png;base64,aW1hZ2U=";
    };
    try {
      assert.deepEqual(await renderer.renderBatchClientSide(11), { uploaded: 1, failed: 0 });
    } finally { fixture.restore(); }
  });
}
