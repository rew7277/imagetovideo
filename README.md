# FreeCut Studio V5 Railway Final Fix

This build fixes the Railway error:

```text
The executable `/opt/venv/bin/uvicorn` could not be found.
```

## Why this works

Railway is forcing this command:

```bash
/opt/venv/bin/uvicorn
```

So this Dockerfile creates that executable as a wrapper:

```bash
/opt/venv/bin/uvicorn -> python -m uvicorn
```

## Deploy Steps

1. Extract this zip.
2. Push all files to GitHub repository root.
3. Railway → New Project → Deploy from GitHub.
4. In Railway service settings, remove any old custom start command if present.
5. Redeploy.

## Healthcheck

```text
/health
```

## Features

- FastAPI app
- Railway Docker deployment
- `/health` and `/ready`
- Video upload
- Video trim
- Resize
- Mute audio
- Add caption text
- MP4 conversion

## Important

This version prioritizes successful Railway deployment. Full AI background removal can be added after this base deployment is stable.