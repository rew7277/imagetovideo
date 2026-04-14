import os, io, uuid, time, base64, requests, numpy as np, shutil
from http.client import IncompleteRead
from requests.exceptions import ChunkedEncodingError
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
from PIL import Image, ImageFilter

app = Flask(__name__)
CORS(app)

OUTPUT_FOLDER = 'outputs'
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

HF_API_KEY = os.environ.get('HF_API_KEY', '')
HF_HEADERS = {"Authorization": f"Bearer {HF_API_KEY}"}
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def safe_post(url, headers, data, timeout=60, retries=2):
    """POST to HF API with streaming read to avoid IncompleteRead errors."""
    for attempt in range(retries):
        try:
            resp = requests.post(url, headers=headers, data=data, timeout=timeout, stream=True)
            if resp.status_code == 503 and attempt == 0:
                time.sleep(20)
                continue
            content = b''.join(resp.iter_content(chunk_size=8192))
            resp._content = content
            return resp
        except (ChunkedEncodingError, IncompleteRead, requests.exceptions.ConnectionError) as e:
            if attempt == retries - 1:
                raise RuntimeError(f'HF API connection failed after {retries} attempts: {e}')
            time.sleep(5)
    return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def image_to_base64(img, fmt='PNG'):
    buf = io.BytesIO(); img.save(buf, format=fmt); return base64.b64encode(buf.getvalue()).decode()

HTML_PAGE = open(os.path.join(os.path.dirname(__file__), 'index.html')).read()

@app.route('/')
def index():
    return Response(HTML_PAGE, mimetype='text/html')

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'hf_key_set': bool(HF_API_KEY)})

@app.route('/api/depth', methods=['POST'])
def depth_estimation():
    if 'file' not in request.files: return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file or not allowed_file(file.filename): return jsonify({'error': 'Invalid file type'}), 400
    file.seek(0, 2)
    if file.tell() > MAX_FILE_SIZE: return jsonify({'error': 'File too large (max 10MB)'}), 400
    file.seek(0)
    try:
        img = Image.open(file).convert('RGB')
        img.thumbnail((512, 512), Image.LANCZOS)
        img_bytes = io.BytesIO(); img.save(img_bytes, format='JPEG', quality=90); img_bytes.seek(0)
        if not HF_API_KEY:
            depth_img = generate_demo_depth(img)
        else:
            api_url = "https://api-inference.huggingface.co/models/Intel/dpt-large"
            resp = safe_post(api_url, HF_HEADERS, img_bytes.read(), timeout=60)
            if resp is None:
                return jsonify({'error': 'HF API request failed'}), 500
            if resp.status_code == 200:
                depth_img = Image.open(io.BytesIO(resp.content)).convert('L')
            else:
                return jsonify({'error': f'HF API error {resp.status_code}: {resp.text}'}), 500
        uid = str(uuid.uuid4())[:8]
        depth_img.save(os.path.join(OUTPUT_FOLDER, f'{uid}_depth.png'))
        anaglyph = generate_anaglyph(img, depth_img)
        anaglyph.save(os.path.join(OUTPUT_FOLDER, f'{uid}_3d.png'))
        return jsonify({
            'success': True, 'uid': uid,
            'original': image_to_base64(img, 'JPEG'),
            'depth_map': image_to_base64(depth_img.convert('RGB'), 'PNG'),
            'anaglyph_3d': image_to_base64(anaglyph, 'PNG'),
            'download_depth': f'/api/download/{uid}_depth.png',
            'download_3d': f'/api/download/{uid}_3d.png',
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_demo_depth(img):
    gray = np.array(img.convert('L'), dtype=np.float32)
    depth = 255 - gray
    h, w = depth.shape; cy, cx = h//2, w//2
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt((X-cx)**2 + (Y-cy)**2); dist = dist / dist.max()
    depth = depth * 0.6 + (1-dist) * 255 * 0.4
    return Image.fromarray(np.clip(depth, 0, 255).astype(np.uint8), 'L').filter(ImageFilter.GaussianBlur(radius=3))

def generate_anaglyph(img, depth):
    img_rgb = np.array(img.convert('RGB'), dtype=np.float32)
    depth_arr = np.array(depth.convert('L'), dtype=np.float32) / 255.0
    h, w = img_rgb.shape[:2]; right = img_rgb.copy()
    for row in range(h):
        shifts = (depth_arr[row] * 12).astype(int)
        for col in range(w):
            right[row, col] = img_rgb[row, min(col + shifts[col], w-1)]
    anaglyph = np.zeros_like(img_rgb)
    anaglyph[:,:,0] = img_rgb[:,:,0]; anaglyph[:,:,1] = right[:,:,1]; anaglyph[:,:,2] = right[:,:,2]
    return Image.fromarray(np.clip(anaglyph, 0, 255).astype(np.uint8), 'RGB')

@app.route('/api/img2video', methods=['POST'])
def image_to_video():
    if 'file' not in request.files: return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file or not allowed_file(file.filename): return jsonify({'error': 'Invalid file type'}), 400
    file.seek(0, 2)
    if file.tell() > MAX_FILE_SIZE: return jsonify({'error': 'File too large (max 10MB)'}), 400
    file.seek(0)
    motion_type = request.form.get('motion', 'parallax')
    try:
        img = Image.open(file).convert('RGB'); img.thumbnail((512, 512), Image.LANCZOS)
        uid = str(uuid.uuid4())[:8]
        video_path = generate_svd_video(img, uid) if (HF_API_KEY and motion_type == 'svd') else generate_parallax_video(img, uid, motion_type)
        if not video_path or not os.path.exists(video_path): return jsonify({'error': 'Video generation failed'}), 500
        fname = os.path.basename(video_path)
        ext = os.path.splitext(fname)[1].lower()  # .gif or .mp4
        return jsonify({'success': True, 'uid': uid, 'video_url': f'/api/stream/{fname}', 'download_url': f'/api/download/{fname}', 'format': ext.lstrip('.')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_parallax_video(img, uid, motion_type='parallax'):
    w, h = img.size; fps = 10; total_frames = fps * 3
    img_np = np.array(img); frames = []
    for i in range(total_frames):
        t = i / total_frames
        if motion_type == 'zoom':
            scale = 1.0 + 0.12 * np.sin(t * np.pi)
            nw, nh = int(w*scale), int(h*scale)
            frame = img.resize((nw, nh), Image.LANCZOS).crop(((nw-w)//2, (nh-h)//2, (nw-w)//2+w, (nh-h)//2+h))
        elif motion_type == 'ken_burns':
            scale = 1.0 + 0.18*t; nw, nh = int(w*scale), int(h*scale)
            frame = img.resize((nw, nh), Image.LANCZOS)
            left = int((nw-w)*t*0.5); top = int((nh-h)*t*0.3)
            frame = frame.crop((left, top, left+w, top+h))
        else:
            shift = int(18 * np.sin(2*np.pi*t))
            frame = Image.fromarray(np.roll(img_np, shift, axis=1))
        frames.append(frame.convert('P', palette=Image.ADAPTIVE, colors=256))
    gif_path = os.path.join(OUTPUT_FOLDER, f'{uid}_video.gif')
    frames[0].save(gif_path, save_all=True, append_images=frames[1:], loop=0, duration=int(1000/fps))
    return gif_path  # Return .gif directly — no mp4 copy needed

def generate_svd_video(img, uid):
    buf = io.BytesIO(); img.save(buf, format='JPEG', quality=90)
    resp = safe_post(
        "https://api-inference.huggingface.co/models/stabilityai/stable-video-diffusion-img2vid-xt",
        HF_HEADERS, buf.getvalue(), timeout=300
    )
    if resp and resp.status_code == 200:
        p = os.path.join(OUTPUT_FOLDER, f'{uid}_video.mp4')
        with open(p, 'wb') as f: f.write(resp.content)
        return p
    return generate_parallax_video(img, uid, 'ken_burns')

@app.route('/api/stream/<filename>')
def stream_file(filename):
    safe = os.path.basename(filename)
    fp = os.path.join(OUTPUT_FOLDER, safe)
    if not os.path.exists(fp): return jsonify({'error': 'File not found'}), 404
    # Serve GIF as image/gif, mp4 as video/mp4
    mime = 'image/gif' if safe.endswith('.gif') else 'video/mp4'
    return send_file(fp, mimetype=mime, conditional=True)

@app.route('/api/download/<filename>')
def download_file(filename):
    safe = os.path.basename(filename)
    fp = os.path.join(OUTPUT_FOLDER, safe)
    if not os.path.exists(fp): return jsonify({'error': 'File not found'}), 404
    return send_file(fp, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
