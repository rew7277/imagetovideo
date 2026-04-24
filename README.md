# FreeCut Studio

AI-powered background removal for images **and** videos, plus a video editor.

## ⚠️ Railway Deployment Fix (IMPORTANT)

If you see **"The executable /opt/venv/bin/uvicorn could not be found"**, Railway has an old
start command cached in its **Service Settings dashboard** that overrides everything.

**Fix it in 3 clicks:**
1. Go to your Railway service → **Settings** tab
2. Scroll to **Deploy** → **Start Command**
3. **Clear the field completely** (leave it blank) → Save

The Dockerfile CMD will then take over and everything works.

The Dockerfile also creates `/opt/venv/bin/uvicorn` as a fallback wrapper so even
if Railway ignores the clear, the container will still start correctly.

## Features
- **Image BG Removal** – Upload JPG/PNG/WEBP → transparent PNG or white-bg JPG
- **Video BG Removal** – Frame-by-frame AI using U2-Net; output as green screen, white, black, or transparent WebM
- **Video Editor** – Trim, resize, caption, mute → MP4

## Tech Stack
- FastAPI + Uvicorn
- `rembg` (U2-Net AI model via ONNX Runtime)
- FFmpeg for video processing
- Pillow for image ops

## Running locally
```bash
pip install -r requirements.txt
python -m uvicorn app:app --reload --port 8080
```

## Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/remove-background/image` | Remove BG from image |
| POST | `/remove-background/video` | Remove BG from video (AI, frame-by-frame) |
| POST | `/edit-video` | Trim / resize / caption video |
| GET  | `/health` | Health check |
