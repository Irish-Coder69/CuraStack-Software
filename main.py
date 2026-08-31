"""
Aura Scribe PSY
Combined therapy practice management and CMS-1500 application.

Python 3.10+  ·  Tkinter + ttk  ·  SQLite backend
"""

import json
import io
import os
import platform
import queue
import re
import hmac
import hashlib
import shutil
import struct
import subprocess
import sys
import threading
import time
import traceback
import tkinter as tk
import tkinter.font as tkFont
import urllib.request
import base64
import uuid
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    from tkcalendar import DateEntry as _DateEntry
    _HAS_CALENDAR = True
except ImportError:
    _HAS_CALENDAR = False

try:
    import sounddevice as _sd  # type: ignore[import-not-found]
    import vosk as _vosk  # type: ignore[import-not-found]
    _HAS_OFFLINE_STT = True
except Exception:
    _sd = None
    _vosk = None
    _HAS_OFFLINE_STT = False

import database as db
import version_manager as vm
from app_paths import APP_ROOT, ASSETS_DIR, DB_FILE, ICON_FILE, VERSION_FILE

try:
    import fitz  # type: ignore[import-not-found]
    from PIL import Image, ImageTk  # type: ignore[import-not-found]
    PDF_RENDER_AVAILABLE = True
except Exception:
    fitz = None
    Image = None
    ImageTk = None
    PDF_RENDER_AVAILABLE = False

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey as _Ed25519PublicKey
    _HAS_ED25519 = True
    _ED25519_ERROR: str = ""
except Exception as _e:
    _Ed25519PublicKey = None  # type: ignore[assignment,misc]
    _HAS_ED25519 = False
    _ED25519_ERROR = str(_e)

# ─── Colour / Style constants ──────────────────────────────────────────────────

BG       = "#f0f4f8"
HDR_BG   = "#1e3a5f"
HDR_FG   = "#ffffff"
ACCENT   = "#2563eb"
ACCENT2  = "#1d4ed8"
SUCCESS  = "#16a34a"
DANGER   = "#dc2626"
MUTED    = "#6b7280"
ROW_ODD  = "#ffffff"
ROW_EVEN = "#eff6ff"
SEL_BG   = "#bfdbfe"

FONT_UI   = ("Arial", 12)
FONT_SM   = ("Arial", 12)
FONT_LG   = ("Arial", 12, "bold")
FONT_H1   = ("Arial", 12, "bold")
FONT_MONO = ("Arial", 12)

SESSION_TYPES  = ["Individual", "Group", "Couples/Family", "Intake/Evaluation", "Crisis", "Telehealth"]
PLACE_CODES    = [("11 - Office", "11"), ("02 - Telehealth", "02"), ("12 - Home", "12"),
                  ("21 - Inpatient Hospital", "21"), ("22 - Outpatient Hospital", "22"),
                  ("23 - Emergency Room", "23")]
CPT_CODES      = ["90791", "90792", "90832", "90834", "90837", "90845",
                  "90846", "90847", "90853", "90863", "99213", "99214"]
CPT_FEE_SCHEDULE_PREF_KEY = "billing.cpt_fee_schedule"
DEFAULT_CPT_FEES = {
    "90791": 175.00,
    "90792": 200.00,
    "90832": 100.00,
    "90834": 130.00,
    "90837": 160.00,
    "90845": 120.00,
    "90846": 130.00,
    "90847": 140.00,
    "90853": 60.00,
    "90863": 70.00,
    "99213": 110.00,
    "99214": 140.00,
}

STATES = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
          "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
          "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
          "VA","WA","WV","WI","WY","DC"]

GITHUB_LATEST_RELEASE_API = "https://api.github.com/repos/Irish-Coder69/AuraScribe-PSY/releases/latest"
GITHUB_RELEASE_BY_TAG_API = "https://api.github.com/repos/Irish-Coder69/AuraScribe-PSY/releases/tags/{tag}"
GITHUB_RELEASES_LIST_API = "https://api.github.com/repos/Irish-Coder69/AuraScribe-PSY/releases?per_page=25"
GITHUB_RELEASES_PAGE = "https://github.com/Irish-Coder69/AuraScribe-PSY/releases/latest"
UPDATE_TEMP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Temp" / "AuraScribePSYUpdates"
STARTUP_LOG_FILE = APP_ROOT / "startup.log"
STARTUP_BANNER_FILE = "Aura Scribe PSY.jpg"
CMS_TEMPLATE_FILE = APP_ROOT / "CMS1500_template.pdf"
VOSK_MODELS_DIR = APP_ROOT / "models"
CMS_BACK_TEMPLATE_CANDIDATES = (
    APP_ROOT / "CMS1500_template_back.pdf",
    APP_ROOT / "CMS 1500_templete_back.pdf",
)

LICENSE_KEY_PREFIX = "THP1"
LICENSE_PREF_KEY = "license_key"
LICENSE_NAME_PREF_KEY = "license_registered_name"
LICENSE_EMAIL_PREF_KEY = "license_registered_email"
UPDATE_ANNOUNCEMENT_SEEN_PREF_KEY = "ui.update_announcement_seen_version"
UPDATE_ANNOUNCEMENT_NOTES_VERSION_PREF_KEY = "ui.update_announcement_notes_version"
UPDATE_ANNOUNCEMENT_NOTES_BODY_PREF_KEY = "ui.update_announcement_notes_body"

# Screen dimensions populated once at startup by TheraTrakApp.__init__.
# Every dialog reads these instead of calling winfo_screen* individually.
SCREEN_W:     int   = 0
SCREEN_H:     int   = 0
SCREEN_FIT_W: int   = 0        # smallest usable monitor work-area width
SCREEN_FIT_H: int   = 0        # smallest usable monitor work-area height
MACHINE_TYPE: str   = "unknown"  # "laptop", "desktop", or "unknown"
SCREEN_DPI:   int   = 96         # logical pixels per inch (96 = 100 % scaling)
UI_SCALE:     float = 1.0        # SCREEN_DPI / 96
UI_MAX_SCALE: float = 1.0        # highest monitor scale seen at startup
UI_DENSE_MODE: bool = False      # compact spacing/fonts for tighter displays

_PC_SYSTEM_TYPE_LABELS = {
    0: "Unspecified",
    1: "Desktop",
    2: "Mobile/Laptop",
    3: "Workstation",
    4: "Enterprise Server",
    5: "SOHO Server",
    6: "Appliance PC",
    7: "Performance Server",
    8: "Maximum",
}

_CHASSIS_TYPE_LABELS = {
    1: "Other",
    2: "Unknown",
    3: "Desktop",
    4: "Low Profile Desktop",
    5: "Pizza Box",
    6: "Mini Tower",
    7: "Tower",
    8: "Portable",
    9: "Laptop",
    10: "Notebook",
    11: "Handheld",
    12: "Docking Station",
    13: "All in One",
    14: "Sub Notebook",
    15: "Space-Saving",
    16: "Lunch Box",
    17: "Main System Chassis",
    18: "Expansion Chassis",
    19: "Sub Chassis",
    20: "Bus Expansion Chassis",
    21: "Peripheral Chassis",
    22: "Storage Chassis",
    23: "Rack Mount Chassis",
    24: "Sealed-Case PC",
    30: "Tablet",
    31: "Convertible",
    32: "Detachable",
}

_PROBE_SOURCE_LABELS = {
    "none": "No signal",
    "wmi": "Windows hardware class",
    "wmi_mixed": "Windows hardware class (mixed)",
    "power_status": "Windows power status",
}


def _format_pc_system_type(value: object) -> str:
    if value is None:
        return "n/a"
    try:
        num = int(value)
    except Exception:
        return str(value)
    return f"{num} ({_PC_SYSTEM_TYPE_LABELS.get(num, 'Unknown code')})"


def _format_chassis_types(values: object) -> str:
    if not values:
        return "n/a"
    parts = []
    for value in values if isinstance(values, (list, tuple)) else [values]:
        try:
            num = int(value)
        except Exception:
            parts.append(str(value))
            continue
        parts.append(f"{num} ({_CHASSIS_TYPE_LABELS.get(num, 'Unknown code')})")
    return ", ".join(parts) if parts else "n/a"


def _format_battery_flag(value: object) -> str:
    if value is None:
        return "n/a"
    try:
        num = int(value)
    except Exception:
        return str(value)
    if num == 128:
        meaning = "No system battery"
    elif num == 255:
        meaning = "Battery status unknown"
    else:
        meaning = "Battery present"
    return f"{num} ({meaning})"


def _format_probe_source(value: object) -> str:
    key = str(value or "none")
    return _PROBE_SOURCE_LABELS.get(key, key)


def get_cpt_fee_schedule() -> dict[str, float]:
    """Return CPT -> fee map from app preferences merged with defaults."""
    schedule = {code: float(DEFAULT_CPT_FEES.get(code, 0.0)) for code in CPT_CODES}
    raw = db.get_app_preference(CPT_FEE_SCHEDULE_PREF_KEY, "")
    if not raw:
        return schedule

    try:
        payload = json.loads(raw)
    except Exception:
        return schedule

    if not isinstance(payload, dict):
        return schedule

    for code in CPT_CODES:
        if code not in payload:
            continue
        try:
            amount = float(payload.get(code, schedule[code]) or 0.0)
        except Exception:
            continue
        if amount < 0:
            amount = 0.0
        schedule[code] = round(amount, 2)
    return schedule


def save_cpt_fee_schedule(schedule: dict[str, float | int | str]) -> None:
    """Persist CPT fee schedule in app preferences as JSON."""
    cleaned: dict[str, float] = {}
    for code in CPT_CODES:
        try:
            amount = float(schedule.get(code, 0.0) or 0.0)
        except Exception:
            amount = 0.0
        if amount < 0:
            amount = 0.0
        cleaned[code] = round(amount, 2)

    db.set_app_preference(
        CPT_FEE_SCHEDULE_PREF_KEY,
        json.dumps(cleaned, separators=(",", ":")),
    )


def get_cpt_fee_amount(cpt_code: str) -> float | None:
    code = str(cpt_code or "").strip()
    if not code:
        return None
    schedule = get_cpt_fee_schedule()
    if code not in schedule:
        return None
    return float(schedule[code])


def _probe_machine_type() -> dict[str, object]:
    """Return detailed machine-type probe results.

    Uses multiple Windows signals to reduce false positives:
    - Win32_ComputerSystem.PCSystemType
    - Win32_SystemEnclosure.ChassisTypes
    - GetSystemPowerStatus battery presence (fallback)
    """
    result: dict[str, object] = {
        "machine_type": "unknown",
        "pc_system_type": None,
        "chassis_types": [],
        "battery_flag": None,
        "source": "none",
        "wmi_votes": [],
    }
    if sys.platform != "win32":
        return result

    # Prefer WMI-reported hardware class over battery-only heuristics.
    wmi_votes: list[str] = []
    try:
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            (
                "$pc=(Get-CimInstance Win32_ComputerSystem | "
                "Select-Object -First 1 -ExpandProperty PCSystemType);"
                "$ch=(Get-CimInstance Win32_SystemEnclosure | "
                "Select-Object -First 1 -ExpandProperty ChassisTypes);"
                "\"$pc|$($ch -join ',')\""
            ),
        ]
        probe_proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        raw = (probe_proc.stdout or "").strip()
        if probe_proc.returncode == 0 and raw:
            pc_text, _, chassis_text = raw.partition("|")
            try:
                pc_val = int(pc_text.strip())
            except Exception:
                pc_val = -1
            if pc_val >= 0:
                result["pc_system_type"] = pc_val

            # Win32_ComputerSystem.PCSystemType: 2 = Mobile.
            if pc_val == 2:
                wmi_votes.append("laptop")
            elif pc_val in (1, 3, 4, 5, 6, 7, 8):
                wmi_votes.append("desktop")

            chassis_vals = []
            for piece in chassis_text.split(","):
                piece = piece.strip()
                if not piece:
                    continue
                try:
                    chassis_vals.append(int(piece))
                except Exception:
                    continue
            result["chassis_types"] = list(chassis_vals)

            portable_chassis = {8, 9, 10, 11, 12, 14, 18, 21, 30, 31, 32}
            desktop_chassis = {3, 4, 5, 6, 7, 13, 15, 16, 17, 23, 24}
            if any(c in portable_chassis for c in chassis_vals):
                wmi_votes.append("laptop")
            if any(c in desktop_chassis for c in chassis_vals):
                wmi_votes.append("desktop")
    except Exception:
        pass

    result["wmi_votes"] = list(wmi_votes)

    if wmi_votes:
        if "desktop" in wmi_votes and "laptop" not in wmi_votes:
            result["machine_type"] = "desktop"
            result["source"] = "wmi"
            return result
        if "laptop" in wmi_votes and "desktop" not in wmi_votes:
            result["machine_type"] = "laptop"
            result["source"] = "wmi"
            return result

    try:
        import ctypes as _ct

        class _SYSTEM_POWER_STATUS(_ct.Structure):
            _fields_ = [
                ("ACLineStatus",        _ct.c_byte),
                ("BatteryFlag",         _ct.c_byte),   # 128 = no system battery
                ("BatteryLifePercent",  _ct.c_byte),
                ("SystemStatusFlag",    _ct.c_byte),
                ("BatteryLifeTime",     _ct.c_ulong),
                ("BatteryFullLifeTime", _ct.c_ulong),
            ]

        _ps = _SYSTEM_POWER_STATUS()
        if _ct.windll.kernel32.GetSystemPowerStatus(_ct.byref(_ps)):
            battery_flag = int(_ps.BatteryFlag) & 0xFF
            result["battery_flag"] = battery_flag
            if battery_flag == 128:
                result["machine_type"] = "desktop"  # no system battery present
                result["source"] = "power_status"
                return result
            if battery_flag != 255:
                result["machine_type"] = "laptop"   # battery information present
                result["source"] = "power_status"
                return result
    except Exception:
        pass

    if "desktop" in wmi_votes:
        result["machine_type"] = "desktop"
        result["source"] = "wmi_mixed"
        return result
    if "laptop" in wmi_votes:
        result["machine_type"] = "laptop"
        result["source"] = "wmi_mixed"
        return result
    return result


def _detect_machine_type() -> str:
    """Return 'laptop', 'desktop', or 'unknown'."""
    return str(_probe_machine_type().get("machine_type", "unknown") or "unknown")


def _monitor_fit_profile(primary_w: int, primary_h: int, primary_dpi: int) -> dict:
    """Return conservative monitor sizing data for cross-monitor fit.

    On multi-monitor systems, this captures the smallest monitor work-area and
    the highest DPI scale so UI defaults fit when the app/dialog is moved to a
    tighter or higher-scale display.
    """
    profile = {
        "count": 1,
        "min_work_w": max(640, int(primary_w or 1280)),
        "min_work_h": max(480, int(primary_h or 720)),
        "max_scale": max(1.0, float(primary_dpi or 96) / 96.0),
    }
    if sys.platform != "win32":
        return profile

    try:
        import ctypes as _ct
        from ctypes import wintypes as _wt

        class _RECT(_ct.Structure):
            _fields_ = [
                ("left", _wt.LONG),
                ("top", _wt.LONG),
                ("right", _wt.LONG),
                ("bottom", _wt.LONG),
            ]

        class _MONITORINFO(_ct.Structure):
            _fields_ = [
                ("cbSize", _wt.DWORD),
                ("rcMonitor", _RECT),
                ("rcWork", _RECT),
                ("dwFlags", _wt.DWORD),
            ]

        user32 = _ct.windll.user32
        shcore = getattr(_ct.windll, "shcore", None)
        MONITOR_DPI_TYPE_EFFECTIVE = 0
        monitors = []

        _MONITORENUMPROC = _ct.WINFUNCTYPE(
            _wt.BOOL,
            _wt.HANDLE,
            _wt.HDC,
            _ct.POINTER(_RECT),
            _wt.LPARAM,
        )

        @_MONITORENUMPROC
        def _enum_cb(hmon, _hdc, _lprc, _lparam):
            mi = _MONITORINFO()
            mi.cbSize = _ct.sizeof(_MONITORINFO)
            if not user32.GetMonitorInfoW(hmon, _ct.byref(mi)):
                return True

            work_w = int(mi.rcWork.right - mi.rcWork.left)
            work_h = int(mi.rcWork.bottom - mi.rcWork.top)
            dpi = int(primary_dpi or 96)

            if shcore is not None:
                try:
                    dpi_x = _wt.UINT()
                    dpi_y = _wt.UINT()
                    hr = shcore.GetDpiForMonitor(
                        hmon,
                        MONITOR_DPI_TYPE_EFFECTIVE,
                        _ct.byref(dpi_x),
                        _ct.byref(dpi_y),
                    )
                    if hr == 0 and dpi_x.value > 0:
                        dpi = int(dpi_x.value)
                except Exception:
                    pass

            if work_w > 0 and work_h > 0:
                monitors.append((work_w, work_h, dpi))
            return True

        user32.EnumDisplayMonitors(0, 0, _enum_cb, 0)
        if monitors:
            profile["count"] = len(monitors)
            profile["min_work_w"] = max(640, min(m[0] for m in monitors))
            profile["min_work_h"] = max(480, min(m[1] for m in monitors))
            profile["max_scale"] = max(float(m[2]) / 96.0 for m in monitors)
    except Exception:
        pass

    return profile


def _screen_fit(desired_w: int, desired_h: int, pad: int = 80) -> tuple[int, int]:
    """Return (w, h) capped to the available screen minus *pad* on each axis.

    Reads the module-level SCREEN_W / SCREEN_H that are set once at startup.
    Falls back to a live query if they have not been populated yet.
    """
    sw = SCREEN_FIT_W or SCREEN_W
    sh = SCREEN_FIT_H or SCREEN_H
    if sw == 0 or sh == 0:
        try:
            root = tk._default_root  # type: ignore[attr-defined]
            if root is not None:
                sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        except Exception:
            pass
    if sw == 0 or sh == 0:
        return desired_w, desired_h
    return min(desired_w, max(sw - pad, 200)), min(desired_h, max(sh - pad, 150))


def _mousewheel_units(event) -> int:
    """Translate mouse-wheel events to Tk scroll units across platforms."""
    if hasattr(event, "num"):
        if event.num == 4:
            return -1
        if event.num == 5:
            return 1
    delta = int(getattr(event, "delta", 0) or 0)
    if delta == 0:
        return 0
    units = int(-delta / 120)
    return units if units != 0 else (-1 if delta > 0 else 1)


def _bind_mousewheel_recursive(root_widget, yview_scroll):
    """Bind wheel scrolling for a widget tree to a shared vertical scroller."""
    def _on_mousewheel(event):
        units = _mousewheel_units(event)
        if units:
            yview_scroll(units, "units")
            return "break"
        return None

    def _bind_tree(widget):
        try:
            widget.bind("<MouseWheel>", _on_mousewheel, add="+")
            widget.bind("<Button-4>", _on_mousewheel, add="+")
            widget.bind("<Button-5>", _on_mousewheel, add="+")
        except Exception:
            return
        for child in widget.winfo_children():
            _bind_tree(child)

    _bind_tree(root_widget)
LICENSE_ACTIVATED_AT_PREF_KEY = "license_activated_at"
LICENSE_TRIAL_START_PREF_KEY = "license_trial_start"
LICENSE_TRIAL_DAYS = 14

# Build lookup mapping for place of service codes
_PLACE_CODE_MAP = {p[0]: p[1] for p in PLACE_CODES}
_PLACE_CODE_REVERSE = {p[1]: p[0] for p in PLACE_CODES}
PATIENT_DX_KEYS = [f"dx{i}" for i in range(1, 13)]
CMS_OVERLAY_ANCHOR_OPTIONS = [
    ("1 Insurance Type", "box_1"),
    ("1a Insured ID", "box_1a"),
    ("1b Group #", "box_1b"),
    ("2 Patient Name", "box_2"),
    ("3 Patient DOB", "box_3_dob"),
    ("3 Sex M", "box_3_sex_m"),
    ("3 Sex F", "box_3_sex_f"),
    ("4 Insured Name", "box_4"),
    ("5 Patient Street", "box_5_street"),
    ("5 Patient City", "box_5_city"),
    ("5 Patient State", "box_5_state"),
    ("5 Patient ZIP", "box_5_zip"),
    ("5 Patient Phone", "box_5_phone"),
    ("6 Patient Relation", "box_6"),
    ("7 Insured Street", "box_7_street"),
    ("7 Insured City", "box_7_city"),
    ("7 Insured State", "box_7_state"),
    ("7 Insured ZIP", "box_7_zip"),
    ("7 Insured Phone", "box_7_phone"),
    ("9 Other Insured", "box_9"),
    ("10 Employment/Accident", "box_10"),
    ("10d Claim Codes", "box_10d"),
    ("11 Insured Plan", "box_11"),
    ("11a Insured DOB", "box_11a"),
    ("11 Insured Sex M", "box_11_sex_m"),
    ("11 Insured Sex F", "box_11_sex_f"),
    ("11d Other Benefit Plan", "box_11d"),
    ("12 Patient Signature", "box_12"),
    ("13 Insured Signature", "box_13"),
    ("14 Illness Date", "box_14_illness_date"),
    ("14 Illness Date QUAL", "box_14_illness_qual"),
    ("15 Other Date", "box_15"),
    ("15 Other Date QUAL", "box_15_qual"),
    ("16 Unable to Work", "box_16"),
    ("17 Referring Name", "box_17"),
    ("17a Referral NPI", "box_17a"),
    ("17b Referral ID", "box_17b"),
    ("18 Hospitalization Dates", "box_18"),
    ("19 Additional Claim Info", "box_19"),
    ("20 Outside Lab", "box_20"),
    ("21 Diagnosis", "box_21"),
    ("22 Resubmission Code", "box_22"),
    ("23 Prior Auth Number", "box_23"),
    ("24A Service Date From", "box_24a_from"),
    ("24A Service Date To", "box_24a_to"),
    ("24B Service POS", "box_24b"),
    ("24C EMG", "box_24c"),
    ("24D Procedure/Modifier", "box_24d"),
    ("24E Diagnosis", "box_24e"),
    ("24F Charges", "box_24f"),
    ("24G Units", "box_24g"),
    ("24I ID Qualifier", "box_24i"),
    ("24J Rendering Provider", "box_24j"),
    ("24J Taxonomy", "box_24j_tax"),
    ("25 Federal Tax ID", "box_25"),
    ("25 SSN Checkbox", "box_25_ssn"),
    ("25 EIN Checkbox", "box_25_ein"),
    ("26 Patient Account #", "box_26"),
    ("27 Accept Assignment", "box_27"),
    ("28 Total Charge", "box_28"),
    ("29 Amount Paid", "box_29"),
    ("31 Provider Signature", "box_31"),
    ("31 Provider Date", "box_31_date"),
    ("32a Facility Name", "box_32a"),
    ("32 Facility Street", "box_32_street"),
    ("32 Facility City", "box_32_city"),
    ("32 Facility State", "box_32_state"),
    ("32 Facility ZIP", "box_32_zip"),
    ("32 Facility NPI", "box_32_npi"),
    ("32 Facility Taxonomy", "box_32_tax"),
    ("32b Facility ID Qual", "box_32b"),
    ("33a Billing Name", "box_33a"),
    ("33 Billing Street", "box_33_street"),
    ("33 Billing City", "box_33_city"),
    ("33 Billing State", "box_33_state"),
    ("33 Billing ZIP", "box_33_zip"),
    ("33 Billing Phone", "box_33_phone"),
    ("33 Billing NPI", "box_33_npi"),
    ("33 Billing Taxonomy", "box_33_tax"),
    ("33b Billing ID Qual", "box_33b"),
]


# ─── Utilities ─────────────────────────────────────────────────────────────────


def _load_cms_overlay_box_offsets(raw_value: object) -> dict[str, dict[str, float]]:
    """Parse persisted per-anchor overlay offsets (inches)."""
    allowed = {key for _, key in CMS_OVERLAY_ANCHOR_OPTIONS}
    parsed: dict[str, dict[str, float]] = {}

    if isinstance(raw_value, dict):
        candidate = raw_value
    else:
        raw_text = str(raw_value or "").strip()
        if not raw_text:
            return parsed
        try:
            candidate = json.loads(raw_text)
        except Exception:
            return parsed

    if not isinstance(candidate, dict):
        return parsed

    for key, value in candidate.items():
        if not isinstance(value, dict):
            continue
        try:
            x_val = float(value.get("x", 0.0) or 0.0)
            y_val = float(value.get("y", 0.0) or 0.0)
        except Exception:
            continue
        if abs(x_val) < 1e-9 and abs(y_val) < 1e-9:
            continue

        clamped = {
            "x": max(-2.0, min(2.0, x_val)),
            "y": max(-2.0, min(2.0, y_val)),
        }

        # Backward-compat for older builds where Box 14 used a single anchor key.
        if key == "box_14":
            parsed.setdefault("box_14_illness_date", dict(clamped))
            parsed.setdefault("box_14_illness_qual", dict(clamped))
            continue

        # Backward-compat for older builds where Box 15 used no qualifier anchor.
        if key == "box_15":
            parsed.setdefault("box_15", dict(clamped))
            parsed.setdefault("box_15_qual", dict(clamped))
            continue

        # Backward-compat for older builds where Box 24A used a single anchor key.
        if key == "box_24a":
            parsed.setdefault("box_24a_from", dict(clamped))
            parsed.setdefault("box_24a_to", dict(clamped))
            continue

        # Backward-compat for older builds where Box 25 used a single anchor key.
        if key == "box_25_type":
            parsed.setdefault("box_25_ssn", dict(clamped))
            parsed.setdefault("box_25_ein", dict(clamped))
            continue

        if key not in allowed:
            continue

        parsed[key] = clamped

    return parsed


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64u_decode(raw: str) -> bytes:
    padded = raw + ("=" * ((4 - len(raw) % 4) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii"))


# Ed25519 public key – used only for license signature verification.
# The private key is NEVER present in the application binary.
_LICENSE_PUBLIC_KEY: bytes = bytes.fromhex(
    "557ecad262753de008f00bfba843d01e086344ea13e90afb6b90fd4b601a87d1"
)

# V3 compact key constants
_V3_BASE_DATE = date(2026, 1, 1)
_V3_PLAN_NAMES = {0: "Developer/Test", 1: "Solo Practice", 2: "Group Practice"}


def _v3_date_from_days(n: int) -> date:
    return _V3_BASE_DATE + timedelta(days=n)


def _current_machine_code() -> str:
    source = "|".join([
        os.environ.get("COMPUTERNAME", "").strip().upper(),
        hex(uuid.getnode()),
        os.environ.get("PROCESSOR_IDENTIFIER", "").strip().upper(),
    ])
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16].upper()


def _validate_license_key(license_key: str, machine_code: str) -> tuple[bool, str, dict[str, str]]:
    stripped = re.sub(r"\s+", "", str(license_key or "").strip())
    if not stripped:
        return False, "No license key entered.", {}

    if not _HAS_ED25519 or _Ed25519PublicKey is None:
        return False, f"Cryptographic library unavailable: {_ED25519_ERROR}", {}
    pub = _Ed25519PublicKey.from_public_bytes(_LICENSE_PUBLIC_KEY)

    # ── V2 legacy: THP1.<base64url_json>.<base64url_sig> ────────────────────
    if stripped.upper().startswith("THP1."):
        parts = stripped.split(".")
        if len(parts) != 3:
            return False, "License key format is invalid.", {}
        try:
            payload_raw = _b64u_decode(parts[1])
            signature_raw = _b64u_decode(parts[2])
        except Exception:
            return False, "License key payload could not be decoded.", {}
        try:
            pub.verify(signature_raw, payload_raw)
        except Exception:
            return False, "License key signature is invalid.", {}
        try:
            payload = json.loads(payload_raw.decode("utf-8"))
        except Exception:
            return False, "License key data is unreadable.", {}
        if not isinstance(payload, dict):
            return False, "License key payload is invalid.", {}
        bound_machine = str(payload.get("mc") or "").strip().upper()
        if bound_machine and bound_machine != machine_code.strip().upper():
            return False, "This license key is for a different computer.", {}
        exp_text = str(payload.get("exp") or "").strip()
        if exp_text:
            try:
                if date.today() > datetime.strptime(exp_text, "%Y-%m-%d").date():
                    return False, "This license key has expired.", {}
            except ValueError:
                return False, "License expiration date is invalid.", {}
        return True, "License key is valid.", {
            "name": str(payload.get("n") or "").strip(),
            "email": str(payload.get("e") or "").strip(),
            "machine": bound_machine,
            "expires": exp_text,
        }

    # ── V3 compact: THP1-XXXXXX-XXXXXX-... (base32 blocks) ─────────────────
    body = re.sub(r"^THP1[-\s]*", "", stripped, flags=re.IGNORECASE)
    clean_b32 = re.sub(r"[^A-Z2-7]", "", body.upper())
    padded_b32 = clean_b32 + "=" * ((8 - len(clean_b32) % 8) % 8)
    try:
        raw = base64.b32decode(padded_b32)
    except Exception:
        return False, "License key could not be decoded.", {}
    if len(raw) < 82:  # 18 payload + 64 sig
        return False, "License key format is invalid.", {}
    payload_bytes, sig_bytes = raw[:18], raw[18:82]
    try:
        pub.verify(sig_bytes, payload_bytes)
    except Exception:
        return False, "License key signature is invalid.", {}
    plan = payload_bytes[1]
    expiry_days = struct.unpack(">H", payload_bytes[8:10])[0]
    mc_bytes = payload_bytes[10:18]
    if mc_bytes != b"\x00" * 8:
        cur_mc_hex = machine_code.strip().upper()[:16].ljust(16, "0")
        try:
            cur_mc_bytes = bytes.fromhex(cur_mc_hex)
        except ValueError:
            cur_mc_bytes = b"\x00" * 8
        if mc_bytes != cur_mc_bytes:
            return False, "This license key is for a different computer.", {}
    exp_str = ""
    if expiry_days > 0:
        exp_date = _v3_date_from_days(expiry_days)
        if date.today() > exp_date:
            return False, "This license key has expired.", {}
        exp_str = exp_date.isoformat()
    plan_name = _V3_PLAN_NAMES.get(plan, f"Plan {plan}")
    return True, "License key is valid.", {
        "name": plan_name,
        "email": "",
        "machine": mc_bytes.hex().upper() if mc_bytes != b"\x00" * 8 else "",
        "expires": exp_str,
    }


def _overlay_box_offsets_inches_to_points(offsets: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for key, val in offsets.items():
        out[key] = {
            "x": float(val.get("x", 0.0) or 0.0) * 72.0,
            "y": float(val.get("y", 0.0) or 0.0) * 72.0,
        }
    return out

def _extract_place_code(place_value: str, default: str = "11") -> str:
    """Extract place of service code from display format or return code if already code."""
    if not place_value:
        return default
    # Normalize typographic dashes to ASCII hyphen before map lookup
    normalized = place_value.replace('\u2013', '-').replace('\u2014', '-').replace('\u2212', '-')
    if normalized in _PLACE_CODE_MAP:
        return _PLACE_CODE_MAP[normalized]
    if place_value in _PLACE_CODE_MAP:
        return _PLACE_CODE_MAP[place_value]
    return place_value


def _resolve_cms_back_template() -> Path | None:
    for candidate in CMS_BACK_TEMPLATE_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def _get_default_printer_name() -> str:
    if not sys.platform.startswith("win"):
        return ""

    # Avoid direct Winspool DLL calls in frozen builds; query via shell instead.
    commands = [
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "(Get-CimInstance Win32_Printer | Where-Object {$_.Default} | Select-Object -First 1 -ExpandProperty Name)",
        ],
        [
            "pwsh.exe",
            "-NoProfile",
            "-Command",
            "(Get-CimInstance Win32_Printer | Where-Object {$_.Default} | Select-Object -First 1 -ExpandProperty Name)",
        ],
    ]

    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                name = (result.stdout or "").strip()
                if name:
                    return name
        except OSError:
            continue

    return ""


def _open_printer_preferences(printer_name: str) -> bool:
    if not sys.platform.startswith("win") or not printer_name:
        return False
    try:
        result = subprocess.run(
            ["rundll32.exe", "printui.dll,PrintUIEntry", "/e", "/n", printer_name],
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode == 0
    except OSError:
        return False


def _get_place_display(place_code: str) -> str:
    """Get display format for place of service code, or return code if not found."""
    if not place_code:
        return "11 - Office"
    if place_code in _PLACE_CODE_REVERSE:
        return _PLACE_CODE_REVERSE[place_code]
    return place_code


def _extract_executable_from_command(raw: str) -> str:
    """Extract an executable path from a Windows command string."""
    txt = str(raw or "").strip().strip('"')
    if not txt:
        return ""

    txt = os.path.expandvars(txt)
    if ".exe," in txt.lower():
        txt = txt.split(",", 1)[0].strip().strip('"')

    if txt.lower().endswith(".exe") and Path(txt).exists():
        return txt

    m = re.search(r'"([A-Za-z]:\\[^\"]+?\.exe)"', txt, flags=re.IGNORECASE)
    if m:
        p = os.path.expandvars(m.group(1))
        if Path(p).exists():
            return p

    m = re.search(r'([A-Za-z]:\\[^\s]+?\.exe)', txt, flags=re.IGNORECASE)
    if m:
        p = os.path.expandvars(m.group(1))
        if Path(p).exists():
            return p

    return ""


def _resolve_windows_shortcut_target(path_text: str) -> str:
    """Resolve a .lnk file to its target executable when possible."""
    if os.name != "nt":
        return ""

    shortcut = Path(str(path_text or "").strip().strip('"'))
    if not shortcut.exists() or shortcut.suffix.lower() != ".lnk":
        return ""

    # Use WScript.Shell so we can convert shortcuts into real launch targets.
    ps_path = str(shortcut).replace("'", "''")
    ps_cmd = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('"
        + ps_path
        + "');"
        "[pscustomobject]@{TargetPath=$s.TargetPath;Arguments=$s.Arguments}|ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return ""

    raw = (result.stdout or "").strip()
    if not raw:
        return ""

    try:
        payload = json.loads(raw)
    except Exception:
        return ""

    if not isinstance(payload, dict):
        return ""

    target = _extract_executable_from_command(str(payload.get("TargetPath") or ""))
    if target:
        return target

    return ""


def _normalize_dictation_launch_path(path_text: str) -> str:
    """Normalize detected launch path to a concrete executable when possible."""
    raw = str(path_text or "").strip().strip('"')
    if not raw:
        return ""

    raw = os.path.expandvars(raw)
    candidate = Path(raw)
    if candidate.suffix.lower() == ".lnk":
        resolved = _resolve_windows_shortcut_target(raw)
        if resolved:
            return resolved

    exe_from_cmd = _extract_executable_from_command(raw)
    if exe_from_cmd:
        return exe_from_cmd

    if candidate.exists():
        return str(candidate)

    return ""


def _find_dictation_apps_systemwide() -> list[tuple[str, str]]:
    """Discover dictation software by scanning installed software metadata and common install locations on Windows."""
    built_in = [("Windows Built-in Dictation (Win+H)", "")]
    if os.name != "nt":
        return built_in

    import winreg

    found: list[tuple[str, str]] = []
    located: set[str] = set()

    keywords = (
        "dictat", "dictation", "speech", "voice", "transcrib", "stt",
        "dragon", "nuance", "whisper", "speechnotes", "otter",
        "serenade", "talon", "voiceaccess", "speech recognition",
    )

    exe_hints = (
        "natspeak.exe", "dragon.exe", "whisper-dictate.exe", "whisperdictate.exe",
        "speechnotes.exe", "otter.exe", "speechux.exe", "voiceaccess.exe",
    )

    def _has_keyword(text: str) -> bool:
        txt = (text or "").lower()
        return any(k in txt for k in keywords)

    def _label_from_text(text: str) -> str:
        txt = (text or "").lower()
        if "dragon" in txt or "nuance" in txt or "naturallyspeaking" in txt:
            return "Dragon NaturallySpeaking"
        if "whisper" in txt:
            return "Whisper Dictate"
        if "speechnotes" in txt:
            return "SpeechNotes"
        if "otter" in txt:
            return "Otter.ai Desktop"
        if "voice access" in txt:
            return "Windows Voice Access"
        if "speech" in txt and "windows" in txt:
            return "Windows Speech Recognition"
        cleaned = (text or "").strip()
        return cleaned if cleaned else "Detected Dictation App"

    def _label_from_path(path: Path) -> str:
        parts = [part for part in path.parts if part]
        for part in reversed(parts):
            part_low = part.lower()
            if _has_keyword(part_low):
                return _label_from_text(part)
            if any(h.replace(".exe", "") in part_low for h in exe_hints):
                return _label_from_text(part)
        return _label_from_text(path.stem or path.name)

    def _extract_exe_path(raw: str) -> str:
        return _extract_executable_from_command(raw)

    def _add(label: str, p: str | Path):
        path_text = str(p or "").strip().strip('"')
        if not path_text:
            return

        normalized = _normalize_dictation_launch_path(path_text)
        if not normalized:
            return

        low = normalized.lower()
        # Filter out uninstallers so we keep real app launchers.
        if any(tok in Path(normalized).name.lower() for tok in ("unins", "uninstall", "remove")):
            return

        if not low.endswith((".exe", ".appref-ms", ".url")):
            return

        key = low
        if key in located:
            return
        located.add(key)
        found.append((label, normalized))

    def _scan_directory(root: Path, *, max_depth: int = 4, max_files: int = 4000, include_shortcuts: bool = True):
        if not root or not root.exists() or not root.is_dir():
            return

        seen_files = 0
        try:
            root = root.resolve()
        except Exception:
            pass

        for dirpath, dirnames, filenames in os.walk(root):
            current_dir = Path(dirpath)
            try:
                depth = len(current_dir.relative_to(root).parts)
            except Exception:
                depth = 0
            if depth >= max_depth:
                dirnames[:] = []

            dir_text = str(current_dir).lower()
            dir_matches = _has_keyword(dir_text) or any(h in dir_text for h in exe_hints)

            for fname in filenames:
                seen_files += 1
                if seen_files > max_files:
                    return

                file_path = current_dir / fname
                name_low = fname.lower()
                if name_low.endswith(".exe"):
                    if dir_matches or _has_keyword(name_low) or any(h in name_low for h in exe_hints):
                        _add(_label_from_path(file_path), file_path)
                elif include_shortcuts and name_low.endswith((".lnk", ".appref-ms", ".url")):
                    if dir_matches or _has_keyword(name_low) or any(k in name_low for k in keywords):
                        _add(_label_from_path(file_path), file_path)

    def _scan_processes():
        if os.name != "nt":
            return

        ps_cmd = (
            "$p=Get-CimInstance Win32_Process | Select-Object Name,ExecutablePath,CommandLine | ConvertTo-Json -Depth 2;"
            "if($p){$p}"
        )
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=12,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            return

        raw = (proc.stdout or "").strip()
        if not raw:
            return

        try:
            payload = json.loads(raw)
        except Exception:
            return

        rows = payload if isinstance(payload, list) else [payload]
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("Name") or "")
            exe_path = str(row.get("ExecutablePath") or "")
            cmdline = str(row.get("CommandLine") or "")
            blob = " ".join(part for part in (name, exe_path, cmdline) if part).strip()
            if not blob or not _has_keyword(blob):
                continue

            candidate = _extract_exe_path(exe_path) or _extract_exe_path(cmdline)
            if candidate:
                _add(_label_from_text(blob), candidate)

    # Fast known-path checks first.
    pf = Path(os.environ.get("ProgramFiles", ""))
    pfx86 = Path(os.environ.get("ProgramFiles(x86)", ""))
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    known_paths = [
        ("Dragon NaturallySpeaking", pf / "Nuance" / "NaturallySpeaking15" / "Program" / "natspeak.exe"),
        ("Dragon NaturallySpeaking", pfx86 / "Nuance" / "NaturallySpeaking15" / "Program" / "natspeak.exe"),
        ("Whisper Dictate", local / "Programs" / "whisper-dictate" / "whisper-dictate.exe"),
        ("SpeechNotes", local / "Programs" / "SpeechNotes" / "speechnotes.exe"),
        ("Otter.ai Desktop", local / "Programs" / "Otter" / "otter.exe"),
    ]
    for label, p in known_paths:
        _add(label, p)

    # Scan common shortcut folders and install locations so apps that do not
    # register cleanly in Add/Remove Programs can still be discovered.
    shortcut_roots = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("PUBLIC", "")) / "Desktop",
        Path(os.environ.get("USERPROFILE", "")) / "Desktop",
        Path(os.environ.get("USERPROFILE", "")) / "Documents",
        Path(os.environ.get("USERPROFILE", "")) / "Downloads",
        Path(os.environ.get("USERPROFILE", "")) / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("USERPROFILE", "")) / "AppData" / "Local" / "Programs",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Packages",
        Path(os.environ.get("OneDrive", "")),
        Path(os.environ.get("OneDriveCommercial", "")),
    ]
    for root in shortcut_roots:
        _scan_directory(root, max_depth=3, max_files=2000, include_shortcuts=True)

    install_roots = [
        pf,
        pfx86,
        local / "Programs",
        local / "Microsoft",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft",
    ]
    for root in install_roots:
        _scan_directory(root, max_depth=4, max_files=5000, include_shortcuts=False)

    # Scan running processes so portable or per-user dictation apps are still
    # discovered even when they are not installed in the usual folders.
    _scan_processes()

    # Scan PATH entries for portable dictation apps.
    path_env = os.environ.get("PATH", "")
    for raw_dir in path_env.split(os.pathsep):
        if not raw_dir:
            continue
        try:
            path_dir = Path(raw_dir.strip().strip('"'))
        except Exception:
            continue
        if not path_dir.exists() or not path_dir.is_dir():
            continue
        try:
            for exe_name in exe_hints:
                candidate = path_dir / exe_name
                if candidate.exists():
                    _add(_label_from_path(candidate), candidate)
        except OSError:
            continue

    # Scan all App Paths entries (not just a fixed whitelist).
    app_paths_root = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, app_paths_root) as base:
                i = 0
                while True:
                    try:
                        sub_name = winreg.EnumKey(base, i)
                        i += 1
                    except OSError:
                        break

                    try:
                        with winreg.OpenKey(base, sub_name) as sk:
                            default_val, _ = winreg.QueryValueEx(sk, "")
                    except OSError:
                        default_val = ""

                    candidate = str(default_val or "").strip().strip('"')
                    blob = f"{sub_name} {candidate}".strip()
                    if not _has_keyword(blob):
                        continue

                    exe = _extract_exe_path(candidate)
                    if exe:
                        _add(_label_from_text(blob), exe)
        except OSError:
            pass

    # Scan installed software (all uninstall entries) and infer executable paths.
    uninstall_roots = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    )
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for root in uninstall_roots:
            try:
                with winreg.OpenKey(hive, root) as base:
                    i = 0
                    while True:
                        try:
                            sub_name = winreg.EnumKey(base, i)
                            i += 1
                        except OSError:
                            break

                        try:
                            with winreg.OpenKey(base, sub_name) as sk:
                                display_name = str(winreg.QueryValueEx(sk, "DisplayName")[0])
                                publisher = str(winreg.QueryValueEx(sk, "Publisher")[0]) if True else ""
                                install_location = str(winreg.QueryValueEx(sk, "InstallLocation")[0]) if True else ""
                                display_icon = str(winreg.QueryValueEx(sk, "DisplayIcon")[0]) if True else ""
                                uninstall_string = str(winreg.QueryValueEx(sk, "UninstallString")[0]) if True else ""
                                quiet_uninstall = str(winreg.QueryValueEx(sk, "QuietUninstallString")[0]) if True else ""
                        except OSError:
                            continue

                        blob = " ".join([
                            display_name or "", publisher or "", sub_name or "",
                            install_location or "", display_icon or "", uninstall_string or "", quiet_uninstall or "",
                        ]).strip()
                        if not _has_keyword(blob):
                            continue

                        label = _label_from_text(display_name or blob)
                        for candidate in (display_icon, uninstall_string, quiet_uninstall):
                            exe = _extract_exe_path(candidate)
                            if exe:
                                _add(label, exe)

                        if install_location:
                            base_path = Path(install_location)
                            for exe_name in exe_hints:
                                _add(label, base_path / exe_name)
            except OSError:
                pass

    def _dragon_first(item):
        lbl = item[0].lower()
        if "dragon" in lbl or "naturallyspeaking" in lbl or "natspeak" in (item[1] or "").lower():
            return (0, lbl)
        return (1, lbl)

    found.sort(key=_dragon_first)
    return built_in + found


def _append_startup_log(message: str):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with STARTUP_LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except OSError:
        pass


def _startup_self_check():
    _append_startup_log("=== Application startup ===")
    _append_startup_log(f"Executable: {sys.executable}")
    _append_startup_log(f"Python: {sys.version.split()[0]}")
    _append_startup_log(f"App root: {APP_ROOT}")
    _append_startup_log(f"CWD: {Path.cwd()}")

    checks = [
        ("ICON_FILE", ICON_FILE),
        ("VERSION_FILE", VERSION_FILE),
        ("DB_FILE", DB_FILE),
    ]
    for name, path in checks:
        _append_startup_log(f"{name}: {'OK' if path.exists() else 'MISSING'} ({path})")


def _install_crash_logger():
    def _handle_uncaught(exc_type, exc_value, exc_tb):
        _append_startup_log("Uncaught exception:")
        _append_startup_log("".join(traceback.format_exception(exc_type, exc_value, exc_tb)).rstrip())
        try:
            messagebox.showerror(
                "Aura Scribe PSY Error",
                "An unexpected error occurred.\n\n"
                f"Details were written to:\n{STARTUP_LOG_FILE}"
            )
        except Exception:
            pass

    sys.excepthook = _handle_uncaught


def ttk_style():
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    _fs = FONT_UI[1]  # honours adaptive size set by TheraTrakApp.__init__
    _btn_pad = 4 if UI_DENSE_MODE else 6
    _entry_pad = 4 if UI_DENSE_MODE else 5
    _tab_pad = [10, 5] if UI_DENSE_MODE else [12, 6]
    style.master.option_add("*Font",       ("Arial", _fs))
    style.master.option_add("*Text.Font",  ("Arial", _fs))
    style.master.option_add("*Entry.Font", ("Arial", _fs))
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, font=FONT_UI)
    style.configure("TButton", font=FONT_UI, padding=_btn_pad)
    style.configure("TEntry", font=FONT_UI, padding=_entry_pad)
    style.configure("TCombobox", font=FONT_UI)
    style.configure("TNotebook", background=HDR_BG, tabmargins=[2, 4, 2, 0])
    style.configure("TNotebook.Tab", background=HDR_BG, foreground="white", font=("Arial", _fs, "bold"), padding=_tab_pad)
    style.map("TNotebook.Tab", background=[("selected", BG), ("active", ACCENT)], foreground=[("selected", HDR_BG), ("active", "white")])
    style.configure("Accent.TButton", background=ACCENT, foreground="white", font=("Arial", _fs, "bold"), padding=_btn_pad + 1)
    style.map("Accent.TButton", background=[("active", ACCENT2), ("pressed", ACCENT2)])
    style.configure("Danger.TButton", background=DANGER, foreground="white", font=("Arial", _fs, "bold"), padding=_btn_pad + 1)
    # Derive row height from actual font metrics so text is not clipped on
    # high-DPI laptop displays.
    _font_metrics = tkFont.Font(root=style.master, font=FONT_UI).metrics()
    _line_h = int(_font_metrics.get("linespace", 16))
    _row_h = max(26 if UI_DENSE_MODE else 28, _line_h + (10 if UI_DENSE_MODE else 12))
    style.configure("Treeview", font=FONT_UI, rowheight=_row_h, background=ROW_ODD, fieldbackground=ROW_ODD)
    style.configure("Treeview.Heading", font=("Arial", _fs, "bold"), background=HDR_BG, foreground="white", padding=(8, 6))
    style.map("Treeview", background=[("selected", SEL_BG)], foreground=[("selected", "#1e3a5f")])
    return style


def lframe(parent, text, **kw):
    """Labelled ttk.LabelFrame with consistent styling."""
    f = ttk.LabelFrame(parent, text=text, padding=(6 if UI_DENSE_MODE else 8), **kw)
    return f


def _sc(n: int) -> int:
    """Scale a pixel column-width value by the current display DPI factor."""
    return max(1, int(n * UI_SCALE))


def btn(parent, text, cmd, style="TButton", **kw):
    return ttk.Button(parent, text=text, command=cmd, style=style, **kw)


def labeled_entry(parent, label, row, col=0, width=20, colspan=1):
    """Place a Label + Entry pair at grid position (row, col)."""
    ttk.Label(parent, text=label).grid(row=row, column=col, sticky="e", padx=(4, 2), pady=2)
    var = tk.StringVar()
    e = ttk.Entry(parent, textvariable=var, width=width)
    e.grid(row=row, column=col + 1, sticky="ew", padx=(0, 8), pady=2, columnspan=colspan)
    return var, e


def labeled_combo(parent, label, values, row, col=0, width=18):
    ttk.Label(parent, text=label).grid(row=row, column=col, sticky="e", padx=(4, 2), pady=2)
    var = tk.StringVar()
    c = ttk.Combobox(parent, textvariable=var, values=values, width=width, state="readonly")
    c.grid(row=row, column=col + 1, sticky="ew", padx=(0, 8), pady=2)
    return var, c


def current_date_str():
    return date.today().strftime("%Y-%m-%d")


def fmt_date(d: str) -> str:
    """YYYY-MM-DD -> MM/DD/YYYY display string."""
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
    except (ValueError, TypeError):
        return d or ""


def fmt_money(v) -> str:
    try:
        return f"${float(v):.2f}"
    except (ValueError, TypeError):
        return "$0.00"


def apply_window_icon(window):
    """Apply icon and ensure window control box (minimize/maximize) is visible."""
    try:
        if ICON_FILE.exists():
            window.iconbitmap(default=str(ICON_FILE))
    except tk.TclError:
        pass
    if sys.platform == "win32":
        def _restore_and_schedule():
            """Restore minimize/maximize styles and reschedule to keep them intact."""
            try:
                import ctypes
                user32         = ctypes.windll.user32
                GWL_STYLE      = -16
                GWL_EXSTYLE    = -20
                WS_MINIMIZEBOX = 0x00020000
                WS_MAXIMIZEBOX = 0x00010000
                WS_EX_TOOLWINDOW = 0x00000080
                SWP_FLAGS      = 0x0037
                hwnd = window.winfo_id()
                if not hwnd:
                    return
                # Get root hwnd from child (winfo_id returns TkChild window)
                root = user32.GetAncestor(hwnd, 2)
                if root:
                    hwnd = root
                # Get current styles and set minimize/maximize unconditionally.
                # Use bitwise OR to merge, never clear existing flags to avoid conflicts.
                cur = user32.GetWindowLongW(hwnd, GWL_STYLE)
                new_style = cur | 0x00C00000 | 0x00080000 | WS_MINIMIZEBOX | WS_MAXIMIZEBOX
                if new_style != cur:
                    user32.SetWindowLongW(hwnd, GWL_STYLE, new_style)
                # Clear WS_EX_TOOLWINDOW from extended styles - it disables minimize.
                cur_ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                new_ex = cur_ex & ~WS_EX_TOOLWINDOW
                if new_ex != cur_ex:
                    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_ex)
                # Force frame redraw to apply the new styles immediately.
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
            except Exception:
                pass

        # Ensure the window is created before we try to get winfo_id().
        window.update_idletasks()
        # Apply immediately once window exists, then repeatedly at increasing intervals
        # to survive all tkinter state changes (state(), transient(), grab_set(), etc).
        for delay_ms in [10, 50, 150, 300, 600]:
            window.after(delay_ms, _restore_and_schedule)


def _load_startup_banner_image(width: int, height: int):
    if Image is None or ImageTk is None:
        return None

    candidates = [
        APP_ROOT / STARTUP_BANNER_FILE,
        ASSETS_DIR / STARTUP_BANNER_FILE,
        Path.cwd() / STARTUP_BANNER_FILE,
        Path.home() / "Pictures" / "Aura Scribe PSY" / STARTUP_BANNER_FILE,
    ]

    for candidate in candidates:
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            with Image.open(candidate) as source:
                source = source.convert("RGB")
                if source.width <= 0 or source.height <= 0:
                    continue
                scale = min(width / source.width, height / source.height)
                new_w = max(1, int(source.width * scale))
                new_h = max(1, int(source.height * scale))
                resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC)
                resized = source.resize((new_w, new_h), resample)
                canvas = Image.new("RGB", (width, height), (17, 40, 60))
                off_x = (width - new_w) // 2
                off_y = (height - new_h) // 2
                canvas.paste(resized, (off_x, off_y))
            return ImageTk.PhotoImage(canvas)
        except Exception:
            continue

    return None


class StartupLoadingScreen(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        apply_window_icon(self)
        self.title("Aura Scribe PSY")
        self.resizable(False, False)
        self.configure(bg="#f5f7fa")
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self._win_w = min(740, max(560, screen_w - 160))
        self._header_h = 300 if screen_h >= 900 else 220

        hdr = tk.Canvas(self, width=self._win_w, height=self._header_h, highlightthickness=0)
        hdr.pack(fill="x")
        banner_photo = _load_startup_banner_image(self._win_w, self._header_h)
        if banner_photo is not None:
            hdr.create_image(self._win_w // 2, self._header_h // 2, image=banner_photo, anchor="center")
            hdr.image = banner_photo
            hdr.create_rectangle(0, 0, self._win_w, self._header_h, outline="#3a8cc3", width=2)
        else:
            c_top = (110, 195, 232)
            c_bot = (58, 140, 195)
            for i in range(self._header_h):
                t = i / max(1, self._header_h - 1)
                r = int(c_top[0] + (c_bot[0] - c_top[0]) * t)
                g = int(c_top[1] + (c_bot[1] - c_top[1]) * t)
                b = int(c_top[2] + (c_bot[2] - c_top[2]) * t)
                hdr.create_line(0, i, self._win_w, i, fill=f"#{r:02x}{g:02x}{b:02x}")
            hdr.create_text(
                self._win_w // 2,
                self._header_h // 2 - 8,
                text="Aura Scribe PSY",
                font=("Segoe UI", 18, "bold"),
                fill="white",
                anchor="center",
            )
            hdr.create_text(
                self._win_w // 2,
                self._header_h // 2 + 16,
                text="Loading...",
                font=("Segoe UI", 10),
                fill="#d6eef8",
                anchor="center",
            )

        tk.Frame(self, bg="#3a8cc3", height=3).pack(fill="x")

        body = tk.Frame(self, bg="#f5f7fa", padx=22, pady=16)
        body.pack(fill="both", expand=True)

        self._status_var = tk.StringVar(value="Starting Aura Scribe PSY...")
        tk.Label(
            body,
            textvariable=self._status_var,
            font=("Segoe UI", 10),
            bg="#f5f7fa",
            fg="#1a2535",
            anchor="w",
            wraplength=self._win_w - 44,
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        self._progress = ttk.Progressbar(body, orient="horizontal", mode="determinate", maximum=100)
        self._progress.pack(fill="x")

        self.update_idletasks()
        width = max(self._win_w, self.winfo_reqwidth())
        height = self.winfo_reqheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.deiconify()
        self.lift()
        self.update()

    def set_step(self, percent: float, status: str) -> None:
        pct = max(0.0, min(100.0, percent))
        self._progress.configure(value=pct)
        self._status_var.set(status)
        self.update_idletasks()
        self.update()

    def close(self) -> None:
        if self.winfo_exists():
            self.destroy()

class UserDirectoryDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        apply_window_icon(self)
        self.title("User Directory")
        _w, _h = _screen_fit(max(900, SCREEN_W - 30), max(480, SCREEN_H - 90), pad=0)
        self.geometry(f"{_w}x{_h}+0+0")
        self.resizable(True, True)
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        self._edit_uid = None
        self._rows = []
        self._vars = {}
        self._active_var = tk.BooleanVar(value=True)
        self._build()
        self._load_users()
        self.grab_set()

    def _build(self):
        container = ttk.Frame(self, padding=8)
        container.pack(fill="both", expand=True)

        # ── Left: treeview ───────────────────────────────────────────────────
        left = ttk.Frame(container)
        left.pack(side="left", fill="both", expand=True)

        cols = ("id", "username", "name", "role", "email", "phone", "active")
        self.tv = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [
            ("id", "ID", 48),
            ("username", "Username", 140),
            ("name", "Name", 190),
            ("role", "Role", 96),
            ("email", "Email", 220),
            ("phone", "Phone", 126),
            ("active", "Active", 76),
        ]:
            self.tv.heading(c, text=h, anchor="w")
            self.tv.column(c, width=_sc(w), stretch=c in ("name", "email"))

        vsb = ttk.Scrollbar(left, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vsb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        _bind_mousewheel_recursive(self.tv, self.tv.yview_scroll)
        self.tv.bind("<<TreeviewSelect>>", self._on_select)

        # ── Right: edit form ─────────────────────────────────────────────────
        right_outer = lframe(container, "Edit User")
        right_outer.pack(side="left", fill="both", expand=True, padx=(8, 0))

        scroll_canvas = tk.Canvas(right_outer, background=BG, highlightthickness=0)
        vsb2 = ttk.Scrollbar(right_outer, orient="vertical", command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=vsb2.set)
        scroll_canvas.pack(side="left", fill="both", expand=True)
        vsb2.pack(side="right", fill="y")

        form = ttk.Frame(scroll_canvas)
        fid = scroll_canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda e: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all")))
        scroll_canvas.bind("<Configure>", lambda e: scroll_canvas.itemconfigure(fid, width=e.width))
        _bind_mousewheel_recursive(form, scroll_canvas.yview_scroll)

        def fv(name):
            v = tk.StringVar()
            self._vars[name] = v
            return v

        # Full-width entry (spans all 6 data columns)
        def fe(lbl, name, r):
            ttk.Label(form, text=lbl).grid(row=r, column=0, sticky="e", padx=(4, 2), pady=3)
            ttk.Entry(form, textvariable=fv(name)).grid(row=r, column=1, columnspan=5, sticky="ew", padx=(0, 8), pady=3)

        # Two-field row  (label | entry | label | entry)
        def fe2(lbl1, n1, lbl2, n2, r):
            ttk.Label(form, text=lbl1).grid(row=r, column=0, sticky="e", padx=(4, 2), pady=3)
            ttk.Entry(form, textvariable=fv(n1)).grid(row=r, column=1, sticky="ew", padx=(0, 4), pady=3)
            ttk.Label(form, text=lbl2).grid(row=r, column=2, sticky="e", padx=(4, 2), pady=3)
            ttk.Entry(form, textvariable=fv(n2)).grid(row=r, column=3, sticky="ew", padx=(0, 8), pady=3)

        # Three-field row (label | entry | label | entry | label | entry)
        def fe3(lbl1, n1, lbl2, n2, lbl3, n3, r):
            ttk.Label(form, text=lbl1).grid(row=r, column=0, sticky="e", padx=(4, 2), pady=3)
            ttk.Entry(form, textvariable=fv(n1)).grid(row=r, column=1, sticky="ew", padx=(0, 4), pady=3)
            ttk.Label(form, text=lbl2).grid(row=r, column=2, sticky="e", padx=(4, 2), pady=3)
            ttk.Entry(form, textvariable=fv(n2)).grid(row=r, column=3, sticky="ew", padx=(0, 4), pady=3)
            ttk.Label(form, text=lbl3).grid(row=r, column=4, sticky="e", padx=(4, 2), pady=3)
            ttk.Entry(form, textvariable=fv(n3)).grid(row=r, column=5, sticky="ew", padx=(0, 8), pady=3)

        for c in (0, 2, 4):
            form.columnconfigure(c, weight=0, minsize=112)
        for c in (1, 3, 5):
            form.columnconfigure(c, weight=1, minsize=132)

        # ── Read-only info row
        info_frm = ttk.Frame(form)
        info_frm.grid(row=0, column=0, columnspan=6, sticky="ew", padx=4, pady=(4, 2))
        self._info_id = ttk.Label(info_frm, text="ID: —", foreground="#888")
        self._info_cr = ttk.Label(info_frm, text="Created: —", foreground="#888")
        self._info_login = ttk.Label(info_frm, text="Last Login: —", foreground="#888")
        self._info_id.pack(side="left", padx=(0, 14))
        self._info_cr.pack(side="left", padx=(0, 14))
        self._info_login.pack(side="left")

        ttk.Separator(form, orient="horizontal").grid(row=1, column=0, columnspan=6, sticky="ew", pady=(2, 6))

        # ── Identity
        fe("Username:", "username", 2)
        fe2("First Name:", "first_name", "Last Name:", "last_name", 3)
        ttk.Label(form, text="Middle Name:").grid(row=4, column=0, sticky="e", padx=(4, 2), pady=3)
        ttk.Entry(form, textvariable=fv("middle_name")).grid(row=4, column=1, sticky="ew", padx=(0, 4), pady=3)
        ttk.Label(form, text="Role:").grid(row=4, column=4, sticky="e", padx=(4, 2), pady=3)
        ttk.Combobox(
            form,
            textvariable=fv("role"),
            values=["Admin", "User", "Provider", "Billing", "Read-Only"],
            state="readonly",
        ).grid(row=4, column=5, sticky="ew", padx=(0, 8), pady=3)

        ttk.Separator(form, orient="horizontal").grid(row=5, column=0, columnspan=6, sticky="ew", pady=6)

        # ── Contact
        fe2("Email:", "email", "Phone:", "phone", 6)

        ttk.Separator(form, orient="horizontal").grid(row=8, column=0, columnspan=6, sticky="ew", pady=6)

        # ── Primary address
        ttk.Label(form, text="Address:", font=("Arial", 9, "bold")).grid(row=9, column=0, columnspan=6, sticky="w", padx=4, pady=(2, 0))
        fe("Street:", "address", 10)
        fe3("City:", "city", "State:", "state", "Zip:", "zip", 11)

        ttk.Separator(form, orient="horizontal").grid(row=12, column=0, columnspan=6, sticky="ew", pady=6)

        # ── Billing address
        ttk.Label(form, text="Billing Address:", font=("Arial", 9, "bold")).grid(row=13, column=0, columnspan=6, sticky="w", padx=4, pady=(2, 0))
        fe("Street:", "billing_address", 14)
        fe3("City:", "billing_city", "State:", "billing_state", "Zip:", "billing_zip", 15)

        ttk.Separator(form, orient="horizontal").grid(row=16, column=0, columnspan=6, sticky="ew", pady=6)

        # ── Password & active
        ttk.Label(form, text="New Password:").grid(row=17, column=0, sticky="e", padx=(4, 2), pady=3)
        ttk.Entry(form, textvariable=fv("password"), show="*").grid(row=17, column=1, columnspan=3, sticky="ew", padx=(0, 4), pady=3)
        ttk.Label(form, text="(leave blank to keep current)", foreground="#888").grid(row=17, column=4, columnspan=2, sticky="w", padx=(0, 8))

        ttk.Checkbutton(form, text="Active", variable=self._active_var).grid(
            row=18, column=0, columnspan=2, sticky="w", padx=4, pady=(8, 4)
        )

        # ── Bottom buttons ───────────────────────────────────────────────────
        bottom = ttk.Frame(self, padding=8)
        bottom.pack(fill="x")
        btn(bottom, "+ Add User", self._add_user).pack(side="left", padx=(0, 4))
        btn(bottom, "Refresh", self._load_users).pack(side="left")
        btn(bottom, "Save Changes", self._save_changes, "Accent.TButton").pack(side="right")
        btn(bottom, "Close", self.destroy).pack(side="right", padx=(0, 4))

    def _load_users(self):
        self._rows = db.get_all_users()
        self.tv.delete(*self.tv.get_children())
        for r in self._rows:
            name = f"{r['first_name']} {r['last_name']}"
            self.tv.insert(
                "",
                "end",
                iid=str(r["id"]),
                values=(
                    r["id"],
                    r["username"],
                    name,
                    r["role"],
                    r["email"],
                    r["phone"],
                    "Yes" if r["is_active"] else "No",
                ),
            )
    def _on_select(self, event=None):
        sel = self.tv.selection()
        if not sel:
            return
        uid = int(sel[0])
        row = next((r for r in self._rows if r["id"] == uid), None)
        if not row:
            return
        self._edit_uid = uid
        for key in ("username", "first_name", "middle_name", "last_name",
            "email", "phone", "role",
                    "address", "city", "state", "zip",
                    "billing_address", "billing_city", "billing_state", "billing_zip"):
            self._vars[key].set(str(row[key] or ""))
        self._vars["password"].set("")
        self._active_var.set(bool(row["is_active"]))
        self._info_id.config(text=f"ID: {row['id']}")
        self._info_cr.config(text=f"Created: {row['created_at'] or '—'}")
        self._info_login.config(text=f"Last Login: {row['last_login'] or 'Never'}")

    def _save_changes(self):
        if self._edit_uid is None:
            messagebox.showinfo("Select", "Please select a user to edit.", parent=self)
            return
        data = {k: v.get().strip() for k, v in self._vars.items()}
        data["is_active"] = int(self._active_var.get())
        try:
            db.update_user(self._edit_uid, data)
        except ValueError as e:
            messagebox.showerror("Validation Error", str(e), parent=self)
            return
        messagebox.showinfo("Saved", "User updated successfully.", parent=self)
        self._vars["password"].set("")
        self._load_users()

    def _add_user(self):
        CreateAccountDialog(self)
        self.after(600, self._load_users)


class CreateAccountDialog(tk.Toplevel):
    def __init__(self, parent, after_create=None):
        super().__init__(parent)
        apply_window_icon(self)
        self.after_create = after_create
        self.title("Create Account")
        _w, _h = _screen_fit(max(900, SCREEN_W - 30), max(560, SCREEN_H - 90), pad=0)
        self.geometry(f"{_w}x{_h}+0+0")
        self.resizable(True, True)
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        self._vars = {}
        self._billing_widgets = {}
        self._same_addr_var = tk.BooleanVar(value=False)
        self._build()
        self.grab_set()

    def _field(self, name, default=""):
        v = tk.StringVar(value=default)
        self._vars[name] = v
        return v

    def _build(self):
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, background=BG, highlightthickness=0)
        vbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        frm = ttk.Frame(canvas, padding=20)
        win_id = canvas.create_window((0, 0), window=frm, anchor="n")

        def _sync_scroll(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(win_id, width=canvas.winfo_width())

        frm.bind("<Configure>", _sync_scroll)
        canvas.bind("<Configure>", _sync_scroll)
        _bind_mousewheel_recursive(frm, canvas.yview_scroll)

        frm.columnconfigure(0, weight=0, minsize=132)
        frm.columnconfigure(1, weight=1, minsize=230)
        frm.columnconfigure(2, weight=0, minsize=28)  # spacer
        frm.columnconfigure(3, weight=0, minsize=148)
        frm.columnconfigure(4, weight=1, minsize=230)

        # ── Title ────────────────────────────────────────────────
        ttk.Label(frm, text="Create User Account", font=FONT_H1).grid(
            row=0, column=0, columnspan=5, sticky="w", pady=(0, 10))

        # ── Row 1: First Name | Username ─────────────────────────
        ttk.Label(frm, text="First Name*").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        _e_first = ttk.Entry(frm, textvariable=self._field("first_name"), width=24)
        _e_first.grid(row=1, column=1, sticky="ew")
        ttk.Label(frm, text="Username*").grid(row=1, column=3, sticky="e", padx=4, pady=4)
        _e_username = ttk.Entry(frm, textvariable=self._field("username"), width=24)
        _e_username.grid(row=1, column=4, sticky="ew")

        # ── Row 2: Middle Name | Password ────────────────────────
        ttk.Label(frm, text="Middle Name").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        _e_middle = ttk.Entry(frm, textvariable=self._field("middle_name"), width=24)
        _e_middle.grid(row=2, column=1, sticky="ew")
        ttk.Label(frm, text="Password*").grid(row=2, column=3, sticky="e", padx=4, pady=4)
        _e_password = ttk.Entry(frm, textvariable=self._field("password"), show="*", width=24)
        _e_password.grid(row=2, column=4, sticky="ew")

        # ── Row 3: Last Name | Confirm Password ──────────────────
        ttk.Label(frm, text="Last Name*").grid(row=3, column=0, sticky="e", padx=4, pady=4)
        _e_last = ttk.Entry(frm, textvariable=self._field("last_name"), width=24)
        _e_last.grid(row=3, column=1, sticky="ew")
        ttk.Label(frm, text="Confirm Password*").grid(row=3, column=3, sticky="e", padx=4, pady=4)
        _e_confirm = ttk.Entry(frm, textvariable=self._field("confirm_password"), show="*", width=24)
        _e_confirm.grid(row=3, column=4, sticky="ew")

        # ── Row 4: Show Password toggle ───────────────────────────
        _show_pw_var = tk.BooleanVar(value=False)
        def _toggle_show_pw():
            ch = "" if _show_pw_var.get() else "*"
            _e_password.config(show=ch)
            _e_confirm.config(show=ch)
        ttk.Checkbutton(
            frm, text="Show Password", variable=_show_pw_var,
            command=_toggle_show_pw
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=4, pady=4)

        # ── Row 5: Phone | Role ───────────────────────────────────
        ttk.Label(frm, text="Phone").grid(row=5, column=0, sticky="e", padx=4, pady=4)
        _e_phone = ttk.Entry(frm, textvariable=self._field("phone"), width=24)
        _e_phone.grid(row=5, column=1, sticky="ew")
        ttk.Label(frm, text="Role").grid(row=5, column=3, sticky="e", padx=4, pady=4)
        _cb_role = ttk.Combobox(frm, textvariable=self._field("role", "User"),
                     values=["Admin", "User", "Billing", "ReadOnly"],
                     width=21, state="readonly")
        _cb_role.grid(row=5, column=4, sticky="ew")

        # ── Row 6: Email | (empty right) ─────────────────────────
        ttk.Label(frm, text="Email").grid(row=6, column=0, sticky="e", padx=4, pady=4)
        _e_email = ttk.Entry(frm, textvariable=self._field("email"), width=24)
        _e_email.grid(row=6, column=1, sticky="ew")

        # ── Mailing Address header ────────────────────────────────
        ttk.Separator(frm, orient="horizontal").grid(row=7, column=0, columnspan=2, sticky="ew", pady=(10, 2))
        ttk.Label(frm, text="Mailing Address", font=FONT_LG).grid(row=8, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 2))

        # ── Billing Address header (same row) ─────────────────────
        ttk.Separator(frm, orient="horizontal").grid(row=7, column=3, columnspan=2, sticky="ew", pady=(10, 2))
        ttk.Label(frm, text="Billing Address", font=FONT_LG).grid(row=8, column=3, columnspan=2, sticky="w", padx=4, pady=(0, 2))
        ttk.Checkbutton(
            frm, text="Same as mailing address",
            variable=self._same_addr_var,
            command=self._toggle_same_addr
        ).grid(row=9, column=3, columnspan=2, sticky="w", padx=4, pady=(0, 4))

        # ── Mailing | Billing fields ──────────────────────────────
        ttk.Label(frm, text="Address").grid(row=9, column=0, sticky="e", padx=4, pady=4)
        _e_address = ttk.Entry(frm, textvariable=self._field("address"), width=28)
        _e_address.grid(row=9, column=1, sticky="ew")

        ttk.Label(frm, text="Billing Address").grid(row=10, column=3, sticky="e", padx=4, pady=4)
        _ba = ttk.Entry(frm, textvariable=self._field("billing_address"), width=24)
        _ba.grid(row=10, column=4, sticky="ew")
        self._billing_widgets["billing_address"] = _ba

        ttk.Label(frm, text="City").grid(row=10, column=0, sticky="e", padx=4, pady=4)
        _e_city = ttk.Entry(frm, textvariable=self._field("city"), width=24)
        _e_city.grid(row=10, column=1, sticky="ew")

        ttk.Label(frm, text="Billing City").grid(row=11, column=3, sticky="e", padx=4, pady=4)
        _bc = ttk.Entry(frm, textvariable=self._field("billing_city"), width=24)
        _bc.grid(row=11, column=4, sticky="ew")
        self._billing_widgets["billing_city"] = _bc

        ttk.Label(frm, text="State").grid(row=11, column=0, sticky="e", padx=4, pady=4)
        _cb_state = ttk.Combobox(frm, textvariable=self._field("state"), values=STATES, width=8, state="readonly")
        _cb_state.grid(row=11, column=1, sticky="ew")

        ttk.Label(frm, text="Billing State").grid(row=12, column=3, sticky="e", padx=4, pady=4)
        _bs = ttk.Combobox(frm, textvariable=self._field("billing_state"), values=STATES, width=8, state="readonly")
        _bs.grid(row=12, column=4, sticky="ew")
        self._billing_widgets["billing_state"] = _bs

        ttk.Label(frm, text="Zip").grid(row=12, column=0, sticky="e", padx=4, pady=4)
        _e_zip = ttk.Entry(frm, textvariable=self._field("zip"), width=12)
        _e_zip.grid(row=12, column=1, sticky="ew")

        ttk.Label(frm, text="Billing Zip").grid(row=13, column=3, sticky="e", padx=4, pady=4)
        _bz = ttk.Entry(frm, textvariable=self._field("billing_zip"), width=12)
        _bz.grid(row=13, column=4, sticky="ew")
        self._billing_widgets["billing_zip"] = _bz

        # ── Tab order: left column top→bottom, then right column ──
        self._set_tab_order([
            _e_first, _e_middle, _e_last, _e_phone, _e_email,
            _e_address, _e_city, _cb_state, _e_zip,
            _e_username, _e_password, _e_confirm, _cb_role,
            self._billing_widgets["billing_address"],
            self._billing_widgets["billing_city"],
            self._billing_widgets["billing_state"],
            self._billing_widgets["billing_zip"],
        ])

        # ── Footer ────────────────────────────────────────────────
        msg = "Password must be at least 8 characters. Required fields are marked with *"
        ttk.Label(frm, text=msg, foreground=MUTED).grid(row=14, column=0, columnspan=5, sticky="w", pady=(6, 2))

        bottom = ttk.Frame(frm)
        bottom.grid(row=15, column=0, columnspan=5, sticky="ew", pady=(10, 0))
        btn(bottom, "Create Account", self._create, "Accent.TButton").pack(side="left", padx=4)
        btn(bottom, "Cancel", self.destroy).pack(side="left")

    def _set_tab_order(self, widgets):
        """Bind Tab/Shift-Tab to enforce left-column-first traversal."""
        for i, w in enumerate(widgets):
            nw = widgets[(i + 1) % len(widgets)]
            pw = widgets[(i - 1) % len(widgets)]
            w.bind("<Tab>", lambda e, nw=nw: nw.focus_set() or "break")
            w.bind("<Shift-Tab>", lambda e, pw=pw: pw.focus_set() or "break")

    def _toggle_same_addr(self):
        if self._same_addr_var.get():
            self._vars["billing_address"].set(self._vars.get("address", tk.StringVar()).get())
            self._vars["billing_city"].set(self._vars.get("city", tk.StringVar()).get())
            self._vars["billing_state"].set(self._vars.get("state", tk.StringVar()).get())
            self._vars["billing_zip"].set(self._vars.get("zip", tk.StringVar()).get())
            for w in self._billing_widgets.values():
                w.config(state="disabled")
        else:
            for w in self._billing_widgets.values():
                w.config(state="normal" if not isinstance(w, ttk.Combobox) else "readonly")

    def _create(self):
        data = {k: v.get().strip() for k, v in self._vars.items()}
        password = data.pop("password", "")
        confirm_password = data.pop("confirm_password", "")
        if password != confirm_password:
            messagebox.showerror("Password", "Password and confirm password do not match.", parent=self)
            return
        data["password"] = password
        try:
            db.create_user(data)
        except ValueError as ex:
            messagebox.showerror("Create Account", str(ex), parent=self)
            return
        except Exception as ex:
            messagebox.showerror("Create Account", f"Could not create account: {ex}", parent=self)
            return

        messagebox.showinfo("Account Created", "User account created successfully.", parent=self)
        if self.after_create:
            self.after_create(data.get("username", ""))
        self.destroy()


class LoginDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        apply_window_icon(self)
        self.user = None
        self.title("Aura Scribe PSY Login")
        _w, _h = _screen_fit(max(900, SCREEN_W - 30), max(560, SCREEN_H - 90), pad=0)
        self.geometry(f"{_w}x{_h}+0+0")
        self.resizable(True, True)
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        self._build()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _build(self):
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        center = ttk.Frame(frm)
        center.pack(expand=True)

        ttk.Label(center, text="Aura Scribe PSY", font=FONT_H1).pack(anchor="center")

        self.v_user = tk.StringVar()
        self.v_pass = tk.StringVar()

        row1 = ttk.Frame(center)
        row1.pack(pady=3)
        ttk.Label(row1, text="Username", width=12).pack(side="left")
        e_user = ttk.Entry(row1, textvariable=self.v_user, width=30)
        e_user.pack(side="left")

        row2 = ttk.Frame(center)
        row2.pack(pady=3)
        ttk.Label(row2, text="Password", width=12).pack(side="left")
        e_pass = ttk.Entry(row2, textvariable=self.v_pass, width=30, show="*")
        e_pass.pack(side="left")

        _show_pw_var = tk.BooleanVar(value=False)
        row3 = ttk.Frame(center)
        row3.pack()
        ttk.Label(row3, width=12).pack(side="left")  # spacer to align with labels above
        ttk.Checkbutton(
            row3, text="Show Password", variable=_show_pw_var,
            command=lambda: e_pass.config(show="" if _show_pw_var.get() else "*")
        ).pack(side="left")

        self.lbl_msg = ttk.Label(center, text="", foreground=DANGER)
        self.lbl_msg.pack(anchor="center", pady=(5, 2))

        action = ttk.Frame(center)
        action.pack(pady=(8, 0))
        btn(action, "Login", self._login, "Accent.TButton").pack(side="left", padx=3)
        btn(action, "Create Account", self._open_create).pack(side="left", padx=3)
        btn(action, "View Users", self._open_users).pack(side="left", padx=3)
        btn(action, "Exit", self._cancel).pack(side="left", padx=3)

        first_use = db.count_users() == 0
        if first_use:
            self.lbl_msg.config(text="No users found. Please create the first account.")

        e_user.focus_set()
        self.bind("<Return>", lambda e: self._login())

    def _open_users(self):
        UserDirectoryDialog(self)

    def _open_create(self):
        CreateAccountDialog(self, after_create=lambda u: self.v_user.set(u))

    def _login(self):
        username = self.v_user.get().strip()
        password = self.v_pass.get()
        if not username or not password:
            self.lbl_msg.config(text="Enter username and password.")
            return
        user = db.verify_user_credentials(username, password)
        if not user:
            self.lbl_msg.config(text="Invalid username or password.")
            return
        self.user = user
        self.destroy()

    def _cancel(self):
        self.user = None
        self.destroy()


# ─── DSM Picker Dialog ─────────────────────────────────────────────────────────

class DSMPicker(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        apply_window_icon(self)
        self.title("DSM-5 / ICD-10 Code Lookup")
        _w, _h = _screen_fit(1200, 850, pad=24)
        self.geometry(f"{_w}x{_h}")
        self.minsize(900, 600)
        self.resizable(True, True)
        self.callback = callback
        self.result = None
        self._build()
        self.transient(parent)
        self.lift()
        self.focus_force()
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        self.grab_set()

    def _build(self):
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="Search:").grid(row=0, column=0, sticky="w")
        self.sv = tk.StringVar()
        self.sv.trace_add("write", lambda *a: self._search())
        self.search_entry = ttk.Entry(top, textvariable=self.sv, width=40)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        frm = ttk.Frame(self, padding=8)
        frm.pack(fill="both", expand=True)
        cols = ("code", "description", "category")
        self.tv = ttk.Treeview(frm, columns=cols, show="headings", selectmode="browse")
        self.tv.heading("code",        text="Code",       anchor="w")
        self.tv.heading("description", text="Description",anchor="w")
        self.tv.heading("category",    text="Category",   anchor="w")
        self.tv.column("code",        width=_sc(150), minwidth=_sc(130), stretch=False)
        self.tv.column("description", width=_sc(560), minwidth=_sc(320), stretch=True)
        self.tv.column("category",    width=_sc(260), minwidth=_sc(210), stretch=False)
        sb = ttk.Scrollbar(frm, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        _bind_mousewheel_recursive(self, self.tv.yview_scroll)
        self.tv.bind("<Double-1>", self._select)

        bot = ttk.Frame(self, padding=8)
        bot.pack(fill="x")
        btn(bot, "Select", self._select, "Accent.TButton").pack(side="right", padx=4)
        btn(bot, "Cancel", self.destroy).pack(side="right")

        self._load_all()
        self.after(0, self.search_entry.focus_set)

    def _load_all(self):
        self.tv.delete(*self.tv.get_children())
        for r in db.get_all_dsm():
            self.tv.insert("", "end", iid=r["code"],
                           values=(r["code"], r["description"], r["category"]))

    def _search(self):
        term = self.sv.get().strip()
        self.tv.delete(*self.tv.get_children())
        rows = db.search_dsm(term) if term else db.get_all_dsm()
        for r in rows:
            self.tv.insert("", "end", iid=r["code"],
                           values=(r["code"], r["description"], r["category"]))

    def _select(self, event=None):
        sel = self.tv.selection()
        if sel:
            code = sel[0]
            self.callback(code)
            self.destroy()


# ─── Patient Form Dialog ───────────────────────────────────────────────────────

class PatientDialog(tk.Toplevel):
    def __init__(self, parent, pid=None, on_save=None):
        super().__init__(parent)
        apply_window_icon(self)
        self.pid = pid
        self.on_save = on_save
        self.title("Edit Patient" if pid else "New Patient")
        _w, _h = _screen_fit(820, 680)
        self.geometry(f"{_w}x{_h}")
        self.resizable(True, True)
        try:
            self.state('zoomed')
        except tk.TclError:
            pass
        self._vars = {}
        self._build()
        if pid:
            self._load()
        # Avoid hard modal grab so Windows minimize works reliably.

    def _fld(self, name):
        v = tk.StringVar()
        self._vars[name] = v
        return v

    def _build(self):
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, background=BG, highlightthickness=0)
        vbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        body = ttk.Frame(canvas, padding=8)
        win_id = canvas.create_window((0, 0), window=body, anchor="nw")

        def _sync_scroll(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(win_id, width=canvas.winfo_width())

        body.bind("<Configure>", _sync_scroll)
        canvas.bind("<Configure>", _sync_scroll)
        _bind_mousewheel_recursive(body, canvas.yview_scroll)

        nb = ttk.Notebook(body)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Demographics tab ──────────────────────────────────────────────────
        f1 = ttk.Frame(nb, padding=10)
        nb.add(f1, text=" Demographics ")
        for c in (0, 2, 4):
            f1.columnconfigure(c, weight=0, minsize=110)
        for c in (1, 3, 5):
            f1.columnconfigure(c, weight=1, minsize=120)

        ttk.Label(f1, text="Last Name*").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(f1, textvariable=self._fld("last_name"), width=22).grid(row=0, column=1, sticky="ew", padx=(0,8))
        ttk.Label(f1, text="First Name*").grid(row=0, column=2, sticky="e", padx=4)
        ttk.Entry(f1, textvariable=self._fld("first_name"), width=20).grid(row=0, column=3, sticky="ew", padx=(0,8))
        ttk.Label(f1, text="MI").grid(row=0, column=4, sticky="e", padx=4)
        ttk.Entry(f1, textvariable=self._fld("middle_name"), width=5).grid(row=0, column=5, sticky="w")

        ttk.Label(f1, text="Date of Birth").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(f1, textvariable=self._fld("dob"), width=14).grid(row=1, column=1, sticky="w")
        ttk.Label(f1, text="(YYYY-MM-DD)").grid(row=1, column=2, sticky="w", padx=2)

        ttk.Label(f1, text="Sex").grid(row=1, column=3, sticky="e", padx=4)
        sex_cb = ttk.Combobox(f1, textvariable=self._fld("sex"),
                              values=["M", "F", "U"], width=5, state="readonly")
        sex_cb.grid(row=1, column=4, sticky="w")

        ttk.Label(f1, text="Status").grid(row=2, column=0, sticky="e", padx=4, pady=3)
        ttk.Combobox(f1, textvariable=self._fld("status"),
                     values=["Active", "Inactive"], width=10, state="readonly"
                     ).grid(row=2, column=1, sticky="w")

        ttk.Label(f1, text="Intake Date").grid(row=2, column=2, sticky="e", padx=4)
        ttk.Entry(f1, textvariable=self._fld("intake_date"), width=14).grid(row=2, column=3, sticky="w")

        ttk.Label(f1, text="Sig on File Date").grid(row=2, column=4, sticky="e", padx=4)
        ttk.Entry(f1, textvariable=self._fld("sig_on_file_date"), width=14).grid(row=2, column=5, sticky="w")

        ttk.Label(f1, text="Address").grid(row=3, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(f1, textvariable=self._fld("address"), width=30).grid(row=3, column=1, sticky="ew", columnspan=3, padx=(0,8))

        ttk.Label(f1, text="City").grid(row=4, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(f1, textvariable=self._fld("city"), width=22).grid(row=4, column=1, sticky="ew", padx=(0,8))
        ttk.Label(f1, text="State").grid(row=4, column=2, sticky="e", padx=4)
        ttk.Combobox(f1, textvariable=self._fld("state"), values=STATES, width=6, state="readonly").grid(row=4, column=3, sticky="w")
        ttk.Label(f1, text="Zip").grid(row=4, column=4, sticky="e", padx=4)
        ttk.Entry(f1, textvariable=self._fld("zip"), width=10).grid(row=4, column=5, sticky="w")

        ttk.Label(f1, text="Phone (Home)").grid(row=5, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(f1, textvariable=self._fld("phone_home"), width=16).grid(row=5, column=1, sticky="w")
        ttk.Label(f1, text="Cell").grid(row=5, column=2, sticky="e", padx=4)
        ttk.Entry(f1, textvariable=self._fld("phone_cell"), width=16).grid(row=5, column=3, sticky="w")
        ttk.Label(f1, text="Work").grid(row=5, column=4, sticky="e", padx=4)
        ttk.Entry(f1, textvariable=self._fld("phone_work"), width=16).grid(row=5, column=5, sticky="w")

        ttk.Label(f1, text="Email").grid(row=6, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(f1, textvariable=self._fld("email"), width=30).grid(row=6, column=1, sticky="ew", columnspan=3)

        ttk.Label(f1, text="Emergency Contact").grid(row=7, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(f1, textvariable=self._fld("emr_name"), width=22).grid(row=7, column=1, sticky="ew", padx=(0,8))
        ttk.Label(f1, text="Phone").grid(row=7, column=2, sticky="e", padx=4)
        ttk.Entry(f1, textvariable=self._fld("emr_phone"), width=16).grid(row=7, column=3, sticky="w")

        # Diagnoses
        dx_frame = lframe(f1, "Primary Diagnoses (ICD-10)")
        dx_frame.grid(row=8, column=0, columnspan=6, sticky="ew", pady=(10, 4))
        for c in range(12):
            dx_frame.columnconfigure(c, weight=1)
        for i, dx in enumerate(PATIENT_DX_KEYS):
            row = i // 6
            col = (i % 6) * 2
            ttk.Label(dx_frame, text=f"Dx {i+1}").grid(row=row, column=col, sticky="e", padx=4, pady=2)
            e = ttk.Entry(dx_frame, textvariable=self._fld(dx), width=12)
            e.grid(row=row, column=col+1, sticky="w", padx=(0,4), pady=2)

        b_dx = ttk.Frame(dx_frame)
        b_dx.grid(row=2, column=0, columnspan=12, pady=4)
        ttk.Button(b_dx, text="Lookup DSM Code",
                   command=lambda: DSMPicker(self, self._dx_pick)).pack(side="left", padx=4)

        # Notes
        ttk.Label(f1, text="Admin Notes").grid(row=9, column=0, sticky="ne", padx=4, pady=3)
        self._notesbox = tk.Text(f1, width=60, height=4, font=FONT_UI, wrap="word")
        self._notesbox.grid(row=9, column=1, columnspan=5, sticky="ew")

        # ── Insurance tab ─────────────────────────────────────────────────────
        f2 = ttk.Frame(nb, padding=10)
        nb.add(f2, text=" Insurance ")
        for c in (0, 2, 4):
            f2.columnconfigure(c, weight=0, minsize=110)
        for c in (1, 3, 5):
            f2.columnconfigure(c, weight=1, minsize=120)

        pri = lframe(f2, "Primary Insurance")
        pri.grid(row=0, column=0, columnspan=6, sticky="ew", pady=4)
        for c in (0, 2, 4):
            pri.columnconfigure(c, weight=0, minsize=110)
        for c in (1, 3, 5):
            pri.columnconfigure(c, weight=1, minsize=120)

        ins_fields = [
            ("Insurance Name", "ins_name", 0), ("Plan Name", "ins_plan", 1),
            ("Member/Policy ID", "ins_id", 2), ("Group Number", "ins_group", 3),
            ("Insured Name", "ins_holder", 4), ("Insured DOB", "ins_holder_dob", 5),
        ]
        for lbl, key, rr in ins_fields:
            ttk.Label(pri, text=lbl).grid(row=rr, column=0, sticky="e", padx=4, pady=2)
            ttk.Entry(pri, textvariable=self._fld(key), width=28).grid(row=rr, column=1, sticky="ew", columnspan=5)

        ttk.Label(pri, text="Insured Sex").grid(row=6, column=0, sticky="e", padx=4, pady=2)
        ttk.Combobox(pri, textvariable=self._fld("ins_holder_sex"), values=["M","F","U"], width=5, state="readonly").grid(row=6, column=1, sticky="w")
        ttk.Label(pri, text="Relationship to Patient").grid(row=6, column=2, sticky="e", padx=4)
        ttk.Combobox(pri, textvariable=self._fld("ins_relation"),
                     values=["Self","Spouse","Child","Other"], width=12, state="readonly").grid(row=6, column=3, sticky="w")

        ttk.Label(pri, text="Insured Address").grid(row=7, column=0, sticky="e", padx=4, pady=2)
        ttk.Entry(pri, textvariable=self._fld("ins_address"), width=28).grid(row=7, column=1, sticky="ew", columnspan=2)
        ttk.Label(pri, text="City").grid(row=7, column=3, sticky="e", padx=4)
        ttk.Entry(pri, textvariable=self._fld("ins_city"), width=16).grid(row=7, column=4, sticky="ew")
        ttk.Label(pri, text="State").grid(row=8, column=0, sticky="e", padx=4, pady=2)
        ttk.Combobox(pri, textvariable=self._fld("ins_state"), values=STATES, width=6, state="readonly").grid(row=8, column=1, sticky="w")
        ttk.Label(pri, text="Zip").grid(row=8, column=2, sticky="e", padx=4)
        ttk.Entry(pri, textvariable=self._fld("ins_zip"), width=10).grid(row=8, column=3, sticky="w")
        ttk.Label(pri, text="Phone").grid(row=8, column=4, sticky="e", padx=4)
        ttk.Entry(pri, textvariable=self._fld("ins_phone"), width=16).grid(row=8, column=5, sticky="w")

        sec = lframe(f2, "Secondary Insurance")
        sec.grid(row=1, column=0, columnspan=6, sticky="ew", pady=4)
        for c in (0, 2, 4):
            sec.columnconfigure(c, weight=0, minsize=110)
        for c in (1, 3, 5):
            sec.columnconfigure(c, weight=1, minsize=120)
        sec_fields = [
            ("Insurance Name", "ins2_name", 0), ("Plan Name", "ins2_plan", 1),
            ("Member/Policy ID", "ins2_id", 2), ("Group Number", "ins2_group", 3),
            ("Insured Name", "ins2_holder", 4),
        ]
        for lbl, key, rr in sec_fields:
            ttk.Label(sec, text=lbl).grid(row=rr, column=0, sticky="e", padx=4, pady=2)
            ttk.Entry(sec, textvariable=self._fld(key), width=28).grid(row=rr, column=1, sticky="ew", columnspan=5)
        ttk.Label(sec, text="Relationship").grid(row=5, column=0, sticky="e", padx=4, pady=2)
        ttk.Combobox(sec, textvariable=self._fld("ins2_relation"),
                     values=["Self","Spouse","Child","Other"], width=12, state="readonly").grid(row=5, column=1, sticky="w")

        # ── Referral tab ──────────────────────────────────────────────────────
        f3 = ttk.Frame(nb, padding=10)
        nb.add(f3, text=" Referral ")
        for c in range(4): f3.columnconfigure(c, weight=1)
        ttk.Label(f3, text="Referring Provider Name").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f3, textvariable=self._fld("referring_name"), width=30).grid(row=0, column=1, sticky="ew")
        ttk.Label(f3, text="Referring NPI").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f3, textvariable=self._fld("referring_npi"), width=14).grid(row=1, column=1, sticky="w")
        ttk.Label(f3, text="Referring Taxonomy (17a)").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f3, textvariable=self._fld("referring_taxonomy"), width=20).grid(row=2, column=1, sticky="w")
        ttk.Label(f3, text="Illness Date (14)").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f3, textvariable=self._fld("illness_date"), width=12).grid(row=2, column=1, sticky="w")
        ttk.Label(f3, text="Illness Date QUAL").grid(row=3, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f3, textvariable=self._fld("illness_date_qual"), width=8).grid(row=3, column=1, sticky="w")
        ttk.Label(f3, text="Other Date (15)").grid(row=4, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f3, textvariable=self._fld("other_date"), width=12).grid(row=4, column=1, sticky="w")
        ttk.Label(f3, text="Other Date QUAL (15)").grid(row=5, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f3, textvariable=self._fld("other_date_qual"), width=8).grid(row=5, column=1, sticky="w")

        # ── Save / Cancel ─────────────────────────────────────────────────────
        bot = ttk.Frame(body, padding=8)
        bot.pack(fill="x", side="bottom")
        btn(bot, "Save Patient", self._save, "Accent.TButton").pack(side="left", padx=6)
        btn(bot, "Cancel", self.destroy).pack(side="left")

    def _dx_pick(self, code):
        # Fill the first empty dx slot
        for key in PATIENT_DX_KEYS:
            if not self._vars[key].get():
                self._vars[key].set(code)
                return
        self._vars[PATIENT_DX_KEYS[-1]].set(code)

    def _load(self):
        pt = db.get_patient(self.pid)
        if not pt:
            return
        for key, var in self._vars.items():
            v = pt[key] if key in pt.keys() else ""
            var.set(v or "")
        if pt["notes"]:
            self._notesbox.insert("1.0", pt["notes"])

    def _save(self):
        data = {k: v.get().strip() for k, v in self._vars.items()}
        if not data.get("last_name") or not data.get("first_name"):
            messagebox.showerror("Required", "Last Name and First Name are required.", parent=self)
            return
        data["notes"] = self._notesbox.get("1.0", "end-1c")
        if self.pid:
            data["id"] = self.pid
        try:
            pid = db.save_patient(data)
        except Exception as ex:
            messagebox.showerror("Save Error", f"Could not save patient:\n{ex}", parent=self)
            return
        if self.on_save:
            self.on_save(pid)
        self.destroy()


# ─── Session Note Dialog ───────────────────────────────────────────────────────

class SessionDialog(tk.Toplevel):
    def __init__(self, parent, sid=None, pid=None, on_save=None):
        super().__init__(parent)
        apply_window_icon(self)
        self.sid = sid
        self.pid = pid
        self.on_save = on_save
        self.title("Edit Session" if sid else "New Session Note")
        self.resizable(True, True)
        self.update_idletasks()
        try:
            self.state("zoomed")
        except Exception:
            _w, _h = _screen_fit(1100, 780)
            self.geometry(f"{_w}x{_h}")
        self._vars = {}
        self._dictating = False
        self._nt = None
        self._goals = None
        self._interventions = None
        self._response = None
        self._plan = None
        self._active_dictation_mode = None
        self._external_dictation_proc = None
        self._dictation_stop = threading.Event()
        self._dictation_thread = None
        self._suspend_cpt_fee_autofill = False
        self._cached_dictation_apps = []
        self._dict_pref_mode = "offline_vosk"
        self._dict_pref_path = ""
        self._dict_pref_label = "Built-in Offline Dictation (Vosk)"
        self._load_dictation_preference()
        self._auto_paste_after_dictation = tk.BooleanVar(value=False)
        self._scan_dictation_apps_async()
        self._build()
        if sid:
            self._load()
        elif pid:
            self._vars["patient_id"].set(str(pid))
            import datetime as _dt
            self._vars["session_date"].set(_dt.date.today().strftime("%m/%d/%Y"))
        self.protocol("WM_DELETE_WINDOW", self._close_dialog)
        # Avoid hard modal grab so Windows minimize works reliably.

    def _fld(self, name, default=""):
        v = tk.StringVar(value=default)
        self._vars[name] = v
        return v

    def _build(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        for c in (0, 2, 4):
            top.columnconfigure(c, weight=0, minsize=112)
        top.columnconfigure(1, weight=1, minsize=150)
        top.columnconfigure(3, weight=1, minsize=130)
        top.columnconfigure(5, weight=1, minsize=150)
        top.columnconfigure(6, weight=0, minsize=124)
        top.columnconfigure(7, weight=1, minsize=124)

        # Patient selector
        ttk.Label(top, text="Patient*").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        self.pt_var = tk.StringVar()
        self.pt_combo = ttk.Combobox(top, textvariable=self.pt_var, width=30, state="readonly")
        self.pt_combo.grid(row=0, column=1, columnspan=2, sticky="ew")
        self._load_patients()
        self._fld("patient_id")

        ttk.Label(top, text="Session Date*").grid(row=0, column=3, sticky="e", padx=4)
        self._fld("session_date")
        if _HAS_CALENDAR:
            self._date_entry = _DateEntry(
                top,
                textvariable=self._vars["session_date"],
                date_pattern="MM/dd/yyyy",
                width=12,
                background="#2b579a",
                foreground="white",
                borderwidth=2,
            )
            self._date_entry.grid(row=0, column=4, sticky="ew")
        else:
            ttk.Entry(top, textvariable=self._vars["session_date"], width=12).grid(row=0, column=4, sticky="ew")
            ttk.Label(top, text="(YYYY-MM-DD)").grid(row=0, column=5, sticky="w")

        ttk.Label(top, text="Duration (min)").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        ttk.Combobox(
            top,
            textvariable=self._fld("duration", "50"),
            values=["15", "20", "30", "45", "50", "53", "60", "75", "90", "120"],
            width=8,
            state="readonly",
        ).grid(row=1, column=1, sticky="ew")

        ttk.Label(top, text="Session Type").grid(row=1, column=2, sticky="e", padx=4)
        ttk.Combobox(top, textvariable=self._fld("session_type", "Individual"),
                 values=SESSION_TYPES, width=18, state="readonly").grid(row=1, column=3, sticky="ew")

        ttk.Label(top, text="Place of Service").grid(row=1, column=4, sticky="e", padx=4)
        pos_cb = ttk.Combobox(top, textvariable=self._fld("place_of_service", "11"),
                               values=[p[0] for p in PLACE_CODES], width=20)
        pos_cb.grid(row=1, column=5, sticky="ew")

        ttk.Label(top, text="CPT Code").grid(row=2, column=0, sticky="e", padx=4, pady=3)
        self._cpt_combo = ttk.Combobox(
            top,
            textvariable=self._fld("cpt_code", "90834"),
            values=CPT_CODES,
            width=10,
        )
        self._cpt_combo.grid(row=2, column=1, sticky="ew")
        ttk.Label(top, text="Modifier").grid(row=2, column=2, sticky="e", padx=4)
        ttk.Entry(top, textvariable=self._fld("cpt_modifier"), width=6).grid(row=2, column=3, sticky="ew")
        ttk.Label(top, text="Fee ($)").grid(row=2, column=4, sticky="e", padx=4)
        ttk.Entry(top, textvariable=self._fld("fee", "0.00"), width=10).grid(row=2, column=5, sticky="ew")
        btn(top, "Dictation Settings", self._open_dictation_settings).grid(row=2, column=6, columnspan=2, sticky="e", padx=4)

        self._vars["cpt_code"].trace_add("write", lambda *_: self._autofill_fee_from_cpt())
        self._cpt_combo.bind("<<ComboboxSelected>>", lambda _e: self._autofill_fee_from_cpt())
        self.after_idle(self._autofill_fee_from_cpt)

        # Diagnoses row
        dx_frame = lframe(self, "Diagnoses")
        dx_frame.pack(fill="x", padx=10, pady=4)
        for c in range(12):
            dx_frame.columnconfigure(c, weight=1)
        for i, dx in enumerate(PATIENT_DX_KEYS):
            row = i // 6
            col = (i % 6) * 2
            ttk.Label(dx_frame, text=f"Dx {i+1}").grid(row=row, column=col, sticky="e", padx=4, pady=2)
            ttk.Entry(dx_frame, textvariable=self._fld(dx), width=10).grid(row=row, column=col+1, sticky="w", padx=(0,6), pady=2)
        ttk.Button(dx_frame, text="Lookup Code",
                   command=lambda: DSMPicker(self, self._dx_pick)).grid(row=2, column=0, columnspan=12, pady=4)

        # Note text
        nb2 = ttk.Notebook(self)
        nb2.pack(fill="both", expand=True, padx=10, pady=4)

        def note_tab(lbl, attr, h=8):
            frm = ttk.Frame(nb2, padding=4)
            nb2.add(frm, text=lbl)
            t = tk.Text(frm, font=FONT_UI, wrap="word", height=h,
                        relief="solid", borderwidth=1)
            sb = ttk.Scrollbar(frm, orient="vertical", command=t.yview)
            t.configure(yscrollcommand=sb.set)
            t.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")
            _bind_mousewheel_recursive(t, t.yview_scroll)
            setattr(self, attr, t)
            return frm

        note_tab(" Progress Note ", "_nt",  12)
        note_tab(" Goals Addressed ", "_goals", 6)
        note_tab(" Interventions ", "_interventions", 6)
        note_tab(" Response ", "_response", 6)
        note_tab(" Plan ", "_plan", 6)
        self._dictation_targets = {
            "Progress Note": self._nt,
            "Goals Addressed": self._goals,
            "Interventions": self._interventions,
            "Response": self._response,
            "Plan": self._plan,
        }

        # Signed / dictation controls / actions
        footer = ttk.Frame(self, padding=(8, 4, 8, 8))
        footer.pack(fill="x", side="bottom")
        bot = ttk.Frame(footer)
        bot.pack(fill="x")
        self.signed_var = tk.IntVar()
        self.billing_var = tk.IntVar(value=1)
        ttk.Checkbutton(bot, text="Mark as Signed / Finalized",
                        variable=self.signed_var).pack(side="left", padx=6)
        ttk.Checkbutton(
            bot,
            text="Create/Update Billing Record on Save",
            variable=self.billing_var,
        ).pack(side="left", padx=10)
        ttk.Label(bot, text="Dictate To").pack(side="left", padx=(8, 4))
        self._dict_target_var = tk.StringVar(value="Progress Note")
        ttk.Combobox(
            bot,
            textvariable=self._dict_target_var,
            values=list(self._dictation_targets.keys()),
            width=16,
            state="readonly",
        ).pack(side="left", padx=(0, 4))
        self._dict_sv = tk.StringVar(value="Dictation: idle")
        self._btn_start_dict = btn(bot, "Start Dictation", self._start_dictation)
        self._btn_start_dict.pack(side="left", padx=6)
        self._btn_stop_dict = btn(bot, "Stop Dictation", self._stop_dictation)
        self._btn_stop_dict.pack(side="left", padx=2)
        self._btn_stop_dict.configure(state="disabled")
        btn(bot, "Paste Dictation", self._paste_dictation_from_clipboard).pack(side="left", padx=2)
        ttk.Checkbutton(bot, text="Auto-paste", variable=self._auto_paste_after_dictation).pack(side="left", padx=(0, 6))
        btn(bot, "Check Dictation Setup", self._check_dictation_setup).pack(side="left", padx=4)
        btn(bot, "Dictation Settings", self._open_dictation_settings).pack(side="left", padx=2)
        ttk.Label(bot, textvariable=self._dict_sv, foreground=MUTED).pack(side="left", padx=8)
        self._set_dictation_idle_status()

        actions = ttk.Frame(footer)
        actions.pack(fill="x", pady=(6, 0))
        btn(actions, "Save Session", self._save, "Accent.TButton").pack(side="right", padx=6)
        btn(actions, "Cancel", self.destroy).pack(side="right")

    def _find_vosk_model(self):
        if not VOSK_MODELS_DIR.exists():
            return None
        for p in sorted(VOSK_MODELS_DIR.iterdir()):
            if p.is_dir() and p.name.lower().startswith("vosk-model"):
                return p
        return None

    def _get_dictation_readiness(self):
        issues = []
        details = []

        if _HAS_OFFLINE_STT:
            details.append("Packages: installed (vosk, sounddevice)")
        else:
            issues.append("Install Python packages 'vosk' and 'sounddevice'.")
            details.append("Packages: missing")

        model_dir = self._find_vosk_model()
        if model_dir:
            details.append(f"Model: found at {model_dir}")
        else:
            issues.append("Add a Vosk model folder under APP_ROOT/models (name starts with 'vosk-model').")
            details.append(f"Model: not found in {VOSK_MODELS_DIR}")

        mic_count = 0
        if _HAS_OFFLINE_STT and _sd is not None:
            try:
                devices = _sd.query_devices()
                mic_count = sum(1 for d in devices if float(d.get("max_input_channels", 0)) > 0)
            except Exception as ex:
                issues.append(f"Could not query audio input devices: {ex}")

        if mic_count > 0:
            details.append(f"Microphone devices: {mic_count} detected")
        else:
            issues.append("No microphone input device was detected.")
            details.append("Microphone devices: none detected")

        ready = len(issues) == 0
        status = "Dictation: ready" if ready else "Dictation: setup needed"
        return ready, status, details, issues

    def _set_dictation_idle_status(self):
        mode = (self._dict_pref_mode or "offline_vosk").strip().lower()
        if mode == "windows_builtin":
            self._dict_sv.set("Dictation: Windows built-in ready (Start uses Win+H)")
            return
        if mode == "external_app":
            app_name = Path(self._dict_pref_path).name if self._dict_pref_path else "configured app"
            self._dict_sv.set(f"Dictation: external app ready ({app_name})")
            return
        _, status, _, _ = self._get_dictation_readiness()
        self._dict_sv.set(status)

    def _load_dictation_preference(self):
        self._dict_pref_mode = (db.get_app_preference("dictation.mode", "offline_vosk") or "offline_vosk").strip()
        self._dict_pref_path = (db.get_app_preference("dictation.path", "") or "").strip()
        self._dict_pref_label = (db.get_app_preference("dictation.label", "") or "").strip()
        if not self._dict_pref_label:
            if self._dict_pref_mode == "windows_builtin":
                self._dict_pref_label = "Windows Built-in Dictation (Win+H)"
            elif self._dict_pref_mode == "external_app":
                self._dict_pref_label = Path(self._dict_pref_path).name if self._dict_pref_path else "External Dictation App"
            else:
                self._dict_pref_label = "Built-in Offline Dictation (Vosk)"

    def _save_dictation_preference(self, mode, path="", label=""):
        self._dict_pref_mode = (mode or "offline_vosk").strip()
        self._dict_pref_path = (path or "").strip()
        self._dict_pref_label = (label or "").strip()
        if not self._dict_pref_label:
            if self._dict_pref_mode == "windows_builtin":
                self._dict_pref_label = "Windows Built-in Dictation (Win+H)"
            elif self._dict_pref_mode == "external_app":
                self._dict_pref_label = Path(self._dict_pref_path).name if self._dict_pref_path else "External Dictation App"
            else:
                self._dict_pref_label = "Built-in Offline Dictation (Vosk)"

        db.set_app_preference("dictation.mode", self._dict_pref_mode)
        db.set_app_preference("dictation.path", self._dict_pref_path)
        db.set_app_preference("dictation.label", self._dict_pref_label)
        self._set_dictation_idle_status()

    def _remove_saved_dictation_program(self, parent_window=None):
        if not messagebox.askyesno(
            "Remove Saved Dictation Program",
            "Remove the saved dictation program and reset to Built-in Offline Dictation (Vosk)?",
            parent=parent_window or self,
        ):
            return
        self._save_dictation_preference("offline_vosk", "", "Built-in Offline Dictation (Vosk)")
        messagebox.showinfo(
            "Removed",
            "Saved dictation program removed. Start Dictation now uses Built-in Offline Dictation (Vosk).",
            parent=parent_window or self,
        )

    def _trigger_windows_dictation_hotkey(self):
        if os.name != "nt":
            return False
        try:
            import ctypes

            user32 = ctypes.windll.user32
            VK_LWIN = 0x5B
            VK_H = 0x48
            KEYEVENTF_KEYUP = 0x0002

            user32.keybd_event(VK_LWIN, 0, 0, 0)
            user32.keybd_event(VK_H, 0, 0, 0)
            user32.keybd_event(VK_H, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
            return True
        except Exception:
            return False

    def _check_dictation_setup(self):
        _, status, details, issues = self._get_dictation_readiness()
        lines = [status, "", "Checks:"]
        lines.extend([f"- {line}" for line in details])
        if issues:
            lines.append("")
            lines.append("Action Needed:")
            lines.extend([f"- {issue}" for issue in issues])
        else:
            lines.append("")
            lines.append("Action Needed:")
            lines.append("- None. Dictation is ready to use.")
        messagebox.showinfo("Dictation Setup Check", "\n".join(lines), parent=self)
        self._dict_sv.set(status)

    def _append_dictation_text(self, text):
        text = (text or "").strip()
        if not text:
            return
        self._insert_text_into_selected_target(text)

    def _insert_text_into_selected_target(self, text):
        text = (text or "").strip()
        if not text:
            return
        target_name = self._dict_target_var.get().strip()
        target_widget = self._dictation_targets.get(target_name, self._nt)
        current = target_widget.get("1.0", "end-1c").strip()
        prefix = "\n" if current else ""
        target_widget.insert("end", f"{prefix}{text}")
        target_widget.see("end")

    def _paste_dictation_from_clipboard(self):
        try:
            text = self.clipboard_get()
        except Exception:
            text = ""
        text = (text or "").strip()
        if not text:
            messagebox.showinfo(
                "Clipboard Empty",
                "No text found in clipboard. Use your preferred dictation software first, then click 'Paste Dictation'.",
                parent=self,
            )
            return
        self._insert_text_into_selected_target(text)
        self._dict_sv.set("Dictation: pasted from clipboard")

    def _scan_dictation_apps_async(self):
        """Background scan for dictation apps at startup. Caches result for UI dialogs."""
        def _scan_thread():
            try:
                self._cached_dictation_apps = self._find_dictation_apps()
            except Exception as e:
                _append_startup_log(f"Dictation scan error: {e}")
                self._cached_dictation_apps = [("Windows Built-in Dictation (Win+H)", "")]
        
        t = threading.Thread(target=_scan_thread, daemon=True)
        t.start()

    @staticmethod
    def _find_dictation_apps():
        """Search for installed dictation apps on Windows. Returns list of (label, exe_path)."""
        return _find_dictation_apps_systemwide()

    def _launch_dictation_app(self, exe_path, mark_active=False):
        try:
            p = str(exe_path or "").strip().strip('"')
            if not p:
                self._show_system_dictation_help()
                return

            resolved = _normalize_dictation_launch_path(p) if os.name == "nt" else p
            launch_path = resolved or p

            if os.name == "nt":
                # Resolve shortcuts/commands to a concrete launcher first.
                os.startfile(launch_path)
                self._external_dictation_proc = None
            else:
                self._external_dictation_proc = subprocess.Popen([launch_path])

            if mark_active:
                self._active_dictation_mode = "external_app"
                self._btn_start_dict.configure(state="disabled")
                self._btn_stop_dict.configure(state="normal")
            self._dict_sv.set("Dictation: external app launched")
        except Exception as ex:
            p = str(exe_path or "").strip().strip('"')
            browse_path = _normalize_dictation_launch_path(p) if os.name == "nt" else p
            browse_path = browse_path or p
            fallback_opened = False
            if os.name == "nt" and browse_path:
                try:
                    target = Path(browse_path)
                    if target.exists() and target.is_file():
                        subprocess.Popen(["explorer", f"/select,{target}"])
                        fallback_opened = True
                    elif target.exists() and target.is_dir():
                        os.startfile(str(target))
                        fallback_opened = True
                    else:
                        parent_dir = target.parent
                        if parent_dir.exists():
                            os.startfile(str(parent_dir))
                            fallback_opened = True
                except Exception:
                    fallback_opened = False

            if fallback_opened:
                messagebox.showerror(
                    "Launch Failed",
                    f"Could not launch:\n{exe_path}\n\n{ex}\n\n"
                    "File Explorer was opened to the detected location so you can launch it manually.",
                    parent=self,
                )
            else:
                messagebox.showerror("Launch Failed", f"Could not launch:\n{exe_path}\n\n{ex}", parent=self)

    def _browse_and_launch_dictation(self):
        path = filedialog.askopenfilename(
            title="Select Dictation Software",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
            parent=self,
        )
        if path:
            self._save_dictation_preference("external_app", path, Path(path).name)
            self._launch_dictation_app(path)

    def _show_dictation_scan_results(self, detected, parent_window=None):
        detected = list(detected or [])
        installed = [(label, exe) for label, exe in detected if exe]
        built_in = [label for label, exe in detected if not exe]

        lines = [
            "Dictation Scan Results",
            "",
            f"Installed dictation apps found: {len(installed)}",
            f"Built-in dictation options found: {len(built_in)}",
            "",
        ]

        if installed:
            lines.append("Installed apps:")
            for label, exe in installed:
                lines.append(f"- {label} -> {exe}")
            lines.append("")

        if built_in:
            lines.append("Built-in options:")
            for label in built_in:
                lines.append(f"- {label}")
            lines.append("")

        if not detected:
            lines.append("No dictation software was detected automatically.")
            lines.append("You can still use Windows built-in dictation or browse for an app manually.")

        win = tk.Toplevel(parent_window or self)
        apply_window_icon(win)
        win.title("Dictation Scan Results")
        win.resizable(True, True)
        win.transient(parent_window or self)

        try:
            win.state("zoomed")
        except Exception:
            _w, _h = _screen_fit(max(900, SCREEN_W - 40), max(620, SCREEN_H - 80), pad=0)
            win.geometry(f"{_w}x{_h}+0+0")

        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Dictation Scan Results", font=FONT_LG).pack(anchor="w")
        ttk.Label(frm, text=f"Installed apps found: {len(installed)}    Built-in options found: {len(built_in)}", foreground=MUTED).pack(anchor="w", pady=(4, 8))

        txt = tk.Text(frm, wrap="word", font=FONT_UI, relief="solid", borderwidth=1)
        sb = ttk.Scrollbar(frm, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        txt.insert("1.0", "\n".join(lines))
        txt.configure(state="disabled")

        btn_row = ttk.Frame(win, padding=(12, 0, 12, 12))
        btn_row.pack(fill="x")

        def _copy_results():
            self.clipboard_clear()
            self.clipboard_append("\n".join(lines))
            self.update()
            messagebox.showinfo("Dictation Scan Results", "Results copied to clipboard.", parent=win)

        btn(btn_row, "Copy Results", _copy_results, "Accent.TButton").pack(side="left", padx=4)
        btn(btn_row, "Close", win.destroy).pack(side="left", padx=4)

    def _show_system_dictation_help(self):
        lines = [
            "Use Any Dictation Software",
            "",
            "TheraTrak supports two dictation paths:",
            "- Built-in offline dictation (Start/Stop Dictation) when local Vosk is configured.",
            "- Any external/platform dictation app via clipboard + 'Paste Dictation'.",
            "",
            "Common platform shortcuts:",
            "- Windows: Win + H  (built-in Windows dictation — works everywhere)",
            "- macOS: Press Fn twice (if enabled in Keyboard settings)",
            "",
            "Workflow:",
            "1) Select 'Dictate To' destination.",
            "2) Run your preferred dictation software (or use Dictation Settings > Launch).",
            "3) Dictate your text.",
            "4) Copy transcript to clipboard if needed.",
            "5) Click 'Paste Dictation' in Session Note.",
        ]
        messagebox.showinfo("Dictation Help", "\n".join(lines), parent=self)

    def _open_models_folder(self):
        try:
            VOSK_MODELS_DIR.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(VOSK_MODELS_DIR))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(VOSK_MODELS_DIR)])
            else:
                subprocess.Popen(["xdg-open", str(VOSK_MODELS_DIR)])
        except Exception as ex:
            messagebox.showerror("Open Folder Failed", f"Could not open models folder:\n{ex}", parent=self)

    def _open_dictation_settings(self):
        _, status, details, issues = self._get_dictation_readiness()
        win = tk.Toplevel(self)
        apply_window_icon(win)
        win.title("Dictation Settings")
        win.resizable(True, True)
        win.transient(self)
        win.grab_set()
        win.update_idletasks()
        try:
            win.state("zoomed")
        except Exception:
            _w, _h = _screen_fit(max(1000, SCREEN_W - 20), max(760, SCREEN_H - 40), pad=0)
            win.geometry(f"{_w}x{_h}+0+0")
        win.lift()
        win.focus_force()

        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Dictation Settings", font=FONT_LG).pack(anchor="w")
        ttk.Label(frm, text=f"Current Status: {status}", foreground=MUTED).pack(anchor="w", pady=(4, 2))
        ttk.Label(
            frm,
            text=f"Default Dictation: {self._dict_pref_label}",
            foreground=ACCENT,
            font=("Arial", 10, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        # ── Header for detected apps section ──────────────────────────────
        header_frame = ttk.Frame(frm)
        header_frame.pack(fill="x", pady=(0, 6))
        ttk.Label(header_frame, text="Detected Dictation Software (computer scan):", font=FONT_SM).pack(side="left")
        
        def _rescan():
            self._cached_dictation_apps = self._find_dictation_apps()
            self._show_dictation_scan_results(self._cached_dictation_apps, parent_window=win)
            win.destroy()
            self._open_dictation_settings()
        
        btn(header_frame, "Rescan Computer", _rescan).pack(side="right")

        # Use cached apps if available, otherwise scan now
        detected = self._cached_dictation_apps if self._cached_dictation_apps else self._find_dictation_apps()

        # ── Dragon quick-launch (shown only when Dragon is detected) ──────
        dragon_apps = [(lbl, exe) for lbl, exe in detected
                       if "dragon" in lbl.lower() or "natspeak" in (exe or "").lower()]
        if dragon_apps:
            dragon_frame = ttk.LabelFrame(frm, text="Dragon NaturallySpeaking (Detected)", padding=8)
            dragon_frame.pack(fill="x", pady=(0, 6))
            dlbl, dexe = dragon_apps[0]
            ttk.Label(dragon_frame, text=f"Found: {dlbl}", foreground=SUCCESS).pack(side="left", padx=(0, 10))

            def _dragon_one_click(_exe=dexe, _lbl=dlbl):
                self._save_dictation_preference("external_app", _exe, _lbl)
                self._launch_dictation_app(_exe)
                win.destroy()

            btn(dragon_frame, "Set Default & Launch Dragon", _dragon_one_click, style="Accent.TButton").pack(side="left")

        # ── Installed dictation apps ──────────────────────────────────────
        app_frame = ttk.LabelFrame(frm, text="Select and Launch", padding=8)
        app_frame.pack(fill="x", pady=(0, 10))

        if detected:
            app_labels = {}
            for label, exe in detected:
                display = f"{label}  —  {Path(exe).name}" if exe else label
                mode = "external_app" if exe else "windows_builtin"
                app_labels[display] = (mode, exe, label)
            app_combo = ttk.Combobox(
                app_frame,
                values=list(app_labels.keys()),
                state="readonly",
                width=56,
            )
            app_combo.current(0)
            app_combo.pack(side="left", padx=(0, 6))

            def _launch_selected():
                sel = app_combo.get()
                picked = app_labels.get(sel)
                if not picked:
                    return
                mode, exe, label = picked
                if mode == "external_app" and exe:
                    self._save_dictation_preference("external_app", exe, label)
                    self._launch_dictation_app(exe)
                    win.destroy()
                else:
                    self._save_dictation_preference("windows_builtin", "", "Windows Built-in Dictation (Win+H)")
                    if self._trigger_windows_dictation_hotkey():
                        self._dict_sv.set("Dictation: Windows built-in listening")
                    else:
                        self._show_system_dictation_help()
                    win.destroy()

            btn(app_frame, "Launch Selected", _launch_selected).pack(side="left")
            
            def _set_as_default():
                sel = app_combo.get()
                picked = app_labels.get(sel)
                if not picked:
                    return
                mode, exe, label = picked
                if mode == "external_app" and exe:
                    self._save_dictation_preference("external_app", exe, label)
                    messagebox.showinfo(
                        "Saved",
                        f"Default dictation set to {label}.\nLaunch from 'Start Dictation' when ready.",
                        parent=win,
                    )
                else:
                    self._save_dictation_preference("windows_builtin", "", "Windows Built-in Dictation (Win+H)")
                    messagebox.showinfo(
                        "Saved",
                        "Default dictation set to Windows Built-in.\nPress Win+H or use 'Start Dictation' when ready.",
                        parent=win,
                    )
            
            btn(app_frame, "Set as Default", _set_as_default).pack(side="left", padx=4)
        else:
            ttk.Label(
                app_frame,
                text="No installed dictation apps detected automatically. Click 'Rescan' or 'Browse' to locate one.",
                foreground=MUTED,
            ).pack(side="left")

        def _use_offline_vosk_default():
            self._save_dictation_preference("offline_vosk", "", "Built-in Offline Dictation (Vosk)")
            messagebox.showinfo("Saved", "Default dictation method set to Built-in Offline Dictation (Vosk).", parent=win)

        # ── Action buttons ────────────────────────────────────────────────────
        action_frame = ttk.LabelFrame(frm, text="Other Options", padding=8)
        action_frame.pack(fill="x", pady=(0, 10))
        
        btn(action_frame, "Browse for Dictation App…", self._browse_and_launch_dictation).pack(side="left", padx=4)
        btn(action_frame, "Use Offline Dictation by Default", _use_offline_vosk_default).pack(side="left", padx=4)
        btn(
            action_frame,
            "Reset to Default",
            lambda: self._remove_saved_dictation_program(win),
        ).pack(side="left", padx=4)

        # ── Offline Vosk status ───────────────────────────────────────────
        ttk.Separator(frm, orient="horizontal").pack(fill="x", pady=4)
        ttk.Label(frm, text="Built-in Offline Dictation (Vosk):", font=FONT_SM).pack(anchor="w", pady=(0, 2))
        ttk.Label(frm, text=f"Models Folder: {VOSK_MODELS_DIR}").pack(anchor="w", pady=(0, 4))

        info = tk.Text(frm, height=7, wrap="word", relief="solid", borderwidth=1)
        info.pack(fill="x")
        lines = ["Checks:"]
        lines.extend([f"- {line}" for line in details])
        lines.append("")
        lines.append("Action Needed:")
        if issues:
            lines.extend([f"- {issue}" for issue in issues])
        else:
            lines.append("- None. Dictation is ready to use.")
        lines.append("")
        lines.append("Model Tip:")
        lines.append("- Place an extracted vosk-model-* folder under the models folder above.")
        info.insert("1.0", "\n".join(lines))
        info.configure(state="disabled")

        # ── Detected app diagnostics ──────────────────────────────────────
        ttk.Separator(frm, orient="horizontal").pack(fill="x", pady=4)
        ttk.Label(frm, text="Detected App Details:", font=FONT_SM).pack(anchor="w", pady=(0, 2))
        diag = tk.Text(frm, height=4, wrap="word", relief="solid", borderwidth=1)
        diag.pack(fill="x")
        diag_lines = []
        for _dlbl, _dexe in detected:
            if _dexe:
                diag_lines.append(f"  {_dlbl}: {_dexe}")
            else:
                diag_lines.append(f"  {_dlbl}: (built-in, no path)")
        if not diag_lines:
            diag_lines = ["  No dictation apps found. Try Rescan."]
        diag.insert("1.0", "\n".join(diag_lines))
        diag.configure(state="disabled")

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(8, 0))
        btn(btns, "Open Models Folder", self._open_models_folder).pack(side="left")
        btn(btns, "Dictation Help", self._show_system_dictation_help).pack(side="left", padx=6)
        btn(btns, "Run Setup Check", self._check_dictation_setup).pack(side="left", padx=6)
        btn(btns, "Close", win.destroy).pack(side="right")

    def _dictation_worker(self, model_dir):
        q = queue.Queue()

        if _sd is None or _vosk is None:
            self.after(0, self._dict_sv.set, "Dictation error: offline dictation packages are unavailable.")
            self.after(0, self._on_dictation_stopped)
            return

        def _audio_callback(indata, frames, time_info, status):
            if self._dictation_stop.is_set():
                return
            q.put(bytes(indata))

        try:
            model = _vosk.Model(str(model_dir))
            rec = _vosk.KaldiRecognizer(model, 16000)

            with _sd.RawInputStream(
                samplerate=16000,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=_audio_callback,
            ):
                while not self._dictation_stop.is_set():
                    try:
                        data = q.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        text = (result.get("text") or "").strip()
                        if text:
                            self.after(0, self._append_dictation_text, text)

                final_result = json.loads(rec.FinalResult())
                final_text = (final_result.get("text") or "").strip()
                if final_text:
                    self.after(0, self._append_dictation_text, final_text)
        except Exception as ex:
            self.after(0, self._dict_sv.set, f"Dictation error: {ex}")
        finally:
            self.after(0, self._on_dictation_stopped)

    def _on_dictation_stopped(self):
        self._dictating = False
        self._active_dictation_mode = None
        self._dictation_stop.set()
        self._btn_start_dict.configure(state="normal")
        self._btn_stop_dict.configure(state="disabled")
        if not self._dict_sv.get().startswith("Dictation error"):
            self._set_dictation_idle_status()

    def _start_dictation(self):
        if self._dictating or self._active_dictation_mode:
            return
        mode = (self._dict_pref_mode or "offline_vosk").strip().lower()

        if mode == "windows_builtin":
            if self._trigger_windows_dictation_hotkey():
                self._active_dictation_mode = "windows_builtin"
                self._btn_start_dict.configure(state="disabled")
                self._btn_stop_dict.configure(state="normal")
                self._dict_sv.set("Dictation: Windows built-in listening")
            else:
                self._show_system_dictation_help()
            return

        if mode == "external_app":
            if self._dict_pref_path:
                self._launch_dictation_app(self._dict_pref_path, mark_active=True)
                self._dict_sv.set("Dictation: external app started. Speak there, then click Paste Dictation.")
                return
            messagebox.showinfo(
                "Dictation App Not Set",
                "No default external dictation app path is saved. Open Dictation Settings and choose Launch once.",
                parent=self,
            )
            return

        if not _HAS_OFFLINE_STT:
            messagebox.showerror(
                "Offline Dictation Unavailable",
                "Offline dictation requires local packages 'vosk' and 'sounddevice'.",
                parent=self,
            )
            return
        model_dir = self._find_vosk_model()
        if not model_dir:
            messagebox.showerror(
                "Model Not Found",
                "Place a Vosk model folder under APP_ROOT/models (e.g., models/vosk-model-small-en-us-0.15).",
                parent=self,
            )
            return
        self._dictation_stop.clear()
        self._dictating = True
        self._dict_sv.set("Dictation: listening...")
        self._btn_start_dict.configure(state="disabled")
        self._btn_stop_dict.configure(state="normal")
        self._dictation_thread = threading.Thread(
            target=self._dictation_worker,
            args=(model_dir,),
            daemon=True,
        )
        self._dictation_thread.start()

    def _stop_dictation(self):
        if self._dictating:
            self._dict_sv.set("Dictation: stopping...")
            self._dictation_stop.set()
            return

        if self._active_dictation_mode == "windows_builtin":
            # Win+H toggles Windows dictation on/off.
            self._trigger_windows_dictation_hotkey()
            self._active_dictation_mode = None
            self._btn_start_dict.configure(state="normal")
            self._btn_stop_dict.configure(state="disabled")
            self._set_dictation_idle_status()
            return

        if self._active_dictation_mode == "external_app":
            proc = self._external_dictation_proc
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
            self._external_dictation_proc = None
            self._active_dictation_mode = None
            self._btn_start_dict.configure(state="normal")
            self._btn_stop_dict.configure(state="disabled")
            self._set_dictation_idle_status()
            if getattr(self, "_auto_paste_after_dictation", None) and self._auto_paste_after_dictation.get():
                self.after(600, self._paste_dictation_from_clipboard)
            return

        self._set_dictation_idle_status()

    def _close_dialog(self):
        self._stop_dictation()
        self.destroy()

    def _load_patients(self):
        self._pts = db.get_all_patients("Active")
        names = [f"{p['last_name']}, {p['first_name']}  (ID:{p['id']})" for p in self._pts]
        self.pt_combo["values"] = names

    def _dx_pick(self, code):
        for key in PATIENT_DX_KEYS:
            if not self._vars[key].get():
                self._vars[key].set(code)
                return
        self._vars[PATIENT_DX_KEYS[-1]].set(code)

    def _autofill_fee_from_cpt(self):
        if self._suspend_cpt_fee_autofill:
            return
        cpt_code = str(self._vars.get("cpt_code", tk.StringVar(value="")).get() or "").strip()
        amount = get_cpt_fee_amount(cpt_code)
        if amount is None:
            return
        self._vars["fee"].set(f"{amount:.2f}")

    def _load(self):
        s = db.get_session(self.sid)
        if not s:
            return
        for key, var in self._vars.items():
            if key == "patient_id":
                continue
            v = s[key] if key in s.keys() else ""
            if key == "fee":
                var.set(f"{float(v or 0):.2f}")
            else:
                var.set(str(v) if v is not None else "")
        # Set patient combo
        for i, p in enumerate(self._pts):
            if p["id"] == s["patient_id"]:
                self.pt_combo.current(i)
                self._vars["patient_id"].set(str(s["patient_id"]))
                break
        self._nt.insert("1.0", s["note_text"] or "")
        self._goals.insert("1.0", s["goals"] or "")
        self._interventions.insert("1.0", s["interventions"] or "")
        self._response.insert("1.0", s["response"] or "")
        self._plan.insert("1.0", s["plan"] or "")
        self.signed_var.set(s["signed"] or 0)
        self.billing_var.set(1)  # Always default ON for both new and edited sessions
        # Sync DateEntry widget to loaded date value
        if _HAS_CALENDAR and hasattr(self, "_date_entry"):
            sd = s["session_date"] or ""
            try:
                import datetime as _dt
                d = _dt.date.fromisoformat(sd)
                self._date_entry.set_date(d)
                # Update the StringVar to display format so widget shows correctly
                self._vars["session_date"].set(d.strftime("%m/%d/%Y"))
            except Exception:
                pass

    def _sync_billing_record(self, sid: int, pid: int, data: dict):
        session_date = str(data.get("session_date", "") or "")
        cpt_code = str(data.get("cpt_code", "") or "")
        session_type = str(data.get("session_type", "") or "Session")
        try:
            fee = float(data.get("fee", 0) or 0)
        except Exception:
            fee = 0.0

        description = f"{session_type} {cpt_code}".strip()
        existing = db.get_billing_record_for_session(sid)

        if existing:
            payload = {
                "id": existing["id"],
                "patient_id": pid,
                "session_id": sid,
                "record_date": existing["record_date"] or session_date or current_date_str(),
                "service_date": session_date,
                "description": description,
                "charge": fee,
                "payment": float(existing["payment"] or 0),
                "payment_type": existing["payment_type"] or "",
                "check_number": existing["check_number"] or "",
                "ins_payment": float(existing["ins_payment"] or 0),
                "adjustment": float(existing["adjustment"] or 0),
                "claim_number": existing["claim_number"] or "",
            }
            payload["balance"] = payload["charge"] - payload["payment"] - payload["ins_payment"] - payload["adjustment"]
            db.save_billing_record(payload)
            return

        payload = {
            "patient_id": pid,
            "session_id": sid,
            "record_date": session_date or current_date_str(),
            "service_date": session_date,
            "description": description,
            "charge": fee,
            "payment": 0.0,
            "payment_type": "",
            "check_number": "",
            "ins_payment": 0.0,
            "adjustment": 0.0,
            "balance": fee,
            "claim_number": "",
        }
        db.save_billing_record(payload)

    def _save(self):
        # Resolve patient ID from combo
        sel = self.pt_combo.current()
        if sel < 0:
            messagebox.showerror("Required", "Please select a patient.", parent=self)
            return
        pid = self._pts[sel]["id"]
        data = {k: v.get().strip() for k, v in self._vars.items()}
        data["patient_id"] = pid
        # Normalise date to YYYY-MM-DD regardless of picker display format
        raw_date = data.get("session_date", "").strip()
        if raw_date:
            import datetime as _dt
            for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
                try:
                    raw_date = _dt.datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d")
                    break
                except ValueError:
                    pass
        data["session_date"] = raw_date
        if not raw_date:
            messagebox.showerror("Required", "Session date is required.", parent=self)
            return
        data["note_text"]     = self._nt.get("1.0", "end-1c")
        data["goals"]         = self._goals.get("1.0", "end-1c")
        data["interventions"] = self._interventions.get("1.0", "end-1c")
        data["response"]      = self._response.get("1.0", "end-1c")
        data["plan"]          = self._plan.get("1.0", "end-1c")
        data["signed"]        = self.signed_var.get()
        if data["signed"]:
            data["signed_date"] = current_date_str()
        try:
            data["fee"] = float(data.get("fee", 0) or 0)
            data["duration"] = int(data.get("duration", 50) or 50)
        except ValueError:
            pass
        if self.sid:
            data["id"] = self.sid
        sid = db.save_session(data)
        if sid is None:
            messagebox.showerror("Save Error", "Could not save session.", parent=self)
            return
        if self.billing_var.get():
            try:
                self._sync_billing_record(sid, pid, data)
            except Exception as ex:
                messagebox.showerror(
                    "Billing Sync Error",
                    f"Session was saved, but billing could not be synced:\n{ex}",
                    parent=self,
                )
        if self.on_save:
            self.on_save(sid)
        self.destroy()


# ─── Billing Record Dialog ─────────────────────────────────────────────────────

class BillingDialog(tk.Toplevel):
    def __init__(self, parent, rid=None, pid=None, seed_session_id=None, on_save=None):
        super().__init__(parent)
        apply_window_icon(self)
        self.rid = rid
        self.pid = pid
        self.seed_session_id = seed_session_id
        self.on_save = on_save
        self.title("Edit Record" if rid else "New Billing Record")
        _w, _h = _screen_fit(560, 420)
        self.geometry(f"{_w}x{_h}")
        self.resizable(True, True)
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        self._vars = {}
        self._session_rows = []
        self._build()
        if rid:
            self._load()
        elif pid:
            self._vars["patient_id"].set(str(pid))
            self._vars["record_date"].set(date.today().strftime("%m/%d/%Y"))
            self._select_patient_by_id(pid)
            self._refresh_session_choices(preferred_sid=self.seed_session_id, auto_prefill=True)
        # Avoid hard modal grab so Windows minimize works reliably.

    def _fld(self, name, default=""):
        v = tk.StringVar(value=default)
        self._vars[name] = v
        return v

    def _build(self):
        f = ttk.Frame(self, padding=14)
        f.pack(fill="both", expand=True)
        for c in (0, 2):
            f.columnconfigure(c, weight=0, minsize=118)
        for c in (1, 3):
            f.columnconfigure(c, weight=1, minsize=150)

        # Patient
        ttk.Label(f, text="Patient*").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.pt_var = tk.StringVar()
        self.pt_combo = ttk.Combobox(f, textvariable=self.pt_var, width=32, state="readonly")
        self.pt_combo.grid(row=0, column=1, columnspan=3, sticky="ew")
        self._load_patients()
        self.pt_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_session_choices(auto_prefill=True))
        self._fld("patient_id")
        self._fld("session_id")

        ttk.Label(f, text="Record Date*").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self._fld("record_date")
        if _HAS_CALENDAR:
            _DateEntry(f, textvariable=self._vars["record_date"], width=12,
                       date_pattern="MM/dd/yyyy").grid(row=1, column=1, sticky="ew")
        else:
            ttk.Entry(f, textvariable=self._vars["record_date"], width=14).grid(row=1, column=1, sticky="ew")
        ttk.Label(f, text="Service Date").grid(row=1, column=2, sticky="e", padx=4)
        self._fld("service_date")
        if _HAS_CALENDAR:
            _DateEntry(f, textvariable=self._vars["service_date"], width=12,
                       date_pattern="MM/dd/yyyy").grid(row=1, column=3, sticky="ew")
        else:
            ttk.Entry(f, textvariable=self._vars["service_date"], width=14).grid(row=1, column=3, sticky="ew")

        ttk.Label(f, text="Description").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f, textvariable=self._fld("description"), width=36).grid(row=2, column=1, columnspan=3, sticky="ew")

        ttk.Label(f, text="Charge ($)").grid(row=3, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f, textvariable=self._fld("charge", "0.00"), width=10).grid(row=3, column=1, sticky="ew")
        ttk.Label(f, text="Pt. Payment ($)").grid(row=3, column=2, sticky="e", padx=4)
        ttk.Entry(f, textvariable=self._fld("payment", "0.00"), width=10).grid(row=3, column=3, sticky="ew")

        ttk.Label(f, text="Ins. Payment ($)").grid(row=4, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f, textvariable=self._fld("ins_payment", "0.00"), width=10).grid(row=4, column=1, sticky="ew")
        ttk.Label(f, text="Adjustment ($)").grid(row=4, column=2, sticky="e", padx=4)
        ttk.Entry(f, textvariable=self._fld("adjustment", "0.00"), width=10).grid(row=4, column=3, sticky="ew")

        ttk.Label(f, text="Payment Type").grid(row=5, column=0, sticky="e", padx=4, pady=4)
        ttk.Combobox(f, textvariable=self._fld("payment_type"),
                     values=["","Cash","Check","Credit Card","Debit Card","PayPal","Venmo","Insurance","Write-off","Other"],
                 width=16).grid(row=5, column=1, sticky="ew")
        ttk.Label(f, text="Check #").grid(row=5, column=2, sticky="e", padx=4)
        ttk.Entry(f, textvariable=self._fld("check_number"), width=12).grid(row=5, column=3, sticky="ew")

        ttk.Label(f, text="Claim #").grid(row=6, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f, textvariable=self._fld("claim_number"), width=20).grid(row=6, column=1, sticky="ew")

        ttk.Label(f, text="Unbilled Session").grid(row=7, column=0, sticky="e", padx=4, pady=4)
        self.sess_var = tk.StringVar()
        self.sess_combo = ttk.Combobox(f, textvariable=self.sess_var, width=32, state="readonly")
        self.sess_combo.grid(row=7, column=1, columnspan=3, sticky="ew")
        self.sess_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_selected_session_prefill())

        ttk.Label(
            f,
            text="Selecting a session auto-fills service date, description, and charge.",
            foreground=MUTED,
        ).grid(row=8, column=0, columnspan=4, sticky="w", padx=4, pady=(0, 2))

        bot = ttk.Frame(self, padding=8)
        bot.pack(fill="x", side="bottom")
        btn(bot, "Save", self._save, "Accent.TButton").pack(side="left", padx=6)
        btn(bot, "Cancel", self.destroy).pack(side="left")

    def _load_patients(self):
        self._pts = db.get_all_patients("Active") + db.get_all_patients("Inactive")
        names = [f"{p['last_name']}, {p['first_name']}  (ID:{p['id']})" for p in self._pts]
        self.pt_combo["values"] = names

    def _load(self):
        conn = db.get_connection()
        r = conn.execute("SELECT * FROM billing_records WHERE id=?", (self.rid,)).fetchone()
        conn.close()
        if not r:
            return
        for key, var in self._vars.items():
            if key == "patient_id":
                continue
            v = r[key] if key in r.keys() else ""
            val = str(v) if v is not None else ""
            if key in ("record_date", "service_date") and val:
                val = fmt_date(val)
            var.set(val)
        for i, p in enumerate(self._pts):
            if p["id"] == r["patient_id"]:
                self.pt_combo.current(i)
                break
        self._refresh_session_choices(preferred_sid=r["session_id"], auto_prefill=False)

    def _select_patient_by_id(self, pid):
        for i, p in enumerate(self._pts):
            if p["id"] == pid:
                self.pt_combo.current(i)
                self._vars["patient_id"].set(str(pid))
                return

    def _refresh_session_choices(self, preferred_sid=None, auto_prefill=False):
        sel = self.pt_combo.current()
        if sel < 0:
            self._session_rows = []
            self.sess_combo["values"] = []
            self.sess_var.set("")
            self._vars["session_id"].set("")
            return

        pid = self._pts[sel]["id"]
        self._vars["patient_id"].set(str(pid))

        session_rows = [dict(s) for s in db.get_unbilled_sessions_for_patient(pid)]
        if preferred_sid:
            existing = db.get_session(preferred_sid)
            if existing and not any(int(s.get("id", 0)) == int(preferred_sid) for s in session_rows):
                session_rows.insert(0, dict(existing))

        self._session_rows = session_rows
        labels = [
            f"{fmt_date(s.get('session_date', ''))} | {s.get('session_type', '')} | {s.get('cpt_code', '')} | {fmt_money(s.get('fee', 0))}"
            for s in self._session_rows
        ]
        self.sess_combo["values"] = labels

        if not self._session_rows:
            self.sess_var.set("")
            self._vars["session_id"].set("")
            return

        idx = 0
        if preferred_sid:
            for i, s in enumerate(self._session_rows):
                if int(s.get("id", 0) or 0) == int(preferred_sid):
                    idx = i
                    break

        self.sess_combo.current(idx)
        if auto_prefill:
            self._apply_selected_session_prefill()

    def _apply_selected_session_prefill(self):
        idx = self.sess_combo.current()
        if idx < 0 or idx >= len(self._session_rows):
            self._vars["session_id"].set("")
            return

        s = self._session_rows[idx]
        self._vars["session_id"].set(str(s.get("id", "") or ""))

        _raw_sd = str(s.get("session_date", "") or "")
        self._vars["service_date"].set(fmt_date(_raw_sd) if _raw_sd else "")
        cpt = str(s.get("cpt_code", "") or "")
        stype = str(s.get("session_type", "") or "Session")
        self._vars["description"].set(f"{stype} {cpt}".strip())
        try:
            fee = float(s.get("fee", 0) or 0)
        except Exception:
            fee = 0.0
        self._vars["charge"].set(f"{fee:.2f}")

    def _save(self):
        sel = self.pt_combo.current()
        if sel < 0:
            messagebox.showerror("Required", "Please select a patient.", parent=self)
            return
        pid = self._pts[sel]["id"]
        data = {k: v.get().strip() for k, v in self._vars.items()}
        data["patient_id"] = pid
        # Normalize dates to ISO YYYY-MM-DD regardless of display format
        import datetime as _bdt
        for _dk in ("record_date", "service_date"):
            _raw = data.get(_dk, "").strip()
            if _raw:
                for _fmt in ("%m/%d/%Y", "%Y-%m-%d"):
                    try:
                        data[_dk] = _bdt.datetime.strptime(_raw, _fmt).strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        pass
        if data.get("session_id"):
            try:
                data["session_id"] = int(data["session_id"])
            except Exception:
                data["session_id"] = None
        else:
            data["session_id"] = None
        for money_key in ["charge","payment","ins_payment","adjustment"]:
            try:
                data[money_key] = float(data.get(money_key, 0) or 0)
            except ValueError:
                data[money_key] = 0.0
        data["balance"] = (data["charge"] - data["payment"]
                           - data["ins_payment"] - data["adjustment"])
        if self.rid:
            data["id"] = self.rid
        db.save_billing_record(data)
        if self.on_save:
            self.on_save()
        self.destroy()


# ─── Patients Tab ──────────────────────────────────────────────────────────────

class PatientsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._status_filter = tk.StringVar(value="Active")
        self._build()
        self.refresh()

    def _build(self):
        # Toolbar
        tb = ttk.Frame(self, padding=(8, 6))
        tb.pack(fill="x")

        btn(tb, "+ New Patient", self._new_patient, "Accent.TButton").pack(side="left", padx=4)
        btn(tb, "Edit", self._edit_patient).pack(side="left", padx=2)
        btn(tb, "Deactivate", self._deactivate).pack(side="left", padx=2)
        btn(tb, "Delete", self._delete, "Danger.TButton").pack(side="left", padx=2)
        btn(tb, "View Sessions", self._view_sessions).pack(side="left", padx=2)
        btn(tb, "Billing Ledger", self._view_billing).pack(side="left", padx=2)

        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=8)

        ttk.Label(tb, text="Show:").pack(side="left")
        ttk.Combobox(tb, textvariable=self._status_filter,
                     values=["Active", "Inactive", "All"], width=10, state="readonly"
                     ).pack(side="left", padx=4)
        self._status_filter.trace_add("write", lambda *a: self.refresh())

        ttk.Label(tb, text="Search:").pack(side="left", padx=(8, 2))
        self._sv = tk.StringVar()
        self._sv.trace_add("write", lambda *a: self.refresh())
        ttk.Entry(tb, textvariable=self._sv, width=24).pack(side="left")
        btn(tb, "Clear", lambda: self._sv.set("")).pack(side="left", padx=2)

        self._lbl_count = ttk.Label(tb, text="", foreground=MUTED)
        self._lbl_count.pack(side="right", padx=8)

        # Treeview
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=8, pady=4)

        cols = ("id","last_name","first_name","dob","phone_home","insurance","dx1","status")
        self.tv = ttk.Treeview(frm, columns=cols, show="headings", selectmode="browse")
        hdrs = [("ID",48),("Last Name",150),("First Name",136),("DOB",96),
            ("Phone",126),("Insurance",190),("Dx1",110),("Status",92)]
        for (hdr, w), col in zip(hdrs, cols):
            self.tv.heading(col, text=hdr, anchor="w")
            self.tv.column(col, width=_sc(w), stretch=col in ("last_name","first_name","insurance"))

        vsb = ttk.Scrollbar(frm, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vsb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tv.bind("<Double-1>", lambda e: self._edit_patient())
        self.tv.tag_configure("even", background=ROW_EVEN)

    def refresh(self):
        self.tv.delete(*self.tv.get_children())
        status = self._status_filter.get()
        term = self._sv.get().strip()
        if term:
            rows = db.search_patients(term, "Active") + (
                db.search_patients(term, "Inactive") if status in ("Inactive","All") else [])
        else:
            rows = []
            if status in ("Active", "All"):
                rows += db.get_all_patients("Active")
            if status in ("Inactive", "All"):
                rows += db.get_all_patients("Inactive")
            rows.sort(key=lambda r: (r["last_name"] or "").lower())

        for i, r in enumerate(rows):
            tag = "even" if i % 2 == 0 else "odd"
            self.tv.insert("", "end", iid=str(r["id"]), tags=(tag,),
                           values=(r["id"], r["last_name"], r["first_name"],
                                   fmt_date(r["dob"]), r["phone_home"] or r["phone_cell"],
                                   r["ins_name"], r["dx1"], r["status"]))
        self._lbl_count.config(text=f"{len(rows)} patient(s)")

    def _selected_pid(self):
        sel = self.tv.selection()
        return int(sel[0]) if sel else None

    def _new_patient(self):
        PatientDialog(self, on_save=lambda _: self.refresh())

    def _edit_patient(self):
        pid = self._selected_pid()
        if not pid:
            messagebox.showinfo("Select", "Please select a patient first.")
            return
        PatientDialog(self, pid=pid, on_save=lambda _: self.refresh())

    def _deactivate(self):
        pid = self._selected_pid()
        if not pid:
            return
        pt = db.get_patient(pid)
        new_status = "Active" if pt["status"] == "Inactive" else "Inactive"
        if messagebox.askyesno("Confirm", f"Set status to {new_status}?"):
            db.set_patient_status(pid, new_status)
            self.refresh()

    def _delete(self):
        pid = self._selected_pid()
        if not pid:
            return
        if messagebox.askyesno("Delete Patient",
                                "Permanently delete this patient and ALL associated records?\n"
                                "This cannot be undone.", icon="warning"):
            db.delete_patient(pid)
            self.refresh()

    def _view_sessions(self):
        pid = self._selected_pid()
        if not pid:
            messagebox.showinfo("Select", "Please select a patient first.")
            return
        # Switch to Sessions tab and filter by patient
        nb = self.master
        if not isinstance(nb, ttk.Notebook):
            return
        for i in range(nb.index("end")):
            if "Session" in nb.tab(i, "text"):
                nb.select(i)
                if hasattr(nb.nametowidget(nb.tabs()[i]), "filter_patient"):
                    nb.nametowidget(nb.tabs()[i]).filter_patient(pid)
                break

    def _view_billing(self):
        pid = self._selected_pid()
        if not pid:
            messagebox.showinfo("Select", "Please select a patient first.")
            return
        nb = self.master
        if not isinstance(nb, ttk.Notebook):
            return
        for i in range(nb.index("end")):
            if "Billing" in nb.tab(i, "text"):
                nb.select(i)
                if hasattr(nb.nametowidget(nb.tabs()[i]), "filter_patient"):
                    nb.nametowidget(nb.tabs()[i]).filter_patient(pid)
                break


# ─── Session Notes Tab ─────────────────────────────────────────────────────────

class SessionNotesTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._pid_filter = None
        self._pts = []
        self._build()
        self._load_patient_list()

    def _build(self):
        tb = ttk.Frame(self, padding=(8, 6))
        tb.pack(fill="x")
        # Patient selector row
        pt_row = ttk.Frame(self, padding=(8, 4))
        pt_row.pack(fill="x")
        ttk.Label(pt_row, text="Patient:").pack(side="left")
        self._pt_sv = tk.StringVar()
        self._pt_cb = ttk.Combobox(pt_row, textvariable=self._pt_sv, state="readonly", width=36)
        self._pt_cb.pack(side="left", padx=6)
        self._pt_cb.bind("<<ComboboxSelected>>", self._on_patient_selected)
        btn(pt_row, "All Patients", self._show_all).pack(side="left", padx=4)

        btn(tb, "+ New Session", self._new_session, "Accent.TButton").pack(side="left", padx=4)
        btn(tb, "Edit", self._edit_session).pack(side="left", padx=2)
        btn(tb, "Delete", self._delete_session, "Danger.TButton").pack(side="left", padx=2)
        btn(tb, "Create Billing", self._to_billing).pack(side="left", padx=2)
        btn(tb, "Generate CMS-1500", self._to_cms).pack(side="left", padx=2)
        btn(tb, "Select All", self._select_all_rows).pack(side="left", padx=2)
        btn(tb, "Clear Selection", self._clear_selection).pack(side="left", padx=2)
        btn(tb, "Save Notes Report PDF", self._save_notes_report_pdf).pack(side="left", padx=2)
        btn(tb, "Print Selected Notes", self._print_selected_notes).pack(side="left", padx=2)

        self._pt_label = ttk.Label(tb, text="", foreground=ACCENT, font=("Calibri", 10, "bold"))
        self._pt_label.pack(side="right", padx=8)

        # Date range filter row
        dr_row = ttk.Frame(self, padding=(8, 2))
        dr_row.pack(fill="x")
        ttk.Label(dr_row, text="Date Range:").pack(side="left")
        ttk.Label(dr_row, text="From:").pack(side="left", padx=(8, 2))
        self._date_from_sv = tk.StringVar()
        ttk.Entry(dr_row, textvariable=self._date_from_sv, width=12).pack(side="left", padx=2)
        ttk.Label(dr_row, text="To:").pack(side="left", padx=(8, 2))
        self._date_to_sv = tk.StringVar()
        ttk.Entry(dr_row, textvariable=self._date_to_sv, width=12).pack(side="left", padx=2)
        ttk.Label(dr_row, text="(MM/DD/YYYY)", foreground=MUTED).pack(side="left", padx=(4, 0))
        btn(dr_row, "Apply Filter", self.refresh).pack(side="left", padx=6)
        btn(dr_row, "Clear Dates", self._clear_date_filter).pack(side="left", padx=2)

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        cols = ("id","patient_name","session_date","session_type","cpt_code","fee","signed")
        self.tv = ttk.Treeview(frm, columns=cols, show="headings", selectmode="extended")
        hdrs = [("ID",48),("Patient",220),("Date",96),("Type",132),("CPT",78),("Fee",90),("Signed",76)]
        for (h, w), c in zip(hdrs, cols):
            self.tv.heading(c, text=h, anchor="w")
            self.tv.column(c, width=_sc(w), stretch=c in ("patient_name",))
        vsb = ttk.Scrollbar(frm, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vsb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tv.bind("<Double-1>", lambda e: self._edit_session())
        self.tv.tag_configure("even", background=ROW_EVEN)
        self.tv.tag_configure("signed", foreground=SUCCESS)

        # Note preview pane
        prev_frame = lframe(self, "Session Note Preview")
        prev_frame.pack(fill="x", padx=8, pady=(0, 8))
        self._preview = tk.Text(prev_frame, height=6, font=FONT_UI, state="disabled",
                                wrap="word", relief="flat", background=BG)
        self._preview.pack(fill="x")
        self.tv.bind("<<TreeviewSelect>>", self._on_select)

    def filter_patient(self, pid):
        self._pid_filter = pid
        pt = db.get_patient(pid)
        if pt:
            self._pt_label.config(text=f"Showing: {pt['last_name']}, {pt['first_name']}")
            name = f"{pt['last_name']}, {pt['first_name']}"
            if name in self._pt_cb["values"]:
                self._pt_sv.set(name)
        self.refresh()

    def _show_all(self):
        self._pid_filter = None
        self._pt_label.config(text="")
        self._date_from_sv.set("")
        self._date_to_sv.set("")
        self._pt_sv.set("— Select Patient —")
        self.refresh()

    def _clear_date_filter(self):
        self._date_from_sv.set("")
        self._date_to_sv.set("")
        self.refresh()

    def _load_patient_list(self):
        self._pts = db.get_all_patients("Active") + db.get_all_patients("Inactive")
        self._pts.sort(key=lambda p: (p["last_name"] or "", p["first_name"] or ""))
        names = ["— Select Patient —"] + [f"{p['last_name']}, {p['first_name']}" for p in self._pts]
        self._pt_cb["values"] = names
        self._pt_sv.set("— Select Patient —")

    def _on_patient_selected(self, event=None):
        name = self._pt_sv.get()
        if name == "— Select Patient —":
            self._show_all()
            return
        match = next((p for p in self._pts if f"{p['last_name']}, {p['first_name']}" == name), None)
        if match:
            self._pid_filter = match["id"]
            self._pt_label.config(text=f"Showing: {name}")
            self._date_from_sv.set("")
            self._date_to_sv.set("")
            self.refresh()

    @staticmethod
    def _to_iso_date(d):
        """Normalize a DB session_date value to YYYY-MM-DD for comparison."""
        import datetime as _dt
        if not d:
            return ""
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
            try:
                return _dt.datetime.strptime(str(d), fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
        return str(d)

    def refresh(self):
        self.tv.delete(*self.tv.get_children())
        if not self._pid_filter:
            # Blank until a patient is chosen
            return
        date_from = self._to_iso_date(self._date_from_sv.get().strip())
        date_to = self._to_iso_date(self._date_to_sv.get().strip())
        rows = db.get_sessions_for_patient(self._pid_filter)
        if date_from:
            rows = [r for r in rows if self._to_iso_date(r["session_date"]) >= date_from]
        if date_to:
            rows = [r for r in rows if self._to_iso_date(r["session_date"]) <= date_to]
        for i, r in enumerate(rows):
            self._insert_row(r, dict(r), r["id"], even=i % 2 == 0)

    def _insert_row(self, r, rd, iid, even=False):
        name = rd.get("patient_name", "")
        if not name:
            pt = db.get_patient(rd.get("patient_id"))
            name = f"{pt['last_name']}, {pt['first_name']}" if pt else "—"
        tags = []
        if even:
            tags.append("even")
        if rd.get("signed"):
            tags.append("signed")
        self.tv.insert("", "end", iid=str(iid), tags=tags,
                       values=(iid, name, fmt_date(rd.get("session_date","")),
                               rd.get("session_type",""), rd.get("cpt_code",""),
                               fmt_money(rd.get("fee",0)),
                               "✓" if rd.get("signed") else ""))

    def _on_select(self, event=None):
        sel = self.tv.selection()
        if not sel:
            return
        sid = int(sel[0])
        s = db.get_session(sid)
        if s:
            note = s["note_text"] or ""
            self._preview.config(state="normal")
            self._preview.delete("1.0", "end")
            self._preview.insert("1.0", note[:600] + ("…" if len(note) > 600 else ""))
            self._preview.config(state="disabled")

    def _sel_sid(self):
        sel = self.tv.selection()
        return int(sel[0]) if sel else None

    def _selected_sids(self):
        return [int(x) for x in self.tv.selection()]

    def _select_all_rows(self):
        rows = self.tv.get_children()
        if not rows:
            return
        self.tv.selection_set(rows)
        self._on_select()

    def _clear_selection(self):
        self.tv.selection_remove(self.tv.selection())
        self._preview.config(state="normal")
        self._preview.delete("1.0", "end")
        self._preview.config(state="disabled")

    def _new_session(self):
        SessionDialog(self, pid=self._pid_filter, on_save=lambda _: self.refresh())

    def _edit_session(self):
        sid = self._sel_sid()
        if not sid:
            messagebox.showinfo("Select", "Please select a session first.")
            return
        SessionDialog(self, sid=sid, on_save=lambda _: self.refresh())

    def _delete_session(self):
        sid = self._sel_sid()
        if not sid:
            return
        if messagebox.askyesno("Delete", "Delete this session note?"):
            try:
                db.delete_session(sid)
                self.refresh()
            except Exception as ex:
                messagebox.showerror("Delete Error", f"Could not delete session:\n{ex}", parent=self)

    def _to_cms(self):
        sid = self._sel_sid()
        if not sid:
            messagebox.showinfo("Select", "Select a session to generate a CMS-1500 form.")
            return
        session_row = db.get_session(sid)
        if not session_row:
            return
        nb = self.master
        if not isinstance(nb, ttk.Notebook):
            return
        for i in range(nb.index("end")):
            if "CMS-1500" in nb.tab(i, "text"):
                nb.select(i)
                tab = nb.nametowidget(nb.tabs()[i])
                if hasattr(tab, "load_from_session"):
                    tab.load_from_session(session_row["patient_id"], [dict(session_row)])
                break

    def _to_billing(self):
        sid = self._sel_sid()
        if not sid:
            messagebox.showinfo("Select", "Select a session to create a billing record.")
            return

        session_row = db.get_session(sid)
        if not session_row:
            messagebox.showerror("Billing", "Could not load the selected session.")
            return

        def _after_save():
            self.refresh()
            app = self.winfo_toplevel()
            tab_billing = getattr(app, "tab_billing", None)
            if tab_billing is not None and hasattr(tab_billing, "refresh"):
                tab_billing.refresh()

        BillingDialog(
            self,
            pid=session_row["patient_id"],
            seed_session_id=session_row["id"],
            on_save=_after_save,
        )

    def _notes_report_context(self):
        selected = self._selected_sids()
        if not selected:
            messagebox.showinfo(
                "Session Notes Report",
                "Select one or more session notes to include in the report.",
            )
            return None, None

        sessions = []
        pids = set()
        for sid in selected:
            row = db.get_session(sid)
            if not row:
                continue
            row_d = dict(row)
            sessions.append(row_d)
            pids.add(int(row_d.get("patient_id") or 0))

        if not sessions:
            messagebox.showerror("Session Notes Report", "Could not load the selected session notes.")
            return None, None

        if len(pids) != 1:
            messagebox.showinfo(
                "Session Notes Report",
                "Please select notes for only one patient at a time.",
            )
            return None, None

        pid = next(iter(pids))
        patient = db.get_patient(pid)
        if not patient:
            messagebox.showerror("Session Notes Report", "Could not load patient data.")
            return None, None

        sessions.sort(key=lambda r: (r.get("session_date") or "", int(r.get("id") or 0)))
        return dict(patient), sessions

    def _build_notes_report_pdf(self, out_path: Path) -> Path | None:
        patient, sessions = self._notes_report_context()
        if not patient or not sessions:
            return None

        if not PDF_RENDER_AVAILABLE or fitz is None:
            messagebox.showerror(
                "Session Notes Report",
                "PDF generation is unavailable. Install PyMuPDF to enable notes report printing.",
            )
            return None

        out_path.parent.mkdir(parents=True, exist_ok=True)

        patient_name = f"{patient.get('last_name', '')}, {patient.get('first_name', '')}".strip(", ")
        if not patient_name:
            patient_name = "Unknown Patient"

        try:
            doc = fitz.open()
            page = doc.new_page(width=612, height=792)
            left = 42
            right = 570
            y = 46

            page.insert_text((left, y), "Session Notes Report", fontsize=18, fontname="helv")
            y += 20
            page.insert_text((left, y), f"Patient: {patient_name}", fontsize=11, fontname="helv")
            y += 14
            page.insert_text((left, y), f"DOB: {fmt_date(patient.get('dob') or '')}", fontsize=10, fontname="helv")
            y += 14
            page.insert_text((left, y), f"Printed: {datetime.now().strftime('%m/%d/%Y %I:%M %p')}", fontsize=10, fontname="helv")
            y += 18
            page.draw_line((left, y), (right, y), color=(0.6, 0.6, 0.6), width=0.8)
            y += 12

            for idx, s in enumerate(sessions, start=1):
                header = (
                    f"{idx}. Date: {fmt_date(s.get('session_date') or '')}   "
                    f"Type: {s.get('session_type') or ''}   "
                    f"CPT: {s.get('cpt_code') or ''}   "
                    f"Fee: {fmt_money(s.get('fee') or 0)}   "
                    f"Signed: {'Yes' if s.get('signed') else 'No'}"
                )

                needed = 130
                if y + needed > 760:
                    page = doc.new_page(width=612, height=792)
                    y = 46

                page.insert_text((left, y), header, fontsize=9.5, fontname="helv")
                y += 14

                section_order = [
                    ("Note", s.get("note_text") or ""),
                    ("Goals", s.get("goals") or ""),
                    ("Interventions", s.get("interventions") or ""),
                    ("Response", s.get("response") or ""),
                    ("Plan", s.get("plan") or ""),
                ]

                for label, text in section_order:
                    if not text:
                        continue

                    block_h = 76
                    if y + block_h > 770:
                        page = doc.new_page(width=612, height=792)
                        y = 46

                    page.insert_text((left, y), f"{label}:", fontsize=9, fontname="helv")
                    y += 2
                    used = page.insert_textbox(
                        fitz.Rect(left + 52, y, right, y + 68),
                        str(text),
                        fontsize=9,
                        fontname="helv",
                        align=0,
                    )
                    y += 70

                    # If text overflowed this box, continue on additional pages.
                    if used < 0:
                        remaining = str(text)
                        while used < 0 and remaining:
                            page = doc.new_page(width=612, height=792)
                            y = 46
                            page.insert_text((left, y), f"{label} (continued):", fontsize=9, fontname="helv")
                            y += 2
                            used = page.insert_textbox(
                                fitz.Rect(left + 52, y, right, y + 700),
                                remaining,
                                fontsize=9,
                                fontname="helv",
                                align=0,
                            )
                            y = 754
                            break

                y += 4
                page.draw_line((left, y), (right, y), color=(0.82, 0.82, 0.82), width=0.7)
                y += 10

            doc.save(str(out_path))
            doc.close()
            return out_path
        except Exception as ex:
            messagebox.showerror("Session Notes Report", f"Could not generate notes report PDF:\n{ex}")
            return None

    def _save_notes_report_pdf(self):
        patient, sessions = self._notes_report_context()
        if not patient or not sessions:
            return

        patient_stub = f"{patient.get('last_name', '')}_{patient.get('first_name', '')}".strip("_").replace(" ", "_")
        out = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"SessionNotes_{patient_stub}_{datetime.now().strftime('%Y%m%d')}.pdf",
        )
        if not out:
            return

        saved = self._build_notes_report_pdf(Path(out))
        if saved:
            messagebox.showinfo("Session Notes Report", f"Notes report saved:\n{saved}")

    def _print_selected_notes(self):
        patient, sessions = self._notes_report_context()
        if not patient or not sessions:
            return

        pid = int(patient.get("id") or 0)
        print_path = APP_ROOT / "temp" / f"session_notes_{pid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        saved = self._build_notes_report_pdf(print_path)
        if not saved:
            return

        if sys.platform.startswith("win"):
            ready = messagebox.askokcancel(
                "Print Session Notes",
                "Click OK to send the selected session notes report to the default printer.",
            )
            if not ready:
                return
            try:
                os.startfile(str(saved), "print")
                messagebox.showinfo("Print Session Notes", "Selected notes sent to the default printer.")
            except OSError as ex:
                messagebox.showerror("Print Session Notes", f"Could not print selected notes:\n{ex}")
        else:
            webbrowser.open(saved.resolve().as_uri())
            messagebox.showinfo("Print Session Notes", f"Opened notes report for printing:\n{saved}")


# ─── Billing Tab ───────────────────────────────────────────────────────────────

class BillingTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._pid_filter = None
        self._patient_filter_var = tk.StringVar()
        self._patient_filter_map = {}
        self._build()
        self.refresh()

    def _build(self):
        tb = ttk.Frame(self, padding=(8, 6))
        tb.pack(fill="x")
        btn(tb, "+ Add Record", self._new_record, "Accent.TButton").pack(side="left", padx=4)
        btn(tb, "Edit", self._edit_record).pack(side="left", padx=2)
        btn(tb, "Delete", self._delete_record, "Danger.TButton").pack(side="left", padx=2)
        btn(tb, "All Records", self._show_all).pack(side="left", padx=2)

        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Label(tb, text="Patient:").pack(side="left")
        self._patient_filter_combo = ttk.Combobox(
            tb,
            textvariable=self._patient_filter_var,
            width=34,
            state="readonly",
        )
        self._patient_filter_combo.pack(side="left", padx=4)
        self._patient_filter_combo.bind("<<ComboboxSelected>>", lambda _e: self._apply_patient_filter_from_combo())
        self._load_patient_filter_options()

        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=8)
        btn(tb, "Save Invoice PDF", self._save_invoice_pdf).pack(side="left", padx=2)
        btn(tb, "Print Invoice", self._print_invoice_pdf).pack(side="left", padx=2)

        self._pt_label = ttk.Label(tb, text="", foreground=ACCENT, font=("Calibri", 10, "bold"))
        self._pt_label.pack(side="right", padx=8)

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        cols = (
            "id", "patient_name", "record_date", "description", "charge", "payment",
            "ins_payment", "adjustment", "balance", "payment_type",
        )
        self.tv = ttk.Treeview(frm, columns=cols, show="headings", selectmode="extended")
        hdrs = [
            ("ID", 48), ("Patient", 180), ("Date", 96), ("Description", 210),
            ("Charge", 88), ("Pt Paid", 84), ("Ins Paid", 84), ("Adj", 78),
            ("Balance", 92), ("Method", 112),
        ]
        for (h, w), c in zip(hdrs, cols):
            self.tv.heading(c, text=h, anchor="w")
            self.tv.column(c, width=_sc(w), stretch=c in ("patient_name", "description"))
        vsb = ttk.Scrollbar(frm, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vsb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tv.bind("<Double-1>", lambda e: self._edit_record())
        self.tv.tag_configure("even", background=ROW_EVEN)
        self.tv.tag_configure("credit", foreground=SUCCESS)
        self.tv.tag_configure("overdue", foreground=DANGER)

        sumbar = ttk.Frame(self, padding=(8, 4))
        sumbar.pack(fill="x", side="bottom")
        self._lbl_charges = ttk.Label(sumbar, text="Total Charges: $0.00", font=FONT_UI)
        self._lbl_charges.pack(side="left", padx=16)
        self._lbl_paid = ttk.Label(sumbar, text="Total Paid: $0.00", font=FONT_UI, foreground=SUCCESS)
        self._lbl_paid.pack(side="left", padx=16)
        self._lbl_balance = ttk.Label(sumbar, text="Balance: $0.00", font=FONT_LG, foreground=DANGER)
        self._lbl_balance.pack(side="left", padx=16)

    def _load_patient_filter_options(self):
        pts = db.get_all_patients("Active") + db.get_all_patients("Inactive")
        uniq = {}
        for p in pts:
            uniq[p["id"]] = p
        ordered = sorted(uniq.values(), key=lambda p: ((p["last_name"] or "").lower(), (p["first_name"] or "").lower()))

        labels = ["All Patients"]
        mapping = {"All Patients": None}
        for p in ordered:
            label = f"{p['last_name']}, {p['first_name']} (ID:{p['id']})"
            labels.append(label)
            mapping[label] = p["id"]

        self._patient_filter_map = mapping
        self._patient_filter_combo["values"] = labels
        self._patient_filter_combo.current(0)

    def _apply_patient_filter_from_combo(self):
        label = self._patient_filter_var.get().strip()
        pid = self._patient_filter_map.get(label)
        if pid is None:
            self._show_all()
            return
        self.filter_patient(pid)

    def filter_patient(self, pid):
        self._pid_filter = pid
        pt = db.get_patient(pid)
        if pt:
            self._pt_label.config(text=f"Showing: {pt['last_name']}, {pt['first_name']}")
            expected = f"{pt['last_name']}, {pt['first_name']} (ID:{pt['id']})"
            if expected in self._patient_filter_map:
                self._patient_filter_var.set(expected)
        self.refresh()

    def _show_all(self):
        self._pid_filter = None
        self._pt_label.config(text="")
        self._patient_filter_var.set("All Patients")
        self.refresh()

    def refresh(self):
        self.tv.delete(*self.tv.get_children())
        if self._pid_filter:
            rows = db.get_billing_for_patient(self._pid_filter)
        else:
            conn = db.get_connection()
            rows = conn.execute(
                """SELECT b.*, p.first_name||' '||p.last_name AS patient_name
                   FROM billing_records b
                   JOIN patients p ON b.patient_id=p.id
                   ORDER BY b.record_date DESC, b.id DESC LIMIT 500"""
            ).fetchall()
            conn.close()

        total_c = total_p = total_b = 0.0
        for i, r in enumerate(rows):
            tag = "even" if i % 2 == 0 else "odd"
            bal = float(r["balance"] or 0)
            if bal < 0:
                tag = "credit"
            name = r["patient_name"] if "patient_name" in r.keys() else ""
            if not name:
                pt = db.get_patient(r["patient_id"])
                name = f"{pt['last_name']}, {pt['first_name']}" if pt else ""
            self.tv.insert(
                "",
                "end",
                iid=str(r["id"]),
                tags=(tag,),
                values=(
                    r["id"],
                    name,
                    fmt_date(r["record_date"]),
                    r["description"],
                    fmt_money(r["charge"]),
                    fmt_money(r["payment"]),
                    fmt_money(r["ins_payment"]),
                    fmt_money(r["adjustment"]),
                    fmt_money(r["balance"]),
                    r["payment_type"],
                ),
            )
            total_c += float(r["charge"] or 0)
            total_p += float(r["payment"] or 0) + float(r["ins_payment"] or 0)
            total_b += bal

        self._lbl_charges.config(text=f"Total Charges: {fmt_money(total_c)}")
        self._lbl_paid.config(text=f"Total Paid: {fmt_money(total_p)}")
        self._lbl_balance.config(
            text=f"Balance: {fmt_money(total_b)}",
            foreground=(DANGER if total_b > 0 else SUCCESS),
        )

    def _sel_rid(self):
        sel = self.tv.selection()
        return int(sel[0]) if sel else None

    def _selected_rids(self):
        return [int(x) for x in self.tv.selection()]

    def _new_record(self):
        BillingDialog(self, pid=self._pid_filter, on_save=self.refresh)

    def _edit_record(self):
        rid = self._sel_rid()
        if not rid:
            messagebox.showinfo("Select", "Please select a record.")
            return
        BillingDialog(self, rid=rid, pid=self._pid_filter, on_save=self.refresh)

    def _delete_record(self):
        rid = self._sel_rid()
        if not rid:
            return
        if messagebox.askyesno("Delete", "Delete this billing record?"):
            db.delete_billing_record(rid)
            self.refresh()

    def _invoice_context(self):
        selected = self._selected_rids()

        if selected:
            rows = []
            pids = set()
            for rid in selected:
                row = db.get_billing_record(rid)
                if not row:
                    continue
                pids.add(int(row["patient_id"]))
                rows.append(dict(row))

            if not rows:
                return None, None
            if len(pids) != 1:
                messagebox.showinfo("Invoice", "Please select bills for only one patient at a time.")
                return None, None

            pid = next(iter(pids))
            return pid, rows

        if self._pid_filter:
            pid = self._pid_filter
            return pid, [dict(r) for r in db.get_billing_for_patient(pid)]

        rid = self._sel_rid()
        if rid:
            row = db.get_billing_record(rid)
            if row:
                pid = int(row["patient_id"])
                return pid, [dict(r) for r in db.get_billing_for_patient(pid)]

        return None, None

    def _build_invoice_pdf(self, out_path: Path) -> Path | None:
        pid, billing_rows = self._invoice_context()
        if not pid:
            messagebox.showinfo(
                "Invoice",
                "Select a patient in Billing, or select billing rows for one patient, then try again.",
            )
            return None

        patient = db.get_patient(pid)
        if not patient:
            messagebox.showerror("Invoice", "Could not load patient data for invoice.")
            return None

        if not billing_rows:
            messagebox.showinfo("Invoice", "No billing records found for this patient.")
            return None

        provider = db.get_provider()
        try:
            from invoice_pdf import generate_patient_invoice

            generate_patient_invoice(out_path, provider, dict(patient), billing_rows)
            return out_path
        except Exception as ex:
            messagebox.showerror("Invoice", f"Could not generate invoice PDF:\n{ex}")
            return None

    def _save_invoice_pdf(self):
        pid, _ = self._invoice_context()
        if not pid:
            messagebox.showinfo(
                "Invoice",
                "Select a patient in Billing, or select billing rows for one patient, then try again.",
            )
            return

        patient = db.get_patient(pid)
        patient_stub = "patient"
        if patient:
            patient_stub = f"{patient['last_name']}_{patient['first_name']}".strip("_").replace(" ", "_")

        out = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"Invoice_{patient_stub}_{datetime.now().strftime('%Y%m%d')}.pdf",
        )
        if not out:
            return

        saved = self._build_invoice_pdf(Path(out))
        if saved:
            messagebox.showinfo("Invoice Saved", f"Invoice PDF saved:\n{saved}")

    def _print_invoice_pdf(self):
        pid, _ = self._invoice_context()
        if not pid:
            messagebox.showinfo(
                "Invoice",
                "Select a patient in Billing, or select billing rows for one patient, then try again.",
            )
            return

        print_path = APP_ROOT / "temp" / f"invoice_{pid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        saved = self._build_invoice_pdf(print_path)
        if not saved:
            return

        if sys.platform.startswith("win"):
            ready = messagebox.askokcancel(
                "Print Invoice",
                "Click OK to send the invoice to the default printer.",
            )
            if not ready:
                return
            try:
                os.startfile(str(saved), "print")
                messagebox.showinfo("Print Invoice", "Invoice sent to the default printer.")
            except OSError as ex:
                messagebox.showerror("Print Invoice", f"Could not print invoice:\n{ex}")
        else:
            webbrowser.open(saved.resolve().as_uri())
            messagebox.showinfo("Print Invoice", f"Opened invoice for printing:\n{saved}")


# ─── CMS-1500 Tab ──────────────────────────────────────────────────────────────

class CMS1500Tab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._field_defs = [
            ("Patient Name", "patient_name"),
            ("Patient DOB", "patient_dob"),
            ("Patient Sex", "patient_sex"),
            ("Patient SSN", "patient_ssn"),
            ("Insured ID", "ins_id"),
            ("Insured Name", "insured_name"),
            ("Insured DOB", "insured_dob"),
            ("Insured Sex", "insured_sex"),
            ("Insured Relation", "insured_relation"),
            ("Insured Group", "insured_group"),
            ("Insured Plan Type", "insured_plan_type"),
            ("Box 1 Type (Optional)", "box1_plan_type"),
            ("Insured Plan Name", "insured_plan_name"),
            ("Other Insured Name", "other_insured_name"),
            ("Other Insured ID", "other_insured_id"),
            ("Other Insured Group", "other_insured_group"),
            ("Other Insured Plan", "other_insured_plan"),
            ("Patient Address", "patient_address"),
            ("Patient City", "patient_city"),
            ("Patient State", "patient_state"),
            ("Patient ZIP", "patient_zip"),
            ("Diagnosis 1", "dx1"),
            ("Diagnosis 2", "dx2"),
            ("Diagnosis 3", "dx3"),
            ("Diagnosis 4", "dx4"),
            ("Diagnosis 5", "dx5"),
            ("Diagnosis 6", "dx6"),
            ("Diagnosis 7", "dx7"),
            ("Diagnosis 8", "dx8"),
            ("Diagnosis 9", "dx9"),
            ("Diagnosis 10", "dx10"),
            ("Diagnosis 11", "dx11"),
            ("Diagnosis 12", "dx12"),
            ("Service Date", "service_date"),
            ("Illness Date", "illness_date"),
            ("Illness Date Qual", "illness_date_qual"),
            ("Other Date", "other_date"),
            ("Other Date Qual", "other_date_qual"),
            ("Unable To Work From", "unable_to_work_from"),
            ("Unable To Work To", "unable_to_work_to"),
            ("Hospitalized From", "hospitalized_from"),
            ("Hospitalized To", "hospitalized_to"),
            ("CPT Code", "cpt_code"),
            ("Modifier", "modifier"),
            ("Place of Service", "place_of_service"),
            ("Units", "units"),
            ("Employment Related (Y/N)", "employment_related"),
            ("Auto Accident (Y/N)", "auto_accident"),
            ("Auto Accident State", "auto_accident_state"),
            ("Other Accident (Y/N)", "other_accident"),
            ("Outside Lab (Y/N)", "outside_lab"),
            ("Outside Lab Charge", "outside_lab_charge"),
            ("Claim Codes (10d)", "claim_codes"),
            ("Patient Account #", "patient_account_no"),
            ("Claim Number", "claim_number"),
            ("Check Number", "check_number"),
            ("Prior Auth Number", "prior_auth_number"),
            ("Additional Claim Info", "additional_claim_info"),
            ("Total Charge", "total_charge"),
            ("Amount Paid", "amount_paid"),
            ("Accept Assignment (YES/NO)", "accept_assignment"),
            ("Federal Tax ID Type", "federal_tax_id_type"),
            ("Billing ID Qualifier", "billing_id_qualifier"),
            ("Referring Name", "referring_name"),
            ("Referring Taxonomy", "referring_taxonomy"),
            ("Referring NPI", "referring_npi"),
            ("Billing Name", "billing_name"),
            ("Billing Address", "billing_address"),
            ("Billing City", "billing_city"),
            ("Billing State", "billing_state"),
            ("Billing ZIP", "billing_zip"),
            ("Billing Phone", "billing_phone"),
            ("Billing NPI", "billing_npi"),
            ("Billing Taxonomy", "billing_taxonomy"),
            ("Tax ID", "tax_id"),
            ("Facility Name", "facility_name"),
            ("Facility Address", "facility_address"),
            ("Facility City", "facility_city"),
            ("Facility State", "facility_state"),
            ("Facility ZIP", "facility_zip"),
            ("Facility NPI", "facility_npi"),
            ("Facility Taxonomy", "facility_taxonomy"),
            ("Provider Signature", "provider_signature"),
            ("Provider Signature Date", "provider_signature_date"),
        ]
        self._vars = {}
        self._current_pid = None
        self._current_sessions = []
        self._current_data = {}
        self._last_preview_path = None
        self._paper_image = None
        self._paper_zoom_min = 1.2
        self._paper_zoom_max = 10.0
        self._paper_zoom_step = 0.15
        self._paper_zoom = 2.0 if MACHINE_TYPE == "laptop" else 1.65
        self._paper_source_path = None
        self._duplex_prefs_prompted_on = ""
        self._build()

    def _build(self):
        tb = ttk.Frame(self, padding=(8, 6))
        tb.pack(fill="x")
        btn(tb, "Auto-Populate from Patient", self._auto_populate, "Accent.TButton").pack(side="left", padx=4)
        btn(tb, "Show Blank Form", self._open_blank_template).pack(side="left", padx=4)
        btn(tb, "Refresh Filled Form", self._refresh_paper_preview).pack(side="left", padx=4)
        btn(tb, "Edit Form Data", self._open_data_editor).pack(side="left", padx=4)
        btn(tb, "Print Preview", self._print_preview).pack(side="left", padx=4)
        btn(tb, "Print", self._print_form).pack(side="left", padx=4)
        btn(tb, "Export PDF", self._export_pdf).pack(side="left", padx=4)
        btn(tb, "Align Overlay", self._align_overlay).pack(side="left", padx=4)

        frm = lframe(self, "CMS-1500 Paper Form")
        frm.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        ttk.Label(
            frm,
            text="This is the actual CMS-1500 template rendered in-app. Use 'Edit Form Data' for manual overrides.",
            foreground=ACCENT,
            justify="left",
            font=("Arial", 12, "bold"),
        ).pack(anchor="w", padx=6, pady=(4, 6))

        for _, key in self._field_defs:
            self._vars[key] = tk.StringVar()

        view_wrap = ttk.Frame(frm)
        view_wrap.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self._paper_canvas = tk.Canvas(view_wrap, background="#dddddd", highlightthickness=0)
        vbar = ttk.Scrollbar(view_wrap, orient="vertical", command=self._paper_canvas.yview)
        hbar = ttk.Scrollbar(view_wrap, orient="horizontal", command=self._paper_canvas.xview)
        self._paper_canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        self._paper_canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        view_wrap.rowconfigure(0, weight=1)
        view_wrap.columnconfigure(0, weight=1)
        self._paper_canvas.bind("<Enter>", self._bind_canvas_wheel)
        self._paper_canvas.bind("<Leave>", self._unbind_canvas_wheel)

        self._paper_status = ttk.Label(frm, text="Loading CMS-1500 template...", foreground=MUTED)
        self._paper_status.pack(anchor="w", padx=6, pady=(0, 4))
        self._dx_usage_hint = ttk.Label(frm, text="Diagnoses used: 0/12", foreground=MUTED)
        self._dx_usage_hint.pack(anchor="w", padx=6, pady=(0, 6))

        self.after(120, self._open_blank_template)

    def _bind_canvas_wheel(self, _event=None):
        self._paper_canvas.bind_all("<MouseWheel>", self._on_canvas_mousewheel)
        self._paper_canvas.bind_all("<Shift-MouseWheel>", self._on_canvas_shift_mousewheel)
        self._paper_canvas.bind_all("<Control-MouseWheel>", self._on_canvas_zoom_mousewheel)
        self._paper_canvas.bind_all("<Button-4>", self._on_canvas_mousewheel)
        self._paper_canvas.bind_all("<Button-5>", self._on_canvas_mousewheel)
        self._paper_canvas.bind_all("<Control-Button-4>", self._on_canvas_zoom_mousewheel)
        self._paper_canvas.bind_all("<Control-Button-5>", self._on_canvas_zoom_mousewheel)

    def _unbind_canvas_wheel(self, _event=None):
        self._paper_canvas.unbind_all("<MouseWheel>")
        self._paper_canvas.unbind_all("<Shift-MouseWheel>")
        self._paper_canvas.unbind_all("<Control-MouseWheel>")
        self._paper_canvas.unbind_all("<Button-4>")
        self._paper_canvas.unbind_all("<Button-5>")
        self._paper_canvas.unbind_all("<Control-Button-4>")
        self._paper_canvas.unbind_all("<Control-Button-5>")

    def _on_canvas_mousewheel(self, event):
        units = _mousewheel_units(event)
        if units:
            self._paper_canvas.yview_scroll(units, "units")
            return "break"
        return None

    def _on_canvas_shift_mousewheel(self, event):
        units = _mousewheel_units(event)
        if units:
            self._paper_canvas.xview_scroll(units, "units")
            return "break"
        return None

    def _on_canvas_zoom_mousewheel(self, event):
        units = _mousewheel_units(event)
        if not units:
            return None
        step = self._paper_zoom_step if units < 0 else -self._paper_zoom_step
        target_zoom = max(self._paper_zoom_min, min(self._paper_zoom_max, self._paper_zoom + step))
        if abs(target_zoom - self._paper_zoom) < 0.0001:
            return "break"
        self._paper_zoom = target_zoom
        if self._paper_source_path and Path(self._paper_source_path).exists():
            self._render_pdf_in_canvas(Path(self._paper_source_path))
        return "break"

    def _open_data_editor(self):
        win = tk.Toplevel(self)
        apply_window_icon(win)
        win.title("CMS-1500 Data Editor")
        win.geometry("980x700")
        win.transient(self.winfo_toplevel())

        shell = ttk.Frame(win, padding=(10, 10, 10, 0))
        shell.pack(fill="both", expand=True)

        canvas = tk.Canvas(shell, highlightthickness=0)
        vbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        body = ttk.Frame(canvas, padding=4)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(3, weight=1)

        win_body = canvas.create_window((0, 0), window=body, anchor="nw")

        def _sync_editor_scroll(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(win_body, width=canvas.winfo_width())

        body.bind("<Configure>", _sync_editor_scroll)
        canvas.bind("<Configure>", _sync_editor_scroll)

        for idx, (label, key) in enumerate(self._field_defs):
            row = idx // 2
            col_base = (idx % 2) * 2
            ttk.Label(body, text=label).grid(row=row, column=col_base, sticky="e", padx=(4, 2), pady=3)
            if key == "box1_plan_type":
                ttk.Combobox(
                    body,
                    textvariable=self._vars[key],
                    values=["", "medicare", "medicaid", "tricare", "champva", "group", "feca", "other"],
                    state="readonly",
                ).grid(row=row, column=col_base + 1, sticky="ew", padx=(0, 8), pady=3)
            else:
                ttk.Entry(body, textvariable=self._vars[key]).grid(
                    row=row,
                    column=col_base + 1,
                    sticky="ew",
                    padx=(0, 8),
                    pady=3,
                )

        foot = ttk.Frame(win, padding=(10, 0, 10, 10))
        foot.pack(fill="x")

        def apply_and_refresh():
            # Keep any structured service lines while reflecting edited scalar values.
            self._current_data.update({k: v.get().strip() for k, v in self._vars.items()})
            self._update_dx_usage_hint(self._current_data)
            self._refresh_paper_preview()
            win.destroy()

        btn(foot, "Apply + Refresh Form", apply_and_refresh, "Accent.TButton").pack(side="right", padx=4)
        btn(foot, "Cancel", win.destroy).pack(side="right", padx=4)

    def _render_pdf_in_canvas(self, pdf_path: Path) -> bool:
        if not PDF_RENDER_AVAILABLE or fitz is None or Image is None or ImageTk is None:
            self._paper_status.config(
                text=(
                    "In-app PDF rendering components are unavailable in this build. "
                    "Please install the latest update."
                ),
                foreground=DANGER,
            )
            return False

        try:
            self._paper_source_path = str(pdf_path)
            doc = fitz.open(str(pdf_path))
            page = doc.load_page(0)
            render_zoom = self._paper_zoom
            pix = page.get_pixmap(matrix=fitz.Matrix(render_zoom, render_zoom), alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            self._paper_image = ImageTk.PhotoImage(img)
            self._paper_canvas.delete("all")
            self._paper_canvas.create_image(0, 0, image=self._paper_image, anchor="nw")
            self._paper_canvas.configure(scrollregion=(0, 0, img.width, img.height))
            self._paper_status.config(text=f"Showing form: {pdf_path.name} (Zoom {int(render_zoom * 100)}%)", foreground=MUTED)
            doc.close()
            return True
        except Exception as ex:
            self._paper_status.config(text=f"Could not render CMS form in app: {ex}", foreground=DANGER)
            return False

    def _open_blank_template(self):
        if not self._ensure_template():
            return
        self._update_dx_usage_hint()
        self._render_pdf_in_canvas(CMS_TEMPLATE_FILE)

    def _update_dx_usage_hint(self, data=None):
        source = data if isinstance(data, dict) else {k: v.get().strip() for k, v in self._vars.items()}
        used = sum(1 for key in PATIENT_DX_KEYS if source.get(key, "").strip())
        self._dx_usage_hint.config(text=f"Diagnoses used: {used}/12")

    def _refresh_paper_preview(self):
        preview_path = APP_ROOT / "temp" / "CMS1500_live_paper_preview.pdf"
        saved = self._fill_to_path(preview_path)
        if not saved:
            return None
        self._update_dx_usage_hint(self._current_data)
        self._last_preview_path = saved
        self._render_pdf_in_canvas(saved)
        return saved

    def _ensure_template(self) -> bool:
        if CMS_TEMPLATE_FILE.exists():
            return True
        messagebox.showerror(
            "Template Missing",
            f"Could not find template:\n{CMS_TEMPLATE_FILE}\n\nAdd CMS1500_template.pdf to the app root.",
        )
        return False

    def _collect_form_data(self):
        # Start with field-by-field UI values
        form = {k: v.get().strip() for k, v in self._vars.items()}
        # Merge in the full data dict (which carries service_lines list)
        # UI scalars take precedence for editable fields; list stays from _current_data.
        if hasattr(self, "_current_data") and self._current_data:
            for k, v in self._current_data.items():
                if k not in form:
                    form[k] = v
                elif k == "service_lines":
                    form[k] = v  # always use the structured list
        # Box 24G (Days or Units): only overwrite per-row values once the user
        # types something in the "Units" field on Edit Form Data; else stays blank.
        units_value = form.get("units", "")
        lines = form.get("service_lines")
        if units_value and isinstance(lines, list):
            for line in lines:
                if isinstance(line, dict):
                    line["units"] = units_value
        return form

    def _fill_to_path(self, output_path: Path, render_mode: str = "full") -> Path | None:
        if not self._ensure_template():
            return None
        try:
            from cms_pdf import fill_cms1500_overlay_pdf, fill_cms1500_pdf
        except ImportError:
            messagebox.showerror("Missing Dependency", "Install dependency: pip install pypdf")
            return None

        data = self._collect_form_data()
        back_template = _resolve_cms_back_template()
        try:
            if render_mode == "overlay":
                provider = db.get_provider()
                box_offsets = _overlay_box_offsets_inches_to_points(
                    _load_cms_overlay_box_offsets(provider.get("cms_overlay_box_offsets"))
                )
                fill_cms1500_overlay_pdf(
                    CMS_TEMPLATE_FILE,
                    output_path,
                    data,
                    box_offsets=box_offsets,
                )
            elif render_mode == "front_only":
                fill_cms1500_pdf(CMS_TEMPLATE_FILE, output_path, data, back_template_path=None)
            else:
                fill_cms1500_pdf(CMS_TEMPLATE_FILE, output_path, data, back_template_path=back_template)
            return output_path
        except Exception as ex:
            messagebox.showerror("CMS-1500", f"Could not generate PDF:\n{ex}")
            return None

    def _log_form_creation(self, source: str, output_path: Path | None = None):
        """Best-effort audit log for CMS-1500 creation events."""
        if not self._current_pid:
            return
        try:
            db.log_cms1500_form_creation(
                int(self._current_pid),
                created_source=source,
                output_path=str(output_path) if output_path else "",
            )
        except Exception:
            # Reporting logs should not block export/print workflows.
            pass

    def _auto_populate(self):
        picker = tk.Toplevel(self)
        apply_window_icon(picker)
        picker.title("Select Patient for CMS-1500")
        target_w = 1100 if MACHINE_TYPE == "laptop" else 760
        target_h = 780 if MACHINE_TYPE == "laptop" else 560
        _w, _h = _screen_fit(target_w, target_h, pad=24)
        picker.geometry(f"{_w}x{_h}")
        picker.minsize(800, 560)
        picker.resizable(True, True)
        picker.grab_set()

        ttk.Label(picker, text="Select Patient:").pack(anchor="w", padx=10, pady=6)
        sv = tk.StringVar()
        patients = db.get_all_patients("Active")
        names = [f"{p['last_name']}, {p['first_name']} (ID:{p['id']})" for p in patients]
        cb = ttk.Combobox(picker, textvariable=sv, values=names, width=48, state="readonly")
        cb.pack(padx=10, pady=4)

        ttk.Label(picker, text="Select Sessions (Ctrl for multi-select):").pack(anchor="w", padx=10, pady=4)
        sess_lv = tk.Listbox(picker, selectmode="extended", exportselection=False, height=10, font=FONT_UI)
        sess_lv.pack(fill="both", expand=True, padx=10)

        def on_patient_select(*_args):
            idx = cb.current()
            if idx < 0:
                return
            pid = patients[idx]["id"]
            sess_lv.delete(0, "end")
            for s in db.get_sessions_for_patient(pid):
                sess_lv.insert("end", f"{fmt_date(s['session_date'])}  {s['cpt_code']}  {fmt_money(s['fee'])}")

        cb.bind("<<ComboboxSelected>>", on_patient_select)

        def do_populate():
            idx = cb.current()
            if idx < 0:
                messagebox.showwarning("Select", "Please choose a patient.", parent=picker)
                return
            pid = patients[idx]["id"]
            sessions = db.get_sessions_for_patient(pid)
            chosen_idx = sess_lv.curselection()
            chosen = [dict(sessions[i]) for i in chosen_idx] if chosen_idx else [dict(sessions[0])] if sessions else []
            self.load_from_session(pid, chosen)
            picker.destroy()

        btn(picker, "Populate Form", do_populate, "Accent.TButton").pack(pady=8)

    def load_from_session(self, pid, sessions):
        patient = db.get_patient(pid)
        provider = db.get_provider()
        billing_rows = db.get_billing_for_patient(pid)
        latest_billing = billing_rows[0] if billing_rows else {}

        def g(row, key, default=""):
            try:
                return row[key] or default
            except Exception:
                return default

        first = sessions[0] if sessions else {}
        # Clamp to 6 service lines (CMS-1500 maximum)
        selected = list(sessions[:6])

        total_charge = 0.0
        for s in selected:
            try:
                total_charge += float(s.get("fee", 0) or 0)
            except Exception:
                pass

        total_paid = 0.0
        for r in billing_rows:
            try:
                total_paid += float(r["payment"] or 0) + float(r["ins_payment"] or 0)
            except Exception:
                pass

        patient_sex = g(patient, "sex").strip().upper()
        if patient_sex.startswith("MALE"):
            patient_sex = "M"
        elif patient_sex.startswith("FEMALE"):
            patient_sex = "F"

        provider_name = g(provider, "practice_name") or f"{g(provider, 'provider_first')} {g(provider, 'provider_last')}".strip()
        rendering_provider_name = f"{g(provider, 'provider_first')} {g(provider, 'provider_last')}".strip()
        billing_npi = g(provider, "npi")
        provider_taxonomy = g(provider, "license_num")
        insured_name = g(patient, "ins_holder") or f"{g(patient, 'last_name')}, {g(patient, 'first_name')}".strip(", ")
        insured_sex = g(patient, "ins_holder_sex") or patient_sex
        insured_relation = g(patient, "ins_relation", "Self")
        insured_dob = g(patient, "ins_holder_dob") or g(patient, "dob")
        insured_address = g(patient, "ins_address") or g(patient, "address")
        insured_city = g(patient, "ins_city") or g(patient, "city")
        insured_state = g(patient, "ins_state") or g(patient, "state")
        insured_zip = g(patient, "ins_zip") or g(patient, "zip")
        insured_phone = g(patient, "ins_phone") or g(patient, "phone_home") or g(patient, "phone_cell")
        patient_phone = g(patient, "phone_home") or g(patient, "phone_cell") or g(patient, "phone_work")

        claim_dx_values = [g(first, k) or g(patient, k) for k in PATIENT_DX_KEYS]

        # Build per-row diagnosis pointer: use "A" if no diagnoses are set, or
        # all applicable pointers based on which of dx1-dx12 this session/claim carry.
        def dx_pointer_for(sess) -> str:
            letters = "ABCDEFGHIJKL"
            ptrs = [letters[i] for i, k in enumerate(PATIENT_DX_KEYS) if g(sess, k) or claim_dx_values[i]]
            return " ".join(ptrs) if ptrs else "A"

        service_lines = [
            {
                "service_date": g(s, "session_date"),
                "cpt_code":     g(s, "cpt_code"),
                "modifier":     g(s, "cpt_modifier"),
                "pos":          _extract_place_code(g(s, "place_of_service", "11")),
                "units":        "",
                "charge":       f"{float(s.get('fee', 0) or 0):.2f}",
                "dx_pointer":   dx_pointer_for(s),
                "id_qualifier": g(provider, "id_qualifier", "ZZ"),
                "taxonomy_code": provider_taxonomy,
                "npi":          billing_npi,
            }
            for s in selected
        ]

        data = {
            "patient_name": f"{g(patient, 'last_name')}, {g(patient, 'first_name')}",
            "patient_dob": g(patient, "dob"),
            "patient_sex": patient_sex,
            "patient_ssn": g(patient, "ssn"),
            "ins_id": g(patient, "ins_id"),
            "insured_name": insured_name,
            "insured_dob": insured_dob,
            "insured_sex": insured_sex,
            "insured_relation": insured_relation,
            "insured_group": g(patient, "ins_group"),
            "insured_plan_name": g(patient, "ins_name") or g(patient, "ins_plan"),
            "insured_plan_type": g(patient, "ins_plan"),
            # Box 1 plan selection is optional and should only be marked when user sets it.
            "box1_plan_type": "",
            "insured_address": insured_address,
            "insured_city": insured_city,
            "insured_state": insured_state,
            "insured_zip": insured_zip,
            "insured_phone": insured_phone,
            "other_insured_name": g(patient, "ins2_holder") or g(patient, "ins2_name"),
            "other_insured_id": g(patient, "ins2_id"),
            "other_insured_group": g(patient, "ins2_group"),
            "other_insured_plan": g(patient, "ins2_plan"),
            "other_insured_relation": g(patient, "ins2_relation"),
            "patient_address": g(patient, "address"),
            "patient_city": g(patient, "city"),
            "patient_state": g(patient, "state"),
            "patient_zip": g(patient, "zip"),
            "patient_phone": patient_phone,
            "dx1": claim_dx_values[0],
            "dx2": claim_dx_values[1],
            "dx3": claim_dx_values[2],
            "dx4": claim_dx_values[3],
            "dx5": claim_dx_values[4],
            "dx6": claim_dx_values[5],
            "dx7": claim_dx_values[6],
            "dx8": claim_dx_values[7],
            "dx9": claim_dx_values[8],
            "dx10": claim_dx_values[9],
            "dx11": claim_dx_values[10],
            "dx12": claim_dx_values[11],
            # Row-1 scalar fallbacks (used when service_lines is ignored)
            "service_date": g(first, "session_date"),
            "illness_date": "",
            "illness_date_qual": "",
            "other_date": "",
            "other_date_qual": "",
            "unable_to_work_from": g(first, "unable_to_work_from") or g(patient, "unable_to_work_from"),
            "unable_to_work_to": g(first, "unable_to_work_to") or g(patient, "unable_to_work_to"),
            "hospitalized_from": g(first, "hospitalized_from") or g(patient, "hospitalized_from"),
            "hospitalized_to": g(first, "hospitalized_to") or g(patient, "hospitalized_to"),
            "cpt_code": g(first, "cpt_code"),
            "modifier": g(first, "cpt_modifier"),
            "place_of_service": _extract_place_code(g(first, "place_of_service", "11")),
            "units": "",
            "employment_related": g(first, "employment_related") or g(patient, "employment_related"),
            "auto_accident": g(first, "auto_accident") or g(patient, "auto_accident"),
            "auto_accident_state": g(first, "auto_accident_state") or g(patient, "auto_accident_state"),
            "other_accident": g(first, "other_accident") or g(patient, "other_accident"),
            "outside_lab": g(first, "outside_lab") or g(patient, "outside_lab"),
            "outside_lab_charge": "",
            "patient_account_no": "",
            "claim_codes": g(latest_billing, "claim_codes"),
            "claim_number": g(latest_billing, "claim_number"),
            "check_number": g(latest_billing, "check_number"),
            "prior_auth_number": g(latest_billing, "claim_number"),
            # Box 19 must stay blank unless the user explicitly enters claim info.
            "additional_claim_info": "",
            "total_charge": f"{total_charge:.2f}",
            "amount_paid": f"{total_paid:.2f}",
            "provider_signature": g(provider, "sig_on_file", "Signature On File"),
            "provider_name": rendering_provider_name or provider_name,
            "provider_suffix": g(provider, "provider_suffix"),
            "patient_signature_date": g(patient, "sig_on_file_date"),
            "provider_signature_date": datetime.now().strftime('%m/%d/%Y'),
            "accept_assignment": "YES" if str(g(provider, "accept_assign", "1")) in {"1", "true", "True", "YES", "yes"} else "NO",
            "federal_tax_id_type": g(provider, "tax_id_type", "EIN"),
            # Feed box 32b/33b qualifiers from provider default when no distinct value exists.
            "billing_id_qualifier": g(provider, "id_qualifier", "ZZ") or "ZZ",
            "facility_id_qualifier": g(provider, "id_qualifier", "ZZ") or "ZZ",
            "referring_name": g(patient, "referring_name"),
            # 17a should only populate from explicit referral data.
            "referring_taxonomy": g(patient, "referring_taxonomy"),
            "referring_npi": g(patient, "referring_npi"),
            "billing_name": provider_name,
            "billing_address": g(provider, "address"),
            "billing_city": g(provider, "city"),
            "billing_state": g(provider, "state"),
            "billing_zip": g(provider, "zip"),
            "billing_phone": g(provider, "phone"),
            "billing_npi": billing_npi,
            "billing_taxonomy": provider_taxonomy,
            "tax_id": g(provider, "tax_id"),
            "facility_name": provider_name,
            "facility_address": g(provider, "address"),
            "facility_city": g(provider, "city"),
            "facility_state": g(provider, "state"),
            "facility_zip": g(provider, "zip"),
            "facility_npi": billing_npi,
            "facility_taxonomy": provider_taxonomy,
            "taxonomy_code": provider_taxonomy,
            # Multi-line list consumed by cms_pdf mapper
            "service_lines": service_lines,
        }

        # Convert ISO dates to MM/DD/YYYY for display in the editor and on the form
        _cms_date_fields = (
            "patient_dob", "insured_dob", "service_date", "illness_date",
            "other_date", "unable_to_work_from", "unable_to_work_to",
            "hospitalized_from", "hospitalized_to",
        )
        for _df in _cms_date_fields:
            if data.get(_df):
                data[_df] = fmt_date(data[_df])
        for _sl in data.get("service_lines", []):
            if _sl.get("service_date"):
                _sl["service_date"] = fmt_date(_sl["service_date"])

        for key, var in self._vars.items():
            var.set(str(data.get(key, "")))

        self._current_pid = pid
        self._current_sessions = sessions
        self._current_data = data  # retained for PDF fill
        self._update_dx_usage_hint(data)
        self._refresh_paper_preview()

    def _show_template_fields(self):
        if not self._ensure_template():
            return
        try:
            from cms_pdf import get_template_fields_with_positions
            fields = get_template_fields_with_positions(CMS_TEMPLATE_FILE)
        except Exception as ex:
            messagebox.showerror("Template Fields", f"Could not read template fields:\n{ex}")
            return

        win = tk.Toplevel(self)
        apply_window_icon(win)
        win.title("CMS-1500 Template Fields")
        win.geometry("980x620")
        txt = tk.Text(win, wrap="none", font=FONT_MONO)
        txt.pack(fill="both", expand=True)

        if not fields:
            txt.insert("1.0", "No fillable fields found.")
        else:
            lines = []
            lines.append("Field | Page | Type | Rect(x1,y1,x2,y2) | Current Value")
            lines.append("-" * 120)
            for f in fields:
                rect = f.get("rect") or (0, 0, 0, 0)
                rect_str = f"({rect[0]:.1f},{rect[1]:.1f},{rect[2]:.1f},{rect[3]:.1f})"
                line = (
                    f"{f.get('name','')} | "
                    f"{f.get('page','')} | "
                    f"{f.get('field_type','')} | "
                    f"{rect_str} | "
                    f"{f.get('value','')}"
                )
                lines.append(line)
            txt.insert("1.0", "\n".join(lines))

        txt.config(state="disabled")

    def _align_overlay(self):
        """Open a dialog to set per-box alignment offsets for pre-printed overlay printing."""
        provider = db.get_provider()
        cur_blank_x = float(provider.get("cms_blank_offset_x") or 0.0)
        cur_blank_y = float(provider.get("cms_blank_offset_y") or 0.0)
        box_offsets = _load_cms_overlay_box_offsets(provider.get("cms_overlay_box_offsets"))

        dlg = tk.Toplevel(self)
        apply_window_icon(dlg)
        dlg.title("Pre-Printed Form Alignment")
        dlg.resizable(True, True)
        dlg.update_idletasks()
        dlg_w, dlg_h = 700, 780
        sw = dlg.winfo_screenwidth()
        sh = dlg.winfo_screenheight()
        x = max(0, (sw - dlg_w) // 2)
        y = max(0, (sh - dlg_h) // 2)
        dlg.geometry(f"{dlg_w}x{dlg_h}+{x}+{y}")
        dlg.grab_set()

        ttk.Label(
            dlg,
            text=(
                "Adjust where text is placed when printing on pre-printed CMS forms.\n"
                "Positive values shift text right/down; negative values shift left/up.\n"
                "Enter values in inches (e.g. 0.1, -0.05)."
            ),
            justify="left",
        ).grid(row=0, column=0, columnspan=4, padx=12, pady=(12, 6), sticky="w")

        ttk.Label(dlg, text="Box-by-Box Overlay Nudge (Pre-Printed Only)", font=("Arial", 10, "bold")).grid(
            row=1, column=0, columnspan=4, padx=12, pady=(0, 4), sticky="w"
        )

        anchor_by_label = {label: key for label, key in CMS_OVERLAY_ANCHOR_OPTIONS}
        label_by_anchor = {key: label for label, key in CMS_OVERLAY_ANCHOR_OPTIONS}
        sv_anchor = tk.StringVar(value=CMS_OVERLAY_ANCHOR_OPTIONS[0][0])

        # ── Scrollable box list ────────────────────────────────────────────────
        ttk.Label(dlg, text="Select box to adjust:").grid(row=2, column=0, padx=12, pady=(4, 2), sticky="w")
        ttk.Label(dlg, text="Selected: 1 Insurance Type", name="lbl_selected", font=("Arial", 9)).grid(
            row=2, column=1, columnspan=3, padx=12, pady=(4, 2), sticky="w"
        )

        list_frame = ttk.Frame(dlg)
        list_frame.grid(row=3, column=0, columnspan=4, padx=12, pady=4, sticky="ew")
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        box_listbox = tk.Listbox(list_frame, height=10, width=56, font=FONT_UI, yscrollcommand=scrollbar.set)
        box_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=box_listbox.yview)
        for label, _key in CMS_OVERLAY_ANCHOR_OPTIONS:
            box_listbox.insert("end", label)

        # ── Per-box nudge entries ──────────────────────────────────────────────
        ttk.Label(dlg, text="Horizontal nudge (inches):").grid(row=4, column=0, padx=12, pady=4, sticky="w")
        sv_box_x = tk.StringVar(value="0")
        ttk.Entry(dlg, textvariable=sv_box_x, width=10).grid(row=4, column=1, padx=12, pady=4, sticky="w")

        ttk.Label(dlg, text="Vertical nudge (inches):").grid(row=5, column=0, padx=12, pady=4, sticky="w")
        sv_box_y = tk.StringVar(value="0")
        ttk.Entry(dlg, textvariable=sv_box_y, width=10).grid(row=5, column=1, padx=12, pady=4, sticky="w")

        nudge_btn_frame = ttk.Frame(dlg)
        nudge_btn_frame.grid(row=4, column=2, columnspan=2, rowspan=2, padx=6, pady=4, sticky="w")
        ttk.Button(nudge_btn_frame, text="Apply Nudge", command=lambda: _apply_box_offset()).pack(side="left", padx=2)
        ttk.Button(nudge_btn_frame, text="Clear Box", command=lambda: _clear_selected_box()).pack(side="left", padx=2)

        offsets_text = tk.Text(dlg, width=60, height=6, font=FONT_MONO, wrap="word")
        offsets_text.grid(row=6, column=0, columnspan=4, padx=12, pady=(8, 4), sticky="ew")

        # ── Helper functions ───────────────────────────────────────────────────
        def _refresh_offsets_text():
            offsets_text.config(state="normal")
            offsets_text.delete("1.0", "end")
            if not box_offsets:
                offsets_text.insert("1.0", "No per-box offsets set.")
            else:
                lines = ["Per-box offsets (inches):"]
                for key in sorted(box_offsets.keys()):
                    lbl = label_by_anchor.get(key, key)
                    x_val = float(box_offsets[key].get("x", 0.0) or 0.0)
                    y_val = float(box_offsets[key].get("y", 0.0) or 0.0)
                    lines.append(f"- {lbl}: x={x_val:+.3f}, y={y_val:+.3f}")
                offsets_text.insert("1.0", "\n".join(lines))
            offsets_text.config(state="disabled")

        def _load_selected_box():
            anchor_key = anchor_by_label.get(sv_anchor.get(), "")
            vals = box_offsets.get(anchor_key, {"x": 0.0, "y": 0.0})
            x_val = float(vals.get("x", 0.0) or 0.0)
            y_val = float(vals.get("y", 0.0) or 0.0)
            sv_box_x.set(f"{x_val:.3f}".rstrip("0").rstrip(".") or "0")
            sv_box_y.set(f"{y_val:.3f}".rstrip("0").rstrip(".") or "0")

        def _update_selected_label():
            try:
                dlg.nametowidget("lbl_selected").config(text=f"Selected: {sv_anchor.get()}")
            except Exception:
                pass

        def _apply_box_offset(show_feedback=True):
            anchor_key = anchor_by_label.get(sv_anchor.get(), "")
            if not anchor_key:
                messagebox.showerror("Alignment", "Select a target box group.", parent=dlg)
                return False
            try:
                box_x = float(sv_box_x.get())
                box_y = float(sv_box_y.get())
            except ValueError:
                messagebox.showerror("Alignment", "Please enter valid box nudge values.", parent=dlg)
                return False
            if abs(box_x) > 2.0 or abs(box_y) > 2.0:
                messagebox.showerror(
                    "Alignment",
                    "Box nudges larger than 2 inches are unlikely to be correct.",
                    parent=dlg,
                )
                return False
            if abs(box_x) < 1e-9 and abs(box_y) < 1e-9:
                box_offsets.pop(anchor_key, None)
            else:
                box_offsets[anchor_key] = {"x": box_x, "y": box_y}
            _refresh_offsets_text()
            if show_feedback:
                messagebox.showinfo("Alignment", f"Saved nudge for {sv_anchor.get()}.", parent=dlg)
            return True

        def _clear_selected_box():
            anchor_key = anchor_by_label.get(sv_anchor.get(), "")
            box_offsets.pop(anchor_key, None)
            _load_selected_box()
            _refresh_offsets_text()

        def _on_box_select(*_args):
            idx = box_listbox.curselection()
            if idx:
                sv_anchor.set(box_listbox.get(idx[0]))
                _update_selected_label()
                _load_selected_box()

        box_listbox.bind("<<ListboxSelect>>", _on_box_select)
        box_listbox.selection_set(0)
        sv_anchor.trace("w", lambda *_: _update_selected_label())
        _load_selected_box()
        _refresh_offsets_text()

        # ── Blank paper shift section ──────────────────────────────────────────
        ttk.Separator(dlg, orient="horizontal").grid(row=7, column=0, columnspan=4, sticky="ew", padx=12, pady=(4, 6))

        ttk.Label(dlg, text="Blank Paper Full-Form Shift", font=("Arial", 10, "bold")).grid(
            row=8, column=0, columnspan=4, padx=12, pady=(0, 4), sticky="w"
        )

        ttk.Label(dlg, text="Horizontal shift (inches):").grid(row=9, column=0, padx=12, pady=4, sticky="w")
        sv_blank_x = tk.StringVar(value=f"{cur_blank_x:.3f}".rstrip("0").rstrip(".") or "0")
        ttk.Entry(dlg, textvariable=sv_blank_x, width=10).grid(row=9, column=1, padx=12, pady=4, sticky="w")

        ttk.Label(dlg, text="Vertical shift (inches):").grid(row=10, column=0, padx=12, pady=4, sticky="w")
        sv_blank_y = tk.StringVar(value=f"{cur_blank_y:.3f}".rstrip("0").rstrip(".") or "0")
        ttk.Entry(dlg, textvariable=sv_blank_y, width=10).grid(row=10, column=1, padx=12, pady=4, sticky="w")

        ttk.Label(
            dlg,
            text=(
                "Use Save + Print Test to print a calibration page with red markers.\n"
                "Apply per-box nudges to fine-tune individual fields on pre-printed forms.\n"
                "Blank-paper values shift the full form (front/back) for printer margins."
            ),
            foreground="gray",
            justify="left",
        ).grid(row=11, column=0, columnspan=4, padx=12, pady=(2, 8), sticky="w")

        # ── Save / Reset / Cancel ─────────────────────────────────────────────
        def _save(close_dialog=True):
            if not _apply_box_offset(show_feedback=False):
                return False
            try:
                blank_x_val = float(sv_blank_x.get())
                blank_y_val = float(sv_blank_y.get())
            except ValueError:
                messagebox.showerror("Alignment", "Please enter valid numbers for blank-paper shift values.", parent=dlg)
                return False
            if abs(blank_x_val) > 2.0 or abs(blank_y_val) > 2.0:
                messagebox.showerror(
                    "Alignment",
                    "Offsets larger than 2 inches are unlikely to be correct.\nPlease re-check the values.",
                    parent=dlg,
                )
                return False
            db.save_provider({
                "cms_blank_offset_x": blank_x_val,
                "cms_blank_offset_y": blank_y_val,
                "cms_overlay_box_offsets": json.dumps(box_offsets, separators=(",", ":")),
            })
            if close_dialog:
                messagebox.showinfo("Alignment", "Overlay alignment saved.", parent=dlg)
                dlg.destroy()
            return True

        def _save_and_print_test():
            if not _save(close_dialog=False):
                return
            dlg.destroy()
            self._print_overlay_alignment_test()

        def _reset():
            sv_blank_x.set("0")
            sv_blank_y.set("0")
            box_offsets.clear()
            _load_selected_box()
            _refresh_offsets_text()

        btn_row = ttk.Frame(dlg)
        btn_row.grid(row=12, column=0, columnspan=4, pady=(0, 12))
        ttk.Button(btn_row, text="Save", command=_save).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Save + Print Test", command=_save_and_print_test).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Reset to 0", command=_reset).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Cancel", command=dlg.destroy).pack(side="left", padx=6)

    def _export_pdf(self):
        paper_mode = messagebox.askyesnocancel(
            "Export Setup",
            "Are you exporting for blank paper?\n\n"
            "Yes: Blank paper (full CMS form; includes back side if template exists)\n"
            "No: Pre-printed CMS form (text overlay only; no second side)\n"
            "Cancel: Do not export",
        )
        if paper_mode is None:
            return

        uses_blank_paper = paper_mode is True
        # Pre-printed export should still show the full front form background,
        # but skip the second side.
        export_mode = "full" if uses_blank_paper else "front_only"

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=(
                f"CMS1500_{self._vars['patient_name'].get().replace(', ', '_') or 'claim'}"
                f"_{'blank' if uses_blank_paper else 'preprinted'}.pdf"
            ),
        )
        if not path:
            return
        saved = self._fill_to_path(Path(path), render_mode=export_mode)
        if saved:
            self._log_form_creation("export", saved)
            mode_text = "blank paper (full form)" if uses_blank_paper else "pre-printed form (front side only)"
            messagebox.showinfo("Exported", f"PDF saved for {mode_text}:\n{saved}")

    def _print_preview(self):
        saved = self._refresh_paper_preview()
        if not saved:
            return
        webbrowser.open(saved.resolve().as_uri())

    def _print_overlay_alignment_test(self):
        if not self._ensure_template():
            return
        try:
            from cms_pdf import fill_cms1500_overlay_alignment_test_pdf
        except ImportError:
            messagebox.showerror("Missing Dependency", "Install dependency: pip install pypdf")
            return

        provider = db.get_provider()
        box_offsets = _overlay_box_offsets_inches_to_points(
            _load_cms_overlay_box_offsets(provider.get("cms_overlay_box_offsets"))
        )
        test_path = APP_ROOT / "temp" / f"CMS1500_overlay_alignment_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        try:
            fill_cms1500_overlay_alignment_test_pdf(
                CMS_TEMPLATE_FILE,
                test_path,
                box_offsets=box_offsets,
            )
        except Exception as ex:
            messagebox.showerror("Alignment Test", f"Could not generate alignment test PDF:\n{ex}")
            return

        if sys.platform.startswith("win"):
            ready = messagebox.askokcancel(
                "Print Alignment Test",
                "Load a pre-printed CMS-1500 form into the printer, then click OK to print the alignment test page.",
            )
            if not ready:
                return
            try:
                os.startfile(str(test_path), "print")
                messagebox.showinfo(
                    "Alignment Test",
                    "Alignment test page sent to the default printer.\nUse the rulers and red reference markers to adjust Align Overlay values.",
                )
            except OSError as ex:
                messagebox.showerror("Alignment Test", f"Could not print alignment test PDF:\n{ex}")
        else:
            webbrowser.open(test_path.resolve().as_uri())
            messagebox.showinfo("Alignment Test", f"Opened alignment test PDF:\n{test_path}")

    def _print_form(self):
        print_path = APP_ROOT / "temp" / f"CMS1500_print_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        try:
            if sys.platform.startswith("win"):
                paper_mode = messagebox.askyesnocancel(
                    "Print Setup",
                    "Are you printing on blank paper?\n\n"
                    "Yes: Blank paper (front/back duplex workflow)\n"
                    "No: Pre-printed CMS form\n"
                    "Cancel: Do not print",
                )
                if paper_mode is None:
                    return

                uses_blank_paper = paper_mode is True
                saved = None
                if not uses_blank_paper:
                    saved = self._fill_to_path(print_path, render_mode="overlay")
                    if not saved:
                        return

                if uses_blank_paper:
                    printer_name = _get_default_printer_name()
                    if not printer_name:
                        messagebox.showerror(
                            "Print",
                            "No default printer is configured. Set a default printer, then try again.",
                        )
                        return

                    today_key = date.today().isoformat()
                    should_open_preferences = self._duplex_prefs_prompted_on != today_key
                    if should_open_preferences:
                        if not _open_printer_preferences(printer_name):
                            messagebox.showwarning(
                                "Print Preferences",
                                f"Could not open printing preferences for:\n{printer_name}\n\nPrinting will continue with the printer's current settings.",
                            )
                        self._duplex_prefs_prompted_on = today_key

                    while True:
                        ready = messagebox.askyesnocancel(
                            "Ready To Print",
                            f"Printer: {printer_name}\n\n"
                            "Yes: Print now\n"
                            "No: Reopen printing preferences\n"
                            "Cancel: Stop without printing",
                        )
                        if ready is True:
                            break
                        if ready is None:
                            return

                        if not _open_printer_preferences(printer_name):
                            messagebox.showwarning(
                                "Print Preferences",
                                f"Could not open printing preferences for:\n{printer_name}\n\nPrinting will continue with the printer's current settings.",
                            )

                    provider = db.get_provider()
                    blank_offset_x_pts = float(provider.get("cms_blank_offset_x") or 0.0) * 72.0
                    blank_offset_y_pts = float(provider.get("cms_blank_offset_y") or 0.0) * 72.0

                    # Print front side only (page 1 of 2) as a separate job.
                    front_path = print_path.with_stem(print_path.stem + "_front")
                    saved_front = self._fill_to_path(front_path, render_mode="front_only")
                    if not saved_front:
                        return
                    self._log_form_creation("print_blank_front", saved_front)
                    front_to_print = saved_front
                    if abs(blank_offset_x_pts) > 0.01 or abs(blank_offset_y_pts) > 0.01:
                        try:
                            from cms_pdf import render_shifted_pdf
                            shifted_front = print_path.with_stem(print_path.stem + "_front_shifted")
                            render_shifted_pdf(saved_front, shifted_front,
                                               offset_x=blank_offset_x_pts,
                                               offset_y=blank_offset_y_pts)
                            front_to_print = shifted_front
                        except Exception as ex:
                            messagebox.showwarning(
                                "Print Alignment",
                                f"Could not apply blank-paper offset to front page:\n{ex}\n\n"
                                "Printing will continue without blank-paper offset.",
                            )
                    os.startfile(str(front_to_print), "print")

                    back_template = _resolve_cms_back_template()
                    if back_template:
                        flip_ok = messagebox.askokcancel(
                            "Flip Paper for Back Side",
                            "Side 1 (front) has been sent to the printer.\n\n"
                            "When it finishes printing:\n"
                            "  1. Remove the sheet from the output tray\n"
                            "  2. Flip it over and reload it into the paper tray\n"
                            "     (printed side down, same orientation)\n\n"
                            "Click OK when the paper is loaded to print side 2,\n"
                            "or Cancel to skip the back side.",
                        )
                        if flip_ok:
                            back_to_print = back_template
                            if abs(blank_offset_x_pts) > 0.01 or abs(blank_offset_y_pts) > 0.01:
                                try:
                                    from cms_pdf import render_shifted_pdf
                                    shifted_back = print_path.with_stem(print_path.stem + "_back_shifted")
                                    render_shifted_pdf(back_template, shifted_back,
                                                       offset_x=blank_offset_x_pts,
                                                       offset_y=blank_offset_y_pts)
                                    back_to_print = shifted_back
                                except Exception as ex:
                                    messagebox.showwarning(
                                        "Print Alignment",
                                        f"Could not apply blank-paper offset to back page:\n{ex}\n\n"
                                        "Printing will continue without blank-paper offset.",
                                    )
                            os.startfile(str(back_to_print), "print")
                            messagebox.showinfo("Print", "Side 2 (back) sent to printer.\nPrinting complete.")
                        else:
                            messagebox.showinfo("Print", "Back side skipped. Front side only was printed.")
                    else:
                        messagebox.showinfo("Print", "CMS-1500 front sent to printer.\n(No back template found.)")
                else:
                    self._log_form_creation("print_preprinted", saved)
                    os.startfile(str(saved), "print")
                    messagebox.showinfo("Print", "CMS-1500 sent to default printer.")
            else:
                saved = self._fill_to_path(print_path, render_mode="full")
                if not saved:
                    return
                self._log_form_creation("print_non_windows", saved)
                webbrowser.open(saved.resolve().as_uri())
                messagebox.showinfo("Print", f"Opened PDF for printing:\n{saved}")
        except OSError as ex:
            messagebox.showerror("Print", f"Could not print PDF:\n{ex}")


# ─── Reports Tab ───────────────────────────────────────────────────────────────

class ReportsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._last_cms_rows = []
        self._last_cms_title = "CMS-1500 Forms Created"
        self._cms_patient_map: dict[str, int] = {}
        self._build()

    def _build(self):
        ttk.Label(self, text="Reports", font=FONT_H1).pack(anchor="w", padx=14, pady=(12, 6))

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(0, weight=1)

        actions = lframe(frm, "Reports")
        actions.grid(row=0, column=0, sticky="nsw", padx=(0, 10))

        output_wrap = lframe(frm, "Report Output")
        output_wrap.grid(row=0, column=1, sticky="nsew")
        output_wrap.columnconfigure(0, weight=1)
        output_wrap.rowconfigure(0, weight=1)

        def report_btn(txt, cmd):
            # Keep report controls compact so the output area has more room.
            btn(actions, txt, cmd, "TButton", width=38).pack(fill="x", padx=4, pady=2)

        cms_filters = lframe(actions, "CMS-1500 Filters")
        cms_filters.pack(fill="x", padx=4, pady=(2, 6))

        ttk.Label(cms_filters, text="Patient").pack(anchor="w", padx=2)
        self._cms_patient_sv = tk.StringVar(value="All Patients")
        self._cms_patient_cb = ttk.Combobox(
            cms_filters,
            textvariable=self._cms_patient_sv,
            state="readonly",
            width=34,
        )
        self._cms_patient_cb.pack(fill="x", pady=(0, 4))

        ttk.Label(cms_filters, text="Month Created").pack(anchor="w", padx=2)
        self._cms_month_sv = tk.StringVar(value="All Months")
        self._cms_month_cb = ttk.Combobox(
            cms_filters,
            textvariable=self._cms_month_sv,
            state="readonly",
            width=34,
            values=[
                "All Months",
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December",
            ],
        )
        self._cms_month_cb.pack(fill="x", pady=(0, 4))

        ttk.Label(cms_filters, text="Year Created (Choose Year)").pack(anchor="w", padx=2)
        self._cms_year_sv = tk.StringVar(value="All Years")
        self._cms_year_cb = ttk.Combobox(
            cms_filters,
            textvariable=self._cms_year_sv,
            state="readonly",
            width=34,
        )
        self._cms_year_cb.pack(fill="x", pady=(0, 6))

        btn(cms_filters, "Run CMS-1500 Forms Created", self._run_cms1500_filtered_report, "TButton", width=34).pack(fill="x")
        self._load_cms_filter_options()

        report_btn("Patient Roster (Active)",    self._rpt_active_patients)
        report_btn("Patient Roster (Inactive)",  self._rpt_inactive_patients)
        report_btn("Sessions This Month",        self._rpt_sessions_month)
        report_btn("Sessions by Patient",        self._rpt_sessions_patient)
        report_btn("Billing Summary",            self._rpt_billing_summary)
        report_btn("Outstanding Balances",       self._rpt_outstanding)
        report_btn("Export CMS-1500 Forms (CSV)", self._export_cms1500_csv)
        report_btn("Export All Patients (CSV)",  self._export_patients_csv)
        report_btn("Export Sessions (CSV)",      self._export_sessions_csv)
        report_btn("Export Billing (CSV)",       self._export_billing_csv)

        self._output = tk.Text(output_wrap, font=FONT_MONO, wrap="none", height=24,
                               relief="solid", borderwidth=1, background="#fafafa")
        sb_v = ttk.Scrollbar(output_wrap, orient="vertical",   command=self._output.yview)
        sb_h = ttk.Scrollbar(output_wrap, orient="horizontal", command=self._output.xview)
        self._output.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)
        self._output.grid(row=0, column=0, sticky="nsew")
        sb_v.grid(row=0, column=1, sticky="ns")
        sb_h.grid(row=1, column=0, sticky="ew")

    def _show(self, text):
        self._output.config(state="normal")
        self._output.delete("1.0", "end")
        self._output.insert("1.0", text)
        self._output.config(state="disabled")

    def _rpt_active_patients(self):
        rows = db.get_all_patients("Active")
        lines = [f"{'ID':>4}  {'Last Name':<18}  {'First':<14}  {'DOB':<12}  "
                 f"{'Phone':<14}  {'Insurance':<22}  Dx1"]
        lines.append("-" * 100)
        for r in rows:
            lines.append(f"{r['id']:>4}  {r['last_name']:<18}  {r['first_name']:<14}  "
                         f"{fmt_date(r['dob']):<12}  {r['phone_home'] or r['phone_cell']:<14}  "
                         f"{r['ins_name']:<22}  {r['dx1']}")
        lines.append(f"\nTotal: {len(rows)} active patients")
        self._show("\n".join(lines))

    def _rpt_inactive_patients(self):
        rows = db.get_all_patients("Inactive")
        lines = [f"{'ID':>4}  {'Last Name':<18}  {'First':<14}  Intake Date"]
        lines.append("-" * 70)
        for r in rows:
            lines.append(f"{r['id']:>4}  {r['last_name']:<18}  {r['first_name']:<14}  {fmt_date(r['intake_date'])}")
        lines.append(f"\nTotal: {len(rows)} inactive patients")
        self._show("\n".join(lines))

    def _rpt_sessions_month(self):
        today = date.today()
        month_prefix = today.strftime("%Y-%m")
        conn = db.get_connection()
        rows = conn.execute(
            """SELECT s.session_date, p.last_name, p.first_name, s.session_type, s.cpt_code, s.fee, s.signed
               FROM session_notes s JOIN patients p ON s.patient_id=p.id
               WHERE s.session_date LIKE ?
               ORDER BY s.session_date""",
            (f"{month_prefix}%",)
        ).fetchall()
        conn.close()
        lines = [f"Sessions for {today.strftime('%B %Y')}", ""]
        lines.append(f"{'Date':<12}  {'Patient':<24}  {'Type':<14}  {'CPT':<8}  {'Fee':>8}  Signed")
        lines.append("-" * 88)
        total_fee = 0.0
        for r in rows:
            total_fee += float(r["fee"] or 0)
            lines.append(f"{fmt_date(r['session_date']):<12}  "
                         f"{r['last_name']+', '+r['first_name']:<24}  "
                         f"{r['session_type']:<14}  {r['cpt_code']:<8}  "
                         f"{fmt_money(r['fee']):>8}  {'✓' if r['signed'] else ''}")
        lines.append(f"\nTotal sessions: {len(rows)}   Total fees: {fmt_money(total_fee)}")
        self._show("\n".join(lines))

    def _rpt_sessions_patient(self):
        conn = db.get_connection()
        rows = conn.execute(
            """SELECT p.id, p.last_name, p.first_name, COUNT(s.id) AS cnt,
                      SUM(s.fee) AS total_fee
               FROM patients p
               LEFT JOIN session_notes s ON s.patient_id=p.id
               WHERE p.status='Active'
               GROUP BY p.id ORDER BY p.last_name""").fetchall()
        conn.close()
        lines = [f"{'Patient':<26}  {'Sessions':>9}  {'Total Fees':>12}"]
        lines.append("-" * 56)
        for r in rows:
            lines.append(f"{r['last_name']+', '+r['first_name']:<26}  "
                         f"{r['cnt']:>9}  {fmt_money(r['total_fee'] or 0):>12}")
        self._show("\n".join(lines))

    def _rpt_billing_summary(self):
        tc, tp, tb = db.get_billing_summary()
        lines = ["Billing Summary – All Patients", "=" * 40,
                 f"Total Charges:  {fmt_money(tc):>12}",
                 f"Total Paid:     {fmt_money(tp):>12}",
                 f"Total Balance:  {fmt_money(tb):>12}"]
        # Per-patient breakdown
        conn = db.get_connection()
        rows = conn.execute(
            """SELECT p.last_name, p.first_name,
                      SUM(b.charge) AS tc, SUM(b.payment)+SUM(b.ins_payment) AS tp,
                      SUM(b.charge)-SUM(b.payment)-SUM(b.ins_payment)-SUM(b.adjustment) AS tb
               FROM billing_records b JOIN patients p ON b.patient_id=p.id
               GROUP BY p.id ORDER BY tb DESC LIMIT 50"""
        ).fetchall()
        conn.close()
        lines += ["", f"\n{'Patient':<26}  {'Charges':>10}  {'Paid':>10}  {'Balance':>10}"]
        lines.append("-" * 62)
        for r in rows:
            lines.append(f"{r['last_name']+', '+r['first_name']:<26}  "
                         f"{fmt_money(r['tc'] or 0):>10}  {fmt_money(r['tp'] or 0):>10}  "
                         f"{fmt_money(r['tb'] or 0):>10}")
        self._show("\n".join(lines))

    def _rpt_outstanding(self):
        conn = db.get_connection()
        rows = conn.execute(
            """SELECT p.last_name, p.first_name, p.phone_home, p.phone_cell,
                      SUM(b.charge)-SUM(b.payment)-SUM(b.ins_payment)-SUM(b.adjustment) AS bal
               FROM billing_records b JOIN patients p ON b.patient_id=p.id
               GROUP BY p.id HAVING bal > 0.005
               ORDER BY bal DESC"""
        ).fetchall()
        conn.close()
        lines = ["Outstanding Balances", "=" * 56,
                 f"{'Patient':<26}  {'Phone':<14}  {'Balance':>10}"]
        lines.append("-" * 56)
        for r in rows:
            phone = r["phone_home"] or r["phone_cell"] or ""
            lines.append(f"{r['last_name']+', '+r['first_name']:<26}  {phone:<14}  {fmt_money(r['bal']):>10}")
        self._show("\n".join(lines))

    def _load_cms_filter_options(self):
        logs = db.get_cms1500_form_creation_logs()

        patient_items = {"All Patients": 0}
        roster_rows = db.get_all_patients("Active") + db.get_all_patients("Inactive")
        for p in roster_rows:
            status = str(p["status"] or "").strip() or "Unknown"
            label = f"{p['last_name']}, {p['first_name']} [{status}] (ID:{int(p['id'])})"
            patient_items[label] = int(p["id"])
        self._cms_patient_map = patient_items
        patient_values = list(patient_items.keys())
        self._cms_patient_cb["values"] = patient_values
        if self._cms_patient_sv.get() not in patient_values:
            self._cms_patient_sv.set("All Patients")

        years = []
        for r in logs:
            created_at = str(r["created_at"] or "")
            yr = created_at[:4]
            if yr.isdigit():
                years.append(yr)
        year_values = ["All Years"] + sorted(set(years), reverse=True)
        self._cms_year_cb["values"] = year_values
        if self._cms_year_sv.get() not in year_values:
            self._cms_year_sv.set("All Years")

        if not self._cms_month_sv.get():
            self._cms_month_sv.set("All Months")

    def _run_cms1500_filtered_report(self):
        self._load_cms_filter_options()
        rows = db.get_cms1500_form_creation_logs()

        selected_patient = self._cms_patient_sv.get().strip()
        selected_month = self._cms_month_sv.get().strip()
        selected_year = self._cms_year_sv.get().strip()

        month_map = {
            "January": "01", "February": "02", "March": "03", "April": "04",
            "May": "05", "June": "06", "July": "07", "August": "08",
            "September": "09", "October": "10", "November": "11", "December": "12",
        }

        if selected_patient and selected_patient != "All Patients":
            pid = self._cms_patient_map.get(selected_patient)
            if pid:
                rows = [r for r in rows if int(r["patient_id"]) == int(pid)]

        if selected_year and selected_year != "All Years":
            rows = [r for r in rows if str(r["created_at"] or "").startswith(f"{selected_year}-")]

        if selected_month and selected_month != "All Months":
            month_num = month_map.get(selected_month)
            if month_num:
                rows = [r for r in rows if str(r["created_at"] or "")[5:7] == month_num]

        title_parts = ["CMS-1500 Forms Created"]
        if selected_patient != "All Patients":
            title_parts.append(selected_patient)
        if selected_month != "All Months":
            title_parts.append(selected_month)
        if selected_year != "All Years":
            title_parts.append(selected_year)
        title = " | ".join(title_parts)

        self._last_cms_rows = rows
        self._last_cms_title = title
        lines = [
            title,
            "=" * 96,
            f"{'Created On':<10}  {'Patient':<28}  {'Source':<20}  {'Patient ID':>10}",
            "-" * 96,
        ]
        for r in rows:
            created_at = str(r["created_at"] or "")
            created_disp = created_at[:10]
            patient_name = f"{r['last_name']}, {r['first_name']}"
            lines.append(
                f"{created_disp:<10}  {patient_name:<28}  {str(r['created_source'] or ''):<20}  {int(r['patient_id']):>10}"
            )
        lines.append(f"\nTotal CMS-1500 forms created: {len(rows)}")
        self._show("\n".join(lines))

    def _rpt_cms1500_created(self, created_from: str = "", created_to: str = "", title: str = "CMS-1500 Forms Created"):
        rows = db.get_cms1500_form_creation_logs(created_from=created_from, created_to=created_to)
        self._last_cms_rows = rows
        self._last_cms_title = title
        lines = [
            title,
            "=" * 96,
            f"{'Created On':<10}  {'Patient':<28}  {'Source':<20}  {'Patient ID':>10}",
            "-" * 96,
        ]
        for r in rows:
            created_at = str(r["created_at"] or "")
            created_disp = created_at[:10]
            patient_name = f"{r['last_name']}, {r['first_name']}"
            lines.append(
                f"{created_disp:<10}  {patient_name:<28}  {str(r['created_source'] or ''):<20}  {int(r['patient_id']):>10}"
            )
        lines.append(f"\nTotal CMS-1500 forms created: {len(rows)}")
        self._show("\n".join(lines))

    def _rpt_cms1500_created_month(self):
        start = date.today().replace(day=1).isoformat() + " 00:00:00"
        self._rpt_cms1500_created(created_from=start, title="CMS-1500 Forms Created (This Month)")

    def _rpt_cms1500_created_last_30(self):
        start = (date.today() - timedelta(days=30)).isoformat() + " 00:00:00"
        self._rpt_cms1500_created(created_from=start, title="CMS-1500 Forms Created (Last 30 Days)")

    def _rpt_cms1500_created_this_year(self):
        self._rpt_cms1500_created_year(date.today().year)

    def _rpt_cms1500_created_past_year(self):
        self._rpt_cms1500_created_year(date.today().year - 1)

    def _rpt_cms1500_created_year(self, year: int):
        start = f"{int(year):04d}-01-01 00:00:00"
        end = f"{int(year) + 1:04d}-01-01 00:00:00"
        self._rpt_cms1500_created(
            created_from=start,
            created_to=end,
            title=f"CMS-1500 Forms Created ({int(year)})",
        )

    def _rpt_cms1500_created_pick_year(self):
        current_year = date.today().year
        year = simpledialog.askinteger(
            "Choose Year",
            "Enter year for CMS-1500 report:",
            parent=self,
            minvalue=2000,
            maxvalue=current_year,
            initialvalue=current_year,
        )
        if year is None:
            return
        self._rpt_cms1500_created_year(int(year))

    def _export_cms1500_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile="cms1500_forms_created.csv")
        if not path:
            return
        import csv as _csv

        rows = self._last_cms_rows or db.get_cms1500_form_creation_logs()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = _csv.writer(f)
            w.writerow(["created_on", "patient_id", "last_name", "first_name", "source", "created_at", "output_path"])
            for r in rows:
                created_at = str(r["created_at"] or "")
                w.writerow([
                    created_at[:10],
                    r["patient_id"],
                    r["last_name"],
                    r["first_name"],
                    r["created_source"],
                    created_at,
                    r["output_path"],
                ])
        messagebox.showinfo("Exported", f"{self._last_cms_title} exported to:\n{path}")

    def _export_patients_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile="patients_export.csv")
        if not path:
            return
        import csv as _csv
        rows = db.get_all_patients("Active") + db.get_all_patients("Inactive")
        keys = rows[0].keys() if rows else []
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = _csv.writer(f)
            w.writerow(keys)
            for r in rows:
                w.writerow([r[k] for k in keys])
        messagebox.showinfo("Exported", f"Patients exported to:\n{path}")

    def _export_sessions_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile="sessions_export.csv")
        if not path:
            return
        import csv as _csv
        conn = db.get_connection()
        rows = conn.execute(
            "SELECT s.*, p.last_name, p.first_name FROM session_notes s JOIN patients p ON s.patient_id=p.id"
        ).fetchall()
        conn.close()
        keys = rows[0].keys() if rows else []
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = _csv.writer(f)
            w.writerow(keys)
            for r in rows:
                w.writerow([r[k] for k in keys])
        messagebox.showinfo("Exported", f"Sessions exported to:\n{path}")

    def _export_billing_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile="billing_export.csv")
        if not path:
            return
        import csv as _csv
        conn = db.get_connection()
        rows = conn.execute(
            "SELECT b.*, p.last_name, p.first_name FROM billing_records b JOIN patients p ON b.patient_id=p.id"
        ).fetchall()
        conn.close()
        keys = rows[0].keys() if rows else []
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = _csv.writer(f)
            w.writerow(keys)
            for r in rows:
                w.writerow([r[k] for k in keys])
        messagebox.showinfo("Exported", f"Billing exported to:\n{path}")


# ─── CPT Codes Tab ────────────────────────────────────────────────────────────

class CPTCodesTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._fee_vars: dict[str, tk.StringVar] = {}
        self._build()
        self.refresh()

    def _build(self):
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="CPT Codes", font=FONT_H1).pack(anchor="w")
        ttk.Label(
            root,
            text="Update fee amounts used to auto-fill Session fee when a CPT code is selected.",
            foreground=MUTED,
        ).pack(anchor="w", pady=(2, 10))

        grid = ttk.Frame(root)
        grid.pack(anchor="w", fill="x")

        ttk.Label(grid, text="CPT Code", font=FONT_LG).grid(row=0, column=0, sticky="w", padx=(0, 14), pady=(0, 6))
        ttk.Label(grid, text="Amount ($)", font=FONT_LG).grid(row=0, column=1, sticky="w", pady=(0, 6))

        for i, code in enumerate(CPT_CODES, start=1):
            ttk.Label(grid, text=code).grid(row=i, column=0, sticky="w", padx=(0, 14), pady=3)
            v = tk.StringVar(value="0.00")
            self._fee_vars[code] = v
            ttk.Entry(grid, textvariable=v, width=12).grid(row=i, column=1, sticky="w", pady=3)

        btn_row = ttk.Frame(root)
        btn_row.pack(anchor="w", pady=(12, 0))
        btn(btn_row, "Save CPT Amounts", self._save, "Accent.TButton").pack(side="left", padx=(0, 8))
        btn(btn_row, "Reset Defaults", self._reset_defaults).pack(side="left")

    def refresh(self):
        schedule = get_cpt_fee_schedule()
        for code in CPT_CODES:
            amount = float(schedule.get(code, 0.0) or 0.0)
            self._fee_vars[code].set(f"{amount:.2f}")

    def _save(self):
        payload: dict[str, float] = {}
        for code in CPT_CODES:
            txt = self._fee_vars[code].get().strip()
            try:
                amt = float(txt or 0.0)
            except ValueError:
                messagebox.showerror("Invalid Amount", f"Enter a valid dollar amount for CPT {code}.")
                return
            if amt < 0:
                messagebox.showerror("Invalid Amount", f"Amount for CPT {code} cannot be negative.")
                return
            payload[code] = round(amt, 2)

        save_cpt_fee_schedule(payload)
        self.refresh()
        messagebox.showinfo("Saved", "CPT amounts saved. Session fee auto-fill now uses these values.")

    def _reset_defaults(self):
        if not messagebox.askyesno(
            "Reset CPT Amounts",
            "Reset all CPT fee amounts to defaults?",
            parent=self,
        ):
            return
        save_cpt_fee_schedule(DEFAULT_CPT_FEES)
        self.refresh()
        messagebox.showinfo("Reset", "CPT amounts reset to default values.")


# ─── Provider / Practice Tab ───────────────────────────────────────────────────

class ProviderPracticeTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._vars = {}
        self._build()
        self._load()

    def _fld(self, name, default=""):
        v = tk.StringVar(value=default)
        self._vars[name] = v
        return v

    def _build(self):
        frm = ttk.Frame(self, padding=14)
        frm.pack(fill="both", expand=True)
        for c in range(4):
            frm.columnconfigure(c, weight=1)

        fields = [
            ("Practice Name",          "practice_name",  0, 0),
            ("Provider Last Name",     "provider_last",  1, 0),
            ("Provider First Name",    "provider_first", 1, 2),
            ("Provider Suffix",        "provider_suffix", 2, 0),
            ("Credentials (LCSW etc.)", "credentials",   2, 2),
            ("NPI",                    "npi",            3, 0),
            ("Tax ID",                 "tax_id",         3, 2),
            ("Tax ID Type (EIN/SSN)",  "tax_id_type",    4, 0),
            ("ID Qualifier",           "id_qualifier",   4, 2),
            ("Taxonomy Codes",         "license_num",    5, 0),
            ("UPIN (legacy)",          "upin",           5, 2),
            ("Address",                "address",        6, 0),
            ("City",                   "city",           7, 0),
            ("State",                  "state",          7, 2),
            ("Zip",                    "zip",            8, 0),
            ("Phone",                  "phone",          8, 2),
            ("Fax",                    "fax",            9, 0),
            ("Email",                  "email",          9, 2),
            ("Default POS",            "default_pos",   10, 0),
        ]
        for lbl, key, r, c in fields:
            ttk.Label(frm, text=lbl).grid(row=r, column=c, sticky="e", padx=4, pady=3)
            ttk.Entry(frm, textvariable=self._fld(key), width=26).grid(
                row=r, column=c + 1, sticky="ew", padx=(0, 12)
            )

        self.accept_var = tk.IntVar(value=1)
        assign_frm = ttk.Frame(frm)
        assign_frm.grid(row=11, column=0, columnspan=4, sticky="w", padx=4, pady=4)
        ttk.Label(assign_frm, text="Assignment:").pack(side="left", padx=(0, 8))
        ttk.Radiobutton(
            assign_frm,
            text="Accept Assignment",
            variable=self.accept_var,
            value=1,
        ).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(
            assign_frm,
            text="Do Not Accept Assignment",
            variable=self.accept_var,
            value=0,
        ).pack(side="left")

        btn(frm, "Save Provider Settings", self._save_provider, "Accent.TButton").grid(
            row=12, column=0, columnspan=2, pady=10, padx=4, sticky="w"
        )

    def _load(self):
        prov = db.get_provider()
        for key, var in self._vars.items():
            var.set(str(prov.get(key, "") or ""))
        self.accept_var.set(prov.get("accept_assign", 1))

    def _save_provider(self):
        data = {k: v.get().strip() for k, v in self._vars.items()}
        data["accept_assign"] = self.accept_var.get()
        db.save_provider(data)
        messagebox.showinfo("Saved", "Provider settings saved.")


# ─── Settings Tab ──────────────────────────────────────────────────────────────

class SettingsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _refresh_app_views(self, *, patients=False, sessions=False, billing=False, select_tab=None):
        app = self.winfo_toplevel()
        if patients and hasattr(app, "tab_patients"):
            app.tab_patients.refresh()
        if sessions and hasattr(app, "tab_sessions"):
            app.tab_sessions.refresh()
        if billing and hasattr(app, "tab_billing"):
            app.tab_billing.refresh()
        if hasattr(app, "_update_stats"):
            app._update_stats()
        if select_tab is not None and hasattr(app, "nb"):
            app.nb.select(select_tab)

    def _build(self):
        f2 = ttk.Frame(self, padding=14)
        f2.pack(fill="both", expand=True)

        ttk.Label(f2, text="Import Data from Any Medical Software",
                  font=FONT_LG).pack(anchor="w", pady=(0, 6))

        info_txt = (
            "Aura Scribe PSY accepts CSV files exported from any medical practice management\n"
            "or EHR system (SimplePractice, Kareo, TherapyNotes, Practice Fusion, etc.).\n\n"
            "HOW TO EXPORT FROM YOUR CURRENT SOFTWARE:\n"
            "  1. Open your current software and go to its export / reports section.\n"
            "  2. Choose CSV or Excel format, then save the file.\n"
            "  3. Use the Import buttons below to bring data into Aura Scribe PSY.\n\n"
            "Aura Scribe PSY automatically maps common column names - exact header names\n"
            "are not required.  For best results, download a CSV template to see the\n"
            "expected structure and rename your exported columns accordingly."
        )
        ttk.Label(f2, text=info_txt, justify="left", wraplength=680).pack(anchor="w")

        ttk.Separator(f2).pack(fill="x", pady=10)

        # ── Import buttons ────────────────────────────────────────────────────
        ttk.Label(f2, text="Import Records", font=("Calibri", 10, "bold")).pack(anchor="w", pady=(0, 4))
        import_frm = ttk.Frame(f2)
        import_frm.pack(anchor="w")
        btn(import_frm, "⬆  Import Patients (CSV)",
            self._import_patients_csv, "Accent.TButton").grid(row=0, column=0, padx=4, pady=4)
        btn(import_frm, "⬆  Import Sessions (CSV)",
            self._import_sessions_csv, "Accent.TButton").grid(row=0, column=1, padx=4, pady=4)
        btn(import_frm, "⬆  Import Billing (CSV)",
            self._import_billing_csv,  "Accent.TButton").grid(row=0, column=2, padx=4, pady=4)

        ttk.Separator(f2).pack(fill="x", pady=10)

        # ── CSV Templates ─────────────────────────────────────────────────────
        ttk.Label(f2, text="Download CSV Templates", font=("Calibri", 10, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Label(f2,
                  text="Download a blank template to see the required columns and format for each record type.",
                  foreground=MUTED).pack(anchor="w", pady=(0, 6))
        tpl_frm = ttk.Frame(f2)
        tpl_frm.pack(anchor="w")
        btn(tpl_frm, "⬇  Patients Template",
            self._download_patients_template, "TButton").grid(row=0, column=0, padx=4, pady=4)
        btn(tpl_frm, "⬇  Sessions Template",
            self._download_sessions_template, "TButton").grid(row=0, column=1, padx=4, pady=4)
        btn(tpl_frm, "⬇  Billing Template",
            self._download_billing_template,  "TButton").grid(row=0, column=2, padx=4, pady=4)
        btn(tpl_frm, "⬇  Bookkeeping Template",
            self._download_bookkeeping_template,  "TButton").grid(row=0, column=3, padx=4, pady=4)

        ttk.Separator(f2).pack(fill="x", pady=10)

        ttk.Label(f2, text="Import Log", font=("Calibri", 10, "bold")).pack(anchor="w", pady=(0, 2))
        self._import_log = tk.Text(f2, height=10, font=FONT_MONO, state="disabled",
                                   relief="solid", borderwidth=1, background="#fafafa")
        self._import_log.pack(fill="both", expand=True)

    def _log(self, text):
        self._import_log.config(state="normal")
        self._import_log.insert("end", text + "\n")
        self._import_log.see("end")
        self._import_log.config(state="disabled")

    def _import_patients_csv(self, path=None, any_filetype=True):
        if not path:
            filetypes = [("CSV Files", "*.csv"), ("Text Files", "*.txt"), ("All Files", "*.*")]
            if any_filetype:
                filetypes = [("All Files", "*.*"), ("CSV Files", "*.csv"), ("Text Files", "*.txt")]
            path = filedialog.askopenfilename(
                title="Select Patients Import File",
                filetypes=filetypes,
            )
        if not path:
            return
        try:
            import migration
            count, warns = migration.import_patients_csv(path)
        except Exception as ex:
            self._log(f"Patients import failed: {path}")
            self._log(f"  ERROR: {ex}")
            messagebox.showerror("Import Failed", f"Could not import patients from:\n{path}\n\nError: {ex}")
            return
        self._log(f"Patients imported: {count}")
        for w in warns[:20]:
            self._log(f"  WARN: {w}")
        self._refresh_app_views(patients=True, select_tab=0)
        messagebox.showinfo("Import Complete", f"Imported {count} patients.\n{len(warns)} warnings.")

    def _import_sessions_csv(self, path=None, any_filetype=True):
        if not path:
            filetypes = [("CSV Files", "*.csv"), ("Text Files", "*.txt"), ("All Files", "*.*")]
            if any_filetype:
                filetypes = [("All Files", "*.*"), ("CSV Files", "*.csv"), ("Text Files", "*.txt")]
            path = filedialog.askopenfilename(
                title="Select Sessions Import File",
                filetypes=filetypes,
            )
        if not path:
            return
        try:
            import migration
            count, warns = migration.import_sessions_csv(path)
        except Exception as ex:
            self._log(f"Sessions import failed: {path}")
            self._log(f"  ERROR: {ex}")
            messagebox.showerror("Import Failed", f"Could not import sessions from:\n{path}\n\nError: {ex}")
            return
        self._log(f"Sessions imported: {count}")
        for w in warns[:20]:
            self._log(f"  WARN: {w}")
        self._refresh_app_views(sessions=True)
        messagebox.showinfo("Import Complete", f"Imported {count} sessions.\n{len(warns)} warnings.")

    def _import_billing_csv(self, path=None, any_filetype=True):
        if not path:
            filetypes = [("CSV Files", "*.csv"), ("Text Files", "*.txt"), ("All Files", "*.*")]
            if any_filetype:
                filetypes = [("All Files", "*.*"), ("CSV Files", "*.csv"), ("Text Files", "*.txt")]
            path = filedialog.askopenfilename(
                title="Select Billing Import File",
                filetypes=filetypes,
            )
        if not path:
            return
        try:
            import migration
            count, warns = migration.import_billing_csv(path)
        except Exception as ex:
            self._log(f"Billing import failed: {path}")
            self._log(f"  ERROR: {ex}")
            messagebox.showerror("Import Failed", f"Could not import billing records from:\n{path}\n\nError: {ex}")
            return
        self._log(f"Billing records imported: {count}")
        for w in warns[:20]:
            self._log(f"  WARN: {w}")
        self._refresh_app_views(billing=True)
        messagebox.showinfo("Import Complete", f"Imported {count} billing records.\n{len(warns)} warnings.")

    def _download_patients_template(self):
        path = filedialog.asksaveasfilename(
            title="Save Patients CSV Template",
            initialfile="patients_template.csv",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All", "*.*")])
        if not path:
            return
        import migration
        migration.write_patients_template(path)
        self._log(f"Patients template saved: {path}")
        messagebox.showinfo("Template Saved", f"Patients CSV template saved to:\n{path}")

    def _download_sessions_template(self):
        path = filedialog.asksaveasfilename(
            title="Save Sessions CSV Template",
            initialfile="sessions_template.csv",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All", "*.*")])
        if not path:
            return
        import migration
        migration.write_sessions_template(path)
        self._log(f"Sessions template saved: {path}")
        messagebox.showinfo("Template Saved", f"Sessions CSV template saved to:\n{path}")

    def _download_billing_template(self):
        path = filedialog.asksaveasfilename(
            title="Save Billing CSV Template",
            initialfile="billing_template.csv",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All", "*.*")])
        if not path:
            return
        import migration
        migration.write_billing_template(path)
        self._log(f"Billing template saved: {path}")
        messagebox.showinfo("Template Saved", f"Billing CSV template saved to:\n{path}")

    def _download_bookkeeping_template(self):
        path = filedialog.asksaveasfilename(
            title="Save Bookkeeping CSV Template",
            initialfile="bookkeeping_template.csv",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All", "*.*")])
        if not path:
            return
        import migration
        migration.write_bookkeeping_template(path)
        self._log(f"Bookkeeping template saved: {path}")
        messagebox.showinfo("Template Saved", f"Bookkeeping CSV template saved to:\n{path}")


# ─── Bookkeeping ───────────────────────────────────────────────────────────────

_BK_MONTHS = ["All", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]

_BK_INC_COLS  = [("inc_client",       "Client Fees"),
                  ("inc_insurance",    "Ins. Pay."),
                  ("inc_other",        "Other Inc.")]
_BK_EXP_COLS  = [("exp_rent",         "Rent"),
                  ("exp_utilities",    "Utilities"),
                  ("exp_office",       "Office Sup."),
                  ("exp_insurance",    "Ins. Exp."),
                  ("exp_phone",        "Phone"),
                  ("exp_professional", "Prof. Fees"),
                  ("exp_advertising",  "Advertising"),
                  ("exp_misc",         "Misc.")]


class BookkeepingEntryDialog(tk.Toplevel):
    """Add / Edit a single bookkeeping entry."""

    _GEOMETRY_PREF_KEY = "bookkeeping_entry_geometry"
    _STD_DEFAULT_DIALOG_SIZE = (1160, 800)
    _STD_MIN_DIALOG_SIZE = (1080, 740)
    _DENSE_DEFAULT_DIALOG_SIZE = (1240, 860)
    _DENSE_MIN_DIALOG_SIZE = (1040, 700)

    def __init__(self, parent, entry=None, on_save=None, preset=None):
        super().__init__(parent)
        apply_window_icon(self)
        self.on_save = on_save
        self._entry  = dict(entry) if entry else {}
        self._preset = dict(preset or {})
        self._is_edit = bool(entry)
        if self._is_edit:
            self.title("Edit Entry")
        else:
            kind = self._preset.get("quick_kind")
            self.title(f"New {kind}" if kind in ("Expense", "Income") else "New Entry")
        self.resizable(True, True)

        self._inc_map = {label: key for key, label in _BK_INC_COLS}
        self._exp_map = {label: key for key, label in _BK_EXP_COLS}

        self._vars: dict[str, tk.StringVar] = {}
        self._tax_var = tk.BooleanVar(value=bool(self._entry.get("is_tax_deductible", 0)))
        self._quick_mode_var = tk.BooleanVar(value=True)
        self._quick_kind_var = tk.StringVar(value="Expense")
        self._quick_cat_var = tk.StringVar(value="")
        self._quick_amt_var = tk.StringVar(value="")
        self._last_normal_geometry = ""
        self._min_dialog_w = 1080
        self._min_dialog_h = 740

        self._build()
        self._load()
        self.transient(parent)
        self._restore_window_placement()
        self.bind("<Configure>", self._on_window_configure, add="+")
        self.protocol("WM_DELETE_WINDOW", self._close_dialog)
        # Avoid hard modal grab so Windows minimize works reliably.
        self.after_idle(self._focus_initial_field)

    def _close_dialog(self):
        self.destroy()

    def _on_window_configure(self, _event=None):
        try:
            state = str(self.state()).lower()
            geom = self.geometry()
        except tk.TclError:
            return
        if state == "zoomed":
            return
        if geom and "x" in geom:
            self._last_normal_geometry = geom

    def _restore_window_placement(self):
        sw = int(SCREEN_FIT_W or SCREEN_W or self.winfo_screenwidth() or 0)
        sh = int(SCREEN_FIT_H or SCREEN_H or self.winfo_screenheight() or 0)
        is_dense = bool(globals().get("UI_DENSE_MODE")) or sw <= 1440 or sh <= 860
        is_short_screen = sh <= 768

        if is_dense:
            default_size = self._DENSE_DEFAULT_DIALOG_SIZE
            min_size = self._DENSE_MIN_DIALOG_SIZE
            default_pad = 12
            min_pad = 20
        else:
            default_size = self._STD_DEFAULT_DIALOG_SIZE
            min_size = self._STD_MIN_DIALOG_SIZE
            default_pad = 28
            min_pad = 40

        default_w, default_h = _screen_fit(*default_size, pad=default_pad)
        self._min_dialog_w, self._min_dialog_h = _screen_fit(*min_size, pad=min_pad)
        self.minsize(self._min_dialog_w, self._min_dialog_h)
        self.geometry(f"{default_w}x{default_h}")

        raw = db.get_app_preference(self._GEOMETRY_PREF_KEY, "")
        if raw:
            try:
                saved = json.loads(raw)
            except Exception:
                saved = None

            if isinstance(saved, dict):
                geom = str(saved.get("geometry") or "").strip()
                if geom and "x" in geom:
                    try:
                        self.geometry(geom)
                        self._last_normal_geometry = geom
                    except tk.TclError:
                        pass

        self._enforce_size_floor()

        # Always reopen in normal mode at the last user-set size/position.
        # This avoids laptop snap-back behavior when Windows reports stale zoom states.
        try:
            self.state("normal")
        except tk.TclError:
            pass

        self._enforce_size_floor()

        if is_short_screen or (self._is_edit and is_dense):
            try:
                self.state("zoomed")
            except tk.TclError:
                pass

    def _enforce_size_floor(self):
        try:
            self.update_idletasks()
            cur_w = int(self.winfo_width())
            cur_h = int(self.winfo_height())
            cur_x = int(self.winfo_x())
            cur_y = int(self.winfo_y())
        except tk.TclError:
            return

        target_w = max(cur_w, int(self._min_dialog_w))
        target_h = max(cur_h, int(self._min_dialog_h))
        if target_w == cur_w and target_h == cur_h:
            return

        try:
            self.geometry(f"{target_w}x{target_h}+{cur_x}+{cur_y}")
            self._last_normal_geometry = self.geometry()
        except tk.TclError:
            try:
                self.geometry(f"{target_w}x{target_h}")
                self._last_normal_geometry = self.geometry()
            except tk.TclError:
                pass

    def _save_window_placement(self):
        try:
            state = self.state()
        except tk.TclError:
            state = "normal"

        state_norm = str(state).lower()
        try:
            current_geom = self.geometry()
        except tk.TclError:
            current_geom = ""

        normal_geom = self._last_normal_geometry or current_geom
        if state_norm != "zoomed" and current_geom and "x" in current_geom:
            normal_geom = current_geom

        payload = {
            "state": "normal",
            "geometry": normal_geom,
        }
        try:
            db.set_app_preference(self._GEOMETRY_PREF_KEY, json.dumps(payload))
        except Exception:
            pass

    def destroy(self):
        self._save_window_placement()
        super().destroy()

    def _mkvar(self, key: str) -> tk.StringVar:
        v = tk.StringVar()
        self._vars[key] = v
        return v

    def _money_entry(self, parent, key: str, row: int, col: int, label: str):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="e", padx=(6, 2), pady=2)
        e = ttk.Entry(parent, textvariable=self._mkvar(key), width=10)
        e.grid(row=row, column=col + 1, sticky="ew", padx=(0, 6), pady=2)

    def _bind_quick_workflow(self, widget, callback=None):
        def _handler(_event=None):
            if callback:
                callback()
            else:
                widget.tk_focusNext().focus_set()
            return "break"

        widget.bind("<Return>", _handler)
        widget.bind("<KP_Enter>", _handler)

    def _focus_initial_field(self):
        target = self._payee_entry if not self._is_edit else self._quick_amt_entry
        target.focus_set()
        if isinstance(target, ttk.Entry):
            target.selection_range(0, "end")

    def _submit_from_keyboard(self):
        self._save(keep_open=not self._is_edit)

    def _on_quick_kind_changed(self):
        labels = [lbl for _, lbl in (_BK_INC_COLS if self._quick_kind_var.get() == "Income" else _BK_EXP_COLS)]
        self._quick_cat_cb.configure(values=labels)
        if self._quick_cat_var.get() not in labels:
            self._quick_cat_var.set(labels[0] if labels else "")

    def _set_detail_visibility(self):
        if self._quick_mode_var.get():
            self._detail_wrap.pack_forget()
        else:
            self._detail_wrap.pack(fill="x", pady=(4, 0))

    def _build(self):
        pad = ttk.Frame(self, padding=12)
        pad.pack(fill="both", expand=True)

        # ── Core details ──
        top = lframe(pad, "Entry Details")
        top.pack(fill="x", pady=(0, 8))
        top.columnconfigure(1, weight=1)
        top.columnconfigure(3, weight=2)

        ttk.Label(top, text="Date *").grid(row=0, column=0, sticky="e", padx=(4, 2), pady=3)
        self._date_entry = ttk.Entry(top, textvariable=self._mkvar("entry_date"), width=14)
        self._date_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=3)

        ttk.Label(top, text="Check #").grid(row=0, column=2, sticky="e", padx=(4, 2), pady=3)
        self._check_entry = ttk.Entry(top, textvariable=self._mkvar("check_number"), width=12)
        self._check_entry.grid(row=0, column=3, sticky="ew", padx=(0, 8), pady=3)

        ttk.Label(top, text="Payee / Description").grid(row=1, column=0, sticky="e", padx=(4, 2), pady=3)
        self._payee_entry = ttk.Entry(top, textvariable=self._mkvar("payee"), width=26)
        self._payee_entry.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=3)

        ttk.Label(top, text="Memo").grid(row=2, column=0, sticky="e", padx=(4, 2), pady=3)
        self._memo_entry = ttk.Entry(top, textvariable=self._mkvar("memo"), width=34)
        self._memo_entry.grid(row=2, column=1, columnspan=3, sticky="ew", padx=(0, 8), pady=3)

        # ── Quick entry (default) ──
        quick = lframe(pad, "Quick Entry")
        quick.pack(fill="x", pady=(0, 8))
        quick.columnconfigure(4, weight=1)
        quick.columnconfigure(6, weight=1)
        quick.columnconfigure(7, weight=1)

        ttk.Label(quick, text="Type").grid(row=0, column=0, sticky="e", padx=(6, 2), pady=4)
        ttk.Radiobutton(
            quick, text="Expense", variable=self._quick_kind_var, value="Expense",
            command=self._on_quick_kind_changed
        ).grid(row=0, column=1, sticky="w", padx=(0, 8), pady=4)
        ttk.Radiobutton(
            quick, text="Income", variable=self._quick_kind_var, value="Income",
            command=self._on_quick_kind_changed
        ).grid(row=0, column=2, sticky="w", padx=(0, 12), pady=4)

        ttk.Label(quick, text="Category").grid(row=0, column=3, sticky="e", padx=(6, 2), pady=4)
        self._quick_cat_cb = ttk.Combobox(
            quick, textvariable=self._quick_cat_var, width=18, state="readonly"
        )
        self._quick_cat_cb.grid(row=0, column=4, sticky="ew", padx=(0, 12), pady=4)

        ttk.Label(quick, text="Amount").grid(row=0, column=5, sticky="e", padx=(6, 2), pady=4)
        self._quick_amt_entry = ttk.Entry(quick, textvariable=self._quick_amt_var, width=12)
        self._quick_amt_entry.grid(row=0, column=6, sticky="ew", padx=(0, 12), pady=4)

        ttk.Checkbutton(quick, text="Tax Deductible", variable=self._tax_var).grid(
            row=1, column=0, columnspan=3, sticky="w", padx=6, pady=3
        )
        ttk.Checkbutton(
            quick,
            text="Show detailed amount fields",
            variable=self._quick_mode_var,
            onvalue=False,
            offvalue=True,
            command=self._set_detail_visibility,
        ).grid(row=1, column=3, columnspan=4, sticky="w", padx=6, pady=3)

        # ── Detailed fields (optional) ──
        self._detail_wrap = ttk.Frame(pad)

        inc = lframe(self._detail_wrap, "Money In (Income)")
        inc.pack(fill="x", pady=(0, 8))
        for i in range(len(_BK_INC_COLS)):
            inc.columnconfigure((i * 2) + 1, weight=1)
        for i, (key, label) in enumerate(_BK_INC_COLS):
            self._money_entry(inc, key, 0, i * 2, label)

        exp = lframe(self._detail_wrap, "Money Out (Expenses)")
        exp.pack(fill="x", pady=(0, 8))
        for i in range(4):
            exp.columnconfigure((i * 2) + 1, weight=1)
        for i, (key, label) in enumerate(_BK_EXP_COLS):
            r, c = divmod(i, 4)
            self._money_entry(exp, key, r, c * 2, label)

        # ── Buttons ──
        bf = ttk.Frame(pad)
        bf.pack(fill="x", pady=(4, 0))
        if not self._is_edit:
            self._save_new_btn = btn(bf, "Save + New", lambda: self._save(keep_open=True))
            self._save_new_btn.pack(side="right", padx=4)
        else:
            self._save_new_btn = None
        self._save_btn = btn(bf, "Save", self._save, "Accent.TButton")
        self._save_btn.pack(side="right", padx=4)
        btn(bf, "Cancel", self.destroy).pack(side="right")

        self._bind_quick_workflow(self._date_entry)
        self._bind_quick_workflow(self._check_entry)
        self._bind_quick_workflow(self._payee_entry)
        self._bind_quick_workflow(self._memo_entry)
        self._bind_quick_workflow(self._quick_cat_cb)
        self._bind_quick_workflow(self._quick_amt_entry, self._submit_from_keyboard)
        self.bind("<Escape>", lambda _event=None: self.destroy())

    def _load(self):
        for key, var in self._vars.items():
            raw = self._entry.get(key, "")
            if key == "entry_date" and not raw:
                raw = current_date_str()
            var.set(str(raw) if raw not in (None, 0, 0.0, "") else
                    ("" if key in ("entry_date", "check_number", "payee", "memo") else ""))

        # Format money fields
        for key, _ in _BK_INC_COLS + _BK_EXP_COLS:
            v = self._entry.get(key, 0.0)
            self._vars[key].set("" if not v else f"{float(v):.2f}")

        # Infer quick-entry values from existing data
        non_zero = []
        for key, label in _BK_INC_COLS + _BK_EXP_COLS:
            amt = float(self._entry.get(key, 0) or 0)
            if amt:
                non_zero.append((key, label, amt))

        if len(non_zero) == 1:
            key, label, amt = non_zero[0]
            self._quick_kind_var.set("Income" if key in dict(_BK_INC_COLS) else "Expense")
            self._on_quick_kind_changed()
            self._quick_cat_var.set(label)
            self._quick_amt_var.set(f"{amt:.2f}")
            self._quick_mode_var.set(True)
        elif len(non_zero) == 0:
            self._quick_kind_var.set("Expense")
            self._on_quick_kind_changed()
            self._quick_amt_var.set("")
            self._quick_mode_var.set(True)
        else:
            self._quick_kind_var.set("Expense")
            self._on_quick_kind_changed()
            self._quick_mode_var.set(False)

        # Apply workflow preset only for brand-new entries.
        if not self._is_edit:
            preset_date = str(self._preset.get("entry_date") or "").strip()
            if preset_date:
                self._vars["entry_date"].set(preset_date)

            preset_kind = str(self._preset.get("quick_kind") or "").strip()
            if preset_kind in ("Expense", "Income"):
                self._quick_kind_var.set(preset_kind)
                self._on_quick_kind_changed()

            preset_cat = str(self._preset.get("quick_category") or "").strip()
            if preset_cat:
                values = set(self._quick_cat_cb.cget("values"))
                if preset_cat in values:
                    self._quick_cat_var.set(preset_cat)

        self._set_detail_visibility()

    def _reset_for_next_entry(self):
        self._vars["check_number"].set("")
        self._vars["payee"].set("")
        self._vars["memo"].set("")
        self._quick_amt_var.set("")
        for key, _ in _BK_INC_COLS + _BK_EXP_COLS:
            self._vars[key].set("")

    def _save(self, keep_open=False):
        date_str = self._vars["entry_date"].get().strip()
        if not date_str:
            messagebox.showerror("Required", "Date is required.", parent=self)
            return
        # Normalise date
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
            try:
                date_str = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue
        else:
            messagebox.showerror("Invalid Date", "Enter date as YYYY-MM-DD or MM/DD/YYYY.", parent=self)
            return

        def _money(key):
            try:
                return round(float(self._vars[key].get() or 0), 2)
            except ValueError:
                return 0.0

        data = {
            "entry_date":       date_str,
            "check_number":     self._vars["check_number"].get().strip(),
            "payee":            self._vars["payee"].get().strip(),
            "memo":             self._vars["memo"].get().strip(),
            "is_tax_deductible": int(self._tax_var.get()),
        }

        for key, _ in _BK_INC_COLS + _BK_EXP_COLS:
            data[key] = 0.0

        if self._quick_mode_var.get():
            cat_label = self._quick_cat_var.get().strip()
            amt_text = self._quick_amt_var.get().strip()

            if not cat_label:
                messagebox.showerror("Required", "Choose a category.", parent=self)
                return

            try:
                amount = round(float(amt_text or 0), 2)
            except ValueError:
                messagebox.showerror("Invalid", "Amount must be a number.", parent=self)
                return

            if amount <= 0:
                messagebox.showerror("Required", "Enter an amount greater than zero.", parent=self)
                return

            cmap = self._inc_map if self._quick_kind_var.get() == "Income" else self._exp_map
            cat_key = cmap.get(cat_label)
            if not cat_key:
                messagebox.showerror("Invalid", "Please choose a valid category.", parent=self)
                return

            data[cat_key] = amount
        else:
            for key, _ in _BK_INC_COLS + _BK_EXP_COLS:
                data[key] = _money(key)

        if "id" in self._entry:
            data["id"] = self._entry["id"]

        db.save_bookkeeping_entry(data)
        if self.on_save:
            self.on_save()

        if keep_open and not self._is_edit:
            self._reset_for_next_entry()
            self.after_idle(self._focus_initial_field)
            return

        self.destroy()



# ─── Appointment Book ──────────────────────────────────────────────────────────

APPT_STATUSES = ["Scheduled", "Completed", "No-Show", "Cancelled", "Rescheduled"]
APPT_TIMES = [
    f"{h:02d}:{m:02d} {'AM' if h < 12 else 'PM'}"
    for h in list(range(6, 12)) + list(range(12, 21))
    for m in (0, 15, 30, 45)
]


def _fmt_appt_time(t):
    """Convert HH:MM to 12-hour display, pass through anything else."""
    if not t:
        return ""
    import datetime as _dt
    for fmt in ("%H:%M %p", "%H:%M", "%I:%M %p"):
        try:
            return _dt.datetime.strptime(t.strip(), fmt).strftime("%I:%M %p").lstrip("0")
        except ValueError:
            pass
    return t


class AppointmentDialog(tk.Toplevel):
    """Add / Edit appointment dialog."""

    def __init__(self, parent, appt_id=None, prefill_date=None, on_save=None):
        super().__init__(parent)
        apply_window_icon(self)
        self.title("New Appointment" if appt_id is None else "Edit Appointment")
        self.resizable(True, True)
        # Avoid hard modal grab so Windows minimize works reliably.
        self._appt_id = appt_id
        self._on_save = on_save
        self._pts = db.get_all_patients("Active")
        self._build(prefill_date)
        if appt_id:
            self._load(appt_id)
        self.after(50, self._maximize_or_center)

    def _maximize_or_center(self):
        self.update_idletasks()
        try:
            self.state("zoomed")
            return
        except tk.TclError:
            pass
        self._center()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = self.master.winfo_rootx() + (self.master.winfo_width() - w) // 2
        y = self.master.winfo_rooty() + (self.master.winfo_height() - h) // 2
        self.geometry(f"+{x}+{y}")

    def _build(self, prefill_date):
        f = ttk.Frame(self, padding=14)
        f.pack(fill="both", expand=True)

        ttk.Label(f, text="Patient: *").grid(row=0, column=0, sticky="e", padx=(0, 6), pady=4)
        self._pt_sv = tk.StringVar()
        names = ["— Select Patient —"] + [f"{p['last_name']}, {p['first_name']}" for p in self._pts]
        self._pt_cb = ttk.Combobox(f, textvariable=self._pt_sv, values=names, state="readonly", width=34)
        self._pt_cb.set("— Select Patient —")
        self._pt_cb.grid(row=0, column=1, columnspan=3, sticky="w", pady=4)

        ttk.Label(f, text="Date: *").grid(row=1, column=0, sticky="e", padx=(0, 6), pady=4)
        self._date_sv = tk.StringVar(value=prefill_date or date.today().strftime("%m/%d/%Y"))
        if _HAS_CALENDAR:
            self._date_entry = _DateEntry(
                f,
                textvariable=self._date_sv,
                date_pattern="MM/dd/yyyy",
                width=12,
                background="#2b579a",
                foreground="white",
                borderwidth=2,
            )
            self._date_entry.grid(row=1, column=1, sticky="w", pady=4)
        else:
            ttk.Entry(f, textvariable=self._date_sv, width=14).grid(row=1, column=1, sticky="w", pady=4)
            ttk.Label(f, text="(MM/DD/YYYY)", foreground=MUTED).grid(row=1, column=2, sticky="w")

        ttk.Label(f, text="Time:").grid(row=2, column=0, sticky="e", padx=(0, 6), pady=4)
        self._time_sv = tk.StringVar(value="09:00 AM")
        ttk.Combobox(f, textvariable=self._time_sv, values=APPT_TIMES, width=12).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(f, text="Duration (min):").grid(row=2, column=2, sticky="e", padx=(10, 6), pady=4)
        self._dur_sv = tk.StringVar(value="50")
        ttk.Combobox(f, textvariable=self._dur_sv,
                     values=["15", "20", "30", "45", "50", "53", "60", "75", "90", "120"],
                     width=6, state="readonly").grid(row=2, column=3, sticky="w", pady=4)

        ttk.Label(f, text="Type:").grid(row=3, column=0, sticky="e", padx=(0, 6), pady=4)
        self._type_sv = tk.StringVar(value="Individual")
        ttk.Combobox(f, textvariable=self._type_sv, values=SESSION_TYPES,
                     state="readonly", width=22).grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(f, text="Status:").grid(row=3, column=2, sticky="e", padx=(10, 6), pady=4)
        self._status_sv = tk.StringVar(value="Scheduled")
        ttk.Combobox(f, textvariable=self._status_sv, values=APPT_STATUSES,
                     state="readonly", width=14).grid(row=3, column=3, sticky="w", pady=4)

        ttk.Label(f, text="Notes:").grid(row=4, column=0, sticky="ne", padx=(0, 6), pady=4)
        self._notes_txt = tk.Text(f, width=46, height=4, font=FONT_UI, wrap="word")
        self._notes_txt.grid(row=4, column=1, columnspan=3, sticky="ew", pady=4)

        bf = ttk.Frame(f)
        bf.grid(row=5, column=0, columnspan=4, pady=(10, 0))
        btn(bf, "Save", self._save, "Accent.TButton").pack(side="left", padx=6)
        btn(bf, "Cancel", self.destroy).pack(side="left", padx=6)

    def _load(self, appt_id):
        a = db.get_appointment(appt_id)
        if not a:
            return
        pt = db.get_patient(a["patient_id"])
        if pt:
            self._pt_sv.set(f"{pt['last_name']}, {pt['first_name']}")
        raw = str(a["appt_date"] or "")
        if raw:
            import datetime as _dt
            for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
                try:
                    raw = _dt.datetime.strptime(raw, fmt).strftime("%m/%d/%Y")
                    break
                except ValueError:
                    pass
        self._date_sv.set(raw)
        self._time_sv.set(a["appt_time"] or "")
        self._dur_sv.set(str(a["duration"] or 50))
        self._type_sv.set(a["session_type"] or "Individual")
        self._status_sv.set(a["status"] or "Scheduled")
        self._notes_txt.delete("1.0", "end")
        self._notes_txt.insert("1.0", a["notes"] or "")

    def _save(self):
        pt_name = self._pt_sv.get()
        if pt_name == "— Select Patient —":
            messagebox.showerror("Required", "Please select a patient.", parent=self)
            return
        match = next((p for p in self._pts if f"{p['last_name']}, {p['first_name']}" == pt_name), None)
        if not match:
            messagebox.showerror("Error", "Patient not found.", parent=self)
            return
        raw_date = self._date_sv.get().strip()
        if not raw_date:
            messagebox.showerror("Required", "Date is required.", parent=self)
            return
        import datetime as _dt
        iso_date = ""
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                iso_date = _dt.datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                pass
        if not iso_date:
            messagebox.showerror("Invalid Date", "Enter date as MM/DD/YYYY.", parent=self)
            return
        try:
            dur = int(self._dur_sv.get() or 50)
        except ValueError:
            dur = 50
        data = {
            "patient_id": match["id"],
            "appt_date": iso_date,
            "appt_time": self._time_sv.get().strip(),
            "duration": dur,
            "session_type": self._type_sv.get(),
            "status": self._status_sv.get(),
            "notes": self._notes_txt.get("1.0", "end-1c").strip(),
        }
        if self._appt_id:
            data["id"] = self._appt_id
        db.save_appointment(data)
        if self._on_save:
            self._on_save()
        self.destroy()


class AppointmentBookTab(ttk.Frame):
    """Day-view appointment book with upcoming appointments list."""

    _STATUS_COLORS = {
        "Scheduled":   "#2563eb",
        "Completed":   "#16a34a",
        "No-Show":     "#dc2626",
        "Cancelled":   "#6b7280",
        "Rescheduled": "#d97706",
    }

    def __init__(self, parent):
        super().__init__(parent)
        self._view_sv = tk.StringVar(value="Day")
        self._sel_date = date.today()
        self._build()
        self.refresh()

    def _build(self):
        tb = ttk.Frame(self, padding=(8, 6))
        tb.pack(fill="x")
        btn(tb, "+ New Appointment", self._new_appt, "Accent.TButton").pack(side="left", padx=4)
        btn(tb, "Edit", self._edit_appt).pack(side="left", padx=2)
        btn(tb, "Delete", self._delete_appt, "Danger.TButton").pack(side="left", padx=2)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=8)
        btn(tb, "Mark Complete", lambda: self._set_status("Completed")).pack(side="left", padx=2)
        btn(tb, "Mark No-Show", lambda: self._set_status("No-Show")).pack(side="left", padx=2)
        btn(tb, "Mark Cancelled", lambda: self._set_status("Cancelled")).pack(side="left", padx=2)
        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Label(tb, text="View:").pack(side="left")
        ttk.Combobox(tb, textvariable=self._view_sv,
                     values=["Day", "Next 7 Days", "Upcoming (30 days)"],
                     state="readonly", width=16).pack(side="left", padx=3)
        self._view_sv.trace_add("write", lambda *a: self.refresh())

        nav = ttk.Frame(self, padding=(8, 2))
        nav.pack(fill="x")
        btn(nav, "< Prev", self._prev_day).pack(side="left")
        btn(nav, "Today", self._go_today).pack(side="left", padx=4)
        btn(nav, "Next >", self._next_day).pack(side="left")
        self._date_sv = tk.StringVar(value=self._sel_date.strftime("%m/%d/%Y"))
        ttk.Entry(nav, textvariable=self._date_sv, width=12).pack(side="left", padx=(10, 2))
        ttk.Label(nav, text="(MM/DD/YYYY)", foreground=MUTED).pack(side="left")
        btn(nav, "Go", self._go_date).pack(side="left", padx=6)
        self._day_lbl = ttk.Label(nav, text="", foreground=ACCENT, font=FONT_LG)
        self._day_lbl.pack(side="left", padx=12)
        self._count_lbl = ttk.Label(nav, text="", foreground=MUTED)
        self._count_lbl.pack(side="right", padx=8)

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        cols = ("id", "date", "time", "patient", "type", "duration", "status", "phone", "notes")
        self.tv = ttk.Treeview(frm, columns=cols, show="headings", selectmode="browse")
        hdrs = [("ID", 48), ("Date", 96), ("Time", 84), ("Patient", 210),
            ("Type", 126), ("Min", 56), ("Status", 110), ("Phone", 126), ("Notes", 260)]
        for (h, w), c in zip(hdrs, cols):
            self.tv.heading(c, text=h, anchor="w")
            self.tv.column(c, width=_sc(w), stretch=(c == "notes"))
        vsb = ttk.Scrollbar(frm, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vsb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tv.tag_configure("even", background=ROW_EVEN)
        for status, color in self._STATUS_COLORS.items():
            tag = "st_" + status.lower().replace("-", "_")
            self.tv.tag_configure(tag, foreground=color)
        self.tv.bind("<Double-1>", lambda e: self._edit_appt())

    def _prev_day(self):
        from datetime import timedelta
        self._sel_date -= timedelta(days=1)
        self._date_sv.set(self._sel_date.strftime("%m/%d/%Y"))
        self._view_sv.set("Day")
        self.refresh()

    def _next_day(self):
        from datetime import timedelta
        self._sel_date += timedelta(days=1)
        self._date_sv.set(self._sel_date.strftime("%m/%d/%Y"))
        self._view_sv.set("Day")
        self.refresh()

    def _go_today(self):
        self._sel_date = date.today()
        self._date_sv.set(self._sel_date.strftime("%m/%d/%Y"))
        self._view_sv.set("Day")
        self.refresh()

    def _go_date(self):
        raw = self._date_sv.get().strip()
        import datetime as _dt
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                self._sel_date = _dt.datetime.strptime(raw, fmt).date()
                self._date_sv.set(self._sel_date.strftime("%m/%d/%Y"))
                self._view_sv.set("Day")
                self.refresh()
                return
            except ValueError:
                pass
        messagebox.showerror("Invalid Date", "Enter date as MM/DD/YYYY.", parent=self)

    def refresh(self):
        self.tv.delete(*self.tv.get_children())
        view = self._view_sv.get()
        if view == "Day":
            iso = self._sel_date.isoformat()
            rows = db.get_appointments_for_date(iso)
            self._day_lbl.config(text=self._sel_date.strftime("%A, %B %d, %Y"))
        elif view == "Next 7 Days":
            rows = db.get_upcoming_appointments(7)
            self._day_lbl.config(text="Next 7 Days")
        else:
            rows = db.get_upcoming_appointments(30)
            self._day_lbl.config(text="Next 30 Days")
        for i, r in enumerate(rows):
            patient = f"{r['last_name']}, {r['first_name']}"
            phone = r["phone_cell"] or r["phone_home"] or ""
            display_date = fmt_date(r["appt_date"])
            time_str = _fmt_appt_time(r["appt_time"])
            status = r["status"] or "Scheduled"
            tag_st = "st_" + status.lower().replace("-", "_")
            tags = ("even", tag_st) if i % 2 == 0 else (tag_st,)
            self.tv.insert("", "end", iid=str(r["id"]), tags=tags,
                           values=(r["id"], display_date, time_str, patient,
                                   r["session_type"], r["duration"],
                                   status, phone, r["notes"] or ""))
        count = len(rows)
        self._count_lbl.config(text=f"{count} appointment{'s' if count != 1 else ''}")

    def _selected_id(self):
        sel = self.tv.selection()
        return int(sel[0]) if sel else None

    def _new_appt(self):
        AppointmentDialog(self, prefill_date=self._sel_date.strftime("%m/%d/%Y"),
                          on_save=self.refresh)

    def _edit_appt(self):
        aid = self._selected_id()
        if not aid:
            messagebox.showinfo("Select Appointment", "Select an appointment to edit.", parent=self)
            return
        AppointmentDialog(self, appt_id=aid, on_save=self.refresh)

    def _delete_appt(self):
        aid = self._selected_id()
        if not aid:
            messagebox.showinfo("Select Appointment", "Select an appointment to delete.", parent=self)
            return
        row = self.tv.item(str(aid))["values"]
        patient = row[3] if len(row) > 3 else "this appointment"
        if messagebox.askyesno("Delete Appointment",
                               f"Delete appointment for {patient}?", parent=self):
            db.delete_appointment(aid)
            self.refresh()

    def _set_status(self, new_status):
        aid = self._selected_id()
        if not aid:
            messagebox.showinfo("Select Appointment", "Select an appointment first.", parent=self)
            return
        a = db.get_appointment(aid)
        if not a:
            return
        data = {k: a[k] for k in a.keys()}
        data["id"] = aid
        data["status"] = new_status
        db.save_appointment(data)
        self.refresh()

class BookkeepingTab(ttk.Frame):
    """Dome-style simplified bookkeeping ledger."""

    _ROW_ODD = "#f0fff4"
    _ROW_EVEN = "#dcfce7"
    _MONTH_HDR_BG = "#1e3a5f"
    _MONTH_HDR_FG = "#ffffff"
    _MONTH_TOT_BG = "#bfdbfe"
    _MONTH_TOT_FG = "#1e3a5f"
    _YEAR_TOT_BG = "#1e40af"
    _YEAR_TOT_FG = "#ffffff"
    _OPN_BAL_BG = "#fef9c3"
    _INC_BAND = "#86efac"
    _EXP_BAND = "#fca5a5"

    def __init__(self, parent):
        super().__init__(parent)
        today = date.today()
        self._year_var = tk.StringVar(value=str(today.year))
        self._month_var = tk.StringVar(value="All")
        self._build()
        self.refresh()

    def _build(self):
        tb = ttk.Frame(self, padding=(8, 6))
        tb.pack(fill="x")
        # Always use two rows — bookkeeping has too many controls for one row
        row1 = ttk.Frame(tb)
        row1.pack(fill="x", pady=(0, 4))
        row2 = ttk.Frame(tb)
        row2.pack(fill="x")

        btn(row1, "+ New Expense", self._new_expense, "Accent.TButton").pack(side="left", padx=(4, 4))
        btn(row1, "+ New Income", self._new_income, "Accent.TButton").pack(side="left", padx=(4, 4))
        btn(row1, "+ New Entry", self._new_entry).pack(side="left", padx=(4, 4))
        btn(row1, "Edit", self._edit_entry).pack(side="left", padx=(4, 4))
        btn(row1, "Delete", self._delete_entry, "Danger.TButton").pack(side="left", padx=(4, 4))
        ttk.Separator(row1, orient="vertical").pack(side="left", fill="y", padx=8)
        btn(row1, "Opening Balance", self._set_opening_balance).pack(side="left", padx=(4, 4))

        btn(row2, "Monthly Summary", self._monthly_summary).pack(side="left", padx=(4, 4))
        btn(row2, "Annual Summary", self._annual_summary).pack(side="left", padx=(4, 4))
        btn(row2, "Import (Any File)", self._import_any_file, "Accent.TButton").pack(side="left", padx=(4, 4))
        btn(row2, "Export CSV", self._export_csv).pack(side="left", padx=(4, 4))
        ttk.Separator(row2, orient="vertical").pack(side="left", fill="y", padx=8)

        ttk.Label(row2, text="Year:").pack(side="left")
        years = [str(y) for y in range(date.today().year + 1, 2019, -1)]
        ttk.Combobox(row2, textvariable=self._year_var, values=years, width=6, state="readonly").pack(side="left", padx=3)
        self._year_var.trace_add("write", lambda *a: self.refresh())

        ttk.Label(row2, text="Month:").pack(side="left", padx=(8, 0))
        ttk.Combobox(row2, textvariable=self._month_var, values=_BK_MONTHS, width=11, state="readonly").pack(side="left", padx=3)
        self._month_var.trace_add("write", lambda *a: self.refresh())

        self._lbl_count = ttk.Label(row2, text="", foreground=MUTED)
        self._lbl_count.pack(side="right", padx=8)

        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        self._grp_canvas = tk.Canvas(outer, height=22, bg=BG, highlightthickness=0)
        self._grp_canvas.grid(row=0, column=0, sticky="ew")

        frm = ttk.Frame(outer)
        frm.grid(row=1, column=0, sticky="nsew")
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(0, weight=1)

        self._cols = (
            ["date", "ck", "payee", "memo", "tax"] +
            [k for k, _ in _BK_INC_COLS] +
            [k for k, _ in _BK_EXP_COLS] +
            ["balance"]
        )
        self.tv = ttk.Treeview(frm, columns=self._cols, show="headings", selectmode="browse")

        col_defs = (
            [("Date", 90, "w"), ("Ck #", 64, "w"), ("Payee / Description", 240, "w"),
             ("Memo", 176, "w"), ("Tax", 56, "center")] +
            [(lbl, 98, "e") for _, lbl in _BK_INC_COLS] +
            [(lbl, 92, "e") for _, lbl in _BK_EXP_COLS] +
            [("Balance", 108, "e")]
        )
        for (hdr, w, anc), col in zip(col_defs, self._cols):
            # Payee stretches to fill spare space; all other columns are fixed.
            _stretch = (col == "payee")
            self.tv.heading(col, text=hdr, anchor="w")
            self.tv.column(col, width=_sc(w), minwidth=max(50, int(_sc(w) * 0.75)), stretch=_stretch, anchor=anc)

        vsb = ttk.Scrollbar(frm, orient="vertical", command=self.tv.yview)
        self._hsb = ttk.Scrollbar(frm, orient="horizontal", command=self._on_xscroll)
        self.tv.configure(yscrollcommand=vsb.set, xscrollcommand=self._on_tv_xview)
        self.tv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self._hsb.grid(row=1, column=0, sticky="ew")

        self.tv.bind("<Double-1>", lambda e: self._edit_entry())
        self.tv.bind("<Configure>", lambda e: self._redraw_group_header())
        self._grp_canvas.bind("<Configure>", lambda e: self._redraw_group_header())

        self.tv.tag_configure("odd", background=self._ROW_ODD, foreground="#1a1a1a")
        self.tv.tag_configure("even", background=self._ROW_EVEN, foreground="#1a1a1a")
        _tag_fs = max(10, int(FONT_UI[1]))
        self.tv.tag_configure("month_hdr", background=self._MONTH_HDR_BG, foreground=self._MONTH_HDR_FG, font=("Arial", _tag_fs, "bold"))
        self.tv.tag_configure("month_tot", background=self._MONTH_TOT_BG, foreground=self._MONTH_TOT_FG, font=("Arial", _tag_fs, "bold"))
        self.tv.tag_configure("year_tot", background=self._YEAR_TOT_BG, foreground=self._YEAR_TOT_FG, font=("Arial", _tag_fs, "bold"))
        self.tv.tag_configure("opn_bal", background=self._OPN_BAL_BG, foreground="#78350f", font=("Arial", _tag_fs, "italic"))
        self.tv.tag_configure("neg_bal", foreground="#dc2626")

        sb = ttk.Frame(self, padding=(8, 3))
        sb.pack(fill="x", side="bottom")
        self._lbl_workflow = ttk.Label(
            sb,
            text="Workflow: 1) Set Year/Month  2) New Expense/Income  3) Save + New for batch entry  4) Review totals",
            foreground=MUTED,
            font=FONT_SM,
        )
        self._lbl_workflow.pack(side="left")
        self._lbl_totals = ttk.Label(sb, text="", foreground=MUTED, font=FONT_SM)
        self._lbl_totals.pack(side="right")

    def _on_xscroll(self, *args):
        self.tv.xview(*args)
        self._redraw_group_header()

    def _on_tv_xview(self, *args):
        self._hsb.set(*args)
        self._redraw_group_header()

    def _redraw_group_header(self):
        c = self._grp_canvas
        c.delete("all")
        cw = c.winfo_width()
        if cw <= 1:
            return

        x = 0
        col_x = {}
        for col in self._cols:
            col_x[col] = x
            x += self.tv.column(col, "width")

        total_w = x
        if total_w == 0:
            return

        x0_frac, _ = self.tv.xview()
        x_off = int(x0_frac * total_w)

        def _band(start_col, end_col, color, label, fg):
            xs = col_x[start_col] - x_off
            xe = col_x[end_col] + self.tv.column(end_col, "width") - x_off
            xs, xe = max(0, xs), min(cw, xe)
            if xe <= xs:
                return
            c.create_rectangle(xs, 1, xe, 21, fill=color, outline="#aaa")
            c.create_text((xs + xe) / 2, 11, text=label, font=("Arial", 8 if UI_DENSE_MODE else 9, "bold"), fill=fg)

        _band(_BK_INC_COLS[0][0], _BK_INC_COLS[-1][0], self._INC_BAND, "INCOME", "#14532d")
        _band(_BK_EXP_COLS[0][0], _BK_EXP_COLS[-1][0], self._EXP_BAND, "EXPENSES", "#7f1d1d")

    def refresh(self):
        self.tv.delete(*self.tv.get_children())
        year = int(self._year_var.get())
        month_idx = _BK_MONTHS.index(self._month_var.get())

        all_rows = db.get_bookkeeping_entries(year, 0)
        opening = db.get_bookkeeping_opening_balance(year)
        balance = opening

        from collections import defaultdict
        monthly = defaultdict(list)
        for r in all_rows:
            try:
                m = int(r["entry_date"][5:7])
            except (IndexError, ValueError):
                m = 0
            monthly[m].append(r)

        if month_idx:
            for m in sorted(monthly.keys()):
                if m < month_idx:
                    for r in monthly[m]:
                        balance += sum(float(r[k] or 0) for k, _ in _BK_INC_COLS)
                        balance -= sum(float(r[k] or 0) for k, _ in _BK_EXP_COLS)
            months_to_show = [month_idx] if month_idx in monthly else []
        else:
            months_to_show = sorted(monthly.keys())

        def _m(v):
            f = float(v or 0)
            return f"${f:,.2f}" if f else ""

        def _empty():
            return [""] * len(self._cols)

        if not month_idx:
            ov = _empty()
            ov[2] = "Opening Balance"
            ov[-1] = f"${opening:,.2f}"
            self.tv.insert("", "end", iid="opn_bal", values=ov, tags=("opn_bal",))

        total_in_period = 0.0
        total_out_period = 0.0
        year_inc = {k: 0.0 for k, _ in _BK_INC_COLS}
        year_exp = {k: 0.0 for k, _ in _BK_EXP_COLS}
        entry_count = 0
        row_idx = 0

        for m in months_to_show:
            rows = monthly[m]
            month_name = _BK_MONTHS[m] if m < len(_BK_MONTHS) else f"Month {m}"
            mhv = _empty()
            mhv[2] = f"------ {month_name.upper()} ------"
            self.tv.insert("", "end", iid=f"mhdr_{m}", values=mhv, tags=("month_hdr",))

            month_inc = {k: 0.0 for k, _ in _BK_INC_COLS}
            month_exp = {k: 0.0 for k, _ in _BK_EXP_COLS}

            for r in rows:
                ti = sum(float(r[k] or 0) for k, _ in _BK_INC_COLS)
                to = sum(float(r[k] or 0) for k, _ in _BK_EXP_COLS)
                balance += ti - to

                for k, _ in _BK_INC_COLS:
                    v = float(r[k] or 0)
                    month_inc[k] += v
                    year_inc[k] += v
                for k, _ in _BK_EXP_COLS:
                    v = float(r[k] or 0)
                    month_exp[k] += v
                    year_exp[k] += v

                total_in_period += ti
                total_out_period += to
                entry_count += 1

                tag = "odd" if row_idx % 2 == 0 else "even"
                row_idx += 1
                tax_mark = "X" if r["is_tax_deductible"] else ""
                bal_tag = ("neg_bal",) if balance < 0 else ()

                values = (
                    [fmt_date(r["entry_date"]), r["check_number"] or "", r["payee"] or "", r["memo"] or "", tax_mark] +
                    [_m(r[k]) for k, _ in _BK_INC_COLS] +
                    [_m(r[k]) for k, _ in _BK_EXP_COLS] +
                    [f"${balance:,.2f}"]
                )
                self.tv.insert("", "end", iid=str(r["id"]), values=values, tags=(tag,) + bal_tag)

            mtv = (
                ["", "", f"  {month_name} Totals", "", ""] +
                [_m(month_inc[k]) for k, _ in _BK_INC_COLS] +
                [_m(month_exp[k]) for k, _ in _BK_EXP_COLS] +
                [f"${balance:,.2f}"]
            )
            self.tv.insert("", "end", iid=f"mtot_{m}", values=mtv, tags=("month_tot",))

        if not month_idx and months_to_show:
            ytv = (
                ["", "", f"  {year} ANNUAL TOTAL", "", ""] +
                [_m(year_inc[k]) for k, _ in _BK_INC_COLS] +
                [_m(year_exp[k]) for k, _ in _BK_EXP_COLS] +
                [f"${balance:,.2f}"]
            )
            self.tv.insert("", "end", iid="year_tot", values=ytv, tags=("year_tot",))

        self._lbl_count.config(text=f"{entry_count} entr{'y' if entry_count == 1 else 'ies'}")
        net = total_in_period - total_out_period
        sign = "+" if net >= 0 else ""
        self._lbl_totals.config(
            text=(f"Opening ${opening:,.2f}   |   Income ${total_in_period:,.2f}   |   "
                  f"Expenses ${total_out_period:,.2f}   |   Net {sign}${net:,.2f}   |   "
                  f"Closing Balance ${balance:,.2f}")
        )
        self.after_idle(self._redraw_group_header)

    def _selected_id(self):
        sel = self.tv.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except (ValueError, TypeError):
            return None

    def _default_entry_date_for_filter(self):
        year = int(self._year_var.get())
        month_idx = _BK_MONTHS.index(self._month_var.get())
        if month_idx == 0:
            return current_date_str()
        return f"{year:04d}-{month_idx:02d}-01"

    def _open_new_entry(self, quick_kind=None):
        preset = {"entry_date": self._default_entry_date_for_filter()}
        if quick_kind in ("Expense", "Income"):
            preset["quick_kind"] = quick_kind
            cats = _BK_EXP_COLS if quick_kind == "Expense" else _BK_INC_COLS
            if cats:
                preset["quick_category"] = cats[0][1]
        BookkeepingEntryDialog(self, on_save=self.refresh, preset=preset)

    def _new_entry(self):
        self._open_new_entry()

    def _new_expense(self):
        self._open_new_entry("Expense")

    def _new_income(self):
        self._open_new_entry("Income")

    def _edit_entry(self):
        eid = self._selected_id()
        if not eid:
            messagebox.showinfo("Select Entry", "Please select a transaction row to edit.", parent=self)
            return
        conn = db.get_connection()
        row = conn.execute("SELECT * FROM bookkeeping_entries WHERE id=?", (eid,)).fetchone()
        conn.close()
        if row:
            BookkeepingEntryDialog(self, entry=dict(row), on_save=self.refresh)

    def _delete_entry(self):
        eid = self._selected_id()
        if not eid:
            messagebox.showinfo("Select Entry", "Please select a transaction row to delete.", parent=self)
            return
        if messagebox.askyesno("Confirm Delete", "Delete this entry? This cannot be undone.", parent=self):
            db.delete_bookkeeping_entry(eid)
            self.refresh()

    def _set_opening_balance(self):
        year = int(self._year_var.get())
        current = db.get_bookkeeping_opening_balance(year)
        dlg = tk.Toplevel(self)
        apply_window_icon(dlg)
        dlg.title(f"Opening Balance - {year}")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        ttk.Label(dlg, text=f"Opening Bank Balance for {year}:", padding=(12, 8)).pack(anchor="w")
        var = tk.StringVar(value=f"{current:.2f}")
        ttk.Entry(dlg, textvariable=var, width=18).pack(padx=12, pady=4)

        def _save():
            try:
                val = float(var.get())
            except ValueError:
                messagebox.showerror("Invalid", "Enter a valid dollar amount.", parent=dlg)
                return
            db.save_bookkeeping_opening_balance(year, val)
            dlg.destroy()
            self.refresh()

        bf = ttk.Frame(dlg, padding=(12, 8))
        bf.pack(fill="x")
        btn(bf, "Save", _save, "Accent.TButton").pack(side="right", padx=4)
        btn(bf, "Cancel", dlg.destroy).pack(side="right")

    def _monthly_summary(self):
        year = int(self._year_var.get())
        months = db.get_bookkeeping_monthly_summary(year)
        if not months:
            messagebox.showinfo("Monthly Summary", f"No entries found for {year}.", parent=self)
            return

        dlg = tk.Toplevel(self)
        apply_window_icon(dlg)
        dlg.title(f"Monthly Summary - {year}")
        dlg.resizable(True, True)
        dlg.transient(self)
        dlg.grab_set()
        dlg.geometry("900x420")

        frm = ttk.Frame(dlg, padding=8)
        frm.pack(fill="both", expand=True)

        cols = (["month", "total_in", "total_out", "net"] + [k for k, _ in _BK_INC_COLS] + [k for k, _ in _BK_EXP_COLS])
        hdrs = (["Month", "Total In", "Total Out", "Net"] + [lbl for _, lbl in _BK_INC_COLS] + [lbl for _, lbl in _BK_EXP_COLS])
        tv2 = ttk.Treeview(frm, columns=cols, show="headings")
        for col, hdr in zip(cols, hdrs):
            tv2.heading(col, text=hdr, anchor="w")
            tv2.column(col, width=_sc(98), anchor="e" if col != "month" else "w", stretch=False)
        tv2.column("month", width=_sc(118))

        hsb2 = ttk.Scrollbar(frm, orient="horizontal", command=tv2.xview)
        tv2.configure(xscrollcommand=hsb2.set)
        tv2.pack(fill="both", expand=True)
        hsb2.pack(fill="x")

        for r in months:
            m_idx = int(r["month"])
            m_name = _BK_MONTHS[m_idx] if m_idx < len(_BK_MONTHS) else r["month"]
            ti = sum(float(r.get(k, 0) or 0) for k, _ in _BK_INC_COLS)
            to = sum(float(r.get(k, 0) or 0) for k, _ in _BK_EXP_COLS)
            net = ti - to
            sign = "+" if net >= 0 else ""
            values = (
                [m_name, f"${ti:,.2f}", f"${to:,.2f}", f"{sign}${net:,.2f}"] +
                [f"${float(r.get(k, 0) or 0):,.2f}" for k, _ in _BK_INC_COLS] +
                [f"${float(r.get(k, 0) or 0):,.2f}" for k, _ in _BK_EXP_COLS]
            )
            tv2.insert("", "end", values=values)

        btn(dlg, "Close", dlg.destroy).pack(side="right", padx=8, pady=6)

    def _annual_summary(self):
        year = int(self._year_var.get())
        s = db.get_bookkeeping_annual_summary(year)
        if not s:
            messagebox.showinfo("Annual Summary", f"No entries found for {year}.", parent=self)
            return

        total_in = sum(s.get(k, 0) for k, _ in _BK_INC_COLS)
        total_out = sum(s.get(k, 0) for k, _ in _BK_EXP_COLS)
        net = total_in - total_out
        opening = db.get_bookkeeping_opening_balance(year)
        closing = opening + net

        def _fmt_money(v):
            return f"${float(v or 0):,.2f}"

        dlg = tk.Toplevel(self)
        apply_window_icon(dlg)
        dlg.title(f"Annual Summary - {year}")
        dlg.resizable(True, True)
        dlg.transient(self)
        dlg.grab_set()
        dlg.geometry("980x620")
        dlg.minsize(840, 520)

        root = ttk.Frame(dlg, padding=10)
        root.pack(fill="both", expand=True)
        root.rowconfigure(1, weight=1)
        root.columnconfigure(0, weight=1)

        hdr = ttk.Frame(root)
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        hdr.columnconfigure(0, weight=1)
        ttk.Label(hdr, text=f"Annual Summary - {year}", font=FONT_LG).grid(row=0, column=0, sticky="w")

        totals = ttk.Frame(root)
        totals.grid(row=1, column=0, sticky="new", pady=(0, 8))
        for i in range(5):
            totals.columnconfigure(i, weight=1)

        total_cards = [
            ("Opening", _fmt_money(opening), "#475569"),
            ("Income", _fmt_money(total_in), "#166534"),
            ("Expenses", _fmt_money(total_out), "#991b1b"),
            ("Net", f"{'+' if net >= 0 else ''}{_fmt_money(net)}", "#1e40af" if net >= 0 else "#b91c1c"),
            ("Closing", _fmt_money(closing), "#334155"),
        ]
        for i, (label, value, color) in enumerate(total_cards):
            card = tk.Frame(totals, bg="#f8fafc", bd=1, relief="solid")
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))
            tk.Label(card, text=label, bg="#f8fafc", fg="#64748b", font=FONT_SM).pack(anchor="w", padx=8, pady=(6, 0))
            tk.Label(card, text=value, bg="#f8fafc", fg=color, font=("Calibri", 13, "bold")).pack(anchor="w", padx=8, pady=(0, 7))

        body = ttk.Frame(root)
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        ttk.Label(body, text="Income", font=FONT_UI).grid(row=0, column=0, sticky="w", pady=(2, 4))
        ttk.Label(body, text="Expenses", font=FONT_UI).grid(row=0, column=1, sticky="w", pady=(2, 4), padx=(10, 0))

        left = ttk.Frame(body)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        right = ttk.Frame(body)
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        cols = ("category", "amount")
        tv_in = ttk.Treeview(left, columns=cols, show="headings", selectmode="none")
        tv_in.heading("category", text="Category", anchor="w")
        tv_in.heading("amount", text="Amount", anchor="e")
        tv_in.column("category", width=_sc(250), anchor="w", stretch=True)
        tv_in.column("amount", width=_sc(126), anchor="e", stretch=False)
        tv_in.grid(row=0, column=0, sticky="nsew")

        tv_exp = ttk.Treeview(right, columns=cols, show="headings", selectmode="none")
        tv_exp.heading("category", text="Category", anchor="w")
        tv_exp.heading("amount", text="Amount", anchor="e")
        tv_exp.column("category", width=_sc(250), anchor="w", stretch=True)
        tv_exp.column("amount", width=_sc(126), anchor="e", stretch=False)
        tv_exp.grid(row=0, column=0, sticky="nsew")

        sb_in = ttk.Scrollbar(left, orient="vertical", command=tv_in.yview)
        tv_in.configure(yscrollcommand=sb_in.set)
        sb_in.grid(row=0, column=1, sticky="ns")

        sb_exp = ttk.Scrollbar(right, orient="vertical", command=tv_exp.yview)
        tv_exp.configure(yscrollcommand=sb_exp.set)
        sb_exp.grid(row=0, column=1, sticky="ns")

        for key, lbl in _BK_INC_COLS:
            tv_in.insert("", "end", values=(lbl, _fmt_money(s.get(key, 0))))
        tv_in.insert("", "end", values=("TOTAL INCOME", _fmt_money(total_in)))

        for key, lbl in _BK_EXP_COLS:
            tv_exp.insert("", "end", values=(lbl, _fmt_money(s.get(key, 0))))
        tv_exp.insert("", "end", values=("TOTAL EXPENSES", _fmt_money(total_out)))

        bf = ttk.Frame(root)
        bf.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        btn(bf, "Close", dlg.destroy).pack(side="right")

    def _export_csv(self):
        year = int(self._year_var.get())
        month_idx = _BK_MONTHS.index(self._month_var.get())
        rows = db.get_bookkeeping_entries(year, month_idx)
        if not rows:
            messagebox.showinfo("No Data", "No entries to export.", parent=self)
            return

        path = filedialog.asksaveasfilename(
            title="Export Bookkeeping CSV",
            defaultextension=".csv",
            initialfile=f"bookkeeping_{year}.csv",
            filetypes=[("CSV Files", "*.csv"), ("All", "*.*")],
        )
        if not path:
            return

        import csv as _csv

        headers = (["Date", "Check #", "Payee", "Memo", "Tax Deductible"] +
                   [lbl for _, lbl in _BK_INC_COLS] +
                   [lbl for _, lbl in _BK_EXP_COLS])
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = _csv.writer(f)
            w.writerow(headers)
            for r in rows:
                w.writerow(
                    [r["entry_date"], r["check_number"] or "", r["payee"] or "",
                     r["memo"] or "", "Yes" if r["is_tax_deductible"] else "No"] +
                    [f"{float(r[k] or 0):.2f}" for k, _ in _BK_INC_COLS] +
                    [f"{float(r[k] or 0):.2f}" for k, _ in _BK_EXP_COLS]
                )
        messagebox.showinfo("Exported", f"Saved to:`n{path}", parent=self)

    def _import_any_file(self):
        path = filedialog.askopenfilename(
            title="Import Bookkeeping File",
            filetypes=[("All Files", "*.*"), ("CSV Files", "*.csv"), ("Text Files", "*.txt")],
        )
        if not path:
            return
        try:
            import migration
            count, warns = migration.import_bookkeeping_csv(path)
        except Exception as ex:
            messagebox.showerror("Import Failed", f"Could not import bookkeeping entries from:\n{path}\n\nError: {ex}", parent=self)
            return
        self.refresh()
        messagebox.showinfo("Import Complete", f"Imported {count} bookkeeping entries.\n{len(warns)} warnings.", parent=self)
class VersionManagerDialog(tk.Toplevel):
    def __init__(self, parent, on_change=None):
        super().__init__(parent)
        apply_window_icon(self)
        self.on_change = on_change
        self.title("Version Manager")
        _w, _h = _screen_fit(420, 280)
        self.geometry(f"{_w}x{_h}")
        self.resizable(True, True)
        self._build()
        self._refresh()
        self.grab_set()

    def _build(self):
        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Current Version", font=FONT_LG).pack(anchor="w")
        self.lbl_ver = ttk.Label(main, text="", font=("Calibri", 14, "bold"), foreground=ACCENT)
        self.lbl_ver.pack(anchor="w", pady=(2, 10))

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=4)
        btn(btn_frame, "+ Build", self._bump_build, "Accent.TButton").pack(side="left", padx=3)
        btn(btn_frame, "+ Patch", self._bump_patch, "Accent.TButton").pack(side="left", padx=3)
        btn(btn_frame, "+ Minor", self._bump_minor, "Accent.TButton").pack(side="left", padx=3)
        btn(btn_frame, "+ Major", self._bump_major, "Accent.TButton").pack(side="left", padx=3)

        set_frame = lframe(main, "Set Exact Version")
        set_frame.pack(fill="x", pady=8)

        self.var_major = tk.StringVar()
        self.var_minor = tk.StringVar()
        self.var_patch = tk.StringVar()
        self.var_build = tk.StringVar()

        ttk.Label(set_frame, text="Major").grid(row=0, column=0, padx=4, pady=3)
        ttk.Entry(set_frame, textvariable=self.var_major, width=6).grid(row=0, column=1, padx=4)
        ttk.Label(set_frame, text="Minor").grid(row=0, column=2, padx=4)
        ttk.Entry(set_frame, textvariable=self.var_minor, width=6).grid(row=0, column=3, padx=4)
        ttk.Label(set_frame, text="Patch").grid(row=0, column=4, padx=4)
        ttk.Entry(set_frame, textvariable=self.var_patch, width=6).grid(row=0, column=5, padx=4)
        ttk.Label(set_frame, text="Build").grid(row=0, column=6, padx=4)
        ttk.Entry(set_frame, textvariable=self.var_build, width=6).grid(row=0, column=7, padx=4)

        btn(set_frame, "Apply Version", self._set_version).grid(row=1, column=0, columnspan=8, pady=6)

        self.lbl_status = ttk.Label(main, text="", foreground=MUTED)
        self.lbl_status.pack(anchor="w", pady=(4, 0))

        bottom = ttk.Frame(main)
        bottom.pack(fill="x", side="bottom", pady=(10, 0))
        btn(bottom, "Close", self.destroy).pack(side="right")

    def _refresh(self):
        data = vm.get_version_data()
        self.lbl_ver.config(text=vm.get_version_string())
        self.var_major.set(str(data["major"]))
        self.var_minor.set(str(data["minor"]))
        self.var_patch.set(str(data["patch"]))
        self.var_build.set(str(data["build"]))

    def _notify_change(self):
        self._refresh()
        if self.on_change:
            self.on_change(vm.get_version_string())

    def _bump_build(self):
        self.lbl_status.config(text=f"Updated: {vm.bump_build()}")
        self._notify_change()

    def _bump_patch(self):
        self.lbl_status.config(text=f"Updated: {vm.bump_patch()}")
        self._notify_change()

    def _bump_minor(self):
        self.lbl_status.config(text=f"Updated: {vm.bump_minor()}")
        self._notify_change()

    def _bump_major(self):
        self.lbl_status.config(text=f"Updated: {vm.bump_major()}")
        self._notify_change()

    def _set_version(self):
        try:
            major = int(self.var_major.get().strip())
            minor = int(self.var_minor.get().strip())
            patch = int(self.var_patch.get().strip())
            build = int(self.var_build.get().strip())
        except ValueError:
            messagebox.showerror("Invalid", "Version numbers must be integers.", parent=self)
            return
        version_text = vm.set_version(major, minor, patch, build)
        self.lbl_status.config(text=f"Updated: {version_text}")
        self._notify_change()


class TheraTrakApp(tk.Tk):
    def __init__(self, current_user=None):
        super().__init__()
        self.withdraw()   # keep hidden until login succeeds
        apply_window_icon(self)
        self.current_user = current_user
        self._version = vm.get_version_string()
        self._startup_update_message = ""
        self._startup_update_available = False
        self._startup_latest_version = ""
        self._startup_dictation_scan_message = ""
        self.title(f"Aura Scribe PSY - {self._version}")
        
        # ── Cache detected dictation software at startup ──────────────────────
        self._cached_dictation_apps = []
        self._scan_dictation_apps_async()

        # ── Detect display and hardware environment once at startup ──────────
        global SCREEN_W, SCREEN_H, SCREEN_FIT_W, SCREEN_FIT_H
        global MACHINE_TYPE, SCREEN_DPI, UI_SCALE, UI_MAX_SCALE, UI_DENSE_MODE
        SCREEN_W     = self.winfo_screenwidth()
        SCREEN_H     = self.winfo_screenheight()
        MACHINE_TYPE = _detect_machine_type()
        try:
            SCREEN_DPI = int(self.winfo_fpixels("1i"))  # pixels per inch
            UI_SCALE   = SCREEN_DPI / 96.0
        except Exception:
            pass
        _mp = _monitor_fit_profile(SCREEN_W, SCREEN_H, SCREEN_DPI)
        SCREEN_FIT_W = int(_mp.get("min_work_w", SCREEN_W))
        SCREEN_FIT_H = int(_mp.get("min_work_h", SCREEN_H))
        UI_MAX_SCALE = float(_mp.get("max_scale", UI_SCALE))

        # Supplement DPI detection via Windows registry — reliable regardless of
        # the process's DPI-awareness context (per-monitor, system, or unaware).
        if sys.platform == "win32":
            try:
                import winreg as _wr
                with _wr.OpenKey(_wr.HKEY_CURRENT_USER, r"Control Panel\Desktop") as _k:
                    _reg_dpi, _ = _wr.QueryValueEx(_k, "LogPixels")
                    if _reg_dpi and int(_reg_dpi) > 0:
                        _reg_scale = int(_reg_dpi) / 96.0
                        UI_MAX_SCALE = max(UI_MAX_SCALE, _reg_scale)
                        UI_SCALE     = max(UI_SCALE,     _reg_scale)
            except Exception:
                pass

        # With SetProcessDpiAwareness(2) active, Tkinter reports physical pixels
        # but widget metrics (font heights, button sizes) scale with DPI — so
        # fewer items fit per physical pixel.  Convert to effective logical pixels
        # (physical ÷ DPI-scale) so all density decisions are DPI-independent.
        _log_w = int(SCREEN_FIT_W / UI_MAX_SCALE) if UI_MAX_SCALE > 1.05 else SCREEN_FIT_W
        _log_h = int(SCREEN_FIT_H / UI_MAX_SCALE) if UI_MAX_SCALE > 1.05 else SCREEN_FIT_H
        UI_DENSE_MODE = (_log_w < 1366 or _log_h < 860)
        _append_startup_log(
            f"Display: {SCREEN_W}x{SCREEN_H}  DPI: {SCREEN_DPI}  "
            f"Scale: {UI_SCALE:.2f}x  Machine: {MACHINE_TYPE}"
        )
        _append_startup_log(
            f"Monitors: {_mp.get('count', 1)}  FitArea: {SCREEN_FIT_W}x{SCREEN_FIT_H}  "
            f"MaxScale: {UI_MAX_SCALE:.2f}x  Logical: {_log_w}x{_log_h}  "
            f"DenseMode: {'yes' if UI_DENSE_MODE else 'no'}"
        )

        # Adapt base font size using logical (DPI-independent) dimensions so
        # thresholds behave the same on every display density.
        global FONT_UI, FONT_SM, FONT_LG, FONT_H1, FONT_MONO
        _fsize = 12
        if _log_h < 700 or _log_w < 980:
            _fsize = 9
        elif _log_h < 820 or _log_w < 1180:
            _fsize = 10
        elif _log_h < 940 or _log_w < 1440:
            _fsize = 11
        if _fsize != 12:
            FONT_UI   = ("Arial", _fsize)
            FONT_SM   = ("Arial", _fsize)
            FONT_LG   = ("Arial", _fsize, "bold")
            FONT_H1   = ("Arial", _fsize, "bold")
            FONT_MONO = ("Arial", _fsize)

        # Window size: first decide the target in logical pixels, then convert
        # to physical pixels for geometry() (which uses physical px when DPI-aware).
        _win_log_w = min(1280, max(980, _log_w - 22))
        _win_log_h = min(820,  max(620, _log_h - 44))
        win_w = min(SCREEN_FIT_W - 16, int(_win_log_w * UI_MAX_SCALE))
        win_h = min(SCREEN_FIT_H - 44, int(_win_log_h * UI_MAX_SCALE))
        self.geometry(f"{win_w}x{win_h}+{(SCREEN_W-win_w)//2}+{(SCREEN_H-win_h)//2}")
        self.minsize(int(800 * UI_MAX_SCALE), int(540 * UI_MAX_SCALE))

        self._style = ttk_style()

        db.initialize_db()

        self._build_header()
        self._build_notebook()
        self._build_statusbar()
        self._build_menu()
        self._update_stats()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_header(self):
        hdr = tk.Frame(self, bg=HDR_BG, height=56)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="Aura Scribe PSY", bg=HDR_BG, fg=HDR_FG,
                 font=("Calibri", 20, "bold")).pack(side="left", padx=16, pady=10)
        tk.Label(hdr, text="Combined Therapy & Billing", bg=HDR_BG, fg="#93c5fd",
                 font=("Calibri", 10)).pack(side="left", padx=2)
        self._lbl_version = tk.Label(hdr, text=self._version, bg=HDR_BG, fg="#bfdbfe",
                                     font=("Calibri", 9, "bold"))
        self._lbl_version.pack(side="left", padx=10)

        stats = tk.Frame(hdr, bg=HDR_BG)
        stats.pack(side="right", padx=14)
        self._lbl_date = tk.Label(stats, text="", bg=HDR_BG, fg="#93c5fd", font=FONT_SM)
        self._lbl_pts = tk.Label(stats, text="", bg=HDR_BG, fg="#93c5fd", font=FONT_SM)
        self._lbl_user = tk.Label(stats, text="", bg=HDR_BG, fg="#bfdbfe", font=FONT_SM)
        self._lbl_date.pack(side="bottom", anchor="e")
        self._lbl_pts.pack(side="bottom", anchor="e")
        self._lbl_user.pack(side="bottom", anchor="e")

    def _build_notebook(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        self.tab_patients = PatientsTab(self.nb)
        self.tab_sessions = SessionNotesTab(self.nb)
        self.tab_appointments = AppointmentBookTab(self.nb)
        self.tab_billing = BillingTab(self.nb)
        self.tab_cpt_codes = CPTCodesTab(self.nb)
        self.tab_cms = CMS1500Tab(self.nb)
        self.tab_bookkeeping = BookkeepingTab(self.nb)
        self.tab_reports = ReportsTab(self.nb)
        self.tab_provider = ProviderPracticeTab(self.nb)
        self.tab_settings = SettingsTab(self.nb)

        self.nb.add(self.tab_patients, text="  Patients  ")
        self.nb.add(self.tab_sessions, text="  Session Notes  ")
        self.nb.add(self.tab_appointments, text="  Appointment Book  ")
        self.nb.add(self.tab_billing, text="  Billing  ")
        self.nb.add(self.tab_cpt_codes, text="  CPT Codes  ")
        self.nb.add(self.tab_cms, text="  CMS-1500  ")
        self.nb.add(self.tab_bookkeeping, text="  Bookkeeping  ")
        self.nb.add(self.tab_reports, text="  Reports  ")
        self.nb.add(self.tab_provider, text="  Provider / Practice  ")
        self.nb.add(self.tab_settings, text="  Data Import  ")

    def _build_statusbar(self):
        sb = tk.Frame(self, bg="#e2e8f0", height=24)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        self._status_lbl = tk.Label(sb, text="Ready", bg="#e2e8f0", fg=MUTED, font=FONT_SM)
        self._status_lbl.pack(side="left", padx=8)
        db_path = str(db.DB_PATH)
        tk.Label(sb, text=f"Database: {db_path}", bg="#e2e8f0", fg=MUTED, font=FONT_SM).pack(side="right", padx=8)

    def _build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Patient", command=lambda: PatientDialog(self, on_save=lambda _: self.tab_patients.refresh()))
        file_menu.add_command(label="New Session", command=lambda: SessionDialog(self, on_save=lambda _: self.tab_sessions.refresh()))
        file_menu.add_separator()

        import_menu = tk.Menu(file_menu, tearoff=0)
        import_menu.add_command(label="Import Patients (Any File Type)", command=self._file_import_patients_any)
        import_menu.add_command(label="Import Sessions (Any File Type)", command=self._file_import_sessions_any)
        import_menu.add_command(label="Import Billing (Any File Type)", command=self._file_import_billing_any)
        import_menu.add_command(label="Import Bookkeeping (Any File Type)", command=self._file_import_bookkeeping_any)
        file_menu.add_cascade(label="Import", menu=import_menu)

        export_menu = tk.Menu(file_menu, tearoff=0)
        export_menu.add_command(label="Export Patients (CSV)", command=self._file_export_patients_csv)
        export_menu.add_command(label="Export Sessions (CSV)", command=self._file_export_sessions_csv)
        export_menu.add_command(label="Export Billing (CSV)", command=self._file_export_billing_csv)
        export_menu.add_separator()
        export_menu.add_command(label="Export Bookkeeping (CSV)", command=self._file_export_bookkeeping_csv)
        file_menu.add_cascade(label="Export", menu=export_menu)

        file_menu.add_separator()
        file_menu.add_command(label="User Directory", command=self._open_user_directory)
        file_menu.add_command(label="Provider Profile", command=self._open_provider_profile)
        file_menu.add_separator()
        file_menu.add_command(label="Backup Database", command=self._backup_db)
        file_menu.add_separator()
        file_menu.add_command(label="Logout", command=self._logout)
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        nav_menu = tk.Menu(menubar, tearoff=0)
        nav_menu.add_command(label="Patients", command=lambda: self.nb.select(self.tab_patients))
        nav_menu.add_command(label="Session Notes", command=lambda: self.nb.select(self.tab_sessions))
        nav_menu.add_command(label="Appointments", command=lambda: self.nb.select(self.tab_appointments))
        nav_menu.add_command(label="Billing", command=lambda: self.nb.select(self.tab_billing))
        nav_menu.add_command(label="CPT Codes", command=lambda: self.nb.select(self.tab_cpt_codes))
        nav_menu.add_command(label="CMS-1500", command=lambda: self.nb.select(self.tab_cms))
        nav_menu.add_command(label="Bookkeeping", command=lambda: self.nb.select(self.tab_bookkeeping))
        nav_menu.add_command(label="Reports", command=lambda: self.nb.select(self.tab_reports))
        nav_menu.add_command(label="Provider / Practice", command=lambda: self.nb.select(self.tab_provider))
        nav_menu.add_command(label="Data Import", command=lambda: self.nb.select(self.tab_settings))
        nav_menu.add_command(label="Provider Profile", command=self._open_provider_profile)
        menubar.add_cascade(label="Navigate", menu=nav_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Check for Updates", command=self._check_for_updates)
        help_menu.add_command(label="License Registration", command=self._open_license_registration)
        help_menu.add_command(label="User Guide", command=self._open_user_guide)
        help_menu.add_command(label="Display Diagnostics", command=self._show_display_diagnostics)
        help_menu.add_command(label="About Aura Scribe PSY", command=self._about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _update_stats(self):
        self._version = vm.get_version_string()
        self.title(f"Aura Scribe PSY - {self._version}")
        self._lbl_version.config(text=self._version)
        n = db.count_patients("Active")
        self._lbl_pts.config(text=f"Active Patients: {n}")
        self._lbl_date.config(text=date.today().strftime("%A, %B %d, %Y"))
        if self.current_user:
            who = f"{self.current_user['first_name']} {self.current_user['last_name']} ({self.current_user['username']})"
            self._lbl_user.config(text=f"Logged In: {who}")
        else:
            self._lbl_user.config(text="Logged In: -")

    def set_logged_in_user(self, user):
        self.current_user = user
        self._update_stats()

    def show_post_update_announcement_if_needed(self):
        current_version = (self._version or vm.get_version_string() or "").strip()
        if not current_version:
            return
        seen_version = (db.get_app_preference(UPDATE_ANNOUNCEMENT_SEEN_PREF_KEY, "") or "").strip()
        current_tuple = self._parse_version_tuple(current_version)
        seen_tuple = self._parse_version_tuple(seen_version)
        if (current_tuple != (0, 0, 0, 0) and seen_tuple == current_tuple) or seen_version == current_version:
            return

        notes_version = (db.get_app_preference(UPDATE_ANNOUNCEMENT_NOTES_VERSION_PREF_KEY, "") or "").strip()
        notes_body = (db.get_app_preference(UPDATE_ANNOUNCEMENT_NOTES_BODY_PREF_KEY, "") or "").strip()
        notes_tuple = self._parse_version_tuple(notes_version)

        details_text = ""
        if notes_body and (notes_tuple == current_tuple or notes_version == current_version):
            details_text = notes_body
            if len(details_text) > 2400:
                details_text = (
                    details_text[:2400].rstrip()
                    + "\n\n(Release notes truncated. Use Help > Check for Updates for full details.)"
                )

        # Fallback: if cached notes are missing/mismatched, fetch release notes for
        # the installed version so users still see "what changed" after updating.
        if not details_text and current_tuple != (0, 0, 0, 0):
            fetched = self._fetch_release_notes_for_version(current_version, timeout=5)
            if fetched:
                fetched_version, fetched_notes = fetched
                details_text = fetched_notes
                if len(details_text) > 2400:
                    details_text = (
                        details_text[:2400].rstrip()
                        + "\n\n(Release notes truncated. Use Help > Check for Updates for full details.)"
                    )
                try:
                    db.set_app_preference(UPDATE_ANNOUNCEMENT_NOTES_VERSION_PREF_KEY, fetched_version)
                    db.set_app_preference(UPDATE_ANNOUNCEMENT_NOTES_BODY_PREF_KEY, fetched_notes)
                except Exception:
                    pass

        if details_text and "what's changed" not in details_text.lower():
            details_text = "## What's Changed\n" + details_text

        canonical_current = self._format_tag_version(current_version)
        db.set_app_preference(UPDATE_ANNOUNCEMENT_SEEN_PREF_KEY, canonical_current)

        if details_text:
            msg = (
                f"Welcome back! You're now running {current_version}.\n\n"
                "What's changed in this update:\n\n"
                f"{details_text}"
            )
        else:
            msg = (
                f"Welcome back! You're now running {current_version}.\n\n"
                "This update was installed successfully.\n"
                "Use Help > Check for Updates to view release details."
            )

        messagebox.showinfo("Aura Scribe PSY Updated", msg, parent=self)

    def _open_user_directory(self):
        UserDirectoryDialog(self)

    def _open_provider_profile(self):
        if hasattr(self, "tab_provider"):
            self.nb.select(self.tab_provider)

    def _file_import_patients_any(self):
        if hasattr(self, "tab_settings"):
            self.tab_settings._import_patients_csv(any_filetype=True)

    def _file_import_sessions_any(self):
        if hasattr(self, "tab_settings"):
            self.tab_settings._import_sessions_csv(any_filetype=True)

    def _file_import_billing_any(self):
        if hasattr(self, "tab_settings"):
            self.tab_settings._import_billing_csv(any_filetype=True)

    def _file_import_bookkeeping_any(self):
        if hasattr(self, "tab_bookkeeping"):
            self.tab_bookkeeping._import_any_file()

    def _file_export_patients_csv(self):
        if hasattr(self, "tab_reports"):
            self.tab_reports._export_patients_csv()

    def _file_export_sessions_csv(self):
        if hasattr(self, "tab_reports"):
            self.tab_reports._export_sessions_csv()

    def _file_export_billing_csv(self):
        if hasattr(self, "tab_reports"):
            self.tab_reports._export_billing_csv()

    def _file_export_bookkeeping_csv(self):
        if hasattr(self, "tab_bookkeeping"):
            self.tab_bookkeeping._export_csv()

    def _logout(self):
        if not messagebox.askyesno("Logout", "Are you sure you want to log out?", parent=self):
            return
        self.current_user = None
        self._update_stats()
        self.withdraw()
        login = LoginDialog(self)
        self.wait_window(login)
        if login.user:
            self.set_logged_in_user(login.user)
            self.deiconify()
            self.show_post_update_announcement_if_needed()
        else:
            self.destroy()

    def _backup_db(self):
        from shutil import copy2
        dest = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("Database", "*.db"), ("All", "*.*")],
            initialfile=f"theratrak_backup_{date.today().strftime('%Y%m%d')}.db")
        if dest:
            copy2(db.DB_PATH, dest)
            messagebox.showinfo("Backup", f"Database backed up to:\n{dest}")

    def _open_user_guide(self):
        guide_candidates = [
            APP_ROOT / "USER_GUIDE.md",
            ASSETS_DIR / "USER_GUIDE.md",
        ]
        guide_path = next((p for p in guide_candidates if p.exists()), None)
        if not guide_path:
            looked_in = "\n".join(str(p) for p in guide_candidates)
            messagebox.showerror("User Guide", f"User guide file not found.\n\nLooked in:\n{looked_in}")
            return
        try:
            content = guide_path.read_text(encoding="utf-8")
        except OSError as ex:
            messagebox.showerror("User Guide", f"Could not read user guide:\n{ex}")
            return

        win = tk.Toplevel(self)
        apply_window_icon(win)
        win.title("Aura Scribe PSY User Guide")
        win.geometry("980x760")
        win.minsize(760, 560)

        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        txt = tk.Text(frm, wrap="word", font=FONT_UI, relief="solid", borderwidth=1)
        sb = ttk.Scrollbar(frm, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        txt.insert("1.0", content)
        txt.configure(state="disabled")

    def _show_display_diagnostics(self):
        # Run a fresh hardware probe at dialog-open time so support data is live,
        # not just the startup-cached snapshot.
        live_machine_probe = _probe_machine_type()
        live_machine = str(live_machine_probe.get("machine_type", "unknown") or "unknown")
        cur_w = self.winfo_screenwidth()
        cur_h = self.winfo_screenheight()
        try:
            cur_dpi = int(self.winfo_fpixels("1i"))
            cur_scale = cur_dpi / 96.0
        except Exception:
            cur_dpi = SCREEN_DPI
            cur_scale = UI_SCALE

        live_profile = _monitor_fit_profile(cur_w, cur_h, cur_dpi)

        startup_machine = MACHINE_TYPE or "unknown"
        current_machine = live_machine or startup_machine or "unknown"
        startup_log = STARTUP_LOG_FILE
        pc_system_type = live_machine_probe.get("pc_system_type")
        chassis_types = live_machine_probe.get("chassis_types") or []
        battery_flag = live_machine_probe.get("battery_flag")
        probe_source = str(live_machine_probe.get("source", "none") or "none")
        wmi_votes = live_machine_probe.get("wmi_votes") or []

        lines = [
            "Aura Scribe PSY Display Diagnostics",
            "",
            f"Version: {self._version}",
            f"Platform: {platform.platform()}",
            f"Python: {sys.version.split()[0]}",
            "",
            f"Machine Type (startup cached): {startup_machine}",
            f"Machine Type (live probe): {current_machine}",
            f"Machine Type Source (live): {_format_probe_source(probe_source)}",
            f"PC System Type (live raw): {_format_pc_system_type(pc_system_type)}",
            f"Chassis Types (live raw): {_format_chassis_types(chassis_types)}",
            f"Battery Flag (live raw): {_format_battery_flag(battery_flag)}",
            f"WMI Votes (live): {', '.join(str(v) for v in wmi_votes) if wmi_votes else 'none'}",
            f"Startup Display (cached): {SCREEN_W} x {SCREEN_H}",
            f"Current Display (live): {cur_w} x {cur_h}",
            f"Detected Monitors (live): {int(live_profile.get('count', 1))}",
            f"Smallest Monitor Work Area (live): {int(live_profile.get('min_work_w', cur_w))} x {int(live_profile.get('min_work_h', cur_h))}",
            f"Startup DPI (cached): {SCREEN_DPI}",
            f"Current DPI (live): {cur_dpi}",
            f"Startup UI Scale (cached): {UI_SCALE:.2f}x",
            f"Current UI Scale (live): {cur_scale:.2f}x",
            f"Highest Monitor Scale (live): {float(live_profile.get('max_scale', cur_scale)):.2f}x",
            f"Base UI Font Size: {FONT_UI[1]} pt",
            "",
            f"Database: {db.DB_PATH}",
            f"Startup Log: {startup_log}",
        ]
        diagnostics_text = "\n".join(lines)

        dlg = tk.Toplevel(self)
        apply_window_icon(dlg)
        dlg.title("Display Diagnostics")
        dlg.geometry("760x460")
        dlg.minsize(620, 360)
        # Keep this as a normal top-level so Windows shows full control box
        # and users can maximize the diagnostics window.
        dlg.resizable(True, True)

        frm = ttk.Frame(dlg, padding=10)
        frm.pack(fill="both", expand=True)

        txt = tk.Text(frm, wrap="word", font=FONT_MONO, relief="solid", borderwidth=1)
        sb = ttk.Scrollbar(frm, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        txt.insert("1.0", diagnostics_text)
        txt.configure(state="disabled")

        btns = ttk.Frame(dlg, padding=(10, 0, 10, 10))
        btns.pack(fill="x")

        def _copy_diag():
            self.clipboard_clear()
            self.clipboard_append(diagnostics_text)
            self.update()
            messagebox.showinfo("Display Diagnostics", "Diagnostics copied to clipboard.", parent=dlg)

        btn(btns, "Copy Diagnostics", _copy_diag, "Accent.TButton").pack(side="left", padx=4)
        btn(btns, "Close", dlg.destroy).pack(side="left", padx=4)

    def _about(self):
        user_line = ""
        if self.current_user:
            user_line = f"Logged In User: {self.current_user['username']} ({self.current_user['role']})\n"
        licensed_name = db.get_app_preference(LICENSE_NAME_PREF_KEY, "")
        licensed_email = db.get_app_preference(LICENSE_EMAIL_PREF_KEY, "")
        license_line = "License: Trial Mode"
        if licensed_name or licensed_email:
            who = licensed_name or licensed_email
            license_line = f"License: Registered to {who}"
        messagebox.showinfo(
            "About Aura Scribe PSY",
            "Aura Scribe PSY\n"
            f"Version: {self._version}\n"
            f"{user_line}"
            f"{license_line}\n"
            "Combined Therapy Practice Management + CMS-1500\n\n"
            "Features:\n"
            "  - Patient management & demographics\n"
            "  - Session notes with DSM-5 / ICD-10 lookup\n"
            "  - Billing ledger & payment tracking\n"
            "  - CMS-1500 fillable PDF (preview + print)\n"
            "  - Reports & CSV data export\n"
            "  - Data migration from previous software exports\n\n"
            f"Database: {db.DB_PATH}\n\n"
            "Created By: Judson M. Fitzpatrick, Irish_Codeers Programming\n"
            f"(c) {datetime.now().year} Irish_Codeers Programming. All rights reserved."
        )

    def _get_trial_days_left(self) -> int:
        start_text = db.get_app_preference(LICENSE_TRIAL_START_PREF_KEY, "")
        if not start_text:
            start = date.today()
            db.set_app_preference(LICENSE_TRIAL_START_PREF_KEY, start.isoformat())
            return LICENSE_TRIAL_DAYS
        try:
            start = datetime.strptime(start_text, "%Y-%m-%d").date()
        except ValueError:
            start = date.today()
            db.set_app_preference(LICENSE_TRIAL_START_PREF_KEY, start.isoformat())
            return LICENSE_TRIAL_DAYS

        elapsed = max(0, (date.today() - start).days)
        return max(0, LICENSE_TRIAL_DAYS - elapsed)

    def _open_license_registration(self, required: bool = False) -> bool:
        machine_code = _current_machine_code()
        current_key = db.get_app_preference(LICENSE_PREF_KEY, "")
        status_ok, status_msg, status_data = _validate_license_key(current_key, machine_code)

        dlg = tk.Toplevel(self)
        apply_window_icon(dlg)
        dlg.title("License Registration")
        dlg.resizable(True, True)
        try:
            dlg.state("zoomed")
        except tk.TclError:
            _w, _h = _screen_fit(max(900, SCREEN_W - 30), max(560, SCREEN_H - 90), pad=0)
            dlg.geometry(f"{_w}x{_h}+0+0")
        dlg.transient(self)
        dlg.grab_set()

        frm = ttk.Frame(dlg, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Aura Scribe PSY License", font=FONT_LG).grid(row=0, column=0, columnspan=3, sticky="w")

        status_text = "Active" if status_ok else "Not Activated"
        if not status_ok and status_msg:
            status_text = f"Not Activated ({status_msg})"
        ttk.Label(frm, text=f"Status: {status_text}").grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 2))

        if status_ok:
            who = status_data.get("name") or status_data.get("email") or "Licensed User"
            ttk.Label(frm, text=f"Registered To: {who}").grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 2))
            if status_data.get("expires"):
                ttk.Label(frm, text=f"Expires: {status_data.get('expires')}").grid(row=3, column=0, columnspan=3, sticky="w", pady=(0, 2))
        else:
            days_left = self._get_trial_days_left()
            ttk.Label(frm, text=f"Trial Remaining: {days_left} day(s)").grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 2))

            # Pricing info ──────────────────────────────────────────────────
            price_frm = ttk.LabelFrame(frm, text="Pricing", padding=8)
            price_frm.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 4))
            ttk.Label(price_frm, text="Solo Practice", font=FONT_LG).grid(row=0, column=0, sticky="w")
            ttk.Label(price_frm, text="$49 / month   (1 provider)").grid(row=0, column=1, sticky="w", padx=(12, 0))
            ttk.Label(price_frm, text="Group Practice", font=FONT_LG).grid(row=1, column=0, sticky="w", pady=(4, 0))
            ttk.Label(price_frm, text="$129 / month   (up to 5 providers)").grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(4, 0))
            ttk.Label(price_frm, text="14-day free trial included with every new installation.",
                      foreground=MUTED).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

            def _open_purchase():
                webbrowser.open("https://github.com/Irish-Coder69/AuraScribe-PSY/releases/latest")

            ttk.Button(price_frm, text="Purchase License \u2192", command=_open_purchase).grid(
                row=3, column=0, columnspan=2, sticky="w", pady=(8, 0)
            )
            # ────────────────────────────────────────────────────────────────

        ttk.Label(frm, text="Machine Code:").grid(row=4, column=0, sticky="w", pady=(8, 2))
        machine_var = tk.StringVar(value=machine_code)
        machine_entry = ttk.Entry(frm, textvariable=machine_var, width=28, state="readonly")
        machine_entry.grid(row=5, column=0, sticky="w")

        def copy_machine_code():
            self.clipboard_clear()
            self.clipboard_append(machine_code)
            self.update()

        ttk.Button(frm, text="Copy", command=copy_machine_code).grid(row=5, column=1, sticky="w", padx=6)

        ttk.Label(frm, text="Enter License Key:").grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 2))
        key_var = tk.StringVar(value=current_key)
        key_text = tk.Text(frm, width=64, height=4, wrap="char", font=("Courier", 9))
        key_text.grid(row=7, column=0, columnspan=3, sticky="ew")
        if current_key:
            key_text.insert("1.0", current_key)
        key_text.focus_set()

        def _get_key() -> str:
            return key_text.get("1.0", "end-1c").strip()

        result = {"activated": status_ok}

        def activate_license():
            candidate = _get_key()
            ok, msg, data = _validate_license_key(candidate, machine_code)
            if not ok:
                messagebox.showerror("License", msg, parent=dlg)
                return

            db.set_app_preference(LICENSE_PREF_KEY, candidate)
            db.set_app_preference(LICENSE_NAME_PREF_KEY, data.get("name", ""))
            db.set_app_preference(LICENSE_EMAIL_PREF_KEY, data.get("email", ""))
            db.set_app_preference(LICENSE_ACTIVATED_AT_PREF_KEY, datetime.now().isoformat(timespec="seconds"))
            result["activated"] = True
            messagebox.showinfo("License", "License activated successfully.", parent=dlg)
            dlg.destroy()

        def clear_license():
            if not messagebox.askyesno("License", "Remove this license key from this computer?", parent=dlg):
                return
            db.set_app_preference(LICENSE_PREF_KEY, "")
            db.set_app_preference(LICENSE_NAME_PREF_KEY, "")
            db.set_app_preference(LICENSE_EMAIL_PREF_KEY, "")
            db.set_app_preference(LICENSE_ACTIVATED_AT_PREF_KEY, "")
            key_text.delete("1.0", "end")
            result["activated"] = False
            messagebox.showinfo("License", "License key removed.", parent=dlg)

        btn_row = ttk.Frame(frm)
        btn_row.grid(row=8, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(btn_row, text="Activate", command=activate_license).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Remove Key", command=clear_license).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Close", command=dlg.destroy).pack(side="left", padx=4)

        dlg.wait_window()

        if required and not result["activated"]:
            messagebox.showwarning(
                "License Required",
                "A valid license key is required to continue using Aura Scribe PSY.",
                parent=self,
            )
        return bool(result["activated"])

    def ensure_license_access(self) -> bool:
        machine_code = _current_machine_code()
        key = db.get_app_preference(LICENSE_PREF_KEY, "")
        valid, _msg, _data = _validate_license_key(key, machine_code)
        if valid:
            return True

        days_left = self._get_trial_days_left()
        if days_left > 0:
            if messagebox.askyesno(
                "Trial Mode",
                "Aura Scribe PSY is running in trial mode.\n\n"
                f"Days remaining: {days_left}\n\n"
                "Pricing:\n"
                "  Solo Practice  —  $49 / month  (1 provider)\n"
                "  Group Practice  —  $129 / month  (up to 5 providers)\n\n"
                "Activate your license key now?",
                parent=self,
            ):
                self._open_license_registration(required=False)
            return True

        return self._open_license_registration(required=True)

    def _parse_version_tuple(self, text):
        nums = [int(n) for n in re.findall(r"\d+", text or "")]
        if not nums:
            return (0, 0, 0, 0)
        while len(nums) < 4:
            nums.append(0)
        return tuple(nums[:4])

    def _format_tag_version(self, tag: str) -> str:
        nums = [int(n) for n in re.findall(r"\d+", tag or "")]
        while len(nums) < 4:
            nums.append(0)
        major, minor, patch, build = nums[:4]
        return f"{major}.{minor}.{patch} Build {build}"

    def _pick_installer_asset(self, payload):
        assets = payload.get("assets") or []
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if name.endswith(".exe") and "installer" in name:
                return asset
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if name.endswith(".exe"):
                return asset
        return None

    def _backup_database_for_update(self):
        db_path = Path(db.DB_PATH)
        if not db_path.exists():
            return None
        backup_dir = UPDATE_TEMP_DIR / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"theratrak_preupdate_{ts}.db"
        shutil.copy2(db_path, backup_path)
        return backup_path

    def _download_file_with_progress(self, url, destination):
        progress_win = tk.Toplevel(self)
        apply_window_icon(progress_win)
        progress_win.title("Downloading Update")
        progress_win.resizable(False, False)
        progress_win.transient(self)
        progress_win.grab_set()
        progress_win.protocol("WM_DELETE_WINDOW", lambda: None)

        C_GRAD_TOP = (110, 195, 232)
        C_GRAD_BOT = (58, 140, 195)
        C_BODY_BG = "#f5f7fa"
        C_SUB_FG = "#556070"
        C_BAR_BG = "#d8e8f2"
        C_DIVIDER = "#3a8cc3"
        C_TITLE_FG = "#1a2535"

        screen_w = progress_win.winfo_screenwidth()
        screen_h = progress_win.winfo_screenheight()
        win_w = min(760, max(620, screen_w - 120))
        header_h = 310 if screen_h >= 900 else 240

        def _load_download_banner(width: int, height: int):
            if Image is None or ImageTk is None:
                return None
            image_name = "Aura Scribe PSY.jpg"
            candidates = [
                APP_ROOT / image_name,
                ASSETS_DIR / image_name,
                Path.cwd() / image_name,
            ]
            for candidate in candidates:
                if not candidate.exists() or not candidate.is_file():
                    continue
                try:
                    with Image.open(candidate) as source:
                        source = source.convert("RGB")
                        if source.width <= 0 or source.height <= 0:
                            continue
                        scale = min(width / source.width, height / source.height)
                        new_w = max(1, int(source.width * scale))
                        new_h = max(1, int(source.height * scale))
                        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC)
                        resized = source.resize((new_w, new_h), resample)
                        canvas = Image.new("RGB", (width, height), (17, 40, 60))
                        off_x = (width - new_w) // 2
                        off_y = (height - new_h) // 2
                        canvas.paste(resized, (off_x, off_y))
                    return ImageTk.PhotoImage(canvas)
                except Exception:
                    continue
            return None

        progress_win.configure(bg=C_BODY_BG)
        hdr = tk.Canvas(progress_win, width=win_w, height=header_h, highlightthickness=0)
        hdr.pack(fill="x")

        banner_photo = _load_download_banner(win_w, header_h)
        if banner_photo is not None:
            hdr.create_image(win_w // 2, header_h // 2, image=banner_photo, anchor="center")
            hdr.image = banner_photo
            hdr.create_rectangle(0, 0, win_w, header_h, outline="#3a8cc3", width=2)
        else:
            r0, g0, b0 = C_GRAD_TOP
            r1, g1, b1 = C_GRAD_BOT
            for i in range(header_h):
                t = i / max(1, header_h - 1)
                r = int(r0 + (r1 - r0) * t)
                g = int(g0 + (g1 - g0) * t)
                b = int(b0 + (b1 - b0) * t)
                hdr.create_line(0, i, win_w, i, fill=f"#{r:02x}{g:02x}{b:02x}")
            hdr.create_text(
                win_w // 2,
                header_h // 2 - 8,
                text="Aura Scribe PSY",
                font=("Segoe UI", 16, "bold"),
                fill="white",
                anchor="center",
            )
            hdr.create_text(
                win_w // 2,
                header_h // 2 + 16,
                text="Downloading update...",
                font=("Segoe UI", 9),
                fill="#d6eef8",
                anchor="center",
            )

        tk.Frame(progress_win, bg=C_DIVIDER, height=3).pack(fill="x")

        body = tk.Frame(progress_win, bg=C_BODY_BG, padx=24, pady=18)
        body.pack(fill="both", expand=True)

        tk.Label(
            body,
            text="Downloading latest installer...",
            font=("Segoe UI", 11, "bold"),
            bg=C_BODY_BG,
            fg=C_TITLE_FG,
            anchor="w",
        ).pack(anchor="w", pady=(0, 6))

        status_var = tk.StringVar(value="Starting download...")
        tk.Label(
            body,
            textvariable=status_var,
            font=("Segoe UI", 9),
            bg=C_BODY_BG,
            fg=C_SUB_FG,
            anchor="w",
            wraplength=win_w - 48,
        ).pack(anchor="w", pady=(0, 10))

        bar_w = win_w - 48
        bar_h = 16
        bar_canvas = tk.Canvas(body, width=bar_w, height=bar_h, bg=C_BAR_BG, highlightthickness=0)
        bar_canvas.pack(anchor="w")

        pct_label = tk.Label(body, text="0%", font=("Segoe UI", 8), bg=C_BODY_BG, fg=C_SUB_FG, anchor="e")
        pct_label.pack(anchor="e", pady=(3, 0))

        mode = {"indeterminate": True, "active": True, "pos": -(bar_w // 3)}
        block = bar_w // 4

        def _draw_determinate(pct: float) -> None:
            bar_canvas.delete("all")
            bar_canvas.create_rectangle(0, 0, bar_w, bar_h, fill=C_BAR_BG, outline="")
            filled = int(bar_w * pct / 100.0)
            for px in range(filled):
                t = px / max(1, bar_w - 1)
                rr = int(110 + (58 - 110) * t)
                gg = int(195 + (140 - 195) * t)
                bb = int(232 + (195 - 232) * t)
                bar_canvas.create_line(px, 0, px, bar_h, fill=f"#{rr:02x}{gg:02x}{bb:02x}")

        def _animate_indeterminate() -> None:
            if not mode["active"] or not mode["indeterminate"]:
                return
            bar_canvas.delete("all")
            bar_canvas.create_rectangle(0, 0, bar_w, bar_h, fill=C_BAR_BG, outline="")
            x = mode["pos"]
            x1, x2 = max(0, x), min(x + block, bar_w)
            if x1 < x2:
                for px in range(x1, x2):
                    t = px / max(1, bar_w - 1)
                    rr = int(110 + (58 - 110) * t)
                    gg = int(195 + (140 - 195) * t)
                    bb = int(232 + (195 - 232) * t)
                    bar_canvas.create_line(px, 0, px, bar_h, fill=f"#{rr:02x}{gg:02x}{bb:02x}")
            mode["pos"] = x + 8
            if mode["pos"] > bar_w:
                mode["pos"] = -block
            progress_win.after(25, _animate_indeterminate)

        _animate_indeterminate()

        progress_win.update_idletasks()
        width = max(win_w, progress_win.winfo_reqwidth())
        height = progress_win.winfo_reqheight()

        # Prefer centering over the app window so placement is correct on
        # multi-monitor setups; fall back to screen center when needed.
        try:
            parent_x = int(self.winfo_rootx())
            parent_y = int(self.winfo_rooty())
            parent_w = int(self.winfo_width())
            parent_h = int(self.winfo_height())
            if parent_w <= 1 or parent_h <= 1:
                raise ValueError("Parent geometry not ready")
            x = parent_x + (parent_w - width) // 2
            y = parent_y + (parent_h - height) // 2
        except Exception:
            x = (screen_w - width) // 2
            y = (screen_h - height) // 2

        vroot_x = int(progress_win.winfo_vrootx())
        vroot_y = int(progress_win.winfo_vrooty())
        vroot_w = int(progress_win.winfo_vrootwidth())
        vroot_h = int(progress_win.winfo_vrootheight())
        x = max(vroot_x, min(x, vroot_x + max(0, vroot_w - width)))
        y = max(vroot_y, min(y, vroot_y + max(0, vroot_h - height)))
        progress_win.geometry(f"{width}x{height}+{x}+{y}")
        progress_win.update()

        downloaded = 0
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Aura-Scribe-PSY-App"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                total_raw = resp.headers.get("Content-Length")
                total = int(total_raw) if total_raw and total_raw.isdigit() else int(getattr(resp, "length", 0) or 0)

                if total > 0:
                    mode["indeterminate"] = False
                    _draw_determinate(0.0)
                    pct_label.configure(text="0%")
                else:
                    progress_win.update()

                with destination.open("wb") as out_f:
                    while True:
                        chunk = resp.read(1024 * 128)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        downloaded += len(chunk)

                        if total > 0:
                            pct = min(100.0, (downloaded / total) * 100.0)
                            _draw_determinate(pct)
                            pct_label.configure(text=f"{int(pct)}%")
                            status_var.set(f"Downloaded {pct:.1f}% ({downloaded // 1024} KB of {total // 1024} KB)")
                            progress_win.title(f"Downloading Update - {pct:.1f}%")
                        else:
                            pct_label.configure(text="...")
                            status_var.set(f"Downloaded {downloaded // 1024} KB")
                            progress_win.title(f"Downloading Update - {downloaded // 1024} KB")

                        progress_win.update()
        finally:
            mode["active"] = False
            progress_win.destroy()

    def _launch_installer_after_exit(self, installer_path):
        install_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / "Aura Scribe PSY"
        app_exe = install_dir / "Aura Scribe PSY.exe"
        if not app_exe.exists() and getattr(sys, "frozen", False):
            app_exe = Path(sys.executable)
        updater_bat = UPDATE_TEMP_DIR / "run_aura_scribe_psy_update.bat"
        log_file = Path(os.environ.get("TEMP", str(Path.home()))) / "aura_scribe_psy_update.log"
        app_pid = os.getpid()

        lines = [
            "@echo off",
            "setlocal",
            f'set "INSTALLER={installer_path}"',
            f'set "APP_PID={app_pid}"',
            f'set "APP_EXE={app_exe}"',
            f'set "LOG={log_file}"',
            'echo [%date% %time%] Updater started > "%LOG%"',
            ':wait_close',
            'tasklist /FI "PID eq %APP_PID%" 2>nul | find "%APP_PID%" >nul',
            'if not errorlevel 1 (',
            '  ping 127.0.0.1 -n 2 >nul',
            '  goto wait_close',
            ')',
            'echo [%date% %time%] App exited, launching installer >> "%LOG%"',
            'start "" /wait "%INSTALLER%"',
            'echo [%date% %time%] Installer finished, errorlevel=%ERRORLEVEL% >> "%LOG%"',
            'if not "%APP_EXE%"=="" if exist "%APP_EXE%" (',
            '  echo [%date% %time%] Relaunching app: %APP_EXE% >> "%LOG%"',
            '  start "" "%APP_EXE%"',
            ')',
            'echo [%date% %time%] Update complete >> "%LOG%"',
            "endlocal",
            "exit /b 0",
        ]

        updater_bat.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
        _append_startup_log(f"Prepared updater script: {updater_bat}")
        _append_startup_log(f"Update log will be written to: {log_file}")

        comspec = os.environ.get("ComSpec", r"C:\Windows\System32\cmd.exe")
        subprocess.Popen(
            [comspec, "/d", "/c", str(updater_bat)],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def _check_for_updates(self):
        try:
            self._check_for_updates_impl()
        except Exception as ex:
            messagebox.showerror(
                "Update Check Failed",
                f"An unexpected error occurred while checking for updates:\n\n{ex}"
            )

    def _fetch_latest_release_payload(self, timeout: int = 8) -> dict:
        req = urllib.request.Request(
            GITHUB_LATEST_RELEASE_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "Aura-Scribe-PSY-App",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        if not isinstance(payload, dict):
            raise ValueError("Unexpected response from update server.")
        return payload

    def _is_aura_scribe_release(self, payload: dict) -> bool:
        if not isinstance(payload, dict):
            return False

        name = str(payload.get("name") or "").lower()
        if "aura scribe" in name or "aurascribe" in name:
            return True

        assets = payload.get("assets")
        if isinstance(assets, list):
            for asset in assets:
                if not isinstance(asset, dict):
                    continue
                asset_name = str(asset.get("name") or "").lower()
                if "aura" in asset_name and "scribe" in asset_name:
                    return True

        return False

    def _fetch_best_release_payload(self, timeout: int = 8) -> dict:
        """Return the most reliable latest published release payload.

        Uses /releases/latest first, then cross-checks /releases list and picks
        the highest non-draft, non-prerelease version to avoid transient API lag.
        """
        latest_payload = self._fetch_latest_release_payload(timeout=timeout)

        req = urllib.request.Request(
            GITHUB_RELEASES_LIST_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "Aura-Scribe-PSY-App",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                items = json.loads(resp.read().decode("utf-8", errors="replace"))
            if not isinstance(items, list):
                return latest_payload
        except Exception:
            return latest_payload

        published = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("draft") or item.get("prerelease"):
                continue
            if not self._is_aura_scribe_release(item):
                continue
            tag = item.get("tag_name") or item.get("name") or ""
            ver = self._parse_version_tuple(str(tag))
            if ver == (0, 0, 0, 0):
                continue
            published.append((ver, item))

        if not published:
            if self._is_aura_scribe_release(latest_payload):
                return latest_payload
            return latest_payload

        best_item = max(published, key=lambda pair: pair[0])[1]
        latest_ver = (0, 0, 0, 0)
        if self._is_aura_scribe_release(latest_payload):
            latest_tag = latest_payload.get("tag_name") or latest_payload.get("name") or ""
            latest_ver = self._parse_version_tuple(str(latest_tag))
        best_tag = best_item.get("tag_name") or best_item.get("name") or ""
        best_ver = self._parse_version_tuple(str(best_tag))

        if best_ver > latest_ver:
            return best_item
        return latest_payload

    def _fetch_release_payload_by_tag(self, tag: str, timeout: int = 6):
        if not tag:
            return None

        req = urllib.request.Request(
            GITHUB_RELEASE_BY_TAG_API.format(tag=tag),
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "Aura-Scribe-PSY-App",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            if not isinstance(payload, dict):
                return None
            return payload
        except Exception:
            return None

    def _version_text_to_release_tag(self, text: str) -> str:
        major, minor, patch, build = self._parse_version_tuple(text)
        if (major, minor, patch, build) == (0, 0, 0, 0):
            return ""
        return f"v{major}.{minor}.{patch}-build{build}"

    def _fetch_release_notes_for_version(self, version_text: str, timeout: int = 6):
        tag = self._version_text_to_release_tag(version_text)
        if not tag:
            return None

        payload = self._fetch_release_payload_by_tag(tag, timeout=timeout)
        if not payload:
            return None

        note_version = payload.get("tag_name") or tag
        note_body = (payload.get("body") or "").strip()
        if not note_body:
            note_body = "No detailed release notes were provided for this build."

        return self._format_tag_version(note_version), note_body

    def _release_notes_preview(self, notes: str, max_chars: int = 900, max_lines: int = 14) -> str:
        if not notes:
            return "## What's Changed\nNo detailed release notes were provided for this build."

        cleaned_lines = []
        for raw in notes.splitlines():
            line = raw.strip()
            if not line:
                continue
            cleaned_lines.append(line)
            if len(cleaned_lines) >= max_lines:
                break

        preview = "\n".join(cleaned_lines).strip()
        if not preview:
            preview = notes.strip()

        if len(preview) > max_chars:
            preview = preview[:max_chars].rstrip() + "..."

        if "what's changed" not in preview.lower():
            preview = "## What's Changed\n" + preview

        return preview

    def _check_for_updates_silent(self) -> str:
        current_ver = self._version
        current_tuple = self._parse_version_tuple(current_ver)
        self._startup_update_available = False
        self._startup_latest_version = ""

        payload = None
        last_error = None
        for timeout in (6, 12):
            try:
                _append_startup_log(
                    f"Startup update check: contacting GitHub releases API (timeout={timeout}s)"
                )
                payload = self._fetch_best_release_payload(timeout=timeout)
                break
            except urllib.error.HTTPError as ex:
                if ex.code == 404:
                    msg = "No public release found on update server."
                    self._startup_update_message = msg
                    _append_startup_log(f"Startup update check: {msg}")
                    return msg
                last_error = ex
            except Exception as ex:
                last_error = ex

        if payload is None:
            msg = "Update check skipped (offline/server unavailable)."
            self._startup_update_message = msg
            if last_error is not None:
                _append_startup_log(f"Startup update check failed: {last_error}")
            else:
                _append_startup_log("Startup update check failed: unknown error")
            return msg

        latest_tag = payload.get("tag_name") or payload.get("name") or ""
        latest_tuple = self._parse_version_tuple(latest_tag)
        latest_display = self._format_tag_version(latest_tag) if latest_tag else "Unknown"
        self._startup_latest_version = latest_display
        _append_startup_log(
            f"Startup update check: GitHub latest selected tag={latest_tag or 'unknown'}"
        )

        if latest_tuple > current_tuple:
            self._startup_update_available = True
            msg = (
                f"Update available on GitHub: {latest_display} "
                f"(current: {current_ver})"
            )
        elif latest_tuple == current_tuple:
            msg = f"Up to date: {latest_display}"
        else:
            msg = f"Running newer build than latest public release ({latest_display})."

        self._startup_update_message = msg
        _append_startup_log(f"Startup update check: {msg}")
        return msg

    def _notify_startup_update_if_available(self) -> None:
        if not self._startup_update_available:
            return

        latest = self._startup_latest_version or "Unknown"
        current = self._version or vm.get_version_string()
        open_now = messagebox.askyesno(
            "Update Available",
            "A new version was found during startup update check.\n\n"
            f"Current Version: {current}\n"
            f"Latest Version: {latest}\n\n"
            "Open update workflow now?",
            parent=self,
        )
        if open_now:
            self._check_for_updates()

    def _check_for_updates_impl(self):
        current_ver = self._version
        current_tuple = self._parse_version_tuple(current_ver)

        payload = None
        try:
            payload = self._fetch_best_release_payload(timeout=8)
        except urllib.error.HTTPError as ex:
            if ex.code == 404:
                messagebox.showinfo(
                    "Check for Updates",
                    "No public release has been found on the update server.\n\n"
                    f"Current Version: {current_ver}\n\n"
                    "You may already have the latest version.\n"
                    f"Check manually at:\n{GITHUB_RELEASES_PAGE}"
                )
            else:
                messagebox.showwarning(
                    "Check for Updates",
                    f"The update server returned an error (HTTP {ex.code}).\n\n"
                    f"Current Version: {current_ver}\n\n"
                    "You can check for updates manually at:\n"
                    f"{GITHUB_RELEASES_PAGE}"
                )
            return
        except Exception:
            messagebox.showwarning(
                "Check for Updates",
                "Could not contact the update server right now.\n\n"
                f"Current Version: {current_ver}\n\n"
                "You can still download the latest installer from:\n"
                f"{GITHUB_RELEASES_PAGE}"
            )
            return

        latest_tag = payload.get("tag_name") or payload.get("name") or ""
        latest_tuple = self._parse_version_tuple(latest_tag)
        latest_display = self._format_tag_version(latest_tag) if latest_tag else "Unknown"
        release_url = payload.get("html_url") or GITHUB_RELEASES_PAGE
        installer_asset = self._pick_installer_asset(payload)
        release_notes = (payload.get("body") or "").strip()
        if (not release_notes) and latest_tag:
            by_tag_payload = self._fetch_release_payload_by_tag(latest_tag, timeout=6)
            if by_tag_payload:
                release_notes = (by_tag_payload.get("body") or "").strip()
        if not release_notes:
            release_notes = "No detailed release notes were provided for this build."
        notes_preview = self._release_notes_preview(release_notes)

        if latest_tuple > current_tuple:
            do_update = messagebox.askyesno(
                "Update Available",
                "A newer version of Aura Scribe PSY is available.\n\n"
                f"Current Version: {current_ver}\n"
                f"Latest Version: {latest_display}\n\n"
                "What's Changed (preview):\n"
                f"{notes_preview}\n\n"
                "Download and install it now?"
            )
            if not do_update:
                return

            # Cache release notes so the next login announcement can show exactly what changed.
            # Wrap in try/except so a DB error never silently kills the update flow.
            try:
                db.set_app_preference(
                    UPDATE_ANNOUNCEMENT_NOTES_VERSION_PREF_KEY,
                    self._format_tag_version(latest_tag) if latest_tag else latest_display,
                )
                db.set_app_preference(UPDATE_ANNOUNCEMENT_NOTES_BODY_PREF_KEY, release_notes)
            except Exception:
                pass  # Non-fatal; update can still proceed without caching notes

            if not installer_asset:
                messagebox.showwarning(
                    "Update Available",
                    "No installer asset was found on the latest release.\n\n"
                    "Opening releases page instead."
                )
                webbrowser.open(release_url)
                return

            asset_url = installer_asset.get("browser_download_url")
            asset_name = installer_asset.get("name") or "Aura Scribe PSY-Installer.exe"
            if not asset_url:
                messagebox.showwarning(
                    "Update Available",
                    "Could not determine the download URL for the installer.\n\n"
                    "Opening the releases page instead."
                )
                webbrowser.open(release_url)
                return

            UPDATE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
            installer_path = UPDATE_TEMP_DIR / asset_name

            try:
                self._download_file_with_progress(asset_url, installer_path)
                backup_path = self._backup_database_for_update()
            except Exception as ex:
                messagebox.showerror(
                    "Update Failed",
                    "Could not download the installer automatically.\n\n"
                    f"Error: {ex}\n\n"
                    "Opening releases page instead."
                )
                webbrowser.open(release_url)
                return

            backup_msg = f"\nDatabase backup created at:\n{backup_path}" if backup_path else ""
            proceed = messagebox.askyesno(
                "Ready to Install Update",
                "The installer has been downloaded.\n\n"
                "Aura Scribe PSY will now close, install the update, and reopen automatically.\n"
                "Your user profiles, patient records, and billing data will be preserved."
                f"{backup_msg}\n\n"
                "What's Changed (preview):\n"
                f"{notes_preview}\n\n"
                "Continue?"
            )
            if not proceed:
                return

            try:
                self._launch_installer_after_exit(installer_path)
            except Exception as ex:
                messagebox.showerror(
                    "Update Failed",
                    f"Could not start the installer: {ex}"
                )
                return

            self.after(150, self._on_close)
            return

        if latest_tuple == current_tuple:
            messagebox.showinfo(
                "Check for Updates",
                "Aura Scribe PSY is up to date.\n\n"
                f"Current Version: {current_ver}\n"
                f"Latest Version: {latest_display}"
            )
            return

        messagebox.showinfo(
            "Check for Updates",
            "You are running a newer build than the latest public release.\n\n"
            f"Current Version: {current_ver}\n"
            f"Latest Release: {latest_display}"
        )

    def _migration_help(self):
        messagebox.showinfo(
            "Data Migration Help",
            "To migrate your existing data from another system:\n\n"
            "1. Open your current software and go to its export/report tools.\n"
            "2. Export each dataset as CSV (or spreadsheet format, if available):\n"
            "   • Patient records → patients.csv\n"
            "   • Session notes   → sessions.csv\n"
            "   • Payments        → billing.csv\n"
            "3. Go to Settings/Import tab in Aura Scribe PSY\n"
            "4. Use the 'Import Patients/Sessions/Billing (CSV)' buttons\n\n"
            "The importer is flexible with column names and will\n"
            "attempt to map fields automatically.\n\n"
            "For billing and CMS-1500, your settings are entered once\n"
            "in Settings -> Provider/Practice."
        )

    def _scan_dictation_apps_async(self):
        """Background scan for dictation apps at startup. Caches result for UI dialogs."""
        def _scan_thread():
            try:
                detected = self._find_dictation_apps()
                self._cached_dictation_apps = detected
                installed_count = sum(1 for _, exe in detected if exe)
                if installed_count > 0:
                    self._startup_dictation_scan_message = f"Dictation scan complete: {installed_count} installed app(s) found."
                else:
                    self._startup_dictation_scan_message = "Dictation scan complete: no installed dictation apps found."
            except Exception as e:
                _append_startup_log(f"Dictation scan error: {e}")
                self._cached_dictation_apps = [("Windows Built-in Dictation (Win+H)", "")]
                self._startup_dictation_scan_message = "Dictation scan complete: using Windows built-in dictation fallback."

        t = threading.Thread(target=_scan_thread, daemon=True)
        t.start()

    @staticmethod
    def _find_dictation_apps():
        """Search for installed dictation apps on Windows. Returns list of (label, exe_path)."""
        return _find_dictation_apps_systemwide()

    def _on_close(self):
        self.destroy()


# ─── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Enable per-monitor DPI awareness on Windows so winfo_screenwidth/height
    # returns physical pixels and widgets are sized correctly on HiDPI displays.
    if sys.platform == "win32":
        try:
            import ctypes
            # Per-Monitor v2 awareness (Windows 10 1703+)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    _install_crash_logger()
    try:
        db.initialize_db()
        _startup_self_check()
        app = TheraTrakApp()
        app.withdraw()

        splash = StartupLoadingScreen(app)
        splash_started = time.perf_counter()

        def _splash_step(percent: float, message: str, pause_seconds: float = 0.55) -> None:
            splash.set_step(percent, message)
            app.update_idletasks()
            if pause_seconds > 0:
                time.sleep(pause_seconds)

        _splash_step(12, "Loading application components...")
        _splash_step(38, "Preparing secure sign-in...")
        _splash_step(62, "Checking GitHub for updates...", pause_seconds=0.45)
        startup_update_msg = app._check_for_updates_silent()
        _splash_step(86, startup_update_msg, pause_seconds=0.55)
        _splash_step(100, "Opening sign-in...", pause_seconds=0.35)

        min_visible_seconds = 3.2
        elapsed = time.perf_counter() - splash_started
        if elapsed < min_visible_seconds:
            time.sleep(min_visible_seconds - elapsed)

        splash.close()

        login = LoginDialog(app)
        app.wait_window(login)

        if login.user:
            app.set_logged_in_user(login.user)
            if not app.ensure_license_access():
                app.destroy()
                raise SystemExit(0)
            if login.winfo_exists():
                login.destroy()
            app.deiconify()
            app.show_post_update_announcement_if_needed()
            app.update_idletasks()
            startup_messages = [
                msg for msg in (app._startup_dictation_scan_message, app._startup_update_message) if msg
            ]
            if startup_messages:
                app._status_lbl.config(text=" | ".join(startup_messages))
            app._notify_startup_update_if_available()
            try:
                app.state("zoomed")
            except tk.TclError:
                app.geometry(f"{SCREEN_W}x{SCREEN_H}+0+0")
            app.mainloop()
        else:
            app.destroy()
    except Exception:
        _append_startup_log("Fatal startup failure:")
        _append_startup_log(traceback.format_exc().rstrip())
        raise
