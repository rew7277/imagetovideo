let selectedFile = null;

const fileInput = document.getElementById("fileInput");
const dropzone = document.getElementById("dropzone");
const preview = document.getElementById("preview");
const resultVideo = document.getElementById("resultVideo");
const statusEl = document.getElementById("status");
const downloadLink = document.getElementById("downloadLink");

function setStatus(message) {
  statusEl.textContent = message;
}

function handleFile(file) {
  if (!file) return;
  selectedFile = file;
  preview.src = URL.createObjectURL(file);
  setStatus(`Selected: ${file.name}`);
}

dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", e => handleFile(e.target.files[0]));

dropzone.addEventListener("dragover", e => {
  e.preventDefault();
  dropzone.style.transform = "scale(1.01)";
});
dropzone.addEventListener("dragleave", () => {
  dropzone.style.transform = "scale(1)";
});
dropzone.addEventListener("drop", e => {
  e.preventDefault();
  dropzone.style.transform = "scale(1)";
  handleFile(e.dataTransfer.files[0]);
});

async function postVideo(url, form) {
  if (!selectedFile) {
    alert("Please upload a video first.");
    return;
  }

  const formData = new FormData(form);
  formData.append("file", selectedFile);

  if (form.id === "editForm") {
    formData.set("mute", form.querySelector("[name=mute]").checked ? "true" : "false");
  }

  resultVideo.style.display = "none";
  downloadLink.style.display = "none";
  setStatus("Processing video...");

  const response = await fetch(url, { method: "POST", body: formData });

  if (!response.ok) {
    let msg = "Processing failed.";
    try {
      const err = await response.json();
      msg = err.error || msg;
    } catch (_) {}
    setStatus(msg);
    return;
  }

  const blob = await response.blob();
  const outputUrl = URL.createObjectURL(blob);

  resultVideo.src = outputUrl;
  resultVideo.style.display = "block";
  downloadLink.href = outputUrl;
  downloadLink.style.display = "inline-block";
  setStatus("Done. Preview or download your output.");
}

document.getElementById("editForm").addEventListener("submit", e => {
  e.preventDefault();
  postVideo("/edit-video", e.currentTarget);
});

document.getElementById("bgForm").addEventListener("submit", e => {
  e.preventDefault();
  postVideo("/remove-background", e.currentTarget);
});