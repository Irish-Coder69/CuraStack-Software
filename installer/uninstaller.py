from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import winreg
import ctypes
from pathlib import Path


APP_NAME = "CuraStack Software"
APP_EXE = "CuraStack Software.exe"
ICON_FILE = "CuraStack Software.ico"
LEGACY_START_MENU_FOLDERS = ("Thorough Track Pro", "TheraTrak-Pro")
LEGACY_ROOT_SHORTCUTS = ("TheraTrak Pro.lnk", "Uninstall TheraTrak Pro.lnk")

MB_OK = 0x00000000
MB_ICONINFORMATION = 0x00000040
MB_YESNO = 0x00000004
MB_ICONQUESTION = 0x00000020
MB_TOPMOST = 0x00040000
MB_SETFOREGROUND = 0x00010000
IDYES = 6


def install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(os.environ["LOCALAPPDATA"]) / "Programs" / APP_NAME


def ask_yes_no(message: str) -> bool:
    result = ctypes.windll.user32.MessageBoxW(
        None,
        message,
        APP_NAME,
        MB_YESNO | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND,
    )
    return result == IDYES


def show_info(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(
        None,
        message,
        APP_NAME,
        MB_OK | MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND,
    )


def desktop_shortcut_candidates() -> list[Path]:
    candidates = [Path.home() / "Desktop"]
    one_drive = os.environ.get("OneDrive")
    if one_drive:
        candidates.append(Path(one_drive) / "Desktop")
    seen = set()
    unique = []
    for p in candidates:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            unique.append(p / f"{APP_NAME}.lnk")
    return unique


def start_menu_program_dirs() -> list[Path]:
    candidates = [
        Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ["ProgramData"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    seen = set()
    unique = []
    for candidate in candidates:
        key = str(candidate).lower()
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def start_menu_dirs() -> list[Path]:
    names = [APP_NAME, *LEGACY_START_MENU_FOLDERS]
    dirs = []
    for programs_dir in start_menu_program_dirs():
        for name in names:
            dirs.append(programs_dir / name)
    return dirs


def remove_registry_entry() -> None:
    key_paths = (
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall\CuraStack Software",
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Aura Scribe PSY",
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall\AuraScribe",
    )
    for key_path in key_paths:
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                winreg.DeleteKey(hive, key_path)
            except FileNotFoundError:
                pass
            except PermissionError:
                pass
            except OSError:
                pass


def remove_shortcuts() -> None:
    for shortcut in desktop_shortcut_candidates():
        try:
            shortcut.unlink(missing_ok=True)
        except OSError:
            pass

    for programs_dir in start_menu_program_dirs():
        for shortcut_name in LEGACY_ROOT_SHORTCUTS:
            try:
                (programs_dir / shortcut_name).unlink(missing_ok=True)
            except OSError:
                pass

    for menu_dir in start_menu_dirs():
        try:
            shutil.rmtree(menu_dir, ignore_errors=True)
        except OSError:
            pass


def stop_running_app() -> None:
    # Best effort: app may be running and lock files in the install directory.
    subprocess.run(
        ["taskkill", "/IM", APP_EXE, "/F"],
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def schedule_self_delete_folder(target: Path) -> None:
    script_path = Path(tempfile.gettempdir()) / "curastack_uninstall_cleanup.cmd"
    script = (
        "@echo off\n"
        "cd /d %TEMP%\n"
        "set TARGET=%~1\n"
        "for /L %%i in (1,1,15) do (\n"
        "  rmdir /s /q \"%TARGET%\" >nul 2>&1\n"
        "  if not exist \"%TARGET%\" goto done\n"
        "  ping 127.0.0.1 -n 2 > nul\n"
        ")\n"
        ":done\n"
        "del /f /q \"%~f0\"\n"
    )
    script_path.write_text(script, encoding="utf-8")
    subprocess.Popen(
        ["cmd.exe", "/c", str(script_path), str(target)],
        cwd=tempfile.gettempdir(),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )


def main() -> int:
    if not ask_yes_no("Uninstall CuraStack Software from this computer?"):
        return 0

    target = install_dir()
    stop_running_app()
    remove_shortcuts()
    remove_registry_entry()

    try:
        # In frozen mode this executable is running from the install directory,
        # so defer deleting the folder until after process exit.
        if getattr(sys, "frozen", False):
            schedule_self_delete_folder(target)
        else:
            shutil.rmtree(target, ignore_errors=True)
    except OSError:
        pass

    show_info("CuraStack Software was uninstalled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
