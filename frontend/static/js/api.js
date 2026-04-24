/**
 * api.js — REST API client for Canvara backend
 * Handles auth headers, JSON encoding, and error parsing.
 */

const API_BASE = window.location.origin + "/api";

/** Read stored JWT from localStorage */
function getToken() {
  return localStorage.getItem("canvara_token");
}

/** Store token + user info after login */
function setSession(data) {
  localStorage.setItem("canvara_token", data.access_token);
  localStorage.setItem("canvara_user_id", data.user_id);
  localStorage.setItem("canvara_username", data.username);
}

/** Clear session on logout */
function clearSession() {
  localStorage.removeItem("canvara_token");
  localStorage.removeItem("canvara_user_id");
  localStorage.removeItem("canvara_username");
}

function isLoggedIn() {
  return !!getToken();
}

function getUsername() {
  return localStorage.getItem("canvara_username") || "";
}

/**
 * Core fetch wrapper — auto-injects Authorization header and parses JSON.
 * Throws an Error with the server's detail message on non-2xx responses.
 */
async function apiFetch(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(API_BASE + path, {
    headers,
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  // 204 No Content — nothing to parse
  if (res.status === 204) return null;

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return data;
}

/* ====================== AUTH ====================== */

async function register(username, email, password) {
  const data = await apiFetch("/auth/register", {
    method: "POST",
    body: { username, email, password },
  });
  setSession(data);
  return data;
}

async function login(username, password) {
  const data = await apiFetch("/auth/login", {
    method: "POST",
    body: { username, password },
  });
  setSession(data);
  return data;
}

function logout() {
  clearSession();
}

/* ====================== CANVAS ====================== */

async function listCanvases() {
  return apiFetch("/canvas/");
}

async function getCanvas(id) {
  return apiFetch(`/canvas/${id}`);
}

async function createCanvas(title, drawingData = "[]", thumbnail = null) {
  return apiFetch("/canvas/", {
    method: "POST",
    body: { title, drawing_data: drawingData, thumbnail },
  });
}

async function saveCanvas(id, title, drawingData, thumbnail) {
  return apiFetch(`/canvas/${id}`, {
    method: "PUT",
    body: { title, drawing_data: drawingData, thumbnail },
  });
}

async function deleteCanvas(id) {
  return apiFetch(`/canvas/${id}`, { method: "DELETE" });
}

/* ====================== WEBSOCKET ====================== */

/**
 * Open a WebSocket connection to the drawing room.
 * Returns the WebSocket object.
 */
function openDrawSocket(canvasId, onMessage) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${window.location.host}/ws/draw/${canvasId}?token=${getToken()}`;
  const ws = new WebSocket(url);

  ws.onopen = () => console.log("[WS] Connected to room", canvasId);
  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      onMessage(msg);
    } catch (_) {}
  };
  ws.onerror = (e) => console.warn("[WS] Error:", e);
  ws.onclose = () => console.log("[WS] Disconnected");

  return ws;
}
