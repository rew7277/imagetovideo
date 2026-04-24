# FreeCut Studio

AI-powered background removal for images **and** videos, plus a video editor.

## Features
- **Image BG Removal** – Upload JPG/PNG/WEBP → get transparent PNG or white-bg JPG
- **Video BG Removal** – Frame-by-frame AI removal using U2-Net model; output as green screen, white, black, or transparent WebM
- **Video Editor** – Trim, resize, caption, mute → export MP4

## Tech Stack
- FastAPI + Uvicorn
- `rembg` (U2-Net AI model) + ONNX Runtime
- FFmpeg for video processing
- Pillow for image ops

## Running locally
```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8080
```

## Deploy on Railway
Set Public Networking → target port **8080**. The Dockerfile handles everything else including model pre-download.

## Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/remove-background/image` | Remove BG from image |
| POST | `/remove-background/video` | Remove BG from video (AI, frame-by-frame) |
| POST | `/edit-video` | Trim / resize / caption video |
| GET  | `/health` | Health check |
