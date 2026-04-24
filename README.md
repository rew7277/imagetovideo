# FreeCut Studio V7 Actual Railway Fix

This version fixes the issue shown in your latest Railway logs:

```text
ModuleNotFoundError: No module named 'sqlalchemy'
/app/backend/main.py
```

## What was wrong

Railway was not starting `app.py`. It was starting:

```text
backend/main.py
```

So this package includes both:

```text
app.py
backend/main.py
```

Both expose the FastAPI `app`.

## Fixes included

- `/opt/venv/bin/uvicorn` compatibility wrapper
- literal `${PORT:-8000}` handling
- Railway port `8082`
- `/health`
- `/ready`
- `backend.main:app`
- SQLAlchemy dependency added
- SQLite fallback database module

## Railway settings

Public Networking target port:

```text
8082
```

Healthcheck path:

```text
/health
```

If Railway has an old custom start command, change it to:

```bash
sh -c 'python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8082}'
```