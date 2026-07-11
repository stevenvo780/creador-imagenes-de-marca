export const meta = {
  name: 'eikon-mega-finish',
  description: 'Mega-workflow: stabilize combinatorial foundation, build backend (DB/worker/storage/API), React SPA, tests+E2E, and 3 audit cycles — each phase verify+repair gated',
  phases: [
    { title: 'P1-Foundation', detail: 'Opus: make combinatorial render real distinct PNGs + bundle fonts + verify' },
    { title: 'P2-Backend', detail: 'Sonnet/MiniMax build DB+worker+storage+API; Opus integrates+verifies' },
    { title: 'P3-SPA', detail: 'Sonnet/MiniMax build Vite+React SPA (wizard/batch/gallery); Opus design+verify' },
    { title: 'P4-Tests-E2E', detail: 'MiniMax/Sonnet synthetic tests; Opus/Codex Playwright E2E + verify' },
    { title: 'P5-Audit', detail: 'Opus+Sonnet+MiniMax: 3 audit cycles (structural/UX/reliability) + fixes' },
  ],
}

const REPO = '/workspace/Pinakotheke/eikon'
const V = `${REPO}/.venv/bin`
const GOLD = '/tmp/claude-1000/-workspace-Pinakotheke-eikon/8cf59348-b16e-43b4-a77b-4b4b27f4106d/scratchpad/golden'

const INV = `Repo root: ${REPO}. cwd = repo root. Python tools: ${V}/python ${V}/ruff ${V}/mypy ${V}/pytest . Node: node/npm/pnpm available, npm registry reachable.
HARD INVARIANTS (verify by RUNNING; never just claim success):
- Existing taxonomy render must stay pixel-identical. Check: render kosmos+iris and compare DECODED-PIXEL sha256 to golden at ${GOLD}/<brand>.pix.json. A pre-existing asset changing = regression to fix.
- "Done" requires the artifact to actually WORK: code that renders must produce PNGs; an API must respond; a page must build. Prove it.
- Keep gates green: ${V}/ruff check . = 0 and ${V}/mypy eikon_core webapp = 0 and make test green.
- NEVER touch: marcas/prizma-pistis.json, marcas/prizma.json, templates/{ad_leaderboard,letterhead,stat_card}.html. Do NOT edit files outside your stated ownership.
- Spanish comments, English identifiers. Multi-tenant: every query scoped by tenant_id.
RENDER MODEL: templates read URL query params -> templates/eikon-runtime.js sets CSS custom props (--bg,--acento,--font-titulo,...) + data-* text; Playwright screenshots. eikon_core/orchestrator.py has async render_combination(...) and run_generator(...). eikon_core/combinatorial/{axes,planner,ranking}.py + config/axes.json drive variety. eikon_core/isotype.py makes procedural SVG marks. webapp/ is FastAPI (JWT cookie, SQLite, storage.py).`

const VERDICT = {
  type: 'object', additionalProperties: false,
  properties: {
    ok: { type: 'boolean' },
    summary: { type: 'string' },
    evidence: { type: 'string', description: 'commands run + their key output' },
    issues: { type: 'array', items: { type: 'object', additionalProperties: false,
      properties: { area: { type: 'string' }, problem: { type: 'string' }, hint: { type: 'string' } },
      required: ['area', 'problem', 'hint'] } },
  }, required: ['ok', 'summary', 'evidence', 'issues'],
}

async function verifyRepair(ph, verifyPrompt, fixContext, max = 2) {
  let v = await agent(verifyPrompt, { model: 'opus', label: `verify:${ph}`, phase: ph, schema: VERDICT })
  let t = 0
  while (v && !v.ok && t < max) {
    const issues = (v.issues || []).slice(0, 6)
    log(`${ph}: repair round ${t + 1} — ${issues.length} issues`)
    await parallel(issues.map((iss, i) => () => agent(
      `${INV}\n\nFIX THIS ISSUE (part of ${ph}). ${fixContext}\nArea: ${iss.area}\nProblem: ${iss.problem}\nHint: ${iss.hint}\nApply a real fix, then re-run the relevant check to confirm. Keep gates green. RETURN what you changed + the check result.`,
      { model: i % 2 ? 'sonnet' : 'opus', label: `fix:${ph}:${i}`, phase: ph })))
    v = await agent(verifyPrompt, { model: 'opus', label: `verify:${ph}#${t + 2}`, phase: ph, schema: VERDICT })
    t++
  }
  return v
}

// ---------------- P1: Foundation ----------------
phase('P1-Foundation')
const p1 = await agent(`${INV}

STABILIZE THE COMBINATORIAL FOUNDATION so it actually renders distinct logos end-to-end. Current state: planner/isotype modules exist and config/axes.json + render wiring (mapping/injection/orchestrator/eikon-system.css) exist, BUT: (a) scripts/eikon_combine_demo.py produces 0 PNGs (render_combination not yielding files), (b) planner emits DUPLICATE combinations (e.g. combos 9 and 11 identical), (c) fonts for typography_pairing are NOT bundled (templates/fonts/ missing), (d) 1 ruff error at scripts/demo_isotype.py:21.
YOU OWN: eikon_core/orchestrator.py (render_combination), eikon_core/combinatorial/*, eikon_core/isotype.py, eikon_core/svg_generator.py, eikon_core/mapping.py, eikon_core/injection.py, config/axes.json, config/typography.json, templates/eikon-system.css, templates/fonts/ (new), templates/{isotipo,logo_symbol_color,logo_symbol_mono,lockup_horizontal,lockup_vertical,wordmark}.html, scripts/eikon_combine_demo.py, scripts/demo_isotype.py.
DELIVER (prove each by running):
1. render_combination renders a Combination to a real PNG. Fix whatever breaks it.
2. planner produces N DISTINCT combinations (no duplicate param-sets); fix the dedup/sampling.
3. Bundle 2-3 open-source font families under templates/fonts/ (download via curl/npm if needed) + @font-face in eikon-system.css; wire typography_pairing to them; verify a non-brand pairing visibly changes the rendered font and stays deterministic.
4. scripts/eikon_combine_demo.py renders 12 logo combinations (palette_scheme×background_treatment×corner_shape) to output/_demo_core/ -> 12 PNGs with 12 DISTINCT decoded-pixel hashes, and re-running gives the SAME 12 hashes. Print all 12 hashes for both runs.
5. scripts/demo_isotype.py also RENDERS the 4 isotype styles to PNG (not just SVG) for kosmos+iris -> 8 distinct legible PNGs in output/_demo_isotype/.
6. Fix the ruff error; keep ${V}/ruff check . = 0 and ${V}/mypy eikon_core webapp = 0 and make test green; existing render still pixel-identical to golden.
RETURN: root-cause of the 0-PNG bug, the dedup fix, font bundling, and the 12-distinct+deterministic + 8-isotype proofs.`,
  { model: 'opus', label: 'foundation', phase: 'P1-Foundation' })

const p1v = await verifyRepair('P1-Foundation',
  `${INV}\n\nVERIFY the combinatorial foundation INDEPENDENTLY by running: (1) ${V}/python scripts/eikon_combine_demo.py and confirm output/_demo_core/ has 12 PNGs with 12 DISTINCT decoded-pixel sha256 (compute them yourself with PIL), and a second run gives identical hashes (deterministic). (2) ${V}/python scripts/demo_isotype.py and confirm 8 distinct isotype PNGs render. (3) ${V}/ruff check . == 0, ${V}/mypy eikon_core webapp == 0, make test green. (4) existing render unchanged: render kosmos+iris, compare decoded-pixel hashes to ${GOLD}/<brand>.pix.json -> all identical. Set ok=true ONLY if ALL hold. List concrete issues otherwise.`,
  'The combinatorial render path must produce 12 distinct deterministic logo PNGs and 8 isotype PNGs, fonts bundled, gates green, no render regression.')
log(`P1 verdict ok=${p1v?.ok}`)

// ---------------- P2: Backend ----------------
phase('P2-Backend')
const [db, worker, storage] = await parallel([
  () => agent(`${INV}

BUILD per-tenant brand data + seed. YOU OWN: webapp/storage.py (EXTEND, keep existing tenants/users/jobs/assets), new webapp/seed.py.
- Add tables + CRUD: brands(id,tenant_id,slug,name,palette_json,typography_json,logo_text,logo_symbol,texts_json,created_at), variations(id,batch_id,tenant_id,brand_id,axis_params_json,seed,score,output_path,wcag_json,layout_status,selected,created_at), batches(id,tenant_id,brand_id,spec_json,status,counts_json,created_at,...). All CRUD scoped by tenant_id. brand CRUD validates ownership.
- webapp/seed.py: idempotent seed converting marcas/*.json into brands rows for an 'owner' tenant (create the tenant if missing). Provide a function + CLI.
ACCEPTANCE: pytest in webapp/tests covering brand CRUD + tenant isolation passes; ${V}/ruff check webapp =0; ${V}/mypy webapp =0. RETURN changes + test results.`,
    { model: 'sonnet', label: 'db+brands+seed', phase: 'P2-Backend' }),
  () => agent(`${INV}

BUILD the async in-process job worker + SSE. YOU OWN: new webapp/jobs/__init__.py, webapp/jobs/worker.py. Do NOT edit webapp/app.py (the API agent wires endpoints later; just expose clean functions).
- A job queue backed by the SQLite jobs/batches tables: enqueue a batch (brand + CombinationSpec + count), a worker coroutine that pulls queued batches and renders each combination via eikon_core.orchestrator.render_combination into a tenant-scoped dir, updating progress, ranking via eikon_core.combinatorial.ranking, persisting variations rows. Respect max_concurrent_jobs; cancellation; atomic status transitions (reuse storage.update_job_status pattern).
- Expose: start_worker(), enqueue_batch(...), and an async generator job_events(batch_id) yielding SSE-friendly progress dicts.
ACCEPTANCE: a pytest spins a batch of 3 combinations through the worker (headless render) and asserts 3 variation rows + status completed; ${V}/ruff check webapp =0; ${V}/mypy webapp =0. RETURN design + test result.`,
    { model: 'sonnet', label: 'worker+sse', phase: 'P2-Backend' }),
  () => agent(`${INV}

BUILD the storage abstraction (folder now, GCS later). YOU OWN: new webapp/storage_backend/__init__.py, base.py, local.py, gcs.py.
- base.py: StorageBackend Protocol (save(tenant_id, key, bytes)->url, open(tenant_id,key)->bytes, url_for(tenant_id,key), list(tenant_id, prefix), zip_many(tenant_id, keys)->bytes).
- local.py: LocalStorage writing under output/tenants/<tenant_id>/... ; path-traversal safe (reuse safe_relative_path idea).
- gcs.py: a stub raising NotImplementedError with the same interface (documented for later).
ACCEPTANCE: pytest covering save/open/list/zip + traversal rejection passes; ${V}/ruff check webapp =0; ${V}/mypy webapp =0. RETURN interface + test result.`,
    { model: 'minimax', label: 'storage-backend', phase: 'P2-Backend' }),
])

const api = await agent(`${INV}

WIRE THE JSON API on top of the DB (webapp/storage.py brands/variations/batches), worker (webapp/jobs), storage (webapp/storage_backend), and the combinatorial engine. YOU OWN: webapp/app.py (refactor to JSON API; keep existing auth/JWT cookie + health), new webapp/api/ routers (auth, brands, wizard, batches, gallery, downloads). Reports from the parallel builders:
DB: <<<${typeof db === 'string' ? db.slice(0, 700) : ''}>>>
WORKER: <<<${typeof worker === 'string' ? worker.slice(0, 700) : ''}>>>
STORAGE: <<<${typeof storage === 'string' ? storage.slice(0, 700) : ''}>>>
ENDPOINTS (all tenant-scoped via the JWT cookie user):
- brands: GET/POST/GET{id}/PUT{id}/DELETE{id}
- wizard: GET /api/v1/wizard/axes -> the catalog from config/axes.json (axes + options + labels) so the SPA can render the step-by-step picker; GET /api/v1/wizard/brands.
- batches: POST /api/v1/batches {brand_id, asset_types, fixed, permuted, count} -> enqueue via worker, return batch_id; GET /api/v1/batches/{id} status+counts; GET /api/v1/batches/{id}/events -> SSE progress; GET /api/v1/batches/{id}/variations -> ranked variations.
- gallery: GET /api/v1/gallery?brand_id=.. list variations (filters, ordering); POST select/unselect.
- downloads: GET /api/v1/variations/{id}/file (single), POST /api/v1/downloads/zip {variation_ids} -> ZIP via storage_backend.zip_many.
Keep CORS-free same-origin; serve the SPA build later from StaticFiles (leave a mount for frontend/dist).
ACCEPTANCE: pytest API tests (use httpx/TestClient): register->login->create brand->create small batch(count=2)->poll status->list variations->download zip; tenant isolation (user B cannot see A's brand). ${V}/ruff check . =0; ${V}/mypy eikon_core webapp =0; make test green. RETURN endpoint list + test results.`,
  { model: 'opus', label: 'api-integration', phase: 'P2-Backend' })

const p2v = await verifyRepair('P2-Backend',
  `${INV}\n\nVERIFY the backend INDEPENDENTLY: run the webapp test suite (${V}/pytest -q webapp/tests and make test-webapp) and confirm: brand CRUD + tenant isolation, a batch of count=2 actually renders 2 variation PNGs through the worker and persists rows, gallery lists them, zip download returns bytes. Also ${V}/ruff check . ==0, ${V}/mypy eikon_core webapp ==0. Spin the app with TestClient and hit /api/v1/wizard/axes -> returns the axes catalog. Set ok=true only if the batch genuinely produced rendered variation files. List issues otherwise.`,
  'The backend must: per-tenant brands, a working SSE batch worker that renders variations, gallery, zip download, tenant isolation, gates green.')
log(`P2 verdict ok=${p2v?.ok}`)

// ---------------- P3: SPA ----------------
phase('P3-SPA')
const scaffold = await agent(`${INV}

SCAFFOLD the React SPA (Vite + React + TypeScript) that talks to the same-origin JSON API and is served by FastAPI from frontend/dist. YOU OWN: frontend/ (new): package.json, vite.config.ts (build to frontend/dist; base '/'; dev proxy to FastAPI), tsconfig, src/main.tsx, src/api/client.ts (typed fetch wrapper using the cookie session; endpoints from webapp/api), src/auth (login/register + session hook), src/App.tsx with routing + a minimal accessible design system (tokens, AA contrast, focus states). Read webapp/api routers to match the contract. Run npm install + npm run build and confirm frontend/dist is produced. Add a StaticFiles mount in webapp/app.py for frontend/dist ONLY IF not already present (coordinate: if present, leave it).
ACCEPTANCE: npm run build succeeds; frontend/dist exists; the app serves index.html at / via FastAPI. RETURN structure + build output.`,
  { model: 'sonnet', label: 'spa-scaffold', phase: 'P3-SPA' })

const [wizardPage, galleryPage] = await parallel([
  () => agent(`${INV}\n\nBUILD the step-by-step WIZARD page of the SPA (React+TS). Scaffold report: <<<${typeof scaffold === 'string' ? scaffold.slice(0, 800) : ''}>>>. YOU OWN: frontend/src/pages/Wizard/* and its components only.
Flow: pick brand (or create one: name/palette/fonts/text) -> step through axes from GET /api/v1/wizard/axes (choose which to FIX vs PERMUTE, pick options, live preview if feasible) -> choose count ("genera N", e.g. 20/50) -> POST /api/v1/batches -> navigate to batch progress (SSE). Accessible (keyboard, labels, AA contrast), clear cognitive flow (don't overload each step). Use the api client. RETURN components + how it calls the API.`,
    { model: 'sonnet', label: 'spa-wizard', phase: 'P3-SPA' }),
  () => agent(`${INV}\n\nBUILD the BATCH-PROGRESS + GALLERY + DOWNLOAD pages of the SPA (React+TS). Scaffold report: <<<${typeof scaffold === 'string' ? scaffold.slice(0, 800) : ''}>>>. YOU OWN: frontend/src/pages/Batch/*, frontend/src/pages/Gallery/* only.
- Batch progress: subscribe to GET /api/v1/batches/{id}/events (SSE), show live progress, then the ranked variations grid.
- Gallery: ordered grid of variations (filter by brand, sort by score), multi-select, single download + "download selected as ZIP" (POST /api/v1/downloads/zip). Accessible, AA contrast, responsive. RETURN components + API usage.`,
    { model: 'minimax', label: 'spa-gallery', phase: 'P3-SPA' }),
])

const p3v = await verifyRepair('P3-SPA',
  `${INV}\n\nVERIFY the SPA INDEPENDENTLY: run npm install (if needed) + npm run build in frontend/ and confirm a clean build (no TS errors) producing frontend/dist. Confirm FastAPI serves index.html at / and static assets. Confirm the wizard + gallery + batch pages exist and import the api client with endpoints matching webapp/api. (Do NOT require a full browser run here.) Set ok=true only if npm run build succeeds and the app serves the SPA. List build/type errors otherwise.`,
  'The React SPA (frontend/) must build cleanly with Vite+TS and be served same-origin by FastAPI, with wizard + batch + gallery pages wired to the JSON API.', 3)
log(`P3 verdict ok=${p3v?.ok}`)

// ---------------- P4: Tests + E2E ----------------
phase('P4-Tests-E2E')
const [synth, e2e] = await parallel([
  () => agent(`${INV}\n\nADD SYNTHETIC pytest coverage for the new backend + combinatorial surfaces (raise coverage toward 70%). YOU OWN: new/extended tests under tests/ and webapp/tests/ (do not weaken existing). Cover: axes/planner/ranking determinism, render_combination produces a file, brands CRUD + tenant isolation, worker batch lifecycle, storage backend, API endpoints (wizard/batches/gallery/downloads), zip. Use TestClient + tmp dirs; keep tests deterministic (small counts). ACCEPTANCE: ${V}/pytest -q green; ${V}/ruff check . =0; ${V}/mypy eikon_core webapp =0. RETURN tests added + coverage delta.`,
    { model: 'sonnet', label: 'synthetic-tests', phase: 'P4-Tests-E2E' }),
  () => agent(`${INV}\n\nBUILD an END-TO-END Playwright test of the full product flow. YOU OWN: new e2e/ (Playwright Python using ${V}/python -m playwright; or pytest-playwright) + a script to launch uvicorn on a test port serving the built SPA. Flow: start server -> register -> login -> create a brand -> run the wizard to generate a small batch (count=3) -> wait for completion -> open gallery -> select -> download zip -> assert the zip has 3 PNGs. Make it runnable headless and reasonably fast. ACCEPTANCE: the E2E run passes end-to-end (paste the run output). RETURN the E2E design + result.`,
    { model: 'codex', label: 'e2e-playwright', phase: 'P4-Tests-E2E' }),
])

const p4v = await verifyRepair('P4-Tests-E2E',
  `${INV}\n\nVERIFY tests+E2E INDEPENDENTLY: run ${V}/pytest -q (all) and confirm green; run the E2E flow and confirm it passes end-to-end (server boots, register->login->brand->wizard->batch count=3->gallery->zip with 3 PNGs). ${V}/ruff check . ==0, ${V}/mypy eikon_core webapp ==0. Set ok=true only if BOTH the full pytest suite AND the E2E pass. List failures with the exact error otherwise.`,
  'Full pytest suite green + a passing Playwright E2E of register->brand->wizard->generate->gallery->zip.', 3)
log(`P4 verdict ok=${p4v?.ok}`)

// ---------------- P5: 3 Audit cycles ----------------
phase('P5-Audit')
const lenses = [
  { key: 'structural', model: 'opus', focus: 'arquitectura, acoplamiento, cohesión de módulos, deuda, límites de responsabilidad, duplicación, manejo de errores, seguridad multi-tenant (aislamiento por tenant_id), JWT/paths.' },
  { key: 'ux', model: 'sonnet', focus: '¿es USABLE el wizard? ¿tiene sentido visual? ¿la combinatoria da variedad real o ruido? CONTRASTE WCAG AA en la UI y en assets generados; ¿suma o resta carga cognitiva?; accesibilidad (teclado, foco, labels).' },
  { key: 'reliability', model: 'minimax', focus: 'cobertura/edge-cases, determinismo de render, fallos del worker/SSE bajo carga, cancelación, integridad de descargas/zip, aislamiento multi-tenant adversarial (user A no ve nada de B), validación de inputs.' },
]
const audits = await parallel(lenses.map((L) => () => agent(
  `${INV}\n\nAUDIT CYCLE — lente ${L.key.toUpperCase()}. Eres auditor adversarial; sigue audit/METHODOLOGY.md (severidades critical/major/minor/note, evidencia + remediación). Examina TODO lo construido (eikon_core/combinatorial, isotype, webapp API/worker/storage, frontend/) con foco en: ${L.focus}\nEjecuta comandos para EVIDENCIAR (gates, tests, render, contraste). Devuelve hallazgos con severidad + evidencia + remediación concreta. NO arregles aquí; solo audita con rigor.`,
  { model: L.model, label: `audit:${L.key}`, phase: 'P5-Audit', schema: VERDICT })))

// Fix critical/major findings across the three lenses, then re-verify the whole product
const allIssues = audits.filter(Boolean).flatMap((a) => (a.issues || []).map((i) => ({ ...i, ok: a.ok })))
log(`P5 audits done; ${allIssues.length} findings`)
if (allIssues.length) {
  await parallel(allIssues.slice(0, 10).map((iss, i) => () => agent(
    `${INV}\n\nREMEDIATE an audit finding (verifiable fix). Area: ${iss.area}\nProblem: ${iss.problem}\nRemediation hint: ${iss.hint}\nApply the fix, re-run the relevant check, keep all gates + tests green. RETURN change + verification.`,
    { model: i % 3 === 0 ? 'opus' : i % 3 === 1 ? 'sonnet' : 'minimax', label: `audit-fix:${i}`, phase: 'P5-Audit' })))
}

const final = await agent(`${INV}\n\nFINAL CLOSEOUT VERIFICATION after audit remediations. Run the FULL battery and report honestly: ${V}/ruff check . ; ${V}/mypy eikon_core webapp ; ${V}/pytest -q ; the E2E flow ; the combinatorial demos (12 distinct + 8 isotypes) ; existing render vs golden ; npm run build in frontend/. Write an audit report to audit/reports/2026-06-29-mega-finish.md (scope, evidence per gate, remaining findings by severity, sign-off). Set ok=true only if there are no open critical/major findings. List anything still open.`,
  { model: 'opus', label: 'final-closeout', phase: 'P5-Audit', schema: VERDICT })

return { p1: p1v, p2: p2v, p3: p3v, p4: p4v, audits, final }
