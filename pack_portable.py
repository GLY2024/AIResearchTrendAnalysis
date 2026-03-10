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
    # Tauri runtime looks for sidecar WITHOUT triple suffix (e.g. arta-backend.exe)
    sidecar_runtime_name = f"arta-backend{ext}"
    # Build system uses triple suffix (e.g. arta-backend-x86_64-pc-windows-msvc.exe)
    sidecar_build_name = f"arta-backend-{triple}{ext}"

    # Sidecar sources (in order of preference)
    tauri_binaries_sidecar = FRONTEND / "src-tauri" / "binaries" / sidecar_build_name
    onefile_sidecar = ROOT / "backend" / "dist" / sidecar_runtime_name

    if not tauri_exe.exists():
        print(f"ERROR: Tauri exe not found: {tauri_exe}")
        print("Run 'uv run python build.py' first.")
        return

    # Clean output
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    # Copy main Tauri exe
    print(f"Copying {tauri_exe.name}...")
    shutil.copy2(tauri_exe, OUTPUT / f"ARTA{ext}")

    # Tauri runtime resolves sidecar as: {resource_dir}/binaries/arta-backend.exe
    # (no target triple suffix at runtime)
    sidecar_dir = OUTPUT / "binaries"
    sidecar_dir.mkdir()

    sidecar_src = None
    if tauri_binaries_sidecar.exists():
        sidecar_src = tauri_binaries_sidecar
        print(f"Copying sidecar (tauri binaries): {sidecar_runtime_name}")
    elif onefile_sidecar.exists():
        sidecar_src = onefile_sidecar
        print(f"Copying sidecar (backend dist): {sidecar_runtime_name}")

    if sidecar_src:
        # Copy with runtime name (no triple suffix)
        shutil.copy2(sidecar_src, sidecar_dir / sidecar_runtime_name)
    else:
        print("WARNING: No backend sidecar found! Build backend first.")

    # Copy WebView2 loader if exists (needed on some Windows machines)
    webview2 = TAURI_RELEASE / "WebView2Loader.dll"
    if webview2.exists():
        shutil.copy2(webview2, OUTPUT)

    # Create data directory
    (OUTPUT / "ddata").mkdir()

    print(f"\nPortable build ready: {OUTPUT}")
    print(f"Contents:")
    for f in sorted(OUTPUT.rglob("*")):
        if f.is_file():
            size_mb = f.stat().st_size / 1024 / 1024
            print(f"  {f.relative_to(OUTPUT)}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
