"""Build script for ARTA desktop application.

Usage:
    uv run python build.py [--backend-only] [--frontend-only] [--dev]

Steps:
    1. Package backend with PyInstaller as a sidecar executable
    2. Copy sidecar to frontend/src-tauri/binaries/
    3. Build Tauri app (unless --backend-only)
"""

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
TAURI_DIR = FRONTEND_DIR / "src-tauri"
BINARIES_DIR = TAURI_DIR / "binaries"


def get_target_triple() -> str:
    """Get the Rust target triple for the current platform."""
    machine = platform.machine().lower()
    system = platform.system().lower()

    arch_map = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "aarch64": "aarch64",
        "arm64": "aarch64",
    }
    arch = arch_map.get(machine, machine)

    if system == "windows":
        return f"{arch}-pc-windows-msvc"
    elif system == "darwin":
        return f"{arch}-apple-darwin"
    elif system == "linux":
        return f"{arch}-unknown-linux-gnu"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def build_backend():
    """Package backend with PyInstaller."""
    print("=== Building backend sidecar ===")

    # Collect templates directory
    templates_dir = BACKEND_DIR / "app" / "agents" / "prompts"
    separator = ";" if platform.system() == "Windows" else ":"

    pyinstaller_args = [
        "uv", "run", "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--name", "arta-backend",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.http.h11_impl",
        "--hidden-import", "uvicorn.protocols.http.httptools_impl",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.protocols.websockets.wsproto_impl",
        "--hidden-import", "uvicorn.protocols.websockets.websockets_impl",
        "--hidden-import", "aiosqlite",
        "--hidden-import", "sqlalchemy.dialects.sqlite",
        "--hidden-import", "openai",
        "--hidden-import", "httpx",
    ]

    # Add templates
    if templates_dir.exists():
        pyinstaller_args += [
            "--add-data",
            f"{templates_dir}{separator}app/agents/prompts",
        ]

    pyinstaller_args.append("run_server.py")

    subprocess.run(pyinstaller_args, cwd=BACKEND_DIR, check=True)

    # Copy to Tauri binaries
    target_triple = get_target_triple()
    BINARIES_DIR.mkdir(parents=True, exist_ok=True)

    src_dir = BACKEND_DIR / "dist" / "arta-backend"
    ext = ".exe" if platform.system() == "Windows" else ""
    sidecar_name = f"arta-backend-{target_triple}{ext}"

    # For onedir mode, copy the entire directory and rename the main exe
    dest_dir = BINARIES_DIR / f"arta-backend-{target_triple}"
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    shutil.copytree(src_dir, dest_dir)

    # Also copy the main exe with target triple suffix to binaries root
    src_exe = src_dir / f"arta-backend{ext}"
    dest_exe = BINARIES_DIR / sidecar_name
    if dest_exe.exists():
        dest_exe.unlink()
    shutil.copy2(src_exe, dest_exe)

    print(f"Backend sidecar built: {dest_exe}")
    print(f"Backend bundle dir: {dest_dir}")


def build_tauri(dev: bool = False):
    """Build the Tauri application."""
    print("=== Building Tauri application ===")
    cmd = ["npx", "tauri"]
    if dev:
        cmd.append("dev")
    else:
        cmd.append("build")

    subprocess.run(cmd, cwd=FRONTEND_DIR, check=True)


def main():
    parser = argparse.ArgumentParser(description="Build ARTA desktop app")
    parser.add_argument("--backend-only", action="store_true", help="Only build backend sidecar")
    parser.add_argument("--frontend-only", action="store_true", help="Only build Tauri app (assumes backend already built)")
    parser.add_argument("--dev", action="store_true", help="Run in dev mode instead of building")
    args = parser.parse_args()

    if not args.frontend_only:
        build_backend()

    if not args.backend_only:
        build_tauri(dev=args.dev)


if __name__ == "__main__":
    main()
