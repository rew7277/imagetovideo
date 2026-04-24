import os
import uuid
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

APP_NAME = "FreeCut Studio"

BASE_DIR = Path(__file__).resolve().parent
if BASE_DIR.name == "backend":
    BASE_DIR = BASE_DIR.parent

UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"

for folder in [UPLOAD_DIR, OUTPUT_DIR, STATIC_DIR, TEMPLATE_DIR]:
    folder.mkdir(exist_ok=True)

app = FastAPI(title=APP_NAME)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": APP_NAME,
        "port": os.getenv("PORT", "8082"),
        "entrypoint": "compatible-app"
    }


@app.get("/ready")
async def ready():
    return {"ready": True}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


def cleanup_file(path: Path):
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def run_command(command: list[str]):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-3000:])
    return result


@app.post("/edit-video")
async def edit_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    start_time: str = Form(""),
    end_time: str = Form(""),
    width: str = Form(""),
    text: str = Form(""),
    mute: str = Form("false")
):
    ext = Path(file.filename or "video.mp4").suffix or ".mp4"
    input_file = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    output_file = OUTPUT_DIR / f"edited_{uuid.uuid4().hex}.mp4"

    with input_file.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    command = ["ffmpeg", "-y"]

    if start_time.strip():
        command += ["-ss", start_time.strip()]
    if end_time.strip():
        command += ["-to", end_time.strip()]

    command += ["-i", str(input_file)]

    filters = []

    if width.strip().isdigit():
        filters.append(f"scale={int(width.strip())}:-2")

    if text.strip():
        safe_text = text.strip().replace("'", "\\'").replace(":", "\\:")
        filters.append(
            "drawtext="
            "fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{safe_text}':"
            "x=(w-text_w)/2:y=h-(text_h*3):"
            "fontsize=36:fontcolor=white:"
            "box=1:boxcolor=black@0.45:boxborderw=12"
        )

    if filters:
        command += ["-vf", ",".join(filters)]

    command += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]

    if mute.lower() == "true":
        command += ["-an"]
    else:
        command += ["-c:a", "aac"]

    command += [str(output_file)]

    try:
        run_command(command)
    except Exception as exc:
        cleanup_file(input_file)
        return JSONResponse({"error": str(exc)}, status_code=500)

    background_tasks.add_task(cleanup_file, input_file)
    return FileResponse(output_file, media_type="video/mp4", filename="edited_video.mp4")


@app.post("/remove-background")
async def process_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form("convert")
):
    ext = Path(file.filename or "video.mp4").suffix or ".mp4"
    input_file = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    output_file = OUTPUT_DIR / f"processed_{uuid.uuid4().hex}.mp4"

    with input_file.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    command = [
        "ffmpeg", "-y",
        "-i", str(input_file),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(output_file)
    ]

    try:
        run_command(command)
    except Exception as exc:
        cleanup_file(input_file)
        return JSONResponse({"error": str(exc)}, status_code=500)

    background_tasks.add_task(cleanup_file, input_file)
    return FileResponse(output_file, media_type="video/mp4", filename="processed_video.mp4")