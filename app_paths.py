"""Application paths that work in source and packaged builds."""

from pathlib import Path
import sys


def get_app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_resource_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    app_root = get_app_root()
    internal = app_root / "_internal"
    if getattr(sys, "frozen", False) and internal.exists():
        return internal
    return app_root


APP_ROOT = get_app_root()
RESOURCE_ROOT = get_resource_root()
ICON_FILE = APP_ROOT / "CuraStack Software.ico"
VERSION_FILE = APP_ROOT / "version.json"
DB_FILE = APP_ROOT / "theratrak.db"
ASSETS_DIR = RESOURCE_ROOT / "assets"