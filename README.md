# FreeCut Studio V2 Fixed

Railway-ready free video background remover and basic video editor.

## Why V2 Fixed?

This version fixes Railway deployment failure:

```text
/opt/venv/bin/uvicorn could not be found
```

Fixes added:

- Uses `python -m uvicorn` instead of direct `/opt/venv/bin/uvicorn`
- Added `start.sh`
- Added `Procfile`
- Added `railway.json`
- Added `nixpacks.toml`
- Dockerfile explicitly installs Python dependencies and FFmpeg

## Deploy to Railway

1. Extract this zip.
2. Upload all files to GitHub repository root.
   - Important: `app.py`, `Dockerfile`, `requirements.txt`, `railway.json` must be in root.
3. Railway → New Project → Deploy from GitHub.
4. Do not manually override start command.
5. Open `/health` after deployment.

## Local Run

```bash
pip install -r requirements.txt
python -m uvicorn app:app --reload --port 8080
```

Open:

```text
http://localhost:8080
```

## Notes

- Background removal uses MediaPipe Selfie Segmentation.
- Best for human/person videos.
- Use short videos first on Railway because video processing is CPU-heavy.
