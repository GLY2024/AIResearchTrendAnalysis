"""Stable development entrypoint for the backend from the repo root."""

from pathlib import Path
import os
import sys

import uvicorn


ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"

# Match the backend package's expected working directory so relative data paths
# keep using backend/data when launched from the repository root.
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=False,
    )
