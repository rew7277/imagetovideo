"""
CanvasApp - Main FastAPI Application
Entry point for the backend server.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from backend.core.database import engine, Base
from backend.routers import auth, canvas, websocket

# Create all database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CanvasApp API",
    description="Real-time collaborative drawing app",
    version="1.0.0",
)

# --- CORS Middleware ---
# Allow frontend origin to communicate with backend
origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Routers ---
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(canvas.router, prefix="/api/canvas", tags=["Canvas"])
app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])

# --- Serve Frontend Static Files ---
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
static_path = os.path.join(frontend_path, "static")

if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    """Serve the main frontend HTML page."""
    index_path = os.path.join(frontend_path, "templates", "index.html")
    return FileResponse(index_path)


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    """Catch-all to serve frontend for SPA routing."""
    index_path = os.path.join(frontend_path, "templates", "index.html")
    return FileResponse(index_path)


@app.get("/api/health")
async def health_check():
    """Health check endpoint for Railway and monitoring."""
    return {"status": "ok", "version": "1.0.0"}
