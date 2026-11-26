from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import __version__
from .config import CONFIG_DIR, MODES, Config

DATA = Path(__file__).resolve().parent / "data"
USAGE = """Kullanım: sky [tui|gui|tui+gui]
        sky --install-desktop     uygulama menüsüne ve simgeye ekle
        sky --uninstall-desktop   menü girdisini kaldır
        sky --version"""

DEPENDENCIES = {"tui": "textual", "gui": "PyQt6"}

def _missing(mode: str) -> list[str]:
    needed = [DEPENDENCIES[m] for m in mode.split("+")]
    return [pkg for pkg in needed if importlib.util.find_spec(pkg) is None]

def _launch_gui_detached():
    subprocess.Popen(
        [sys.executable, "-m", "sky", "gui"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

def _data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")

def _launcher_command() -> str:
    exe = shutil.which("sky")
    if exe:
        return f'"{exe}"'
    return f'"{sys.executable}" -m sky'

def install_desktop() -> int:
    data = _data_home()
    apps, icons = data / "applications", data / "icons" / "hicolor" / "scalable" / "apps"
    apps.mkdir(parents=True, exist_ok=True)
    icons.mkdir(parents=True, exist_ok=True)
    shutil.copy(DATA / "sky.svg", icons / "sky.svg")

    lines = (DATA / "sky.desktop").read_text(encoding="utf-8").splitlines()
    lines = [f"Exec={_launcher_command()} gui" if ln.startswith("Exec=") else ln for ln in lines]
    (apps / "sky.desktop").write_text("\n".join(lines) + "\n", encoding="utf-8")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    conf = CONFIG_DIR / "sky.conf"
    if not conf.exists():
        shutil.copy(DATA / "sky.conf", conf)

    for cmd in (["update-desktop-database", str(apps)],
                ["gtk-update-icon-cache", "-f", "-t", str(data / "icons" / "hicolor")]):
        try:
            subprocess.run(cmd, check=False, capture_output=True)
        except FileNotFoundError:
            pass
    print(f"✅ Menü girdisi eklendi: {apps / 'sky.desktop'}")
    print("   Uygulama menüsünde 'Sky' olarak görünür (görünmezse oturumu yenile).")
    return 0

def uninstall_desktop() -> int:
    data = _data_home()
    for p in (data / "applications" / "sky.desktop",
              data / "icons" / "hicolor" / "scalable" / "apps" / "sky.svg"):
        p.unlink(missing_ok=True)
    print(f"🗑️ Menü girdisi kaldırıldı. (Ayarlar korundu: {CONFIG_DIR})")
    return 0

def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    first = argv[0] if argv else None

    if first in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    if first in ("-V", "--version"):
        print(f"sky {__version__}")
        return 0
    if first == "--install-desktop":
        return install_desktop()
    if first == "--uninstall-desktop":
        return uninstall_desktop()

    cfg = Config()
    for warning in cfg.warnings:
        print(f"[sky] uyarı: {warning}", file=sys.stderr)

    mode = first.lower() if first else cfg.default_mode
    if mode not in MODES:
        print(f"Bilinmeyen kip: {mode!r}\n{USAGE}", file=sys.stderr)
        return 2

    missing = _missing(mode)
    if missing:
        print(f"[sky] Eksik paket: {', '.join(missing)}\n"
              f"      Kurmak için: pip install {' '.join(missing)}", file=sys.stderr)
        return 1

    if mode == "tui":
        from .tui import run
        run(cfg)
    elif mode == "gui":
        from .gui import run
        run(cfg)
    else:
        _launch_gui_detached()
        from .tui import run
        run(cfg)
    return 0
