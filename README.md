# FreeCut Studio V6 Port Final Fix

This version fixes the Railway error:

```text
Invalid value for '--port': '${PORT:-8000}' is not a valid integer.
```

## What changed

Railway is passing `${PORT:-8000}` as a literal string without shell expansion.
This Dockerfile creates a smart `/opt/venv/bin/uvicorn` wrapper that replaces the broken literal port with the real `$PORT`, or defaults to `8082`.

## Railway Networking

Your Railway public networking target port is:

```text
8082
```

This project defaults to `8082` and exposes `8082`.

## Deploy Steps

1. Extract this zip.
2. Push files directly to GitHub root.
3. Railway → redeploy.
4. Keep public networking target port as `8082`.
5. Healthcheck path: `/health`.

## If still failing

In Railway → Service → Settings → Start Command, remove any custom command.
If you must keep one, use:

```bash
sh -c 'python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8082}'
```