# Railway Fix for `/opt/venv/bin/uvicorn could not be found`

This version includes a hard compatibility fix.

## What changed

The Dockerfile now creates:

```bash
/opt/venv/bin/uvicorn
```

as a wrapper for:

```bash
python -m uvicorn
```

So even if Railway keeps using the old cached command, deployment should not fail with:

```text
The executable `/opt/venv/bin/uvicorn` could not be found.
```

## Important Railway Settings

After pushing this version to GitHub:

1. Railway → Your Service → Settings
2. Check **Start Command**
3. Remove any custom command like:

```bash
/opt/venv/bin/uvicorn app:app --host 0.0.0.0 --port $PORT
```

4. Keep it blank OR use:

```bash
python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}
```

5. Redeploy with **Clear Build Cache** if available.

## GitHub Folder Structure

Make sure files are in repository root:

```text
app.py
Dockerfile
requirements.txt
railway.json
start.sh
templates/
static/
```

Do not upload one extra nested folder like:

```text
repo/free_video_bg_editor/app.py
```

unless Railway root directory is set to that folder.
