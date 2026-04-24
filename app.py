import os
import io
import uuid
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": APP_NAME, "port": os.getenv("PORT", "8080"), "public_networking_target_port": "8080"}


@app.get("/ready")
async def ready():
    return {"ready": True}


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


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


def run_command(command: list):
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
    ext = Path(file.filename or "video.mp4").suffix.lower() or ".mp4"
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


@app.post("/remove-background/image")
async def remove_background_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    output_format: str = Form("png"),
):
    ext = Path(file.filename or "image.png").suffix.lower() or ".png"
    if ext not in IMAGE_EXTENSIONS:
        return JSONResponse({"error": f"Unsupported image format: {ext}"}, status_code=400)

    input_file = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    uid = uuid.uuid4().hex
    out_ext = ".png" if output_format == "png" else ".jpg"
    output_file = OUTPUT_DIR / f"nobg_{uid}{out_ext}"

    with input_file.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        from rembg import remove
        image_bytes = input_file.read_bytes()
        result_bytes = remove(image_bytes)

        if output_format == "jpg":
            from PIL import Image as PILImage
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
        cleanup_file(input_file)
        return JSONResponse({"error": str(exc)}, status_code=500)

    background_tasks.add_task(cleanup_file, input_file)
    return FileResponse(output_file, media_type=media_type, filename=filename)


@app.post("/remove-background/video")
async def remove_background_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    bg_color: str = Form("green"),
    fps: str = Form(""),
):
    ext = Path(file.filename or "video.mp4").suffix.lower() or ".mp4"
    if ext not in VIDEO_EXTENSIONS:
        return JSONResponse({"error": f"Unsupported video format: {ext}"}, status_code=400)

    uid = uuid.uuid4().hex
    input_file = UPLOAD_DIR / f"{uid}{ext}"
    frames_dir = FRAMES_DIR / uid
    processed_dir = FRAMES_DIR / f"{uid}_out"
    frames_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    use_transparent = bg_color == "transparent"
    out_ext = ".webm" if use_transparent else ".mp4"
    output_file = OUTPUT_DIR / f"nobg_{uid}{out_ext}"

    with input_file.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        from rembg import remove, new_session
        from PIL import Image as PILImage

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=r_frame_rate",
             "-of", "default=noprint_wrappers=1:nokey=1", str(input_file)],
            capture_output=True, text=True
        )
        src_fps_str = probe.stdout.strip() or "25/1"
        if "/" in src_fps_str:
            n, d = src_fps_str.split("/")
            src_fps = float(n) / float(d)
        else:
            src_fps = float(src_fps_str)

        target_fps = float(fps.strip()) if fps.strip() else min(src_fps, 25.0)

        run_command([
            "ffmpeg", "-y", "-i", str(input_file),
            "-vf", f"fps={target_fps}",
            str(frames_dir / "frame_%06d.png")
        ])

        frame_paths = sorted(frames_dir.glob("frame_*.png"))
        if not frame_paths:
            raise RuntimeError("No frames extracted from video.")

        session = new_session("u2net")

        BG_COLORS = {
            "green": (0, 255, 0),
            "white": (255, 255, 255),
            "black": (0, 0, 0),
        }
        bg_rgb = BG_COLORS.get(bg_color, (0, 255, 0))

        for frame_path in frame_paths:
            raw = frame_path.read_bytes()
            result_bytes = remove(raw, session=session)
            img = PILImage.open(io.BytesIO(result_bytes)).convert("RGBA")

            if use_transparent:
                out_img = img
            else:
                bg = PILImage.new("RGBA", img.size, (*bg_rgb, 255))
                bg.paste(img, mask=img.split()[3])
                out_img = bg.convert("RGB")

            out_path = processed_dir / frame_path.name
            out_img.save(str(out_path), format="PNG")

        if use_transparent:
            run_command([
                "ffmpeg", "-y",
                "-framerate", str(target_fps),
                "-i", str(processed_dir / "frame_%06d.png"),
                "-c:v", "libvpx-vp9",
                "-pix_fmt", "yuva420p",
                "-b:v", "0", "-crf", "35",
                str(output_file)
            ])
            media_type = "video/webm"
            dl_name = "no_background.webm"
        else:
            run_command([
                "ffmpeg", "-y",
                "-framerate", str(target_fps),
                "-i", str(processed_dir / "frame_%06d.png"),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-pix_fmt", "yuv420p",
                str(output_file)
            ])
            media_type = "video/mp4"
            dl_name = "no_background.mp4"
            # Try to merge audio back
            audio_output = OUTPUT_DIR / f"nobg_audio_{uid}.mp4"
            try:
                run_command([
                    "ffmpeg", "-y",
                    "-i", str(output_file),
                    "-i", str(input_file),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-c:a", "aac", "-shortest",
                    str(audio_output)
                ])
                output_file.unlink()
                audio_output.rename(output_file)
            except Exception:
                if audio_output.exists():
                    audio_output.unlink()

    except Exception as exc:
        cleanup_file(input_file)
        cleanup_dir(frames_dir)
        cleanup_dir(processed_dir)
        return JSONResponse({"error": str(exc)}, status_code=500)

    background_tasks.add_task(cleanup_file, input_file)
    background_tasks.add_task(cleanup_dir, frames_dir)
    background_tasks.add_task(cleanup_dir, processed_dir)
    return FileResponse(output_file, media_type=media_type, filename=dl_name)


@app.post("/remove-background")
async def remove_background_legacy(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form("convert"),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return await remove_background_image(background_tasks, file, output_format="png")
    else:
        return await remove_background_video(background_tasks, file, bg_color="green", fps="")
