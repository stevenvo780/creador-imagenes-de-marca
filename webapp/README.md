# Eikon Web MVP

MVP local multi-tenant para disparar jobs Eikon desde una API FastAPI.

## Seguridad base

- Auth por cookie JWT `HttpOnly`, `SameSite=Lax`.
- Passwords con PBKDF2-HMAC-SHA256 y salt por usuario.
- SQLite local bajo `data/webapp/eikon.db` (git-ignored).
- Jobs invocan `python3 eikon.py ...` con lista de argumentos; nunca `shell=True`.
- Slugs/categorías se validan con allow-list regex para evitar path traversal.

## Instalar deps web

```bash
python3 -m pip install -r webapp/requirements-webapp.txt
```

## Arrancar

```bash
uvicorn webapp.app:app --reload --host 127.0.0.1 --port 8000
```

## Smoke

```bash
curl http://127.0.0.1:8000/health
```

Los assets generados siguen bajo `output/`; la base y logs web viven bajo `data/webapp/`.
