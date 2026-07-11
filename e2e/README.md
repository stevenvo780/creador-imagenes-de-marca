# Eikon E2E Playwright Suite

This suite starts a real uvicorn subprocess on `127.0.0.1:8765`, injects a clean temporary SQLite database, and drives the API through same-origin browser `fetch` calls from a headless Playwright page.

## Requirements

```bash
python3 -m pip install pytest pytest-asyncio pytest-playwright playwright fastapi "uvicorn[standard]" httpx
python3 -m playwright install chromium
```

`pytest-playwright` is compatible with the suite, but the local `page` fixture also launches Playwright directly so the tests remain runnable in minimal Python environments.

## Run

```bash
python3 -m pytest -v e2e/test_full_flow.py::test_end_to_end_full_flow
```

Optional port override:

```bash
EIKON_E2E_PORT=8766 python3 -m pytest -v e2e/test_full_flow.py::test_end_to_end_full_flow
```

## Coverage

The single flow covers registration, login, `/auth/me`, wizard catalogs, brand creation, same-tenant brand isolation, cross-tenant isolation, batch rendering, gallery listing, and `POST /api/v1/downloads/batch/{batch_id}` ZIP validation. The ZIP is opened with Python `zipfile` before PNG count, PNG signature, and size assertions are made.

Failure screenshots are written to `/tmp/eikon-e2e-screenshots`.
