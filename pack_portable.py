"""Create a portable (no-install) distribution of ARTA.

Usage:
    uv run python pack_portable.py

Output:
    dist/ARTA-portable/ directory with everything needed to run
"""

import shutil
import platform
from pathlib import Path

ROOT = Path(__file__).parent
FRONTEND = ROOT / "frontend"
TAURI_RELEASE = FRONTEND / "src-tauri" / "target" / "release"
BACKEND_DIST = ROOT / "backend" / "dist" / "arta-backend"
OUTPUT = ROOT / "dist" / "ARTA-portable"


def get_target_triple() -> str:
    machine = platform.machine().lower()
    arch_map = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}
    arch = arch_map.get(machine, machine)
    system = platform.system().lower()
    if system == "windows":
        return f"{arch}-pc-windows-msvc"
    elif system == "darwin":
        return f"{arch}-apple-darwin"
    else:
        return f"{arch}-unknown-linux-gnu"


def main():
    ext = ".exe" if platform.system() == "Windows" else ""
    triple = get_target_triple()

    tauri_exe = TAURI_RELEASE / f"arta{ext}"
    sidecar_name = f"arta-backend-{triple}{ext}"

    if not tauri_exe.exists():
        print(f"ERROR: Tauri exe not found: {tauri_exe}")
        print("Run 'build_tauri.bat' first.")
        return

    # Clean output
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    # Copy main Tauri exe
    print(f"Copying {tauri_exe.name}...")
    shutil.copy2(tauri_exe, OUTPUT / f"ARTA{ext}")

    # Copy sidecar binary (Tauri looks for it relative to the exe)
    sidecar_dir = OUTPUT / "binaries"
    sidecar_dir.mkdir()

    # Try onefile first
    onefile = ROOT / "backend" / "dist" / f"arta-backend{ext}"
    if onefile.exists():
        print(f"Copying sidecar (onefile): {sidecar_name}")
        shutil.copy2(onefile, sidecar_dir / sidecar_name)
    elif BACKEND_DIST.exists():
        # Fallback: keep the onedir runtime flat so the renamed exe can load
        # its sibling _internal directory.
        print(f"Copying sidecar (onedir): {BACKEND_DIST.name}/")
        for item in BACKEND_DIST.iterdir():
            if item.name == f"arta-backend{ext}":
                continue
            destination = sidecar_dir / item.name
            if destination.exists():
                if destination.is_dir():
                    shutil.rmtree(destination)
                else:
                    destination.unlink()
            if item.is_dir():
                shutil.copytree(item, destination)
            else:
                shutil.copy2(item, destination)
        shutil.copy2(BACKEND_DIST / f"arta-backend{ext}", sidecar_dir / sidecar_name)
    else:
        print("WARNING: No backend sidecar found! Build backend first.")

    # Copy WebView2 loader if exists (needed on some Windows machines)
    webview2 = TAURI_RELEASE / "WebView2Loader.dll"
    if webview2.exists():
        shutil.copy2(webview2, OUTPUT)

    # Create data directory
    (OUTPUT / "data").mkdir()

    print(f"\nPortable build ready: {OUTPUT}")
    print(f"Contents:")
    for f in sorted(OUTPUT.rglob("*")):
        if f.is_file():
            size_mb = f.stat().st_size / 1024 / 1024
            print(f"  {f.relative_to(OUTPUT)}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
