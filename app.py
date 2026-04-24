import os
import io
import uuid
import shutil
import subprocess
import logging
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_NAME = "FreeCut Studio"

BASE_DIR = Path(__file__).resolve().parent
if BASE_DIR.name == "backend":
    BASE_DIR = BASE_DIR.parent

UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
FRAMES_DIR = BASE_DIR / "frames"
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"

for folder in [UPLOAD_DIR, OUTPUT_DIR, FRAMES_DIR, STATIC_DIR, TEMPLATE_DIR]:
    folder.mkdir(exist_ok=True)

app = FastAPI(title=APP_NAME)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Accept everything — let Pillow/ffmpeg decide what's valid
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif",
    ".gif", ".heic", ".heif", ".avif", ".ico", ".ppm", ".pgm",
    ".pbm", ".pnm", ".dib", ".jfif", ".jp2", ".j2k",
}
VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv",
    ".wmv", ".mpeg", ".mpg", ".3gp", ".3g2", ".ts", ".mts",
    ".m2ts", ".vob", ".ogv", ".rm", ".rmvb", ".asf", ".divx",
}

# Max FPS for BG removal — keeps processing time sane
MAX_BG_FPS = 15.0
# Max frames to process (safety cap — ~10s at 15fps)
MAX_FRAMES = 150


@app.get("/health")
async def health():
    return {"status": "ok", "service": APP_NAME, "port": os.getenv("PORT", "8080")}

@app.get("/ready")
async def ready():
    return {"ready": True}

@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── Helpers ──────────────────────────────────────────────────────────────────

def cleanup_file(path: Path):
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass

def cleanup_dir(path: Path):
    try:
        if path.exists():
            shutil.rmtree(path)
    except Exception:
        pass

def run_command(command: list, timeout: int = 300):
    """Run a subprocess, raise RuntimeError with stderr on failure."""
    logger.info("Running: %s", " ".join(str(c) for c in command))
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-3000:])
    return result

def get_video_fps(input_file: Path) -> float:
    """Probe source FPS, return float."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate",
         "-of", "default=noprint_wrappers=1:nokey=1", str(input_file)],
        capture_output=True, text=True
    )
    raw = probe.stdout.strip() or "25/1"
    if "/" in raw:
        n, d = raw.split("/")
        d = float(d) or 1
        return float(n) / d
    return float(raw) or 25.0

def get_video_duration(input_file: Path) -> float:
    """Probe duration in seconds."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(input_file)],
        capture_output=True, text=True
    )
    try:
        return float(probe.stdout.strip())
    except Exception:
        return 0.0

def has_audio(input_file: Path) -> bool:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_type",
         "-of", "default=noprint_wrappers=1:nokey=1", str(input_file)],
        capture_output=True, text=True
    )
    return bool(probe.stdout.strip())


# ── Video Editor ─────────────────────────────────────────────────────────────

@app.post("/edit-video")
async def edit_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    start_time: str = Form(""),
    end_time: str = Form(""),
    width: str = Form(""),
    text: str = Form(""),
    mute: str = Form("false"),
):
    ext = Path(file.filename or "video.mp4").suffix.lower() or ".mp4"
    input_file = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    output_file = OUTPUT_DIR / f"edited_{uuid.uuid4().hex}.mp4"

    with input_file.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    command = ["ffmpeg", "-y"]
    if start_time.strip():
        command += ["-ss", start_time.strip()]
    if end_time.strip():
        command += ["-to", end_time.strip()]
    command += ["-i", str(input_file)]

    filters = []
    if width.strip().isdigit():
        w = int(width.strip())
        # Ensure even dimensions for libx264
        filters.append(f"scale={w}:trunc(ow/a/2)*2")
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
    command += ["-an"] if mute.lower() == "true" else ["-c:a", "aac"]
    command += [str(output_file)]

    try:
        run_command(command)
    except Exception as exc:
        cleanup_file(input_file)
        return JSONResponse({"error": str(exc)}, status_code=500)

    background_tasks.add_task(cleanup_file, input_file)
    return FileResponse(output_file, media_type="video/mp4", filename="edited_video.mp4")


# ── Image BG Removal ─────────────────────────────────────────────────────────

@app.post("/remove-background/image")
async def remove_background_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    output_format: str = Form("png"),
):
    ext = Path(file.filename or "image.png").suffix.lower() or ".png"
    # Accept any extension — if Pillow can't open it we'll catch the exception
    input_file = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    uid = uuid.uuid4().hex
    out_ext = ".png" if output_format == "png" else ".jpg"
    output_file = OUTPUT_DIR / f"nobg_{uid}{out_ext}"

    with input_file.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        from rembg import remove
        from PIL import Image as PILImage

        # Convert input to PNG bytes first (handles HEIC, BMP, etc.)
        img_in = PILImage.open(str(input_file)).convert("RGB")
        buf_in = io.BytesIO()
        img_in.save(buf_in, format="PNG")
        image_bytes = buf_in.getvalue()

        result_bytes = remove(image_bytes)

        if output_format == "jpg":
            img = PILImage.open(io.BytesIO(result_bytes)).convert("RGBA")
            bg = PILImage.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            buf = io.BytesIO()
            bg.save(buf, format="JPEG", quality=92)
            output_file.write_bytes(buf.getvalue())
            media_type = "image/jpeg"
            filename = "no_background.jpg"
        else:
            output_file.write_bytes(result_bytes)
            media_type = "image/png"
            filename = "no_background.png"

    except Exception as exc:
        logger.exception("Image BG removal failed")
        cleanup_file(input_file)
        return JSONResponse({"error": str(exc)}, status_code=500)

    background_tasks.add_task(cleanup_file, input_file)
    return FileResponse(output_file, media_type=media_type, filename=filename)


# ── Video BG Removal ─────────────────────────────────────────────────────────

@app.post("/remove-background/video")
async def remove_background_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    bg_color: str = Form("green"),
    fps: str = Form(""),
):
    ext = Path(file.filename or "video.mp4").suffix.lower() or ".mp4"
    uid = uuid.uuid4().hex
    input_file  = UPLOAD_DIR / f"{uid}{ext}"
    frames_dir  = FRAMES_DIR / uid
    proc_dir    = FRAMES_DIR / f"{uid}_out"
    frames_dir.mkdir(parents=True, exist_ok=True)
    proc_dir.mkdir(parents=True, exist_ok=True)

    use_transparent = bg_color == "transparent"
    out_ext      = ".webm" if use_transparent else ".mp4"
    output_file  = OUTPUT_DIR / f"nobg_{uid}{out_ext}"

    with input_file.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        from rembg import remove, new_session
        from PIL import Image as PILImage

        # ── 1. Determine FPS ────────────────────────────────────────────────
        src_fps = get_video_fps(input_file)
        duration = get_video_duration(input_file)
        logger.info("Video: src_fps=%.2f  duration=%.2fs", src_fps, duration)

        # User override → clamp to MAX_BG_FPS
        if fps.strip():
            try:
                target_fps = min(float(fps.strip()), MAX_BG_FPS)
            except ValueError:
                target_fps = min(src_fps, MAX_BG_FPS)
        else:
            target_fps = min(src_fps, MAX_BG_FPS)

        # Safety cap: if video is long, drop fps further
        estimated_frames = int(duration * target_fps)
        if estimated_frames > MAX_FRAMES:
            target_fps = MAX_FRAMES / duration
            logger.info("Capping to %.2f fps to stay under %d frames", target_fps, MAX_FRAMES)

        target_fps = max(target_fps, 1.0)  # never go below 1 fps
        logger.info("Target FPS: %.2f  (~%d frames)", target_fps, int(duration * target_fps))

        # ── 2. Extract frames ────────────────────────────────────────────────
        # Normalise to yuv420p first to avoid odd pixel format errors
        run_command([
            "ffmpeg", "-y", "-i", str(input_file),
            "-vf", f"fps={target_fps:.4f},format=rgb24",
            "-q:v", "2",
            str(frames_dir / "frame_%06d.png"),
        ])

        frame_paths = sorted(frames_dir.glob("frame_*.png"))
        if not frame_paths:
            raise RuntimeError("No frames could be extracted from the video.")

        logger.info("Extracted %d frames", len(frame_paths))

        # ── 3. Remove BG frame-by-frame ──────────────────────────────────────
        session = new_session("u2net")

        BG_COLORS = {
            "green": (0, 255, 0),
            "white": (255, 255, 255),
            "black": (0, 0, 0),
        }
        bg_rgb = BG_COLORS.get(bg_color, (0, 255, 0))

        for i, frame_path in enumerate(frame_paths):
            raw = frame_path.read_bytes()
            result_bytes = remove(raw, session=session)
            img = PILImage.open(io.BytesIO(result_bytes)).convert("RGBA")

            if use_transparent:
                out_img = img
            else:
                bg = PILImage.new("RGBA", img.size, (*bg_rgb, 255))
                bg.paste(img, mask=img.split()[3])
                out_img = bg.convert("RGB")

            out_img.save(str(proc_dir / frame_path.name), format="PNG")

            if (i + 1) % 10 == 0:
                logger.info("Processed %d/%d frames", i + 1, len(frame_paths))

        # ── 4. Reassemble ────────────────────────────────────────────────────
        if use_transparent:
            run_command([
                "ffmpeg", "-y",
                "-framerate", f"{target_fps:.4f}",
                "-i", str(proc_dir / "frame_%06d.png"),
                "-c:v", "libvpx-vp9",
                "-pix_fmt", "yuva420p",
                "-b:v", "0", "-crf", "33",
                "-auto-alt-ref", "0",   # required for alpha in vp9
                str(output_file),
            ])
            media_type = "video/webm"
            dl_name = "no_background.webm"
        else:
            run_command([
                "ffmpeg", "-y",
                "-framerate", f"{target_fps:.4f}",
                "-i", str(proc_dir / "frame_%06d.png"),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-pix_fmt", "yuv420p",
                str(output_file),
            ])
            media_type = "video/mp4"
            dl_name = "no_background.mp4"

            # ── 5. Merge audio back (MP4 only) ───────────────────────────────
            if has_audio(input_file):
                audio_out = OUTPUT_DIR / f"nobg_audio_{uid}.mp4"
                try:
                    run_command([
                        "ffmpeg", "-y",
                        "-i", str(output_file),
                        "-i", str(input_file),
                        "-map", "0:v:0", "-map", "1:a:0",
                        "-c:v", "copy", "-c:a", "aac",
                        "-shortest",
                        str(audio_out),
                    ])
                    output_file.unlink()
                    audio_out.rename(output_file)
                    logger.info("Audio merged successfully")
                except Exception as ae:
                    logger.warning("Audio merge failed (video-only output): %s", ae)
                    if audio_out.exists():
                        audio_out.unlink()

    except Exception as exc:
        logger.exception("Video BG removal failed")
        cleanup_file(input_file)
        cleanup_dir(frames_dir)
        cleanup_dir(proc_dir)
        return JSONResponse({"error": str(exc)}, status_code=500)

    background_tasks.add_task(cleanup_file, input_file)
    background_tasks.add_task(cleanup_dir, frames_dir)
    background_tasks.add_task(cleanup_dir, proc_dir)
    return FileResponse(output_file, media_type=media_type, filename=dl_name)


# ── Legacy endpoint ───────────────────────────────────────────────────────────

@app.post("/remove-background")
async def remove_background_legacy(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form("convert"),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return await remove_background_image(background_tasks, file, output_format="png")
    return await remove_background_video(background_tasks, file, bg_color="green", fps="")
