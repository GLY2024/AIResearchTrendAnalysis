"""Entry point for PyInstaller-packaged ARTA backend."""

import sys
import os

# When frozen by PyInstaller, set proper base path
if getattr(sys, "frozen", False):
    # Running as packaged executable (may be in binaries/ subdir)
    exe_dir = os.path.dirname(sys.executable)
    app_root = os.path.dirname(exe_dir) if os.path.basename(exe_dir) == "binaries" else exe_dir
    os.environ.setdefault("ARTA_DATA_DIR", os.path.join(app_root, "data"))
    os.chdir(app_root)
    # Strip \\?\ prefix if present (Windows UNC extended path)
    data_dir = os.environ.get("ARTA_DATA_DIR", "")
    if data_dir.startswith("\\\\?\\"):
        os.environ["ARTA_DATA_DIR"] = data_dir[4:]
    # Ensure data directory exists
    os.makedirs(os.environ["ARTA_DATA_DIR"], exist_ok=True)

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
