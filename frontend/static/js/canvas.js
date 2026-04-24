/**
 * canvas.js — Drawing engine for Canvara
 * 
 * Supports: pen, eraser, line, rectangle, circle tools
 * Undo/redo via stroke history
 * WebSocket broadcast of strokes for real-time collaboration
 * Background removal via pixel manipulation
 */

class DrawingEngine {
  constructor(canvasId, previewCanvasId) {
    this.canvas = document.getElementById(canvasId);
    this.preview = document.getElementById(previewCanvasId);
    this.ctx = this.canvas.getContext("2d");
    this.pctx = this.preview.getContext("2d");

    // Drawing state
    this.isDrawing = false;
    this.tool = "pen";
    this.color = "#e8ff6b";
    this.size = 5;
    this.opacity = 1;

    // Stroke history for undo/redo
    this.history = [];       // array of ImageData snapshots
    this.redoStack = [];
    this.MAX_HISTORY = 40;

    // Shape tool drag start
    this.dragStart = null;
    this.snapshotBeforeDrag = null;

    // WebSocket for collaboration
    this.ws = null;
    this.onStrokeFromRemote = null; // callback

    this._bindEvents();
    this.resize();
    window.addEventListener("resize", () => this.resize());
  }

  resize() {
    const wrapper = this.canvas.parentElement;
    // Canvas fills wrapper, maintaining a logical 1200x800 drawing space
    const W = Math.min(wrapper.clientWidth - 40, 1400);
    const H = Math.min(wrapper.clientHeight - 40, 900);

    // Save current drawing
    const imgData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);

    this.canvas.width = W;
    this.canvas.height = H;
    this.preview.width = W;
    this.preview.height = H;

    // Restore drawing
    this.ctx.putImageData(imgData, 0, 0);
  }

  // =================== TOOLS ===================

  setTool(tool) { this.tool = tool; }
  setColor(color) { this.color = color; }
  setSize(size) { this.size = parseInt(size, 10); }

  // =================== HISTORY ===================

  saveSnapshot() {
    const snap = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
    this.history.push(snap);
    if (this.history.length > this.MAX_HISTORY) this.history.shift();
    this.redoStack = []; // clear redo on new action
  }

  undo() {
    if (this.history.length === 0) return;
    // Save current to redo
    this.redoStack.push(this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height));
    const prev = this.history.pop();
    this.ctx.putImageData(prev, 0, 0);
  }

  redo() {
    if (this.redoStack.length === 0) return;
    this.saveSnapshot();
    const next = this.redoStack.pop();
    this.ctx.putImageData(next, 0, 0);
  }

  clearCanvas() {
    this.saveSnapshot();
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "clear" }));
    }
  }

  // =================== LOAD DATA ===================

  loadFromJSON(jsonString) {
    try {
      const strokes = JSON.parse(jsonString);
      if (!Array.isArray(strokes) || strokes.length === 0) return;
      this._replayStrokes(strokes);
    } catch (e) {
      console.warn("Failed to load drawing data:", e);
    }
  }

  _replayStrokes(strokes) {
    // Group strokes by strokeId and replay in order
    let currentStroke = null;
    strokes.forEach(pt => {
      if (pt.type === "clear") {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        return;
      }
      this._applyPoint(pt, false);
    });
  }

  // =================== SERIALIZATION ===================

  getDrawingJSON() {
    return JSON.stringify(this._strokeLog);
  }

  getThumbnail() {
    // Create small thumbnail canvas
    const thumb = document.createElement("canvas");
    thumb.width = 320; thumb.height = 240;
    const tctx = thumb.getContext("2d");
    tctx.drawImage(this.canvas, 0, 0, 320, 240);
    return thumb.toDataURL("image/png");
  }

  exportPNG() {
    // White background export
    const exp = document.createElement("canvas");
    exp.width = this.canvas.width;
    exp.height = this.canvas.height;
    const ectx = exp.getContext("2d");
    ectx.fillStyle = "#fff";
    ectx.fillRect(0, 0, exp.width, exp.height);
    ectx.drawImage(this.canvas, 0, 0);
    const link = document.createElement("a");
    link.href = exp.toDataURL("image/png");
    link.download = "canvara-drawing.png";
    link.click();
  }

  // =================== BACKGROUND REMOVAL ===================

  /**
   * Simple background removal: makes white/near-white pixels transparent.
   * Works best on drawings with a plain background.
   */
  removeBackground(threshold = 240) {
    const imgData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
    const d = imgData.data;
    for (let i = 0; i < d.length; i += 4) {
      const r = d[i], g = d[i+1], b = d[i+2];
      // Pixel is "background" if all channels are above threshold
      if (r > threshold && g > threshold && b > threshold) {
        d[i+3] = 0; // fully transparent
      }
    }
    this.saveSnapshot();
    this.ctx.putImageData(imgData, 0, 0);
  }

  // =================== REMOTE EVENTS ===================

  applyRemoteStroke(msg) {
    if (msg.type === "clear") {
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
      return;
    }
    this._applyPoint(msg, false);
  }

  // =================== DRAWING INTERNALS ===================

  _applyPoint(pt, broadcast = true) {
    const c = this.ctx;

    if (pt.tool === "eraser") {
      c.globalCompositeOperation = "destination-out";
    } else {
      c.globalCompositeOperation = "source-over";
    }

    c.strokeStyle = pt.color || this.color;
    c.lineWidth = pt.size || this.size;
    c.lineCap = "round";
    c.lineJoin = "round";

    if (pt.isNewStroke) {
      c.beginPath();
      c.moveTo(pt.x, pt.y);
    } else {
      c.lineTo(pt.x, pt.y);
      c.stroke();
    }

    if (broadcast && this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(pt));
    }
  }

  _getPos(e) {
    const rect = this.canvas.getBoundingClientRect();
    const touch = e.touches ? e.touches[0] : e;
    return {
      x: (touch.clientX - rect.left) * (this.canvas.width / rect.width),
      y: (touch.clientY - rect.top) * (this.canvas.height / rect.height),
    };
  }

  // =================== EVENT BINDING ===================

  _bindEvents() {
    this._strokeLog = [];

    const onStart = (e) => {
      e.preventDefault();
      this.isDrawing = true;
      this.saveSnapshot();

      const pos = this._getPos(e);

      if (["line", "rect", "circle"].includes(this.tool)) {
        // Shape tools: save a snapshot before drag so we can clear preview
        this.dragStart = pos;
        this.snapshotBeforeDrag = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
        return;
      }

      const pt = {
        type: "stroke",
        tool: this.tool,
        x: pos.x, y: pos.y,
        color: this.color,
        size: this.size,
        isNewStroke: true,
      };
      this._strokeLog.push(pt);
      this._applyPoint(pt);
    };

    const onMove = (e) => {
      e.preventDefault();
      if (!this.isDrawing) return;
      const pos = this._getPos(e);

      if (["line", "rect", "circle"].includes(this.tool) && this.dragStart) {
        // Draw shape preview on preview canvas
        this.pctx.clearRect(0, 0, this.preview.width, this.preview.height);
        this.pctx.strokeStyle = this.color;
        this.pctx.lineWidth = this.size;
        this.pctx.lineCap = "round";
        this.pctx.globalCompositeOperation = "source-over";
        this.pctx.beginPath();

        if (this.tool === "line") {
          this.pctx.moveTo(this.dragStart.x, this.dragStart.y);
          this.pctx.lineTo(pos.x, pos.y);
        } else if (this.tool === "rect") {
          this.pctx.rect(
            this.dragStart.x, this.dragStart.y,
            pos.x - this.dragStart.x, pos.y - this.dragStart.y,
          );
        } else if (this.tool === "circle") {
          const rx = Math.abs(pos.x - this.dragStart.x) / 2;
          const ry = Math.abs(pos.y - this.dragStart.y) / 2;
          const cx = this.dragStart.x + (pos.x - this.dragStart.x) / 2;
          const cy = this.dragStart.y + (pos.y - this.dragStart.y) / 2;
          this.pctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
        }
        this.pctx.stroke();
        return;
      }

      const pt = {
        type: "stroke",
        tool: this.tool,
        x: pos.x, y: pos.y,
        color: this.color,
        size: this.size,
        isNewStroke: false,
      };
      this._strokeLog.push(pt);
      this._applyPoint(pt);
    };

    const onEnd = (e) => {
      if (!this.isDrawing) return;
      this.isDrawing = false;

      if (["line", "rect", "circle"].includes(this.tool) && this.dragStart) {
        const pos = this._getPos(e.changedTouches ? e.changedTouches[0] : e);
        this.pctx.clearRect(0, 0, this.preview.width, this.preview.height);

        // Draw final shape on main canvas
        const c = this.ctx;
        c.strokeStyle = this.color;
        c.lineWidth = this.size;
        c.lineCap = "round";
        c.globalCompositeOperation = "source-over";
        c.beginPath();

        if (this.tool === "line") {
          c.moveTo(this.dragStart.x, this.dragStart.y);
          c.lineTo(pos.x, pos.y);
        } else if (this.tool === "rect") {
          c.rect(
            this.dragStart.x, this.dragStart.y,
            pos.x - this.dragStart.x, pos.y - this.dragStart.y,
          );
        } else if (this.tool === "circle") {
          const rx = Math.abs(pos.x - this.dragStart.x) / 2;
          const ry = Math.abs(pos.y - this.dragStart.y) / 2;
          const cx = this.dragStart.x + (pos.x - this.dragStart.x) / 2;
          const cy = this.dragStart.y + (pos.y - this.dragStart.y) / 2;
          c.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
        }
        c.stroke();
        this.dragStart = null;
      }
    };

    // Mouse
    this.canvas.addEventListener("mousedown", onStart);
    this.canvas.addEventListener("mousemove", onMove);
    this.canvas.addEventListener("mouseup", onEnd);
    this.canvas.addEventListener("mouseleave", onEnd);

    // Touch
    this.canvas.addEventListener("touchstart", onStart, { passive: false });
    this.canvas.addEventListener("touchmove", onMove, { passive: false });
    this.canvas.addEventListener("touchend", onEnd);
  }
}
