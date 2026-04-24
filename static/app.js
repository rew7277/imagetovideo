let selectedFile = null;

const fileInput = document.getElementById("fileInput");
const dropzone = document.getElementById("dropzone");
const preview = document.getElementById("preview");
const resultVideo = document.getElementById("resultVideo");
const statusEl = document.getElementById("status");
const downloadLink = document.getElementById("downloadLink");

function setStatus(text) {
  statusEl.textContent = text;
}

function handleFile(file) {
  if (!file) return;
  selectedFile = file;
  preview.src = URL.createObjectURL(file);
  preview.style.display = "block";
  setStatus(`Selected: ${file.name}`);
}

dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => handleFile(e.target.files[0]));

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.style.transform = "scale(1.01)";
});
dropzone.addEventListener("dragleave", () => {
  dropzone.style.transform = "scale(1)";
});
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.style.transform = "scale(1)";
  handleFile(e.dataTransfer.files[0]);
});

async function postForm(url, form) {
  if (!selectedFile) {
    alert("Please upload a video first.");
    return;
  }

  const data = new FormData(form);
  data.append("file", selectedFile);

  if (form.id === "editForm") {
    data.set("mute", form.querySelector("[name=mute]").checked ? "true" : "false");
  }

  resultVideo.style.display = "none";
  downloadLink.style.display = "none";
  setStatus("Processing video... Larger videos may take time on Railway free tier.");

  const response = await fetch(url, { method: "POST", body: data });

  if (!response.ok) {
    let message = "Processing failed.";
    try {
      const err = await response.json();
      message = err.error || message;
    } catch (_) {}
    setStatus(message);
    return;
  }

  const blob = await response.blob();
  const outUrl = URL.createObjectURL(blob);

  resultVideo.src = outUrl;
  resultVideo.style.display = "block";

  downloadLink.href = outUrl;
  downloadLink.style.display = "inline-block";

  setStatus("Done. Preview or download your output.");
}

document.getElementById("bgForm").addEventListener("submit", (e) => {
  e.preventDefault();
  postForm("/remove-background", e.currentTarget);
});

document.getElementById("editForm").addEventListener("submit", (e) => {
  e.preventDefault();
  postForm("/edit-video", e.currentTarget);
});
