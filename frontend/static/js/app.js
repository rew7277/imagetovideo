/**
 * app.js — Main SPA controller for Canvara
 * Manages screen routing, UI events, and wires API + DrawingEngine together.
 */

// ====================== GLOBALS ======================

let engine = null;          // DrawingEngine instance
let currentCanvasId = null; // ID of canvas being edited
let autoSaveTimer = null;   // debounce timer for auto-save

// ====================== UTILITIES ======================

function showScreen(screenId) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  document.getElementById(screenId).classList.add("active");
}

function toast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => {
    el.style.animation = "toastOut 0.3s ease forwards";
    setTimeout(() => el.remove(), 300);
  }, 3000);
}

function formatDate(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function showLoader(show) {
  document.getElementById("canvas-loader").classList.toggle("active", show);
}

// ====================== AUTH SCREEN ======================

function initAuthScreen() {
  // Tab switching
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });

  // Login
  document.getElementById("btn-login").addEventListener("click", async () => {
    const username = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value;
    const errEl = document.getElementById("login-error");
    errEl.textContent = "";
    try {
      await login(username, password);
      await initDashboard();
      showScreen("dashboard-screen");
    } catch (err) {
      errEl.textContent = err.message;
    }
  });

  // Register
  document.getElementById("btn-register").addEventListener("click", async () => {
    const username = document.getElementById("reg-username").value.trim();
    const email = document.getElementById("reg-email").value.trim();
    const password = document.getElementById("reg-password").value;
    const errEl = document.getElementById("register-error");
    errEl.textContent = "";
    try {
      await register(username, email, password);
      await initDashboard();
      showScreen("dashboard-screen");
    } catch (err) {
      errEl.textContent = err.message;
    }
  });

  // Allow Enter key on inputs
  ["login-username", "login-password"].forEach(id => {
    document.getElementById(id).addEventListener("keydown", e => {
      if (e.key === "Enter") document.getElementById("btn-login").click();
    });
  });

  // Decorative animated background canvas
  initAuthBg();
}

function initAuthBg() {
  const bgCanvas = document.getElementById("auth-canvas-bg");
  const ctx = bgCanvas.getContext("2d");
  bgCanvas.width = window.innerWidth;
  bgCanvas.height = window.innerHeight;

  const particles = Array.from({ length: 60 }, () => ({
    x: Math.random() * bgCanvas.width,
    y: Math.random() * bgCanvas.height,
    vx: (Math.random() - 0.5) * 0.8,
    vy: (Math.random() - 0.5) * 0.8,
    size: Math.random() * 3 + 1,
    color: Math.random() > 0.5 ? "#e8ff6b" : "#6bffd8",
  }));

  function drawBg() {
    ctx.clearRect(0, 0, bgCanvas.width, bgCanvas.height);
    particles.forEach(p => {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0 || p.x > bgCanvas.width) p.vx *= -1;
      if (p.y < 0 || p.y > bgCanvas.height) p.vy *= -1;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fillStyle = p.color;
      ctx.fill();
    });
    requestAnimationFrame(drawBg);
  }
  drawBg();
}

// ====================== DASHBOARD ======================

async function initDashboard() {
  document.getElementById("dash-username").textContent = getUsername();
  await refreshCanvasGrid();
}

async function refreshCanvasGrid() {
  const grid = document.getElementById("canvas-grid");
  const empty = document.getElementById("empty-state");

  try {
    const canvases = await listCanvases();
    // Remove existing cards (but keep empty state element)
    grid.querySelectorAll(".canvas-card").forEach(c => c.remove());

    if (canvases.length === 0) {
      empty.style.display = "";
      return;
    }
    empty.style.display = "none";

    canvases.forEach(cv => {
      const card = document.createElement("div");
      card.className = "canvas-card";
      card.innerHTML = `
        <div class="canvas-card-thumb">
          ${cv.thumbnail
            ? `<img src="${cv.thumbnail}" alt="Preview" />`
            : `<span>✦</span>`
          }
        </div>
        <div class="canvas-card-body">
          <div class="canvas-card-title">${escapeHtml(cv.title)}</div>
          <div class="canvas-card-meta">${formatDate(cv.updated_at)}</div>
        </div>
        <button class="canvas-card-del" title="Delete" data-id="${cv.id}">✕</button>
      `;

      // Open canvas on click
      card.addEventListener("click", (e) => {
        if (e.target.closest(".canvas-card-del")) return;
        openStudio(cv.id);
      });

      // Delete button
      card.querySelector(".canvas-card-del").addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!confirm(`Delete "${cv.title}"? This cannot be undone.`)) return;
        try {
          await deleteCanvas(cv.id);
          toast("Canvas deleted", "success");
          await refreshCanvasGrid();
        } catch (err) {
          toast("Delete failed: " + err.message, "error");
        }
      });

      grid.appendChild(card);
    });
  } catch (err) {
    toast("Failed to load canvases: " + err.message, "error");
  }
}

function escapeHtml(str) {
  return str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

// ====================== STUDIO ======================

async function openStudio(canvasId = null) {
  showLoader(true);
  showScreen("studio-screen");

  // Initialize engine if needed (first time)
  if (!engine) {
    engine = new DrawingEngine("drawing-canvas", "preview-canvas");
    initToolbar();
    initKeyboardShortcuts();
  } else {
    // Clear canvas for fresh load
    engine.ctx.clearRect(0, 0, engine.canvas.width, engine.canvas.height);
    engine._strokeLog = [];
    engine.history = [];
    engine.redoStack = [];
  }

  // Disconnect previous WS
  if (engine.ws) {
    engine.ws.close();
    engine.ws = null;
  }

  if (canvasId) {
    // Load existing canvas
    currentCanvasId = canvasId;
    try {
      const cv = await getCanvas(canvasId);
      document.getElementById("canvas-title-input").value = cv.title;
      engine.loadFromJSON(cv.drawing_data);
      // Override stroke log with fresh log (replay loaded data)
      engine._strokeLog = [];
    } catch (err) {
      toast("Failed to load canvas: " + err.message, "error");
    }
  } else {
    // New canvas — will be created on first save
    currentCanvasId = null;
    document.getElementById("canvas-title-input").value = "Untitled Canvas";
  }

  showLoader(false);

  // Connect WebSocket for collaboration (only for saved canvases)
  if (currentCanvasId) {
    engine.ws = openDrawSocket(currentCanvasId, (msg) => {
      engine.applyRemoteStroke(msg);
    });
  }

  // Start auto-save (every 30 seconds)
  if (autoSaveTimer) clearInterval(autoSaveTimer);
  autoSaveTimer = setInterval(autoSave, 30000);
}

async function autoSave() {
  if (!currentCanvasId) return; // Don't auto-save brand new unsaved canvas
  try {
    const title = document.getElementById("canvas-title-input").value.trim() || "Untitled Canvas";
    await saveCanvas(currentCanvasId, title, engine.getDrawingJSON(), engine.getThumbnail());
  } catch (err) {
    console.warn("Auto-save failed:", err.message);
  }
}

async function manualSave() {
  const title = document.getElementById("canvas-title-input").value.trim() || "Untitled Canvas";
  const drawingData = engine.getDrawingJSON();
  const thumbnail = engine.getThumbnail();

  showLoader(true);
  try {
    if (currentCanvasId) {
      await saveCanvas(currentCanvasId, title, drawingData, thumbnail);
      toast("Saved! ✓", "success");
    } else {
      const cv = await createCanvas(title, drawingData, thumbnail);
      currentCanvasId = cv.id;
      // Now open WS for new canvas
      engine.ws = openDrawSocket(currentCanvasId, (msg) => {
        engine.applyRemoteStroke(msg);
      });
      toast("Canvas created! ✓", "success");
    }
  } catch (err) {
    toast("Save failed: " + err.message, "error");
  } finally {
    showLoader(false);
  }
}

// ====================== TOOLBAR ======================

function initToolbar() {
  // Tool buttons
  document.querySelectorAll(".tool-btn[data-tool]").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tool-btn[data-tool]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      engine.setTool(btn.dataset.tool);
      // Change cursor
      document.getElementById("canvas-wrapper").style.cursor =
        btn.dataset.tool === "eraser" ? "cell" : "crosshair";
    });
  });

  // Color picker
  const colorPicker = document.getElementById("color-picker");
  const colorPreview = document.getElementById("color-preview");
  colorPreview.style.background = colorPicker.value;

  colorPicker.addEventListener("input", () => {
    engine.setColor(colorPicker.value);
    colorPreview.style.background = colorPicker.value;
  });

  // Preset colors
  document.querySelectorAll(".preset-color").forEach(btn => {
    btn.addEventListener("click", () => {
      const c = btn.dataset.color;
      engine.setColor(c);
      colorPicker.value = c;
      colorPreview.style.background = c;
    });
  });

  // Brush size
  const sizeSlider = document.getElementById("brush-size");
  const sizeVal = document.getElementById("brush-size-val");
  sizeSlider.addEventListener("input", () => {
    engine.setSize(sizeSlider.value);
    sizeVal.textContent = sizeSlider.value;
  });

  // Undo / Redo / Clear
  document.getElementById("btn-undo").addEventListener("click", () => engine.undo());
  document.getElementById("btn-redo").addEventListener("click", () => engine.redo());
  document.getElementById("btn-clear").addEventListener("click", () => {
    if (confirm("Clear the entire canvas?")) engine.clearCanvas();
  });

  // Export PNG
  document.getElementById("btn-export").addEventListener("click", () => engine.exportPNG());

  // Background removal
  document.getElementById("btn-bg-remove").addEventListener("click", () => {
    engine.removeBackground(230);
    toast("Background removed!", "success");
  });

  // Save
  document.getElementById("btn-save").addEventListener("click", manualSave);

  // Back to dashboard
  document.getElementById("btn-back-dash").addEventListener("click", async () => {
    if (autoSaveTimer) clearInterval(autoSaveTimer);
    if (engine && engine.ws) { engine.ws.close(); engine.ws = null; }
    await initDashboard();
    showScreen("dashboard-screen");
  });

  // Share (copy link)
  document.getElementById("btn-share").addEventListener("click", async () => {
    if (!currentCanvasId) {
      toast("Save the canvas first to get a shareable link", "info");
      return;
    }
    await navigator.clipboard.writeText(window.location.origin + `/?canvas=${currentCanvasId}`);
    toast("Link copied to clipboard!", "success");
  });
}

function initKeyboardShortcuts() {
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT") return;
    const ctrl = e.ctrlKey || e.metaKey;
    if (ctrl && e.key === "z") { e.preventDefault(); engine.undo(); }
    if (ctrl && (e.key === "y" || (e.shiftKey && e.key === "z"))) { e.preventDefault(); engine.redo(); }
    if (ctrl && e.key === "s") { e.preventDefault(); manualSave(); }
    // Tool shortcuts
    if (!ctrl) {
      const keys = { p: "pen", e: "eraser", l: "line", r: "rect", c: "circle" };
      if (keys[e.key]) {
        const tool = keys[e.key];
        document.querySelector(`[data-tool="${tool}"]`)?.click();
      }
    }
  });
}

// ====================== MODAL: NEW CANVAS ======================

function initNewCanvasModal() {
  const modal = document.getElementById("modal-new-canvas");

  document.getElementById("btn-new-canvas").addEventListener("click", () => {
    modal.classList.remove("hidden");
    document.getElementById("new-canvas-title").value = "";
    document.getElementById("new-canvas-title").focus();
  });

  document.getElementById("btn-modal-cancel").addEventListener("click", () => {
    modal.classList.add("hidden");
  });

  document.getElementById("btn-modal-create").addEventListener("click", () => {
    modal.classList.add("hidden");
    openStudio(null);
  });

  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.add("hidden");
  });
}

// ====================== LOGOUT ======================

function initLogout() {
  document.getElementById("btn-logout").addEventListener("click", () => {
    if (autoSaveTimer) clearInterval(autoSaveTimer);
    if (engine && engine.ws) engine.ws.close();
    logout();
    showScreen("auth-screen");
    toast("Logged out", "info");
  });
}

// ====================== BOOT ======================

async function boot() {
  initAuthScreen();
  initLogout();
  initNewCanvasModal();

  // Check if already logged in
  if (isLoggedIn()) {
    try {
      await initDashboard();

      // Check if URL has ?canvas=ID to deep-link
      const params = new URLSearchParams(window.location.search);
      const canvasParam = params.get("canvas");
      if (canvasParam) {
        openStudio(parseInt(canvasParam));
      } else {
        showScreen("dashboard-screen");
      }
    } catch (err) {
      // Token expired
      logout();
      showScreen("auth-screen");
    }
  } else {
    showScreen("auth-screen");
  }
}

// Start the app
boot();
