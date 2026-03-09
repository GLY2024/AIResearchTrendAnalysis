"""Entry point for PyInstaller-packaged ARTA backend."""

import sys
import os

# When frozen by PyInstaller, set proper base path
if getattr(sys, "frozen", False):
    # Running as packaged executable
    base_dir = os.path.dirname(sys.executable)
    os.chdir(base_dir)
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)

import uvicorn
from app.main import app
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
