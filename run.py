"""
run.py — Convenience script to start Canvara locally.
Usage: python run.py
"""

import uvicorn
import os
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,  # Auto-reload on code changes
        log_level="info",
    )
