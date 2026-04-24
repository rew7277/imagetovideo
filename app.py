import os
import uuid
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, Form, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

try:
    import mediapipe as mp
except Exception:
    mp = None

APP_NAME = "FreeCut Studio"
ROOT = Path(__file__).parent
UPLOAD_DIR = ROOT / "uploads"
OUTPUT_DIR = ROOT / "outputs"
STATIC_DIR = ROOT / "static"
TEMPLATE_DIR = ROOT / "templates"

for d in [UPLOAD_DIR, OUTPUT_DIR, STATIC_DIR, TEMPLATE_DIR]:
    d.mkdir(exist_ok=True)

app = FastAPI(title=APP_NAME)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


def cleanup_file(path: Path):
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def run_ffmpeg(cmd: list[str]):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2500:])
    return result


def get_video_info(path: Path):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError("Unable to open uploaded video.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = round(frames / fps, 2) if fps else 0
    cap.release()
    return {"fps": fps, "width": width, "height": height, "frames": frames, "duration": duration}


def hex_to_bgr(hex_color: str):
    hex_color = (hex_color or "#00ff00").replace("#", "")
    if len(hex_color) != 6:
        hex_color = "00ff00"
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (b, g, r)


def remove_video_background(
    input_path: Path,
    output_path: Path,
    mode: str = "transparent_green",
    bg_color: str = "#00ff00",
    blur_strength: int = 21,
    threshold: float = 0.35,
    max_seconds: Optional[int] = 30,
):
    if mp is None:
        raise RuntimeError("MediaPipe import failed. Please redeploy using the included Dockerfile.")

    info = get_video_info(input_path)
    fps = info["fps"] or 25
    width = info["width"]
    height = info["height"]

    cap = cv2.VideoCapture(str(input_path))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    temp_no_audio = OUTPUT_DIR / f"{uuid.uuid4().hex}_noaudio.mp4"
    writer = cv2.VideoWriter(str(temp_no_audio), fourcc, fps, (width, height))

    max_frames = int(max_seconds * fps) if max_seconds and max_seconds > 0 else None

    bg_bgr = np.array(hex_to_bgr(bg_color), dtype=np.uint8)
    if blur_strength % 2 == 0:
        blur_strength += 1
    blur_strength = max(3, min(99, blur_strength))

    segmenter = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=1)

    frame_count = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if max_frames and frame_count >= max_frames:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = segmenter.process(rgb)
        mask = result.segmentation_mask

        condition = mask > threshold
        condition_3 = np.stack((condition,) * 3, axis=-1)

        if mode == "blur":
            background = cv2.GaussianBlur(frame, (blur_strength, blur_strength), 0)
        elif mode == "solid":
            background = np.zeros(frame.shape, dtype=np.uint8)
            background[:] = bg_bgr
        else:
            background = np.zeros(frame.shape, dtype=np.uint8)
            background[:] = (0, 255, 0)

        output = np.where(condition_3, frame, background)
        writer.write(output.astype(np.uint8))
        frame_count += 1

    cap.release()
    writer.release()
    segmenter.close()

    try:
        run_ffmpeg([
            "ffmpeg", "-y",
            "-i", str(temp_no_audio),
            "-i", str(input_path),
            "-map", "0:v:0", "-map", "1:a:0?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest",
            str(output_path)
        ])
        cleanup_file(temp_no_audio)
    except Exception:
        shutil.move(str(temp_no_audio), str(output_path))

    return output_path


def basic_edit_video(
    input_path: Path,
    output_path: Path,
    start_time: str = "",
    end_time: str = "",
    mute: bool = False,
    width: str = "",
    text: str = "",
):
    cmd = ["ffmpeg", "-y"]

    if start_time:
        cmd += ["-ss", start_time]
    if end_time:
        cmd += ["-to", end_time]

    cmd += ["-i", str(input_path)]

    filters = []
    if width and width.isdigit():
        filters.append(f"scale={int(width)}:-2")

    if text:
        safe_text = text.replace("'", "\\'").replace(":", "\\:")
        filters.append(
            "drawtext="
            "fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{safe_text}':"
            "x=(w-text_w)/2:y=h-(text_h*3):"
            "fontsize=36:fontcolor=white:"
            "box=1:boxcolor=black@0.45:boxborderw=12"
        )

    if filters:
        cmd += ["-vf", ",".join(filters)]

    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]

    if mute:
        cmd += ["-an"]
    else:
        cmd += ["-c:a", "aac"]

    cmd += [str(output_path)]
    run_ffmpeg(cmd)
    return output_path


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok", "app": APP_NAME}


@app.post("/remove-background")
async def remove_background(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form("transparent_green"),
    bg_color: str = Form("#00ff00"),
    blur_strength: int = Form(31),
    threshold: float = Form(0.35),
    max_seconds: int = Form(20),
):
    ext = Path(file.filename).suffix.lower() or ".mp4"
    src = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    out = OUTPUT_DIR / f"bg_removed_{uuid.uuid4().hex}.mp4"

    with src.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        remove_video_background(src, out, mode, bg_color, blur_strength, threshold, max_seconds)
    except Exception as e:
        cleanup_file(src)
        return JSONResponse({"error": str(e)}, status_code=500)

    background_tasks.add_task(cleanup_file, src)
    return FileResponse(out, media_type="video/mp4", filename="background_removed.mp4")


@app.post("/edit-video")
async def edit_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    start_time: str = Form(""),
    end_time: str = Form(""),
    mute: str = Form("false"),
    width: str = Form(""),
    text: str = Form(""),
):
    ext = Path(file.filename).suffix.lower() or ".mp4"
    src = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    out = OUTPUT_DIR / f"edited_{uuid.uuid4().hex}.mp4"

    with src.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        basic_edit_video(
            src, out,
            start_time=start_time.strip(),
            end_time=end_time.strip(),
            mute=mute.lower() == "true",
            width=width.strip(),
            text=text.strip()
        )
    except Exception as e:
        cleanup_file(src)
        return JSONResponse({"error": str(e)}, status_code=500)

    background_tasks.add_task(cleanup_file, src)
    return FileResponse(out, media_type="video/mp4", filename="edited_video.mp4")
