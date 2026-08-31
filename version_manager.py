"""
CuraStack Software version manager.
Stores semantic version and build metadata in version.json.
"""

import json

from app_paths import APP_ROOT, VERSION_FILE

BASE_DIR = APP_ROOT

DEFAULT_VERSION = {
    "major": 1,
    "minor": 0,
    "patch": 0,
    "build": 1,
}


def _to_int(value, fallback):
    try:
        return int(value)
    except (ValueError, TypeError):
        return fallback


def _normalize(data: dict) -> dict:
    """Ensure version dict has valid integer keys and minimum values."""
    major = max(0, _to_int(data.get("major"), DEFAULT_VERSION["major"]))
    minor = max(0, _to_int(data.get("minor"), DEFAULT_VERSION["minor"]))
    patch = max(0, _to_int(data.get("patch"), DEFAULT_VERSION["patch"]))
    build = max(1, _to_int(data.get("build"), DEFAULT_VERSION["build"]))
    return {"major": major, "minor": minor, "patch": patch, "build": build}


def load_version() -> dict:
    if not VERSION_FILE.exists():
        save_version(DEFAULT_VERSION)
        return DEFAULT_VERSION.copy()

    try:
        with VERSION_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = DEFAULT_VERSION.copy()

    data = _normalize(data)
    save_version(data)
    return data


def save_version(data: dict) -> None:
    data = _normalize(data)
    with VERSION_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def get_version_data() -> dict:
    return load_version()


def get_semver() -> str:
    v = load_version()
    return f"{v['major']}.{v['minor']}.{v['patch']}"


def get_version_string() -> str:
    v = load_version()
    return f"{v['major']}.{v['minor']}.{v['patch']} Build {v['build']}"


def set_version(major: int, minor: int, patch: int, build: int) -> str:
    data = {
        "major": major,
        "minor": minor,
        "patch": patch,
        "build": build,
    }
    save_version(data)
    return get_version_string()


def bump_build() -> str:
    v = load_version()
    v["build"] += 1
    save_version(v)
    return get_version_string()


def bump_patch() -> str:
    v = load_version()
    v["patch"] += 1
    v["build"] = 1
    save_version(v)
    return get_version_string()


def bump_minor() -> str:
    v = load_version()
    v["minor"] += 1
    v["patch"] = 0
    v["build"] = 1
    save_version(v)
    return get_version_string()


def bump_major() -> str:
    v = load_version()
    v["major"] += 1
    v["minor"] = 0
    v["patch"] = 0
    v["build"] = 1
    save_version(v)
    return get_version_string()
