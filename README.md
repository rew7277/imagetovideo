# DEPTH·FORGE — 2D→3D & Image→Video

Convert 2D images to 3D depth maps/anaglyphs and animate images into videos.

## Features

| Feature | Engine | Notes |
|---------|--------|-------|
| Depth Map | Intel DPT-Large (HuggingFace) | Real AI depth estimation |
| 3D Anaglyph | Custom NumPy renderer | View with Red-Cyan glasses |
| Parallax Video | OpenCV warp | Local, no API needed |
| Zoom / Ken Burns | OpenCV affine | Local, no API needed |
| AI Video (SVD) | Stable Video Diffusion (HF) | Requires HF API key |

---

## Local Setup

```bash
git clone <repo>
cd img3d

pip install -r requirements.txt

# Optional: set HuggingFace API key for AI-powered depth + SVD video
export HF_API_KEY=hf_xxxxxxxxxxxx

python app.py
# → http://localhost:5000
```

---

## Deploy on Railway

### Method 1: GitHub → Railway (Recommended)

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. Select your repo → Railway auto-detects Python + Procfile
4. Add environment variable:
   - `HF_API_KEY` = your HuggingFace token (get free at huggingface.co/settings/tokens)
5. Deploy → copy the Railway URL

### Method 2: Railway CLI

```bash
npm install -g @railway/cli
railway login
railway init
railway up
railway variables set HF_API_KEY=hf_xxxxxxxxxxxx
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `HF_API_KEY` | Optional | HuggingFace token for AI depth + SVD video. Without it, app runs in demo mode with gradient-based depth. |
| `PORT` | Auto-set by Railway | Server port |

---

## API Endpoints

### `POST /api/depth`
- **Body**: `multipart/form-data` with `file` (image)
- **Returns**: JSON with `original`, `depth_map`, `anaglyph_3d` as base64, plus download URLs

### `POST /api/img2video`
- **Body**: `multipart/form-data` with `file` (image) + `motion` (`parallax`|`zoom`|`ken_burns`|`svd`)
- **Returns**: JSON with `video_b64` (MP4 base64) + `download_url`

### `GET /api/download/<filename>`
- Download generated output files

### `GET /health`
- Health check — returns `{status: "ok", hf_key_set: true/false}`

---

## Getting a Free HuggingFace API Key

1. Sign up at [huggingface.co](https://huggingface.co)
2. Go to **Settings → Access Tokens**
3. Create a **Read** token
4. Set as `HF_API_KEY` in Railway variables

The free tier allows ~1000 inference calls/day.

---

## Tech Stack

- **Backend**: Python Flask + Gunicorn
- **Image Processing**: Pillow + NumPy
- **Video Generation**: OpenCV (local) / Stable Video Diffusion (AI)
- **3D Depth AI**: Intel DPT-Large via HuggingFace Inference API
- **Deploy**: Railway.app (GitHub integration)
