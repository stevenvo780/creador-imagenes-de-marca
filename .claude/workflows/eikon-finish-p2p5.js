export const meta = {
  name: 'eikon-finish-p2p5',
  description: 'Build backend (worker/storage/API on committed DB), React SPA, tests+E2E, 3 audit cycles — verify+repair gated, 5-provider distributed',
  phases: [
    { title: 'P2-Backend', detail: 'MiniMax/Gemini/OpenCode build worker+storage+DB-CRUD; Opus integrates API; Opus verify' },
    { title: 'P3-SPA', detail: 'Sonnet scaffold; Gemini wizard; MiniMax gallery; Opus design+verify' },
    { title: 'P4-Tests-E2E', detail: 'MiniMax/OpenCode synthetic tests; Codex E2E; Opus verify' },
    { title: 'P5-Audit', detail: 'Opus/Gemini/MiniMax 3 audit lenses + distributed fixes + Opus closeout' },
  ],
}

const REPO = '/workspace/Pinakotheke/eikon'
const V = `${REPO}/.venv/bin`

const INV = `Repo root: ${REPO}. cwd = repo root. Python tools: ${V}/python ${V}/ruff ${V}/mypy ${V}/pytest . Node: node/npm/pnpm available, registry reachable.
FOUNDATION ALREADY DONE & COMMITTED (build ON it, don't rebuild): eikon_core/combinatorial/{axes,planner,ranking}.py + config/axes.json + config/typography.json drive variety; eikon_core/orchestrator.py has async render_combination(browser, marca_slug, combination, asset_type, marca, axes_config, ...) which renders a Combination to a PNG (12 distinct deterministic combos proven). eikon_core/isotype.py makes procedural SVG marks. webapp/storage.py ALREADY has SQLite tables+CRUD for tenants/users/jobs/assets AND scaffolding for brands/variations/batches; webapp/seed.py seeds marcas/*.json into an owner tenant. webapp/ is FastAPI (JWT httpOnly cookie auth in webapp/security.py + webapp/app.py).
HARD INVARIANTS (verify by RUNNING; never just claim success):
- Existing render must stay pixel-identical: run \`${V}/python scripts/eikon_render_guard.py\` -> prints OK for both brands (exit 0). Fix any regression.
- "Done" requires the artifact to WORK: an API must respond (TestClient), a batch must produce rendered PNG files, a page must build. Prove it with commands.
- Keep gates green: \`${V}/ruff check .\` = 0, \`${V}/mypy eikon_core webapp\` = 0, \`${V}/pytest -q\` green.
- NEVER touch: marcas/prizma-pistis.json, marcas/prizma.json, templates/{ad_leaderboard,letterhead,stat_card}.html, .claude/. Edit only files in YOUR stated ownership.
- Spanish comments, English identifiers. Multi-tenant: every query scoped by tenant_id; user A must never see B's data.`

const VERDICT = {
  type: 'object', additionalProperties: false,
  properties: {
    ok: { type: 'boolean' }, summary: { type: 'string' }, evidence: { type: 'string' },
    issues: { type: 'array', items: { type: 'object', additionalProperties: false,
      properties: { area: { type: 'string' }, problem: { type: 'string' }, hint: { type: 'string' } },
      required: ['area', 'problem', 'hint'] } },
  }, required: ['ok', 'summary', 'evidence', 'issues'],
}
const FIXMODELS = [{ model: 'opus' }, { agentType: 'minimax' }, { agentType: 'opencode' }, { model: 'sonnet' }]
async function verifyRepair(ph, verifyPrompt, fixContext, max = 2) {
  let v = await agent(verifyPrompt, { model: 'opus', label: `verify:${ph}`, phase: ph, schema: VERDICT })
  let t = 0
  while (v && !v.ok && t < max) {
    const issues = (v.issues || []).slice(0, 6)
    log(`${ph}: repair ${t + 1} — ${issues.length} issues`)
    await parallel(issues.map((iss, i) => () => agent(
      `${INV}\n\nFIX THIS (${ph}). ${fixContext}\nArea: ${iss.area}\nProblem: ${iss.problem}\nHint: ${iss.hint}\nApply a real fix, re-run the relevant check, keep gates green. RETURN change + check output.`,
      { ...FIXMODELS[i % FIXMODELS.length], label: `fix:${ph}:${i}`, phase: ph })))
    v = await agent(verifyPrompt, { model: 'opus', label: `verify:${ph}#${t + 2}`, phase: ph, schema: VERDICT })
    t++
  }
  return v
}

// ---------- P2 Backend ----------
phase('P2-Backend')
const [dbc, worker, storage] = await parallel([
  () => agent(`${INV}\n\nCOMPLETE per-tenant brand/variation/batch DATA + CRUD. YOU OWN: webapp/storage.py (extend; keep existing), webapp/seed.py. Read what's there first. Ensure: brands CRUD (create/get/list/update/delete) scoped+ownership-checked by tenant_id; variations rows (batch_id,tenant_id,brand_id,axis_params_json,seed,score,output_path,wcag_json,layout_status,selected); batches rows (tenant_id,brand_id,spec_json,status,counts_json). Idempotent seed of marcas/*.json -> owner tenant. ACCEPTANCE: ${V}/pytest -q webapp/tests green incl. tenant isolation; ${V}/ruff check webapp =0; ${V}/mypy webapp =0. RETURN API + test results.`,
    { agentType: 'minimax', label: 'db-crud', phase: 'P2-Backend' }),
  () => agent(`${INV}\n\nBUILD async in-process job worker + SSE. YOU OWN: new webapp/jobs/__init__.py, webapp/jobs/worker.py (do NOT edit webapp/app.py). enqueue_batch(tenant_id, brand, CombinationSpec, count) persists a batch + queued; an async worker pulls queued batches, renders each combination via eikon_core.orchestrator.render_combination into a tenant-scoped dir, ranks via eikon_core.combinatorial.ranking, writes variation rows + progress; max_concurrent_jobs; cancellation; atomic status. Expose job_events(batch_id) async-gen for SSE. ACCEPTANCE: a pytest drives a count=3 batch through the worker (headless) -> 3 variation rows + 3 PNG files + status completed; ${V}/ruff check webapp =0; ${V}/mypy webapp =0. RETURN design + test result.`,
    { agentType: 'opencode', label: 'worker+sse', phase: 'P2-Backend' }),
  () => agent(`${INV}\n\nBUILD storage abstraction (folder now, GCS later). YOU OWN: new webapp/storage_backend/{__init__,base,local,gcs}.py. base: StorageBackend Protocol (save/open/url_for/list/zip_many). local: LocalStorage under output/tenants/<tenant_id>/..., path-traversal safe. gcs: documented NotImplementedError stub. ACCEPTANCE: pytest save/open/list/zip + traversal-reject green; ${V}/ruff check webapp =0; ${V}/mypy webapp =0. RETURN interface + test result.`,
    { agentType: 'gemini', label: 'storage-backend', phase: 'P2-Backend' }),
])
const api = await agent(`${INV}\n\nWIRE THE JSON API. YOU OWN: webapp/app.py (refactor to JSON API; KEEP auth/JWT cookie + health), new webapp/api/ routers. Builders' reports: DB<<<${(dbc || '').slice(0, 600)}>>> WORKER<<<${(worker || '').slice(0, 600)}>>> STORAGE<<<${(storage || '').slice(0, 600)}>>>.
Endpoints (tenant-scoped via cookie user): brands GET/POST/GET{id}/PUT{id}/DELETE{id}; wizard GET /api/v1/wizard/axes (catalog from config/axes.json: axes+options+labels) + GET /api/v1/wizard/brands; batches POST /api/v1/batches {brand_id,asset_types,fixed,permuted,count}->enqueue, GET {id} status, GET {id}/events SSE, GET {id}/variations ranked; gallery GET /api/v1/gallery?brand_id list + POST select; downloads GET /api/v1/variations/{id}/file + POST /api/v1/downloads/zip {ids}->zip via storage_backend. Same-origin; add a StaticFiles mount for frontend/dist (for the SPA later).
ACCEPTANCE: pytest API tests (TestClient): register->login->create brand->POST batch count=2->poll->list variations(2 rendered)->zip; tenant isolation (B can't see A). ${V}/ruff check . =0; ${V}/mypy eikon_core webapp =0; ${V}/pytest -q green. RETURN endpoints + results.`,
  { model: 'opus', label: 'api-integration', phase: 'P2-Backend' })
const p2v = await verifyRepair('P2-Backend',
  `${INV}\n\nVERIFY backend INDEPENDENTLY: run ${V}/pytest -q (all) green; spin app with TestClient, register->login->create brand->POST /api/v1/batches count=2->poll status->GET variations and confirm 2 ACTUAL PNG files were rendered on disk->POST downloads/zip returns a zip with 2 PNGs; confirm GET /api/v1/wizard/axes returns the catalog; confirm tenant isolation (2nd user can't GET 1st user's brand -> 403/404). ${V}/ruff check . ==0, ${V}/mypy eikon_core webapp ==0, scripts/eikon_render_guard.py OK. ok=true only if the batch genuinely rendered files. List issues otherwise.`,
  'Backend: per-tenant brands CRUD, SSE batch worker that renders real variation PNGs, gallery, zip, tenant isolation, gates green.')
log(`P2 ok=${p2v?.ok}`)

// ---------- P3 SPA ----------
phase('P3-SPA')
const scaffold = await agent(`${INV}\n\nSCAFFOLD the React SPA (Vite+React+TypeScript) served same-origin by FastAPI from frontend/dist. YOU OWN: frontend/ (new): package.json, vite.config.ts (build->frontend/dist, base '/', dev proxy to FastAPI), tsconfig, src/main.tsx, src/api/client.ts (typed fetch using cookie session; read webapp/api routers for the contract), src/auth (login/register + session hook), src/App.tsx (routing + minimal ACCESSIBLE design system: tokens, AA contrast, focus states). Run npm install + npm run build; confirm frontend/dist built and FastAPI serves index.html at /. ACCEPTANCE: npm run build succeeds (no TS errors); frontend/dist exists. RETURN structure + build output.`,
  { model: 'sonnet', label: 'spa-scaffold', phase: 'P3-SPA' })
const [wiz, gal] = await parallel([
  () => agent(`${INV}\n\nBUILD the step-by-step WIZARD page (React+TS). Scaffold:<<<${(scaffold || '').slice(0, 700)}>>>. YOU OWN: frontend/src/pages/Wizard/* only. Flow: pick/create brand -> step through axes from GET /api/v1/wizard/axes (choose FIX vs PERMUTE per axis, pick options) -> choose count ("genera N": 20/50) -> POST /api/v1/batches -> go to batch progress. Accessible (keyboard/labels/AA), low cognitive load per step, uses the api client. RETURN components + API calls.`,
    { agentType: 'gemini', label: 'spa-wizard', phase: 'P3-SPA' }),
  () => agent(`${INV}\n\nBUILD BATCH-PROGRESS + GALLERY + DOWNLOAD pages (React+TS). Scaffold:<<<${(scaffold || '').slice(0, 700)}>>>. YOU OWN: frontend/src/pages/Batch/*, frontend/src/pages/Gallery/* only. Batch: subscribe GET /api/v1/batches/{id}/events (SSE), show live progress then ranked grid. Gallery: ordered grid (filter by brand, sort by score), multi-select, single download + "download selected as ZIP" (POST /api/v1/downloads/zip). Accessible, AA, responsive. RETURN components + API usage.`,
    { agentType: 'minimax', label: 'spa-gallery', phase: 'P3-SPA' }),
])
const p3v = await verifyRepair('P3-SPA',
  `${INV}\n\nVERIFY SPA INDEPENDENTLY: cd frontend && npm install (if needed) && npm run build -> must succeed with NO TS errors, producing frontend/dist. Confirm FastAPI serves index.html at / and static assets. Confirm Wizard + Batch + Gallery pages exist and import the api client with endpoints matching webapp/api. ok=true only if npm run build succeeds and app serves the SPA. List build/type errors otherwise.`,
  'React SPA (frontend/) must build cleanly (Vite+TS) and be served same-origin by FastAPI, with wizard+batch+gallery wired to the API.', 3)
log(`P3 ok=${p3v?.ok}`)

// ---------- P4 Tests + E2E ----------
phase('P4-Tests-E2E')
const [synth, e2e] = await parallel([
  () => agent(`${INV}\n\nADD SYNTHETIC pytest coverage for new backend+combinatorial surfaces (push coverage up). YOU OWN: new/extended tests under tests/ and webapp/tests/ (don't weaken existing). Cover: axes/planner/ranking determinism, render_combination produces a file, brands CRUD+isolation, worker batch lifecycle, storage backend, API endpoints, zip. TestClient + tmp dirs, deterministic small counts. ACCEPTANCE: ${V}/pytest -q green; ${V}/ruff check . =0; ${V}/mypy eikon_core webapp =0. RETURN tests + coverage delta.`,
    { agentType: 'minimax', label: 'synthetic-tests', phase: 'P4-Tests-E2E' }),
  () => agent(`${INV}\n\nBUILD an END-TO-END Playwright test of the full flow. YOU OWN: new e2e/ (pytest-playwright or playwright python via ${V}/python -m playwright) + a launcher that runs uvicorn on a test port serving the built SPA. Flow: start server -> register -> login -> create brand -> wizard generate small batch (count=3) -> wait completion -> gallery -> select -> download zip -> assert zip has 3 PNGs. Headless, reasonably fast. ACCEPTANCE: the E2E run passes end-to-end (paste output). RETURN design + result.`,
    { agentType: 'codex', label: 'e2e-playwright', phase: 'P4-Tests-E2E' }),
])
const p4v = await verifyRepair('P4-Tests-E2E',
  `${INV}\n\nVERIFY tests+E2E INDEPENDENTLY: ${V}/pytest -q (all) green; run the E2E and confirm it passes end-to-end (server boots, register->login->brand->wizard->batch count=3->gallery->zip with 3 PNGs). ${V}/ruff check . ==0, ${V}/mypy eikon_core webapp ==0, scripts/eikon_render_guard.py OK. ok=true only if BOTH full pytest AND E2E pass. List exact failures otherwise.`,
  'Full pytest green + passing Playwright E2E (register->brand->wizard->generate->gallery->zip).', 3)
log(`P4 ok=${p4v?.ok}`)

// ---------- P5 Audit x3 ----------
phase('P5-Audit')
const lenses = [
  { key: 'structural', m: { model: 'opus' }, focus: 'arquitectura, acoplamiento, cohesión, deuda, duplicación, manejo de errores, seguridad multi-tenant (aislamiento por tenant_id), JWT/paths.' },
  { key: 'ux', m: { agentType: 'gemini' }, focus: 'usabilidad del wizard, sentido visual, variedad real vs ruido de la combinatoria, CONTRASTE WCAG AA (UI + assets), carga cognitiva, accesibilidad (teclado/foco/labels).' },
  { key: 'reliability', m: { agentType: 'minimax' }, focus: 'cobertura/edge-cases, determinismo de render, fallos worker/SSE, cancelación, integridad de zip, aislamiento multi-tenant adversarial, validación de inputs.' },
]
const audits = await parallel(lenses.map((L) => () => agent(
  `${INV}\n\nAUDIT CYCLE — lente ${L.key.toUpperCase()}. Auditor adversarial siguiendo audit/METHODOLOGY.md (severidades critical/major/minor/note + evidencia + remediación). Examina TODO (eikon_core/combinatorial, isotype, webapp API/worker/storage, frontend/) con foco: ${L.focus}\nEjecuta comandos para EVIDENCIAR. Devuelve hallazgos con severidad+evidencia+remediación. NO arregles; solo audita.`,
  { ...L.m, label: `audit:${L.key}`, phase: 'P5-Audit', schema: VERDICT })))
const findings = audits.filter(Boolean).flatMap((a) => a.issues || [])
log(`P5 audits: ${findings.length} findings`)
if (findings.length) {
  await parallel(findings.slice(0, 12).map((iss, i) => () => agent(
    `${INV}\n\nREMEDIATE an audit finding (verifiable). Area: ${iss.area}\nProblem: ${iss.problem}\nHint: ${iss.hint}\nApply fix, re-run the relevant check, keep all gates+tests green. RETURN change + verification.`,
    { ...FIXMODELS[i % FIXMODELS.length], label: `audit-fix:${i}`, phase: 'P5-Audit' })))
}
const final = await agent(`${INV}\n\nFINAL CLOSEOUT after remediations. Run the FULL battery, report honestly: ${V}/ruff check . ; ${V}/mypy eikon_core webapp ; ${V}/pytest -q ; the E2E ; scripts/eikon_render_guard.py ; cd frontend && npm run build. Write audit/reports/2026-06-29-mega-finish.md (scope, evidence per gate, remaining findings by severity, sign-off). ok=true only if no open critical/major. List anything still open.`,
  { model: 'opus', label: 'final-closeout', phase: 'P5-Audit', schema: VERDICT })

return { p2: p2v, p3: p3v, p4: p4v, audits, final }
