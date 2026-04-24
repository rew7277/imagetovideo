# FreeCut Studio

Free Canva-style MVP for video background removal and simple editing.

## Features

- Upload video from browser
- Remove person background using free MediaPipe Selfie Segmentation
- Output modes:
  - Green screen background
  - Solid color background
  - Blurred background
- Basic video editing using FFmpeg:
  - Trim start/end time
  - Mute audio
  - Resize width
  - Add caption text
- FastAPI backend
- Railway deployable through Dockerfile

## Local Run

```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8080
```

Open:

```text
http://localhost:8080
```

## Railway Deployment

1. Create GitHub repository.
2. Upload these files.
3. Go to Railway.
4. New Project → Deploy from GitHub.
5. Select repository.
6. Railway will detect Dockerfile and deploy.
7. Open generated Railway URL.

## Important Limits

This is an MVP, not a full Canva clone.

MediaPipe Selfie Segmentation works best for humans/person videos.
For product videos, pets, vehicles, or complex backgrounds, use a stronger model later.

Railway free/basic machines can be slow for long videos. Keep first test videos under 30 seconds.

## Suggested Next Features

- User login and project saving
- Timeline editor
- Templates
- Video crop presets: YouTube Shorts, Instagram Reels, landscape
- AI captions/subtitles
- Audio library
- Cloud storage using S3
- Queue processing using Redis/RQ or Celery
- Better background removal model using MODNet or Robust Video Matting
