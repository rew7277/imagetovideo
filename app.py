import os, io, uuid, time, base64, requests, numpy as np, shutil
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
from PIL import Image, ImageFilter

app = Flask(__name__)
CORS(app)

OUTPUT_FOLDER = 'outputs'
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

HF_API_KEY = os.environ.get('HF_API_KEY', '')

# Disable Accept-Encoding so HF never sends gzip/chunked compressed bodies
# — a primary cause of IncompleteRead on Railway's proxy layer.
HF_HEADERS = {
    "Authorization": f"Bearer {HF_API_KEY}",
    "Accept-Encoding": "identity",   # <-- critical fix
}
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


def safe_hf_post(url, data, timeout=90, retries=3):
    """
    POST to HuggingFace Inference API with robust response reading.

    Root cause of IncompleteRead:
      requests uses http.client under the hood. When the server sends a
      chunked or gzip-compressed response and the TCP connection hiccups
      (common on Railway's proxy), iter_content / .content raise
      IncompleteRead mid-stream.

    Fix:
      1. 'Accept-Encoding: identity' tells HF not to gzip the response,
         eliminating decompression errors entirely.
      2. stream=True + resp.raw.read(decode_content=True) reads via
         urllib3's socket layer which handles chunked encoding natively
         without triggering http.client's stricter length checks.
      3. Retry up to `retries` times with exponential back-off.
    """
    delay = 5
    for attempt in range(retries):
        try:
            resp = requests.post(
                url,
                headers=HF_HEADERS,
                data=data,
                timeout=timeout,
                stream=True,            # don't buffer in requests
            )

            # HF returns 503 when the model is loading — wait and retry
            if resp.status_code == 503:
                wait = 20 + delay * attempt
                app.logger.warning(f"HF 503 on attempt {attempt+1}, waiting {wait}s")
                resp.close()
                time.sleep(wait)
                continue

            # Read via urllib3 raw socket — bypasses http.client IncompleteRead
            raw_content = resp.raw.read(decode_content=True)
            resp._content = raw_content          # make .content work normally
            resp._content_consumed = True
            return resp

        except Exception as e:
            app.logger.warning(f"HF request attempt {attempt+1} failed: {e}")
            if attempt == retries - 1:
                raise RuntimeError(
                    f"HF API failed after {retries} attempts: {e}"
                ) from e
            time.sleep(delay * (attempt + 1))

    return None


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def image_to_base64(img, fmt='PNG'):
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()

HTML_PAGE = open(os.path.join(os.path.dirname(__file__), 'index.html')).read()

@app.route('/')
def index():
    return Response(HTML_PAGE, mimetype='text/html')

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'hf_key_set': bool(HF_API_KEY)})

@app.route('/api/depth', methods=['POST'])
def depth_estimation():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    file.seek(0, 2)
    if file.tell() > MAX_FILE_SIZE:
        return jsonify({'error': 'File too large (max 10MB)'}), 400
    file.seek(0)
    try:
        img = Image.open(file).convert('RGB')
        img.thumbnail((512, 512), Image.LANCZOS)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG', quality=90)
        img_bytes.seek(0)

        if not HF_API_KEY:
            depth_img = generate_demo_depth(img)
        else:
            api_url = "https://api-inference.huggingface.co/models/Intel/dpt-large"
            resp = safe_hf_post(api_url, img_bytes.read(), timeout=90)
            if resp is None or resp.status_code != 200:
                status = resp.status_code if resp else 'N/A'
                body   = resp.text[:200] if resp else ''
                return jsonify({'error': f'HF API error {status}: {body}'}), 500
            depth_img = Image.open(io.BytesIO(resp.content)).convert('L')

        uid = str(uuid.uuid4())[:8]
        depth_img.save(os.path.join(OUTPUT_FOLDER, f'{uid}_depth.png'))
        anaglyph = generate_anaglyph(img, depth_img)
        anaglyph.save(os.path.join(OUTPUT_FOLDER, f'{uid}_3d.png'))
        return jsonify({
            'success': True, 'uid': uid,
            'original':    image_to_base64(img, 'JPEG'),
            'depth_map':   image_to_base64(depth_img.convert('RGB'), 'PNG'),
            'anaglyph_3d': image_to_base64(anaglyph, 'PNG'),
            'download_depth': f'/api/download/{uid}_depth.png',
            'download_3d':    f'/api/download/{uid}_3d.png',
        })
    except Exception as e:
        app.logger.exception("depth_estimation error")
        return jsonify({'error': str(e)}), 500


def generate_demo_depth(img):
    gray  = np.array(img.convert('L'), dtype=np.float32)
    depth = 255 - gray
    h, w  = depth.shape
    cy, cx = h // 2, w // 2
    Y, X  = np.ogrid[:h, :w]
    dist  = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
    dist  = dist / dist.max()
    depth = depth * 0.6 + (1 - dist) * 255 * 0.4
    return (
        Image.fromarray(np.clip(depth, 0, 255).astype(np.uint8), 'L')
             .filter(ImageFilter.GaussianBlur(radius=3))
    )


def generate_anaglyph(img, depth):
    img_rgb   = np.array(img.convert('RGB'), dtype=np.float32)
    depth_arr = np.array(depth.convert('L'), dtype=np.float32) / 255.0
    h, w      = img_rgb.shape[:2]
    right     = img_rgb.copy()
    for row in range(h):
        shifts = (depth_arr[row] * 12).astype(int)
        for col in range(w):
            right[row, col] = img_rgb[row, min(col + shifts[col], w - 1)]
    anaglyph = np.zeros_like(img_rgb)
    anaglyph[:, :, 0] = img_rgb[:, :, 0]
    anaglyph[:, :, 1] = right[:, :, 1]
    anaglyph[:, :, 2] = right[:, :, 2]
    return Image.fromarray(np.clip(anaglyph, 0, 255).astype(np.uint8), 'RGB')


@app.route('/api/img2video', methods=['POST'])
def image_to_video():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    file.seek(0, 2)
    if file.tell() > MAX_FILE_SIZE:
        return jsonify({'error': 'File too large (max 10MB)'}), 400
    file.seek(0)
    motion_type = request.form.get('motion', 'parallax')
    try:
        img = Image.open(file).convert('RGB')
        img.thumbnail((512, 512), Image.LANCZOS)
        uid = str(uuid.uuid4())[:8]
        if HF_API_KEY and motion_type == 'svd':
            video_path = generate_svd_video(img, uid)
        else:
            video_path = generate_parallax_video(img, uid, motion_type)
        if not video_path or not os.path.exists(video_path):
            return jsonify({'error': 'Video generation failed'}), 500
        fname = os.path.basename(video_path)
        fmt   = os.path.splitext(fname)[1].lstrip('.')   # 'gif' or 'mp4'
        return jsonify({
            'success': True, 'uid': uid,
            'video_url':    f'/api/stream/{fname}',
            'download_url': f'/api/download/{fname}',
            'format': fmt,
        })
    except Exception as e:
        app.logger.exception("image_to_video error")
        return jsonify({'error': str(e)}), 500


def generate_parallax_video(img, uid, motion_type='parallax'):
    w, h         = img.size
    fps          = 10
    total_frames = fps * 3
    img_np       = np.array(img)
    frames       = []
    for i in range(total_frames):
        t = i / total_frames
        if motion_type == 'zoom':
            scale = 1.0 + 0.12 * np.sin(t * np.pi)
            nw, nh = int(w * scale), int(h * scale)
            frame = img.resize((nw, nh), Image.LANCZOS).crop(
                ((nw - w) // 2, (nh - h) // 2, (nw - w) // 2 + w, (nh - h) // 2 + h)
            )
        elif motion_type == 'ken_burns':
            scale  = 1.0 + 0.18 * t
            nw, nh = int(w * scale), int(h * scale)
            frame  = img.resize((nw, nh), Image.LANCZOS)
            left   = int((nw - w) * t * 0.5)
            top    = int((nh - h) * t * 0.3)
            frame  = frame.crop((left, top, left + w, top + h))
        else:
            shift = int(18 * np.sin(2 * np.pi * t))
            frame = Image.fromarray(np.roll(img_np, shift, axis=1))
        frames.append(frame.convert('P', palette=Image.ADAPTIVE, colors=256))

    gif_path = os.path.join(OUTPUT_FOLDER, f'{uid}_video.gif')
    frames[0].save(
        gif_path, save_all=True, append_images=frames[1:],
        loop=0, duration=int(1000 / fps)
    )
    return gif_path   # .gif served directly — no mp4 copy needed


def generate_svd_video(img, uid):
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=90)
    resp = safe_hf_post(
        "https://api-inference.huggingface.co/models/stabilityai/stable-video-diffusion-img2vid-xt",
        buf.getvalue(), timeout=300
    )
    if resp and resp.status_code == 200:
        p = os.path.join(OUTPUT_FOLDER, f'{uid}_video.mp4')
        with open(p, 'wb') as f:
            f.write(resp.content)
        return p
    # Fall back to local Ken Burns if SVD fails
    return generate_parallax_video(img, uid, 'ken_burns')


@app.route('/api/stream/<filename>')
def stream_file(filename):
    safe = os.path.basename(filename)
    fp   = os.path.join(OUTPUT_FOLDER, safe)
    if not os.path.exists(fp):
        return jsonify({'error': 'File not found'}), 404
    mime = 'image/gif' if safe.endswith('.gif') else 'video/mp4'
    return send_file(fp, mimetype=mime, conditional=True)


@app.route('/api/download/<filename>')
def download_file(filename):
    safe = os.path.basename(filename)
    fp   = os.path.join(OUTPUT_FOLDER, safe)
    if not os.path.exists(fp):
        return jsonify({'error': 'File not found'}), 404
    return send_file(fp, as_attachment=True)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
