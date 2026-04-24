// ── Tab switching ────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  });
});

// ── Generic dropzone setup ───────────────────────────────────────
function setupDropzone(dropzoneId, inputId, onFile) {
  const dz = document.getElementById(dropzoneId);
  const input = document.getElementById(inputId);
  dz.addEventListener('click', () => input.click());
  input.addEventListener('change', e => { if (e.target.files[0]) onFile(e.target.files[0]); });
  dz.addEventListener('dragover', e => { e.preventDefault(); dz.style.transform = 'scale(1.01)'; });
  dz.addEventListener('dragleave', () => { dz.style.transform = 'scale(1)'; });
  dz.addEventListener('drop', e => {
    e.preventDefault(); dz.style.transform = 'scale(1)';
    if (e.dataTransfer.files[0]) onFile(e.dataTransfer.files[0]);
  });
}

// ── Helpers ──────────────────────────────────────────────────────
function showStatus(elId, msg) { document.getElementById(elId).textContent = msg; }
function setLoading(btnId, loading) {
  const btn = document.getElementById(btnId);
  if (loading) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Processing…';
  } else {
    btn.disabled = false;
    btn.innerHTML = btn.dataset.label || btn.innerHTML;
  }
}
function initBtn(id, label) {
  const btn = document.getElementById(id);
  btn.dataset.label = label;
}

// ═══════════════════════════════════════════════════════
// IMAGE BG REMOVAL
// ═══════════════════════════════════════════════════════
let imgFile = null;
initBtn('imgSubmit', 'Remove Background');

setupDropzone('imgDropzone', 'imgFileInput', file => {
  imgFile = file;
  const preview = document.getElementById('imgPreview');
  preview.src = URL.createObjectURL(file);
  preview.style.display = 'block';
  showStatus('imgStatus', `Selected: ${file.name}`);
});

document.getElementById('imgSubmit').addEventListener('click', async () => {
  if (!imgFile) { alert('Please upload an image first.'); return; }

  setLoading('imgSubmit', true);
  showStatus('imgStatus', 'Removing background… this may take a few seconds.');
  document.getElementById('imgDownload').style.display = 'none';
  document.getElementById('imgResultImg').style.display = 'none';

  const fd = new FormData();
  fd.append('file', imgFile);
  fd.append('output_format', document.getElementById('imgFormat').value);

  try {
    const res = await fetch('/remove-background/image', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Server error ${res.status}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const img = document.getElementById('imgResultImg');
    img.src = url;
    img.style.display = 'block';
    const dl = document.getElementById('imgDownload');
    dl.href = url;
    const fmt = document.getElementById('imgFormat').value;
    dl.download = `no_background.${fmt}`;
    dl.style.display = 'inline-block';
    showStatus('imgStatus', 'Done! Preview below or download.');
  } catch (e) {
    showStatus('imgStatus', '❌ ' + e.message);
  }

  setLoading('imgSubmit', false);
});

// ═══════════════════════════════════════════════════════
// VIDEO BG REMOVAL
// ═══════════════════════════════════════════════════════
let vidFile = null;
initBtn('vidSubmit', 'Remove Background');

setupDropzone('vidDropzone', 'vidFileInput', file => {
  vidFile = file;
  const preview = document.getElementById('vidPreview');
  preview.src = URL.createObjectURL(file);
  preview.style.display = 'block';
  showStatus('vidStatus', `Selected: ${file.name}`);
});

document.getElementById('vidSubmit').addEventListener('click', async () => {
  if (!vidFile) { alert('Please upload a video first.'); return; }

  setLoading('vidSubmit', true);
  showStatus('vidStatus', '⏳ Processing frames with AI… this can take several minutes for long clips. Please wait.');
  document.getElementById('vidDownload').style.display = 'none';
  document.getElementById('vidResultVideo').style.display = 'none';

  const fd = new FormData();
  fd.append('file', vidFile);
  fd.append('bg_color', document.getElementById('vidBgColor').value);
  fd.append('fps', document.getElementById('vidFps').value.trim());

  try {
    const res = await fetch('/remove-background/video', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Server error ${res.status}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const video = document.getElementById('vidResultVideo');
    video.src = url;
    video.style.display = 'block';
    const dl = document.getElementById('vidDownload');
    dl.href = url;
    const isWebm = document.getElementById('vidBgColor').value === 'transparent';
    dl.download = isWebm ? 'no_background.webm' : 'no_background.mp4';
    dl.style.display = 'inline-block';
    showStatus('vidStatus', 'Done! Preview below or download.');
  } catch (e) {
    showStatus('vidStatus', '❌ ' + e.message);
  }

  setLoading('vidSubmit', false);
});

// ═══════════════════════════════════════════════════════
// VIDEO EDITOR
// ═══════════════════════════════════════════════════════
let editFile = null;
initBtn('editSubmit', 'Edit Video');

setupDropzone('editDropzone', 'editFileInput', file => {
  editFile = file;
  const preview = document.getElementById('editPreview');
  preview.src = URL.createObjectURL(file);
  preview.style.display = 'block';
  showStatus('editStatus', `Selected: ${file.name}`);
});

document.getElementById('editSubmit').addEventListener('click', async () => {
  if (!editFile) { alert('Please upload a video first.'); return; }

  setLoading('editSubmit', true);
  showStatus('editStatus', 'Processing video…');
  document.getElementById('editDownload').style.display = 'none';
  document.getElementById('editResultVideo').style.display = 'none';

  const fd = new FormData();
  fd.append('file', editFile);
  fd.append('start_time', document.getElementById('startTime').value);
  fd.append('end_time', document.getElementById('endTime').value);
  fd.append('width', document.getElementById('resizeWidth').value);
  fd.append('text', document.getElementById('captionText').value);
  fd.append('mute', document.getElementById('muteAudio').checked ? 'true' : 'false');

  try {
    const res = await fetch('/edit-video', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Server error ${res.status}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const video = document.getElementById('editResultVideo');
    video.src = url;
    video.style.display = 'block';
    const dl = document.getElementById('editDownload');
    dl.href = url;
    dl.download = 'edited_video.mp4';
    dl.style.display = 'inline-block';
    showStatus('editStatus', 'Done! Preview below or download.');
  } catch (e) {
    showStatus('editStatus', '❌ ' + e.message);
  }

  setLoading('editSubmit', false);
});
