// ── Tab switching ────────────────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  });
});

// ── Generic dropzone ─────────────────────────────────────────────────────────
function setupDropzone(dropzoneId, inputId, onFile) {
  const dz    = document.getElementById(dropzoneId);
  const input = document.getElementById(inputId);
  dz.addEventListener('click', () => input.click());
  input.addEventListener('change', e => { if (e.target.files[0]) onFile(e.target.files[0]); });
  dz.addEventListener('dragover',  e => { e.preventDefault(); dz.classList.add('drag-over'); });
  dz.addEventListener('dragleave', ()  => dz.classList.remove('drag-over'));
  dz.addEventListener('drop', e => {
    e.preventDefault(); dz.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) onFile(e.dataTransfer.files[0]);
  });
}

function setStatus(elId, msg, isError = false) {
  const el = document.getElementById(elId);
  el.textContent = msg;
  el.style.color = isError ? '#dc2626' : '';
}

function setLoading(btnId, loading, label) {
  const btn = document.getElementById(btnId);
  btn.disabled = loading;
  btn.innerHTML = loading
    ? '<span class="spinner"></span>Processing… please wait'
    : label;
}

// ── Pulse timer shown while processing ───────────────────────────────────────
let _timerInterval = null;
function startTimer(statusId) {
  let secs = 0;
  clearInterval(_timerInterval);
  _timerInterval = setInterval(() => {
    secs++;
    const el = document.getElementById(statusId);
    if (el) {
      const m = String(Math.floor(secs / 60)).padStart(2,'0');
      const s = String(secs % 60).padStart(2,'0');
      el.textContent = `⏳ Processing… ${m}:${s} elapsed — this may take a few minutes`;
    }
  }, 1000);
}
function stopTimer() { clearInterval(_timerInterval); }

// ── Shared fetch helper with no timeout (server may take minutes) ─────────────
async function postFormData(url, formData) {
  // No AbortController — we wait as long as the server needs
  const res = await fetch(url, { method: 'POST', body: formData });
  return res;
}

// ═══════════════════════════════════════════
// IMAGE BG REMOVAL
// ═══════════════════════════════════════════
let imgFile = null;

setupDropzone('imgDropzone', 'imgFileInput', file => {
  imgFile = file;
  const preview = document.getElementById('imgPreview');
  preview.src = URL.createObjectURL(file);
  preview.style.display = 'block';
  setStatus('imgStatus', `Selected: ${file.name}`);
});

document.getElementById('imgSubmit').addEventListener('click', async () => {
  if (!imgFile) { alert('Please upload an image first.'); return; }

  setLoading('imgSubmit', true, 'Remove Background');
  startTimer('imgStatus');
  document.getElementById('imgDownload').style.display = 'none';
  document.getElementById('imgResultImg').style.display = 'none';

  const fd = new FormData();
  fd.append('file', imgFile);
  fd.append('output_format', document.getElementById('imgFormat').value);

  try {
    const res = await postFormData('/remove-background/image', fd);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Server error ${res.status}`);
    }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const img  = document.getElementById('imgResultImg');
    img.src    = url;
    img.style.display = 'block';
    const dl   = document.getElementById('imgDownload');
    dl.href    = url;
    dl.download = `no_background.${document.getElementById('imgFormat').value}`;
    dl.style.display = 'inline-block';
    stopTimer();
    setStatus('imgStatus', '✅ Done! Preview below or download.');
  } catch (e) {
    stopTimer();
    setStatus('imgStatus', '❌ ' + e.message, true);
  }
  setLoading('imgSubmit', false, 'Remove Background');
});

// ═══════════════════════════════════════════
// VIDEO BG REMOVAL
// ═══════════════════════════════════════════
let vidFile = null;

setupDropzone('vidDropzone', 'vidFileInput', file => {
  vidFile = file;
  const preview = document.getElementById('vidPreview');
  preview.src   = URL.createObjectURL(file);
  preview.style.display = 'block';
  // Show estimated time warning
  const sizeMB = (file.size / 1024 / 1024).toFixed(1);
  setStatus('vidStatus', `Selected: ${file.name} (${sizeMB} MB)`);
});

document.getElementById('vidSubmit').addEventListener('click', async () => {
  if (!vidFile) { alert('Please upload a video first.'); return; }

  setLoading('vidSubmit', true, 'Remove Background');
  startTimer('vidStatus');
  document.getElementById('vidDownload').style.display   = 'none';
  document.getElementById('vidResultVideo').style.display = 'none';

  const fd = new FormData();
  fd.append('file', vidFile);
  fd.append('bg_color', document.getElementById('vidBgColor').value);
  fd.append('fps', document.getElementById('vidFps').value.trim());

  try {
    const res = await postFormData('/remove-background/video', fd);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Server error ${res.status}`);
    }
    const blob  = await res.blob();
    const url   = URL.createObjectURL(blob);
    const video = document.getElementById('vidResultVideo');
    video.src   = url;
    video.style.display = 'block';
    const dl    = document.getElementById('vidDownload');
    dl.href     = url;
    const isWebm = document.getElementById('vidBgColor').value === 'transparent';
    dl.download  = isWebm ? 'no_background.webm' : 'no_background.mp4';
    dl.style.display = 'inline-block';
    stopTimer();
    setStatus('vidStatus', '✅ Done! Preview below or download.');
  } catch (e) {
    stopTimer();
    setStatus('vidStatus', '❌ ' + e.message, true);
  }
  setLoading('vidSubmit', false, 'Remove Background');
});

// ═══════════════════════════════════════════
// VIDEO EDITOR
// ═══════════════════════════════════════════
let editFile = null;

setupDropzone('editDropzone', 'editFileInput', file => {
  editFile = file;
  const preview = document.getElementById('editPreview');
  preview.src   = URL.createObjectURL(file);
  preview.style.display = 'block';
  setStatus('editStatus', `Selected: ${file.name}`);
});

document.getElementById('editSubmit').addEventListener('click', async () => {
  if (!editFile) { alert('Please upload a video first.'); return; }

  setLoading('editSubmit', true, 'Edit Video');
  startTimer('editStatus');
  document.getElementById('editDownload').style.display    = 'none';
  document.getElementById('editResultVideo').style.display = 'none';

  const fd = new FormData();
  fd.append('file', editFile);
  fd.append('start_time', document.getElementById('startTime').value);
  fd.append('end_time',   document.getElementById('endTime').value);
  fd.append('width',      document.getElementById('resizeWidth').value);
  fd.append('text',       document.getElementById('captionText').value);
  fd.append('mute',       document.getElementById('muteAudio').checked ? 'true' : 'false');

  try {
    const res = await postFormData('/edit-video', fd);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `Server error ${res.status}`);
    }
    const blob  = await res.blob();
    const url   = URL.createObjectURL(blob);
    const video = document.getElementById('editResultVideo');
    video.src   = url;
    video.style.display = 'block';
    const dl    = document.getElementById('editDownload');
    dl.href     = url;
    dl.download  = 'edited_video.mp4';
    dl.style.display = 'inline-block';
    stopTimer();
    setStatus('editStatus', '✅ Done! Preview below or download.');
  } catch (e) {
    stopTimer();
    setStatus('editStatus', '❌ ' + e.message, true);
  }
  setLoading('editSubmit', false, 'Edit Video');
});
