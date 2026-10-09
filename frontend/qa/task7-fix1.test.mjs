import { test, afterEach } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import ts from "typescript";
const jsUrl = (source) =>
  "data:text/javascript;base64," +
  Buffer.from(
    ts.transpile(source, {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ES2022,
    }),
  ).toString("base64");
const read = (path) =>
  process.env.EIKON_FIX1_BASE
    ? execFileSync(
        "git",
        [
          "show",
          `${process.env.EIKON_FIX1_BASE}:frontend/${path.replace(/^\.\.\//, "")}`,
        ],
        { encoding: "utf8" },
      )
    : readFileSync(new URL(path, import.meta.url), "utf8");
const clientUrl = jsUrl(read("../src/api/client.ts")),
  client = await import(clientUrl);
const api = await import(
  jsUrl(
    read("../src/api/media.ts").replace(
      /["']\.\/client["']/,
      JSON.stringify(clientUrl),
    ),
  )
);
const nativeFetch = globalThis.fetch;
afterEach(() => {
  api.clearPrivateMedia();
  globalThis.fetch = nativeFetch;
});
const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
const deferred = () => {
  let resolve;
  const promise = new Promise((r) => {
    resolve = r;
  });
  return { promise, resolve };
};
const tick = () => new Promise((r) => setImmediate(r));
// Executes the actual handler/effect AST with controlled transport/state, rather than reproducing JSX.
function sourceNode(path, name) {
  const source = ts.createSourceFile(
    path,
    read(path),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  let result;
  function visit(n) {
    if (ts.isVariableDeclaration(n) && n.name.getText(source) === name)
      result = n.initializer;
    if (ts.isFunctionDeclaration(n) && n.name?.text === name) result = n;
    ts.forEachChild(n, visit);
  }
  visit(source);
  if (!result) throw new Error(`Missing ${name}`);
  return { source, result };
}
function handler(name, bindings) {
  let { source, result } = sourceNode("../src/pages/Gallery/index.tsx", name);
  if (ts.isCallExpression(result)) result = result.arguments[0];
  const text = ts.transpile(`const fn=${result.getText(source)};`, {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ES2022,
  });
  return new Function(
    "bindings",
    `const {${Object.keys(bindings).join(",")}}=bindings;${text};return fn;`,
  )(bindings);
}
for (const kind of ["zip", "individual"])
  for (const end of ["logout", "unmount", "close", "normal"])
    test(`${kind} late body ${end}: no cross-session URL/click and normal download retained`, async () => {
      const body = deferred(),
        started = deferred();
      let signal;
      globalThis.fetch = async (url, options) => {
        if (url === "/auth/me")
          return json({
            user: { email: "beta@example.test" },
            tenant: { id: 2 },
          });
        signal = options.signal;
        started.resolve();
        return { ok: true, status: 200, blob: () => body.promise };
      };
      let urls = 0,
        clicks = 0,
        revokes = 0;
      const downloadController = { current: new AbortController() },
        states = [];
      const bindings = {
        selected: new Set([1]),
        setZipping: (v) => states.push(v),
        setDownloading: () => {},
        downloads: client.downloads,
        beginSessionWork: client.beginSessionWork,
        downloadController,
        URL: {
          createObjectURL: () => {
            urls++;
            return "blob:qa";
          },
          revokeObjectURL: () => {
            revokes++;
          },
        },
        document: {
          createElement: () => ({
            click() {
              clicks++;
            },
          }),
        },
        alert: () => {},
        ApiError: client.ApiError,
        isAbort: api.isAbort,
      };
      const run = handler(
        kind === "zip" ? "handleZip" : "handleDownloadOne",
        bindings,
      )(1);
      await started.promise;
      if (end === "logout") {
        api.clearPrivateMedia();
        const beta = await client.auth.me();
        assert.equal(beta.user.email, "beta@example.test");
      }
      if (end === "unmount" || end === "close")
        downloadController.current.abort();
      body.resolve(new Blob(["alpha-only"]));
      await run;
      if (end === "normal") {
        assert.equal(clicks, 1);
        assert.equal(urls, 1);
        assert.equal(revokes, 1);
      } else {
        assert.equal(urls, 0);
        assert.equal(clicks, 0);
        assert.ok(signal?.aborted);
      }
    });
// Real more() and first-page effect share a query generation. Simulate transitions, not markup snapshots.
function mediaFunctions(bindings) {
  bindings.queryKey = JSON.stringify([
    bindings.filters,
    bindings.refresh,
    bindings.legacy,
  ]);
  bindings.queryKeyRef.current = bindings.queryKey;
  const text = read("../src/pages/Media/index.tsx"),
    source = ts.createSourceFile(
      "index.tsx",
      text,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX,
    );
  let more, effect;
  function visit(n) {
    if (ts.isFunctionDeclaration(n) && n.name?.text === "more") more = n;
    if (
      ts.isCallExpression(n) &&
      n.expression.getText(source) === "useEffect" &&
      n.arguments[1]?.getText(source) === "[filters, refresh, legacy]"
    )
      effect = n.arguments[0];
    ts.forEachChild(n, visit);
  }
  visit(source);
  const compiled = ts.transpile(
    `function harness(){const more=${more.getText(source)};const effect=${effect.getText(source)};return {more,effect};}`,
    { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
  );
  return new Function(
    "bindings",
    `const {${Object.keys(bindings).join(",")}}=bindings;${compiled};return harness();`,
  )(bindings);
}
for (const transition of ["filter", "reload", "view"])
  test(`stale pagination after ${transition} cannot overwrite new list/cursor`, async () => {
    const delayed = deferred();
    let items = [{ id: 1, status: "pending_review" }],
      cursor = 10,
      busy = false,
      loading = false;
    const state = {
        current: {
          controller: new AbortController(),
          generation: 1,
          key: "old",
        },
      },
      query = { current: state.current },
      queryKeyRef = { current: "" },
      filters = { status: "pending_review" },
      controller = { current: new AbortController() };
    let requests = 0;
    const listMedia = async (payload) => {
      requests++;
      if (payload.cursor) return delayed.promise;
      return { items: [{ id: 9, status: "approved" }], next_cursor: 90 };
    };
    const setItems = (value) => {
        items = typeof value === "function" ? value(items) : value;
      },
      setNext = (value) => {
        cursor = value;
      };
    const old = mediaFunctions({
      filters,
      refresh: 0,
      legacy: false,
      next: 10,
      controller,
      query,
      queryKeyRef,
      moreBusy: false,
      listMedia,
      setItems,
      setNext,
      setMoreBusy: (v) => (busy = v),
      setLoading: (v) => (loading = v),
      setError: () => {},
      isAbort: api.isAbort,
      mediaError: api.mediaError,
    });
    // Initialize the query generation, then start its delayed second page.
    const cleanup = old.effect();
    await tick();
    const pending = old.more();
    await tick();
    cleanup();
    const fresh = mediaFunctions({
      filters: transition === "filter" ? { status: "approved" } : filters,
      refresh: transition === "reload" ? 1 : 0,
      legacy: transition === "view",
      next: null,
      controller,
      query,
      queryKeyRef,
      moreBusy: false,
      listMedia,
      setItems,
      setNext,
      setMoreBusy: (v) => (busy = v),
      setLoading: (v) => (loading = v),
      setError: () => {},
      isAbort: api.isAbort,
      mediaError: api.mediaError,
    });
    const freshCleanup = fresh.effect();
    await tick();
    if (transition === "view") {
      freshCleanup();
      const back = mediaFunctions({
        filters,
        refresh: 0,
        legacy: false,
        next: null,
        controller,
        query,
        queryKeyRef,
        moreBusy: false,
        listMedia,
        setItems,
        setNext,
        setMoreBusy: (v) => (busy = v),
        setLoading: (v) => (loading = v),
        setError: () => {},
        isAbort: api.isAbort,
        mediaError: api.mediaError,
      });
      back.effect();
      await tick();
    }
    delayed.resolve({
      items: [{ id: 2, status: "pending_review" }],
      next_cursor: 20,
    });
    await pending;
    assert.deepEqual(items, [{ id: 9, status: "approved" }]);
    assert.equal(cursor, 90);
    assert.equal(busy, false);
    assert.equal(loading, false);
    assert.equal(requests, 3);
  });
const snapshot = {
  brand_id: 2,
  brand_version: 3,
  project: {
    id: 4,
    name: "Campaña original",
    description: "Original",
    archived: 0,
  },
  identity: {
    name: "Marca original",
    palette: { bg: "#ffffff" },
    typography: { titulos: "Manrope" },
    texts: { ig_post: { titulo: "Texto original" } },
    logo_style: "orbital",
    logo_seed: 7,
  },
  reference_logo: null,
};
const media = {
  id: 1,
  source: "codex",
  brief_id: 5,
  brand_id: 2,
  project_id: 4,
  brand_version: 3,
  snapshot_hash: "a".repeat(64),
  width: 512,
  height: 512,
};
const brief = {
  id: 5,
  brand_id: 2,
  project_id: 4,
  brand_version: 3,
  snapshot_hash: media.snapshot_hash,
  prompt: "Encargo original: conservar texto y logo",
  width: 512,
  height: 512,
  snapshot,
};
for (const condition of [
  "unchanged",
  "changed",
  "brief401",
  "reference404",
  "legacy-no-brief",
])
  test(`review evidence ${condition}: immutable prompt/snapshot and fail-closed readiness`, async () => {
    const official = new Blob(["official-alpha"], { type: "image/png" });
    const hash = Buffer.from(
      await crypto.subtle.digest("SHA-256", await official.arrayBuffer()),
    ).toString("hex");
    const original = structuredClone(brief);
    original.snapshot.reference_logo = {
      sha256: hash,
      url: `/api/v1/brands/2/reference-logo?sha256=${hash}`,
    };
    const current = structuredClone(original.snapshot);
    if (condition === "changed") {
      current.brand_version = 4;
      current.identity.name = "Marca nueva";
      current.reference_logo = {
        sha256: "b".repeat(64),
        url: "/api/v1/brands/2/reference-logo?sha256=" + "b".repeat(64),
      };
    }
    const paths = [];
    globalThis.fetch = async (path, options) => {
      paths.push(path);
      assert.equal(options.credentials, "include");
      assert.equal(options.cache, "no-store");
      if (path.includes("generation-briefs"))
        return json(original, condition === "brief401" ? 401 : 200);
      if (path.endsWith("/brief")) return json(current);
      return condition === "reference404"
        ? json({ detail: "missing" }, 404)
        : new Response(official);
    };
    const value =
      condition === "legacy-no-brief"
        ? { ...media, source: "legacy", brief_id: null }
        : media;
    if (["brief401", "reference404"].includes(condition)) {
      await assert.rejects(
        api.loadMediaReviewContext(value, new AbortController().signal),
      );
      return;
    }
    const context = await api.loadMediaReviewContext(
      value,
      new AbortController().signal,
    );
    if (condition === "legacy-no-brief") {
      assert.equal(context.ready, false);
      assert.equal(context.brief, null);
      assert.deepEqual(paths, []);
      return;
    }
    assert.equal(context.brief.prompt, brief.prompt);
    assert.equal(context.brief.snapshot.identity.name, "Marca original");
    assert.equal(context.brief.snapshot.brand_version, 3);
    assert.ok(paths.includes(original.snapshot.reference_logo.url));
    assert.equal(context.ready, condition !== "changed");
    api.releasePrivateUrl(context.logoUrl);
  });

// Hook/JSX harness renders the actual MediaDetail component and runs its effects.
// It verifies readiness/visible evidence without claiming native browser rendering.
const hookUrl =
  "data:text/javascript;base64," +
  Buffer.from(
    "export const useState=(...a)=>globalThis.qaHooks.useState(...a);export const useRef=(...a)=>globalThis.qaHooks.useRef(...a);export const useEffect=(...a)=>globalThis.qaHooks.useEffect(...a);",
  ).toString("base64");
const hooksUrl = jsUrl(
  read("../src/pages/Media/usePrivateOperation.ts").replace(
    /["']react["']/,
    JSON.stringify(hookUrl),
  ),
);
const visualUrl =
  "data:text/javascript;base64," +
  Buffer.from(
    "export function Button(){};export function Modal(){};export function PrivateImage(){};",
  ).toString("base64");
const mediaUrl = jsUrl(
  read("../src/api/media.ts").replace(
    /["']\.\/client["']/,
    JSON.stringify(clientUrl),
  ),
);
const detailSource = read("../src/pages/Media/MediaDetail.tsx")
  .replace(/["']react["']/, JSON.stringify(hookUrl))
  .replace(/["']\.\/usePrivateOperation["']/, JSON.stringify(hooksUrl))
  .replace(/["']\.\.\/\.\.\/api\/media["']/, JSON.stringify(mediaUrl))
  .replace(/["']\.\.\/\.\.\/api\/client["']/, JSON.stringify(clientUrl))
  .replace(/["']\.\.\/\.\.\/components["']/, JSON.stringify(visualUrl))
  .replace(/["']\.\/PrivateImage["']/, JSON.stringify(visualUrl));
const detailJs = ts
  .transpile(detailSource, {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ES2022,
    jsx: ts.JsxEmit.ReactJSX,
  })
  .replace(
    /"react\/jsx-runtime"/g,
    JSON.stringify(import.meta.resolve("react/jsx-runtime")),
  );
const { MediaDetail } = await import(
  "data:text/javascript;base64," + Buffer.from(detailJs).toString("base64")
);
function detailHarness() {
  const previous = globalThis.qaHooks,
    slots = [];
  let cursor = 0,
    dirty = true,
    tree,
    queued = [];
  globalThis.qaHooks = {
    useState(initial) {
      const idx = cursor++;
      if (!slots[idx])
        slots[idx] = {
          value: typeof initial === "function" ? initial() : initial,
        };
      return [
        slots[idx].value,
        (value) => {
          const next =
            typeof value === "function" ? value(slots[idx].value) : value;
          if (!Object.is(next, slots[idx].value)) {
            slots[idx].value = next;
            dirty = true;
          }
        },
      ];
    },
    useRef(initial) {
      const idx = cursor++;
      if (!slots[idx]) slots[idx] = { value: { current: initial } };
      return slots[idx].value;
    },
    useEffect(effect, deps) {
      const idx = cursor++;
      const slot = slots[idx] ?? (slots[idx] = {});
      if (!slot.deps || !deps.every((d, i) => Object.is(d, slot.deps[i]))) {
        queued.push(() => {
          slot.cleanup?.();
          slot.cleanup = effect();
          slot.deps = deps;
        });
      }
    },
  };
  function render() {
    cursor = 0;
    dirty = false;
    tree = MediaDetail({ id: 1, owner: true, onClose() {}, onReviewed() {} });
    const run = queued;
    queued = [];
    for (const effect of run) effect();
  }
  function nodes(node, result = []) {
    if (Array.isArray(node)) for (const n of node) nodes(n, result);
    else if (node && typeof node === "object" && node.props) {
      result.push(node);
      if (node.props.children !== undefined) nodes(node.props.children, result);
    }
    return result;
  }
  function text(node) {
    if (Array.isArray(node)) return node.map(text).join(" ");
    if (node && typeof node === "object" && node.props)
      return node.props.children === undefined ? "" : text(node.props.children);
    return typeof node === "string" || typeof node === "number"
      ? String(node)
      : "";
  }
  render();
  return {
    async settle() {
      for (let i = 0; i < 12; i++) {
        await tick();
        if (dirty) render();
      }
    },
    text: () => text(tree),
    nodes: () => nodes(tree),
    button(name) {
      return nodes(tree).find(
        (n) => n.type?.name === "Button" && text(n) === name,
      );
    },
    restore() {
      for (const slot of slots) slot.cleanup?.();
      if (previous === undefined) delete globalThis.qaHooks;
      else globalThis.qaHooks = previous;
    },
  };
}
for (const condition of [
  "loading",
  "unchanged",
  "changed",
  "brief401",
  "reference404",
])
  test(`MediaDetail ${condition}: actual review controls gated by immutable evidence`, async () => {
    const official = new Blob(["official-alpha"], { type: "image/png" }),
      sha = Buffer.from(
        await crypto.subtle.digest("SHA-256", await official.arrayBuffer()),
      ).toString("hex");
    const original = structuredClone(brief);
    original.snapshot.reference_logo = {
      sha256: sha,
      url: `/api/v1/brands/2/reference-logo?sha256=${sha}`,
    };
    const current = structuredClone(original.snapshot);
    if (condition === "changed") {
      current.brand_version = 4;
      current.identity.name = "Marca nueva";
      current.reference_logo = null;
    }
    const waiting = deferred();
    globalThis.fetch = async (path) => {
      if (path === "/api/v1/media/1")
        return json({
          ...media,
          status: "pending_review",
          reviews: [],
          download_url: "/api/v1/media/1/download",
          provenance: {},
        });
      if (path.includes("generation-briefs"))
        return condition === "loading"
          ? waiting.promise
          : json(original, condition === "brief401" ? 401 : 200);
      if (path.endsWith("/brief")) return json(current);
      return condition === "reference404"
        ? json({ detail: "missing" }, 404)
        : new Response(official);
    };
    const harness = detailHarness();
    try {
      await harness.settle();
      const button = harness.button("Aprobar");
      assert.ok(button);
      assert.equal(Boolean(button.props.disabled), condition !== "unchanged");
      assert.equal(
        Boolean(harness.button("Rechazar").props.disabled),
        condition !== "unchanged",
      );
      const images = harness
        .nodes()
        .filter(
          (n) =>
            n.type === "img" && n.props.alt === "Logo original del encargo",
        );
      if (condition === "unchanged" || condition === "changed") {
        assert.match(
          harness.text(),
          /Encargo original: conservar texto y logo/,
        );
        assert.match(harness.text(), /Marca original/);
        assert.doesNotMatch(harness.text(), /Marca nueva/);
        assert.equal(images.length, 1);
      } else {
        assert.equal(images.length, 0);
        assert.doesNotMatch(
          harness.text(),
          /Encargo original: conservar texto y logo/,
        );
      }
    } finally {
      harness.restore();
      waiting.resolve(json(original));
      await tick();
    }
  });
for (const fault of [
  "external-reference",
  "corrupt-reference",
  "brief-version",
])
  test(`${fault} fails before an approval context becomes ready`, async () => {
    const original = structuredClone(brief);
    const content = new Blob(["official-alpha"], { type: "image/png" }),
      sha = Buffer.from(
        await crypto.subtle.digest("SHA-256", await content.arrayBuffer()),
      ).toString("hex");
    original.snapshot.reference_logo = {
      sha256: sha,
      url: `/api/v1/brands/2/reference-logo?sha256=${sha}`,
    };
    if (fault === "external-reference")
      original.snapshot.reference_logo.url =
        "https://example.test/private-logo";
    if (fault === "brief-version") original.brand_version = 4;
    const paths = [];
    globalThis.fetch = async (path) => {
      paths.push(path);
      if (path.includes("generation-briefs")) return json(original);
      if (path.endsWith("/brief")) return json(original.snapshot);
      return new Response(
        fault === "corrupt-reference" ? new Blob(["corrupt"]) : content,
      );
    };
    await assert.rejects(
      api.loadMediaReviewContext(media, new AbortController().signal),
    );
    assert.ok(paths.every((path) => path.startsWith("/api/v1/")));
  });

// Closing a modal rotates the operation; unmount must cancel the replacement too.
test("private operation cleanup aborts the replacement after modal close", async () => {
  const previous = globalThis.qaHooks,
    ref = { current: null };
  let cleanup;
  globalThis.qaHooks = {
    useRef: () => ref,
    useEffect: (effect) => {
      cleanup = effect();
    },
  };
  try {
    const { usePrivateOperation } = await import(hooksUrl);
    const operation = usePrivateOperation();
    operation.current.abort();
    operation.current = new AbortController();
    const replacement = operation.current;
    cleanup();
    assert.equal(replacement.signal.aborted, true);
  } finally {
    if (previous === undefined) delete globalThis.qaHooks;
    else globalThis.qaHooks = previous;
  }
});
