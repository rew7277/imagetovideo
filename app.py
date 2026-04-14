import os
import io
import uuid
import time
import base64
import requests
import numpy as np
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from PIL import Image
import json

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

HF_API_KEY = os.environ.get('HF_API_KEY', '')
HF_HEADERS = {"Authorization": f"Bearer {HF_API_KEY}"}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def image_to_base64(img: Image.Image, fmt='PNG') -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()

def base64_to_image(b64: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(b64)))

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'hf_key_set': bool(HF_API_KEY)})


# ─── 2D → Depth Map (pseudo-3D) ───────────────────────────────────────────────

@app.route('/api/depth', methods=['POST'])
def depth_estimation():
    """Generate depth map from image using Intel DPT-Large via HuggingFace."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Use PNG/JPG/WEBP.'}), 400

    file.seek(0, 2)
    if file.tell() > MAX_FILE_SIZE:
        return jsonify({'error': 'File too large (max 10MB)'}), 400
    file.seek(0)

    try:
        img = Image.open(file).convert('RGB')
        # Resize for faster processing
        img.thumbnail((512, 512), Image.LANCZOS)

        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG', quality=90)
        img_bytes.seek(0)

        # Call HuggingFace Depth Estimation API
        api_url = "https://api-inference.huggingface.co/models/Intel/dpt-large"
        
        if not HF_API_KEY:
            # Fallback: generate a fake depth map for demo
            depth_img = generate_demo_depth(img)
        else:
            response = requests.post(
                api_url,
                headers=HF_HEADERS,
                data=img_bytes.read(),
                timeout=60
            )
            if response.status_code == 200:
                depth_img = Image.open(io.BytesIO(response.content)).convert('L')
            elif response.status_code == 503:
                # Model loading, retry once
                time.sleep(20)
                img_bytes.seek(0)
                response = requests.post(api_url, headers=HF_HEADERS, data=img_bytes.read(), timeout=60)
                if response.status_code == 200:
                    depth_img = Image.open(io.BytesIO(response.content)).convert('L')
                else:
                    return jsonify({'error': f'HF API error: {response.text}'}), 500
            else:
                return jsonify({'error': f'HF API error {response.status_code}: {response.text}'}), 500

        # Save outputs
        uid = str(uuid.uuid4())[:8]
        orig_path = os.path.join(OUTPUT_FOLDER, f'{uid}_orig.jpg')
        depth_path = os.path.join(OUTPUT_FOLDER, f'{uid}_depth.png')
        anaglyph_path = os.path.join(OUTPUT_FOLDER, f'{uid}_3d.png')

        img.save(orig_path)
        depth_img.save(depth_path)

        # Generate Red-Cyan Anaglyph 3D
        anaglyph = generate_anaglyph(img, depth_img)
        anaglyph.save(anaglyph_path)

        return jsonify({
            'success': True,
            'uid': uid,
            'original': image_to_base64(img, 'JPEG'),
            'depth_map': image_to_base64(depth_img.convert('RGB'), 'PNG'),
            'anaglyph_3d': image_to_base64(anaglyph, 'PNG'),
            'download_depth': f'/api/download/{uid}_depth.png',
            'download_3d': f'/api/download/{uid}_3d.png',
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def generate_demo_depth(img: Image.Image) -> Image.Image:
    """Fallback demo depth map using brightness-based heuristic."""
    gray = np.array(img.convert('L'), dtype=np.float32)
    # Invert and normalize for basic depth feel
    depth = 255 - gray
    # Add radial gradient for center-focus depth
    h, w = depth.shape
    cy, cx = h // 2, w // 2
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt((X - cx)**2 + (Y - cy)**2)
    dist = dist / dist.max()
    depth = depth * 0.6 + (1 - dist) * 255 * 0.4
    depth = np.clip(depth, 0, 255).astype(np.uint8)
    # Blur for smoothness
    from PIL import ImageFilter
    d_img = Image.fromarray(depth, 'L')
    return d_img.filter(ImageFilter.GaussianBlur(radius=3))


def generate_anaglyph(img: Image.Image, depth: Image.Image) -> Image.Image:
    """Create Red-Cyan anaglyph 3D image using depth map for shift."""
    img_rgb = np.array(img.convert('RGB'), dtype=np.float32)
    depth_arr = np.array(depth.convert('L'), dtype=np.float32) / 255.0

    max_shift = 12
    h, w = img_rgb.shape[:2]

    left = img_rgb.copy()
    right = img_rgb.copy()

    for row in range(h):
        for col in range(w):
            shift = int(depth_arr[row, col] * max_shift)
            # Right eye shifted
            src_col = min(col + shift, w - 1)
            right[row, col] = img_rgb[row, src_col]

    # Red channel from left, Cyan (G+B) from right
    anaglyph = np.zeros_like(img_rgb)
    anaglyph[:, :, 0] = left[:, :, 0]   # Red from left
    anaglyph[:, :, 1] = right[:, :, 1]  # Green from right
    anaglyph[:, :, 2] = right[:, :, 2]  # Blue from right

    return Image.fromarray(np.clip(anaglyph, 0, 255).astype(np.uint8), 'RGB')


# ─── Image → Video (Warp Animation) ──────────────────────────────────────────

@app.route('/api/img2video', methods=['POST'])
def image_to_video():
    """
    Generate a parallax/zoom video from image + depth map.
    Uses SVD (Stable Video Diffusion) if HF key is set, else local parallax.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    file.seek(0, 2)
    if file.tell() > MAX_FILE_SIZE:
        return jsonify({'error': 'File too large (max 10MB)'}), 400
    file.seek(0)

    motion_type = request.form.get('motion', 'parallax')  # parallax | zoom | ken_burns

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

        # Read video and return as base64
        with open(video_path, 'rb') as f:
            video_b64 = base64.b64encode(f.read()).decode()

        return jsonify({
            'success': True,
            'uid': uid,
            'video_b64': video_b64,
            'download_url': f'/api/download/{uid}_video.mp4',
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def generate_parallax_video(img: Image.Image, uid: str, motion_type: str = 'parallax') -> str:
    """Generate parallax/zoom/ken_burns animation locally using OpenCV."""
    import cv2

    frames = []
    w, h = img.size
    fps = 24
    duration_sec = 4
    total_frames = fps * duration_sec

    output_path = os.path.join(OUTPUT_FOLDER, f'{uid}_video.mp4')
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    img_np = np.array(img)
    img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

    for i in range(total_frames):
        t = i / total_frames  # 0 → 1

        if motion_type == 'zoom':
            # Smooth zoom in
            scale = 1.0 + 0.15 * np.sin(t * np.pi)
            M = cv2.getRotationMatrix2D((w // 2, h // 2), 0, scale)
            frame = cv2.warpAffine(img_cv, M, (w, h))

        elif motion_type == 'ken_burns':
            # Zoom + pan (Ken Burns)
            scale = 1.0 + 0.2 * t
            tx = -30 * t
            ty = -20 * t
            M = np.float32([[scale, 0, tx + w*(1-scale)/2],
                             [0, scale, ty + h*(1-scale)/2]])
            frame = cv2.warpAffine(img_cv, M, (w, h))

        else:  # parallax - horizontal shift with easing
            shift = int(20 * np.sin(2 * np.pi * t))
            M = np.float32([[1, 0, shift], [0, 1, 0]])
            frame = cv2.warpAffine(img_cv, M, (w, h),
                                   borderMode=cv2.BORDER_REFLECT)

        out.write(frame)

    out.release()
    return output_path


def generate_svd_video(img: Image.Image, uid: str) -> str:
    """Call HuggingFace SVD API for AI video generation."""
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG', quality=90)

    api_url = "https://api-inference.huggingface.co/models/stabilityai/stable-video-diffusion-img2vid-xt"
    response = requests.post(
        api_url,
        headers=HF_HEADERS,
        data=img_bytes.getvalue(),
        timeout=300
    )

    if response.status_code == 200:
        output_path = os.path.join(OUTPUT_FOLDER, f'{uid}_video.mp4')
        with open(output_path, 'wb') as f:
            f.write(response.content)
        return output_path
    else:
        # Fallback to local parallax
        return generate_parallax_video(img, uid, 'ken_burns')


# ─── Download endpoint ────────────────────────────────────────────────────────

@app.route('/api/download/<filename>')
def download_file(filename):
    # Security: only allow our generated files
    safe_name = os.path.basename(filename)
    filepath = os.path.join(OUTPUT_FOLDER, safe_name)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    return send_file(filepath, as_attachment=True)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
