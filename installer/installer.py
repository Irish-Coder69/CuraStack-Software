from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
import time
import winreg
import json
import ctypes
from uuid import UUID
from pathlib import Path
from tkinter import DoubleVar, Tk, Toplevel, StringVar, filedialog, messagebox, ttk


APP_NAME = "CuraStack Software"
APP_EXE = "CuraStack Software.exe"
UNINSTALL_EXE = "CuraStack Software Uninstaller.exe"
LEGACY_APP_DIR_NAMES = ("AuraScribe", "Aura Scribe PSY")
LEGACY_APP_EXE_NAMES = ("AuraScribe.exe", "Aura Scribe PSY.exe")
APP_BUNDLE_DIR = "app"
UNINSTALL_CMD = "Uninstall CuraStack Software.cmd"
UNINSTALL_SHORTCUT_NAME = "Uninstall CuraStack Software.lnk"
ICON_FILE = "CuraStack Software.ico"
SETUP_WIZARD_JPG = "CuraStack Software.jpg"
VERSION_FILE = "version.json"
DB_FILE_NAME = "theratrak.db"
UNINSTALL_KEY_CURRENT = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\CuraStack Software"
UNINSTALL_KEYS_LEGACY = (
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall\AuraScribe",
    r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Aura Scribe PSY",
)
LEGACY_START_MENU_FOLDERS = ("Thorough Track Pro", "TheraTrak-Pro")
LEGACY_ROOT_SHORTCUTS = ("TheraTrak Pro.lnk", "Uninstall TheraTrak Pro.lnk")

# Even older standalone data folder used before the app lived under Programs\<name>\theratrak.db.
# Schema there (clients/therapy_sessions/billing_records/users, etc.) predates the current
# patients/session_notes/users schema, so it needs field-mapping instead of a raw file copy.
LEGACY_THERATRAK_PRO_DB = Path(os.environ.get("LOCALAPPDATA", "")) / "TheraTrak Pro" / "Data" / "theratrak_v2.db"

# Minimal current-schema tables needed by _import_legacy_theratrak_pro_schema(). A brand new
# install has no theratrak.db yet (the app itself creates it on first launch via
# database.initialize_db()), so these must be created before any field-mapped rows can be
# inserted. Kept in sync with database.py's schema for the tables this importer writes to.
_CURRENT_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS patients (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    last_name        TEXT NOT NULL,
    first_name       TEXT NOT NULL,
    middle_name      TEXT DEFAULT '',
    dob              TEXT DEFAULT '',
    sex              TEXT DEFAULT 'U',
    ssn              TEXT DEFAULT '',
    address          TEXT DEFAULT '',
    address2         TEXT DEFAULT '',
    city             TEXT DEFAULT '',
    state            TEXT DEFAULT '',
    zip              TEXT DEFAULT '',
    phone_home       TEXT DEFAULT '',
    phone_cell       TEXT DEFAULT '',
    phone_work       TEXT DEFAULT '',
    email            TEXT DEFAULT '',
    ins_name         TEXT DEFAULT '',
    ins_id           TEXT DEFAULT '',
    ins_group        TEXT DEFAULT '',
    ins_plan         TEXT DEFAULT '',
    ins_holder       TEXT DEFAULT '',
    ins_holder_dob   TEXT DEFAULT '',
    ins_holder_sex   TEXT DEFAULT '',
    ins_relation     TEXT DEFAULT 'Self',
    ins_address      TEXT DEFAULT '',
    ins_city         TEXT DEFAULT '',
    ins_state        TEXT DEFAULT '',
    ins_zip          TEXT DEFAULT '',
    ins_phone        TEXT DEFAULT '',
    ins2_name        TEXT DEFAULT '',
    ins2_id          TEXT DEFAULT '',
    ins2_group       TEXT DEFAULT '',
    ins2_plan        TEXT DEFAULT '',
    ins2_holder      TEXT DEFAULT '',
    ins2_relation    TEXT DEFAULT '',
    dx1              TEXT DEFAULT '',
    dx2              TEXT DEFAULT '',
    dx3              TEXT DEFAULT '',
    dx4              TEXT DEFAULT '',
    dx5              TEXT DEFAULT '',
    dx6              TEXT DEFAULT '',
    dx7              TEXT DEFAULT '',
    dx8              TEXT DEFAULT '',
    dx9              TEXT DEFAULT '',
    dx10             TEXT DEFAULT '',
    dx11             TEXT DEFAULT '',
    dx12             TEXT DEFAULT '',
    emr_name         TEXT DEFAULT '',
    emr_relation     TEXT DEFAULT '',
    emr_phone        TEXT DEFAULT '',
    referring_name   TEXT DEFAULT '',
    referring_taxonomy TEXT DEFAULT '',
    referring_npi    TEXT DEFAULT '',
    illness_date     TEXT DEFAULT '',
    illness_date_qual TEXT DEFAULT '',
    other_date       TEXT DEFAULT '',
    other_date_qual  TEXT DEFAULT '',
    intake_date      TEXT DEFAULT '',
    sig_on_file_date TEXT DEFAULT '',
    status           TEXT DEFAULT 'Active',
    notes            TEXT DEFAULT '',
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS session_notes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id       INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    session_date     TEXT NOT NULL,
    start_time       TEXT DEFAULT '',
    end_time         TEXT DEFAULT '',
    duration         INTEGER DEFAULT 50,
    session_type     TEXT DEFAULT 'Individual',
    place_of_service TEXT DEFAULT '11',
    cpt_code         TEXT DEFAULT '90834',
    cpt_modifier     TEXT DEFAULT '',
    dx1              TEXT DEFAULT '',
    dx2              TEXT DEFAULT '',
    dx3              TEXT DEFAULT '',
    dx4              TEXT DEFAULT '',
    dx5              TEXT DEFAULT '',
    dx6              TEXT DEFAULT '',
    dx7              TEXT DEFAULT '',
    dx8              TEXT DEFAULT '',
    dx9              TEXT DEFAULT '',
    dx10             TEXT DEFAULT '',
    dx11             TEXT DEFAULT '',
    dx12             TEXT DEFAULT '',
    fee              REAL DEFAULT 0.0,
    note_text        TEXT DEFAULT '',
    goals            TEXT DEFAULT '',
    interventions    TEXT DEFAULT '',
    response         TEXT DEFAULT '',
    plan             TEXT DEFAULT '',
    signed           INTEGER DEFAULT 0,
    signed_date      TEXT DEFAULT '',
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS billing_records (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id       INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    session_id       INTEGER REFERENCES session_notes(id),
    record_date      TEXT NOT NULL,
    service_date     TEXT DEFAULT '',
    description      TEXT DEFAULT '',
    charge           REAL DEFAULT 0.0,
    payment          REAL DEFAULT 0.0,
    payment_type     TEXT DEFAULT '',
    check_number     TEXT DEFAULT '',
    ins_payment      REAL DEFAULT 0.0,
    adjustment       REAL DEFAULT 0.0,
    balance          REAL DEFAULT 0.0,
    claim_number     TEXT DEFAULT '',
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    username         TEXT NOT NULL UNIQUE,
    password_hash    TEXT NOT NULL,
    password_salt    TEXT NOT NULL,
    first_name       TEXT NOT NULL,
    middle_name      TEXT DEFAULT '',
    last_name        TEXT NOT NULL,
    suffix           TEXT DEFAULT '',
    email            TEXT DEFAULT '',
    phone            TEXT DEFAULT '',
    role             TEXT DEFAULT 'User',
    address          TEXT DEFAULT '',
    city             TEXT DEFAULT '',
    state            TEXT DEFAULT '',
    zip              TEXT DEFAULT '',
    license_number   TEXT DEFAULT '',
    npi_number       TEXT DEFAULT '',
    billing_address  TEXT DEFAULT '',
    billing_city     TEXT DEFAULT '',
    billing_state    TEXT DEFAULT '',
    billing_zip      TEXT DEFAULT '',
    is_active        INTEGER DEFAULT 1,
    created_at       TEXT DEFAULT (datetime('now')),
    last_login       TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS bookkeeping_entries (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date       TEXT NOT NULL,
    check_number     TEXT DEFAULT '',
    payee            TEXT DEFAULT '',
    memo             TEXT DEFAULT '',
    is_tax_deductible INTEGER DEFAULT 0,
    inc_client       REAL DEFAULT 0.0,
    inc_insurance    REAL DEFAULT 0.0,
    inc_other        REAL DEFAULT 0.0,
    exp_rent         REAL DEFAULT 0.0,
    exp_utilities    REAL DEFAULT 0.0,
    exp_office       REAL DEFAULT 0.0,
    exp_insurance    REAL DEFAULT 0.0,
    exp_phone        REAL DEFAULT 0.0,
    exp_professional REAL DEFAULT 0.0,
    exp_advertising  REAL DEFAULT 0.0,
    exp_misc         REAL DEFAULT 0.0,
    created_at       TEXT DEFAULT (datetime('now'))
);
"""


def _find_bundled_python_dll(app_bundle_dir: Path) -> Path | None:
    """Return the path relative to app_bundle_dir of the Python runtime DLL.

    PyInstaller places the DLL inside _internal/  (e.g. python311.dll or
    python312.dll depending on the build Python version).  Probing for it
    at runtime avoids a hardcoded version number that breaks if the build
    environment is ever upgraded.
    """
    internal = app_bundle_dir / "_internal"
    if internal.is_dir():
        for dll in sorted(internal.glob("python3*.dll")):
            return Path("_internal") / dll.name
    return None


def _is_app_running() -> bool:
    """Return True if the packaged app executable is currently running."""
    exe_names = (APP_EXE, *LEGACY_APP_EXE_NAMES)
    try:
        for exe_name in exe_names:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/NH", "/FO", "CSV"],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if exe_name.lower() in result.stdout.lower():
                return True
        return False
    except OSError:
        return False


def _stop_running_app() -> None:
    # Best-effort stop so install can replace locked binaries.
    for exe_name in (APP_EXE, *LEGACY_APP_EXE_NAMES):
        try:
            subprocess.run(
                ["taskkill", "/IM", exe_name, "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            pass


def _wait_for_app_exit(timeout: float = 10.0) -> bool:
    """Wait up to *timeout* seconds for the app to fully exit.

    Returns True when the process is gone, False if it is still running
    after the timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _is_app_running():
            return True
        time.sleep(0.5)
    return not _is_app_running()


def _is_skippable_shutil_error(ex: shutil.Error) -> bool:
    """Return True if copytree failed only on locked files that already exist at destination."""
    details = ex.args[0] if ex.args and isinstance(ex.args[0], list) else []
    if not details:
        return False
    for item in details:
        if not isinstance(item, tuple) or len(item) < 3:
            return False
        _src, dst, msg = item[0], item[1], str(item[2])
        if "permission denied" not in msg.lower():
            return False
        try:
            if not Path(dst).exists():
                return False
        except OSError:
            return False
    return True


def _copy_with_retries(src: Path, dst: Path, attempts: int = 8) -> None:
    for attempt in range(1, attempts + 1):
        try:
            if src.is_dir():
                if dst.exists():
                    if not dst.is_dir() or dst.is_symlink():
                        dst.unlink(missing_ok=True)
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            return
        except PermissionError:
            if attempt >= attempts:
                raise
            _stop_running_app()
            time.sleep(0.75)
        except shutil.Error as ex:
            # copytree can raise shutil.Error when one or more files are locked.
            # If locked files already exist at destination, keep install moving.
            if _is_skippable_shutil_error(ex):
                return
            if attempt >= attempts:
                raise ex
            _stop_running_app()
            time.sleep(0.75)
        except OSError:
            if attempt >= attempts:
                raise
            _stop_running_app()
            time.sleep(1.5)


def _copy_app_bundle_with_progress(
    app_bundle: Path,
    target: Path,
    progress_cb,
) -> None:
    """Copy bundled app payload file-by-file so progress updates stay responsive."""
    file_pairs: list[tuple[Path, Path]] = []

    for item in sorted(app_bundle.iterdir(), key=lambda p: p.name.lower()):
        dst_item = target / item.name
        if item.is_dir():
            dst_item.mkdir(parents=True, exist_ok=True)
            for root, dirnames, filenames in os.walk(item):
                dirnames.sort()
                filenames.sort()
                root_path = Path(root)
                rel_root = root_path.relative_to(item)
                for dirname in dirnames:
                    (dst_item / rel_root / dirname).mkdir(parents=True, exist_ok=True)
                for filename in filenames:
                    if filename.lower() == DB_FILE_NAME:
                        # Never overwrite user data from installer payload.
                        continue
                    src_file = root_path / filename
                    dst_file = dst_item / rel_root / filename
                    file_pairs.append((src_file, dst_file))
        else:
            if item.name.lower() == DB_FILE_NAME:
                continue
            file_pairs.append((item, dst_item))

    total_files = max(1, len(file_pairs))
    for index, (src_file, dst_file) in enumerate(file_pairs, start=1):
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        _copy_with_retries(src_file, dst_file)
        if index == 1 or index == total_files or index % 25 == 0:
            progress_cb(index, total_files, src_file.name)


def bundled_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def install_dir() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "Programs" / APP_NAME


def _candidate_install_dirs() -> list[Path]:
    base = Path(os.environ["LOCALAPPDATA"]) / "Programs"
    names = [APP_NAME, *LEGACY_APP_DIR_NAMES]
    seen: set[str] = set()
    out: list[Path] = []
    for name in names:
        p = base / name
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _read_install_location_from_registry(key_path: str) -> Path | None:
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "InstallLocation")
            location = Path(str(value)).expanduser()
            if location.exists() and location.is_dir():
                return location
        except (FileNotFoundError, PermissionError, OSError, ValueError, TypeError):
            continue
    return None


def detect_existing_install_dir() -> Path | None:
    for key_path in (UNINSTALL_KEY_CURRENT, *UNINSTALL_KEYS_LEGACY):
        from_reg = _read_install_location_from_registry(key_path)
        if from_reg is not None:
            return from_reg

    for candidate in _candidate_install_dirs():
        if (candidate / APP_EXE).exists():
            return candidate
        for legacy_exe in LEGACY_APP_EXE_NAMES:
            if (candidate / legacy_exe).exists():
                return candidate
    return None


def _sqlite_has_table(db_path: Path, table: str) -> bool:
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            return row is not None
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return False


def _hash_password(password: str, salt_hex: str) -> str:
    salt = bytes.fromhex(salt_hex)
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000).hex()


def _classify_income(category: str, payment_source: str) -> str:
    text = f"{category or ''} {payment_source or ''}".lower()
    if "insur" in text:
        return "inc_insurance"
    if "client" in text or "self" in text or "copay" in text:
        return "inc_client"
    return "inc_other"


def _classify_expense(category_name: str) -> str:
    text = (category_name or "").lower()
    if "rent" in text:
        return "exp_rent"
    if "utilit" in text:
        return "exp_utilities"
    if "office" in text or "supply" in text or "supplies" in text:
        return "exp_office"
    if "insur" in text:
        return "exp_insurance"
    if "phone" in text or "internet" in text or "communication" in text:
        return "exp_phone"
    if "professional" in text or "license" in text or "cle" in text or "continuing" in text:
        return "exp_professional"
    if "advertis" in text or "marketing" in text:
        return "exp_advertising"
    return "exp_misc"


def _import_legacy_theratrak_pro_schema(source_db: Path, target_db: Path) -> bool:
    """Field-map an old TheraTrak Pro era DB (clients/therapy_sessions/...) into the
    current schema (patients/session_notes/billing_records/users/bookkeeping_entries).
    Used when a straight file copy would be schema-incompatible. Returns True on success."""
    import datetime as _dt

    try:
        src = sqlite3.connect(str(source_db))
        src.row_factory = sqlite3.Row
        dst = sqlite3.connect(str(target_db))
        dst.row_factory = sqlite3.Row
        dst.execute("PRAGMA foreign_keys = OFF")
        dst.executescript(_CURRENT_SCHEMA_DDL)

        now = _dt.datetime.now().isoformat()

        for u in src.execute("SELECT * FROM users").fetchall():
            existing = dst.execute(
                "SELECT id FROM users WHERE lower(username)=lower(?)", (u["username"],)
            ).fetchone()
            if existing:
                continue
            full_name = (u["full_name"] or "").strip()
            parts = full_name.split()
            if len(parts) >= 3:
                first, middle, last = parts[0], " ".join(parts[1:-1]), parts[-1]
            elif len(parts) == 2:
                first, middle, last = parts[0], "", parts[1]
            else:
                first, middle, last = (full_name or u["username"]), "", ""
            salt_hex = secrets.token_hex(16)
            pw_hash = _hash_password(u["password"] or "", salt_hex)
            dst.execute(
                """INSERT INTO users
                   (username, password_hash, password_salt, first_name, middle_name, last_name,
                    suffix, email, phone, role, license_number, npi_number, billing_address,
                    is_active, created_at, last_login)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                (
                    u["username"], pw_hash, salt_hex, first, middle, last,
                    u["suffix"] or "", u["email"] or "", u["phone"] or "", "Admin",
                    u["license_number"] or "", u["npi_number"] or "", u["billing_address"] or "",
                    u["created_at"] or now, u["last_login"] or "",
                ),
            )

        client_to_patient: dict[int, int] = {}
        for c in src.execute("SELECT * FROM clients").fetchall():
            cur = dst.execute(
                """INSERT INTO patients
                   (last_name, first_name, middle_name, dob, sex, address, city, state, zip,
                    phone_home, email, ins_name, ins_id, ins_group, ins_holder, ins_holder_dob,
                    ins_holder_sex, ins_relation, ins_address, ins_city, ins_state, ins_zip,
                    ins_phone, referring_name, intake_date, sig_on_file_date, status, notes,
                    emr_name, emr_phone, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    c["last_name"] or "", c["first_name"] or "", c["middle_name"] or "",
                    c["date_of_birth"] or "", (c["sex"] or "U")[:1], c["address"] or "",
                    c["city"] or "", c["state"] or "", c["zip_code"] or "",
                    c["phone"] or "", c["email"] or "",
                    c["insurance_provider"] or "", c["insurance_id"] or "",
                    c["insurance_group_number"] or "", c["insured_name"] or "",
                    c["insured_dob"] or "", (c["insured_sex"] or "")[:1],
                    c["relationship_to_insured"] or "Self", c["insured_address"] or "",
                    c["insured_city"] or "", c["insured_state"] or "", c["insured_zip"] or "",
                    c["insured_phone"] or "", c["referral_source"] or "",
                    c["intake_date"] or "", c["signature_date"] or "",
                    c["status"] or "Active", c["notes"] or "",
                    c["emergency_contact"] or "", c["emergency_phone"] or "", c["created_at"] or now,
                ),
            )
            client_to_patient[c["client_id"]] = cur.lastrowid

        session_to_note: dict[int, int] = {}
        for s in src.execute("SELECT * FROM therapy_sessions").fetchall():
            patient_id = client_to_patient.get(s["client_id"])
            if patient_id is None:
                continue
            extra_bits = []
            if s["presenting_issues"]:
                extra_bits.append(f"Presenting issues: {s['presenting_issues']}")
            if s["homework_assigned"]:
                extra_bits.append(f"Homework assigned: {s['homework_assigned']}")
            if s["therapist_name"]:
                extra_bits.append(f"Therapist: {s['therapist_name']}")
            if s["session_number"]:
                extra_bits.append(f"Session #: {s['session_number']}")
            note_text = s["progress_notes"] or ""
            if extra_bits:
                note_text = (note_text + "\n\n[Imported from legacy data]\n" +
                             "\n".join(extra_bits)).strip()
            cur = dst.execute(
                """INSERT INTO session_notes
                   (patient_id, session_date, start_time, duration, session_type,
                    note_text, interventions, response, plan, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    patient_id, s["session_date"] or "", s["session_time"] or "",
                    s["duration_minutes"] or 50, s["session_type"] or "Individual",
                    note_text, s["interventions"] or "", s["clinical_observations"] or "",
                    s["next_session_plan"] or "", s["created_at"] or now,
                ),
            )
            session_to_note[s["session_id"]] = cur.lastrowid

        for b in src.execute("SELECT * FROM billing_records").fetchall():
            patient_id = client_to_patient.get(b["client_id"])
            if patient_id is None:
                continue
            note_id = session_to_note.get(b["session_id"])
            dst.execute(
                """INSERT INTO billing_records
                   (patient_id, session_id, record_date, service_date, description, charge,
                    payment, payment_type, ins_payment, balance, claim_number, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    patient_id, note_id, b["service_date"] or "", b["service_date"] or "",
                    b["service_description"] or "", b["fee_amount"] or 0.0,
                    b["client_paid"] or 0.0, b["payment_status"] or "",
                    b["insurance_paid"] or 0.0, b["balance_due"] or 0.0,
                    b["invoice_number"] or "", b["created_at"] or now,
                ),
            )
            if note_id is not None:
                dx_codes = [
                    b["diagnosis_code"], b["diagnosis_code_b"], b["diagnosis_code_c"],
                    b["diagnosis_code_d"], b["diagnosis_code_e"], b["diagnosis_code_f"],
                    b["diagnosis_code_g"], b["diagnosis_code_h"], b["diagnosis_code_i"],
                    b["diagnosis_code_j"], b["diagnosis_code_k"], b["diagnosis_code_l"],
                ]
                dx_cols = ",".join(f"dx{i + 1}=?" for i in range(12))
                dst.execute(
                    f"UPDATE session_notes SET cpt_code=?, {dx_cols} WHERE id=?",
                    [b["cpt_code"] or "90834", *[d or "" for d in dx_codes], note_id],
                )

        expense_categories = {
            r["category_id"]: r["category_name"]
            for r in src.execute("SELECT category_id, category_name FROM expense_categories")
        }
        for inc in src.execute("SELECT * FROM income_transactions"):
            col = _classify_income(inc["category"], inc["payment_source"])
            dst.execute(
                f"""INSERT INTO bookkeeping_entries
                    (entry_date, check_number, payee, memo, {col}, created_at)
                    VALUES (?,?,?,?,?,?)""",
                (
                    inc["transaction_date"] or "", inc["reference_number"] or "",
                    inc["payment_source"] or "", inc["description"] or "",
                    inc["amount"] or 0.0, inc["created_at"] or now,
                ),
            )
        for exp in src.execute("SELECT * FROM expense_transactions"):
            cat_name = expense_categories.get(exp["category_id"], exp["expense_type"] or "")
            col = _classify_expense(cat_name)
            dst.execute(
                f"""INSERT INTO bookkeeping_entries
                    (entry_date, check_number, payee, memo, is_tax_deductible, {col}, created_at)
                    VALUES (?,?,?,?,?,?,?)""",
                (
                    exp["transaction_date"] or "", exp["reference_number"] or "",
                    exp["vendor_name"] or "", exp["description"] or "",
                    1 if exp["is_tax_deductible"] else 0,
                    exp["amount"] or 0.0, exp["created_at"] or now,
                ),
            )

        # Preserve tables with no current UI equivalent verbatim, so nothing is lost.
        for table in ("treatment_plans", "assessments", "chart_of_accounts",
                       "accounts_payable", "accounts_receivable", "licenses", "cpt_codes"):
            try:
                cols = [r[1] for r in src.execute(f"PRAGMA table_info({table})")]
            except sqlite3.Error:
                continue
            if not cols:
                continue
            col_defs = ",".join(f'"{c}" TEXT' for c in cols)
            dst.execute(f'CREATE TABLE IF NOT EXISTS legacy_{table} ({col_defs})')
            rows = src.execute(f"SELECT * FROM {table}").fetchall()
            if rows:
                placeholders = ",".join("?" * len(cols))
                col_list = ",".join(f'"{c}"' for c in cols)
                dst.executemany(
                    f'INSERT INTO legacy_{table} ({col_list}) VALUES ({placeholders})',
                    [tuple(r) for r in rows],
                )

        dst.commit()
        src.close()
        dst.close()
        return True
    except (sqlite3.Error, OSError):
        return False


def _migrate_legacy_database(target: Path) -> Path | None:
    """Bring existing user data into a fresh install if the target has no DB yet.

    Checks two kinds of legacy sources:
      1. Same-schema theratrak.db in another Programs\\<LegacyName> install folder
         (AuraScribe / Aura Scribe PSY) - straight file copy.
      2. Old TheraTrak Pro era DB (clients/therapy_sessions/... schema) at
         %LOCALAPPDATA%\\TheraTrak Pro\\Data\\theratrak_v2.db - field-mapped import.

    A same-schema source is preferred when both exist, since it's an exact copy.
    """
    target_db = target / DB_FILE_NAME
    if target_db.exists():
        return None

    target_resolved = target.resolve()
    candidates: list[Path] = []
    for install_path in _candidate_install_dirs():
        try:
            same_path = install_path.resolve() == target_resolved
        except OSError:
            same_path = False
        if same_path:
            continue
        db_path = install_path / DB_FILE_NAME
        if db_path.exists() and db_path.is_file():
            candidates.append(db_path)

    same_schema_candidates = [c for c in candidates if _sqlite_has_table(c, "patients")]
    if same_schema_candidates:
        source_db = max(same_schema_candidates, key=lambda p: p.stat().st_mtime)
        target_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_db, target_db)
        return source_db

    # Old-schema candidates found under a Programs\<LegacyName> folder (unlikely, but
    # handled defensively) plus the dedicated TheraTrak Pro data folder.
    old_schema_candidates = [c for c in candidates if _sqlite_has_table(c, "clients")]
    if LEGACY_THERATRAK_PRO_DB.exists() and LEGACY_THERATRAK_PRO_DB.is_file():
        old_schema_candidates.append(LEGACY_THERATRAK_PRO_DB)
    if not old_schema_candidates:
        return None

    source_db = max(old_schema_candidates, key=lambda p: p.stat().st_mtime)
    target_db.parent.mkdir(parents=True, exist_ok=True)
    # initialize_db()'s schema (patients/session_notes/... tables) must already exist in
    # target_db before field-mapped inserts can run; the caller creates it right after
    # copying the app bundle, so target_db exists as an empty-schema DB at this point.
    if _import_legacy_theratrak_pro_schema(source_db, target_db):
        return source_db
    return None


def _can_write_to_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".curastack_write_test.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _apply_window_icon(window, icon_candidate: Path | None = None) -> None:
    icon_path = icon_candidate or (bundled_dir() / ICON_FILE)
    if icon_path.exists():
        try:
            window.iconbitmap(default=str(icon_path))
        except Exception:
            pass


def _setup_wizard_image_candidates() -> list[Path]:
    base = bundled_dir()
    return [
        base / SETUP_WIZARD_JPG,
        base / "assets" / SETUP_WIZARD_JPG,
        Path.cwd() / SETUP_WIZARD_JPG,
        Path.home() / "Pictures" / APP_NAME / SETUP_WIZARD_JPG,
    ]


def _load_setup_wizard_banner(width: int, height: int):
    try:
        from PIL import Image, ImageOps, ImageTk
    except Exception:
        return None

    for candidate in _setup_wizard_image_candidates():
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            with Image.open(candidate) as source:
                source = source.convert("RGB")
                fit_mode = getattr(Image, "Resampling", Image).LANCZOS
                # Keep the full artwork visible and pad to the banner size.
                rendered = ImageOps.pad(
                    source,
                    (width, height),
                    method=fit_mode,
                    color=(17, 40, 60),
                    centering=(0.5, 0.5),
                )
            return ImageTk.PhotoImage(rendered)
        except Exception:
            continue
    return None


def choose_install_dir(root: Tk, default_path: Path) -> Path | None:
    import tkinter as tk

    # ── Palette ─────────────────────────────────────────────────────────────
    # Header: warm sky-blue gradient (uplifting, open, calming)
    C_GRAD_TOP  = (110, 195, 232)   # #6ec3e8  — light sky blue
    C_GRAD_BOT  = (58,  140, 195)   # #3a8cc3  — medium sky blue
    C_HDR_TEXT  = "#ffffff"
    C_HDR_SUB   = "#d6eef8"
    C_DIVIDER   = "#3a8cc3"
    C_BODY_BG   = "#f5f7fa"
    C_LABEL_FG  = "#1a2535"
    C_SUB_FG    = "#556070"
    C_ENTRY_BG  = "#ffffff"
    C_ENTRY_HI  = "#3a8cc3"
    C_BROWSE_BG = "#ddeef8"
    C_BROWSE_FG = "#1d5f8a"
    C_BTN_INST  = "#3a8cc3"
    C_BTN_CNCL  = "#6b7280"
    C_BTN_FG    = "#ffffff"
    C_BAR_BG    = "#e4ecf4"

    FONT_TITLE  = ("Segoe UI", 17, "bold")
    FONT_SUB    = ("Segoe UI", 9)
    FONT_LABEL  = ("Segoe UI", 10)
    FONT_ENTRY  = ("Segoe UI", 10)
    FONT_BTN    = ("Segoe UI", 10, "bold")
    FONT_BROWSE = ("Segoe UI", 9)

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    DIALOG_W = min(760, max(620, screen_w - 120))
    HEADER_H = 310 if screen_h >= 900 else 240

    dialog = Toplevel(root)
    dialog.title(f"{APP_NAME} Setup Wizard")
    dialog.resizable(False, False)
    dialog.configure(bg=C_BODY_BG)
    dialog.attributes("-topmost", True)
    dialog.grab_set()
    dialog.minsize(DIALOG_W, 1)
    _apply_window_icon(dialog)

    # ── Header canvas: gradient + "A-with-waveform" logo ────────────────────
    hdr = tk.Canvas(dialog, width=DIALOG_W, height=HEADER_H, highlightthickness=0)
    hdr.pack(fill="x")

    banner_photo = _load_setup_wizard_banner(DIALOG_W, HEADER_H)
    if banner_photo is not None:
        hdr.create_image(DIALOG_W // 2, HEADER_H // 2, image=banner_photo, anchor="center")
        hdr.image = banner_photo
        hdr.create_rectangle(0, 0, DIALOG_W, HEADER_H, outline="#3a8cc3", width=2)
    else:
        # Gradient fill
        r0, g0, b0 = C_GRAD_TOP
        r1, g1, b1 = C_GRAD_BOT
        for i in range(HEADER_H):
            t = i / max(1, HEADER_H - 1)
            r = int(r0 + (r1 - r0) * t)
            g = int(g0 + (g1 - g0) * t)
            b = int(b0 + (b1 - b0) * t)
            hdr.create_line(0, i, DIALOG_W, i, fill=f"#{r:02x}{g:02x}{b:02x}")

        # ── Logo: clean thin-lined "A" with waveform crossbar ───────────────
        cx = DIALOG_W // 2
        a_y = 8
        b_y = 52
        hw = 24

        hdr.create_line(cx, a_y, cx - hw, b_y, fill="white", width=1.8, capstyle="round")
        hdr.create_line(cx, a_y, cx + hw, b_y, fill="white", width=1.8, capstyle="round")

        t_c = 0.55
        wf_y = a_y + (b_y - a_y) * t_c
        wf_xl = cx - hw * t_c
        wf_xr = cx + hw * t_c

        wf_nodes = [
            (-1.00, 0.00),
            (-0.80, -0.30),
            (-0.58, -0.80),
            (-0.36, 0.25),
            (-0.14, -1.00),
            (0.08, 0.40),
            (0.28, -0.70),
            (0.50, 0.20),
            (0.72, -0.50),
            (0.88, -0.20),
            (1.00, 0.00),
        ]
        amp = 5.0
        wf_pts = []
        span = wf_xr - wf_xl
        for nx, ny in wf_nodes:
            wf_pts.append(wf_xl + (nx + 1) / 2.0 * span)
            wf_pts.append(wf_y + ny * amp)

        hdr.create_line(
            *wf_pts,
            fill="white",
            width=1.6,
            smooth=True,
            capstyle="round",
            joinstyle="round",
        )

        hdr.create_text(cx, b_y + 18, text=APP_NAME, font=FONT_TITLE, fill=C_HDR_TEXT, anchor="center")
        hdr.create_text(cx, b_y + 40, text="Setup Wizard", font=FONT_SUB, fill=C_HDR_SUB, anchor="center")

    # ── Accent divider ───────────────────────────────────────────────────────
    tk.Frame(dialog, bg=C_DIVIDER, height=3).pack(fill="x")

    # ── Body ─────────────────────────────────────────────────────────────────
    body = tk.Frame(dialog, bg=C_BODY_BG, padx=28, pady=22)
    body.pack(fill="both", expand=True)

    tk.Label(body, text="Choose Installation Folder",
             font=("Segoe UI", 11, "bold"), bg=C_BODY_BG,
             fg=C_LABEL_FG).pack(anchor="w")
    tk.Label(body,
             text="Select where CuraStack Software should be installed on your computer.",
             font=FONT_LABEL, bg=C_BODY_BG, fg=C_SUB_FG).pack(anchor="w",
                                                                pady=(2, 16))

    # ── Path row ─────────────────────────────────────────────────────────────
    path_var  = StringVar(value=str(default_path))
    path_frame = tk.Frame(body, bg=C_BODY_BG)
    path_frame.pack(fill="x")

    tk.Label(path_frame, text="Install to:", font=FONT_LABEL,
             bg=C_BODY_BG, fg=C_LABEL_FG, width=9,
             anchor="w").pack(side="left")

    entry = tk.Entry(path_frame, textvariable=path_var, font=FONT_ENTRY,
                     bg=C_ENTRY_BG, fg=C_LABEL_FG, relief="flat",
                     highlightthickness=1, highlightbackground=C_ENTRY_HI,
                     highlightcolor=C_ENTRY_HI, insertbackground=C_ENTRY_HI,
                     width=44)
    entry.pack(side="left", fill="x", expand=True, ipady=5)

    def _browse() -> None:
        start_dir = Path(path_var.get().strip() or str(default_path))
        selected = filedialog.askdirectory(
            parent=dialog,
            title=f"Select {APP_NAME} install folder",
            initialdir=str(start_dir.parent if start_dir.parent.exists()
                           else start_dir),
            mustexist=False,
        )
        if selected:
            path_var.set(selected)

    tk.Button(path_frame, text="Browse…", font=FONT_BROWSE,
              bg=C_BROWSE_BG, fg=C_BROWSE_FG, relief="flat", cursor="hand2",
              padx=10, pady=5, command=_browse,
              activebackground="#b8d8ef",
              activeforeground=C_BROWSE_FG).pack(side="left", padx=(8, 0))

    tk.Label(body, text="Default: %LOCALAPPDATA%\\Programs\\CuraStack Software",
             font=("Segoe UI", 8), bg=C_BODY_BG,
             fg="#aaaaaa").pack(anchor="w", pady=(6, 0))

    result: dict[str, Path | None] = {"path": None}

    def _install() -> None:
        raw = path_var.get().strip().strip('"')
        if not raw:
            messagebox.showerror(APP_NAME,
                                 "Please choose an installation folder.",
                                 parent=dialog)
            return
        target = Path(raw)
        if target.exists() and target.is_file():
            messagebox.showerror(APP_NAME,
                                 "Install path points to a file, not a folder.",
                                 parent=dialog)
            return
        if not _can_write_to_dir(target):
            messagebox.showerror(APP_NAME,
                                 "CuraStack Software cannot write to this folder.\n"
                                 "Choose another location.",
                                 parent=dialog)
            return
        result["path"] = target
        dialog.destroy()

    def _cancel() -> None:
        dialog.destroy()

    # ── Bottom bar ────────────────────────────────────────────────────────────
    bar = tk.Frame(dialog, bg=C_BAR_BG, pady=12)
    bar.pack(fill="x", side="bottom")

    cancel_btn = tk.Button(bar, text="Cancel", font=FONT_BTN,
                           bg=C_BTN_CNCL, fg=C_BTN_FG, relief="flat",
                           padx=20, pady=7, cursor="hand2", command=_cancel,
                           activebackground="#4b5563",
                           activeforeground=C_BTN_FG)
    cancel_btn.pack(side="right", padx=(0, 20))
    cancel_btn.bind("<Enter>", lambda e: cancel_btn.configure(bg="#4b5563"))
    cancel_btn.bind("<Leave>", lambda e: cancel_btn.configure(bg=C_BTN_CNCL))

    install_btn = tk.Button(bar, text="Install  →", font=FONT_BTN,
                            bg=C_BTN_INST, fg=C_BTN_FG, relief="flat",
                            padx=20, pady=7, cursor="hand2", command=_install,
                            activebackground="#1d5f8a",
                            activeforeground=C_BTN_FG)
    install_btn.pack(side="right", padx=(0, 8))
    install_btn.bind("<Enter>", lambda e: install_btn.configure(bg="#1d5f8a"))
    install_btn.bind("<Leave>", lambda e: install_btn.configure(bg=C_BTN_INST))

    dialog.bind("<Return>", lambda e: _install())
    dialog.bind("<Escape>", lambda e: _cancel())

    # ── Centre on screen ──────────────────────────────────────────────────────
    dialog.update_idletasks()
    w  = max(DIALOG_W, dialog.winfo_reqwidth())
    h  = dialog.winfo_reqheight()
    sx = dialog.winfo_screenwidth()
    sy = dialog.winfo_screenheight()
    dialog.geometry(f"{w}x{h}+{max(0,(sx-w)//2)}+{max(0,(sy-h)//2)}")

    entry.focus_set()
    dialog.deiconify()
    dialog.lift()
    dialog.wait_window()
    return result["path"]


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


def desktop_dir() -> Path:
    # Resolve real desktop location (works with OneDrive and folder redirection).
    folder_id = UUID("B4BFCC3A-DB2C-424C-B029-7FE99A87C641")
    guid_bytes = folder_id.bytes_le

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_uint32),
            ("Data2", ctypes.c_uint16),
            ("Data3", ctypes.c_uint16),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    guid = GUID(
        int.from_bytes(guid_bytes[0:4], "little"),
        int.from_bytes(guid_bytes[4:6], "little"),
        int.from_bytes(guid_bytes[6:8], "little"),
        (ctypes.c_ubyte * 8).from_buffer_copy(guid_bytes[8:16]),
    )

    path_ptr = ctypes.c_wchar_p()
    hr = ctypes.windll.shell32.SHGetKnownFolderPath(
        ctypes.byref(guid),
        0,
        None,
        ctypes.byref(path_ptr),
    )
    if hr == 0 and path_ptr.value:
        desktop = Path(path_ptr.value)
        ctypes.windll.ole32.CoTaskMemFree(path_ptr)
        return desktop
    return Path.home() / "Desktop"


def get_display_version(version_path: Path) -> str:
    if not version_path.exists():
        return "1.0.0"
    try:
        with version_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        major = int(data.get("major", 1))
        minor = int(data.get("minor", 0))
        patch = int(data.get("patch", 0))
        build = int(data.get("build", 1))
        return f"{major}.{minor}.{patch}.{build}"
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return "1.0.0"


def create_shortcut(
    shortcut_path: Path,
    target_path: Path,
    icon_path: Path,
    working_dir: Path,
    arguments: str = "",
) -> None:
    def _ps_quote(p: Path) -> str:
        return str(p).replace("'", "''")

    if shortcut_path.exists():
        shortcut_path.unlink()

    icon_location = _ps_quote(icon_path)
    if icon_path.suffix.lower() != ".ico":
        icon_location = f"{icon_location},0"

    ps = f"""
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut('{_ps_quote(shortcut_path)}')
$shortcut.TargetPath = '{_ps_quote(target_path)}'
$shortcut.WorkingDirectory = '{_ps_quote(working_dir)}'
$shortcut.IconLocation = '{icon_location}'
$shortcut.Arguments = '{arguments.replace("'", "''")}'
$shortcut.Description = '{APP_NAME}'
$shortcut.Save()
""".strip()
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def write_uninstall_cmd(target: Path) -> Path:
    uninstall_cmd = target / UNINSTALL_CMD
    script = (
        "@echo off\n"
        "setlocal\n"
        "set \"LOG=%TEMP%\\curastack-uninstall.log\"\n"
        "echo [%date% %time%] Uninstall started>\"%LOG%\"\n"
        "cd /d \"%~dp0\"\n"
        "echo [%date% %time%] Working dir: %cd%>>\"%LOG%\"\n"
        f"taskkill /IM \"{APP_EXE}\" /F >>\"%LOG%\" 2>&1\\n"
        "for %%P in (\"%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\" \"%ProgramData%\\Microsoft\\Windows\\Start Menu\\Programs\" \"%USERPROFILE%\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\") do (\n"
        "  echo [%date% %time%] Cleaning Programs root: %%~P>>\"%LOG%\"\n"
        "  del /f /q \"%%~P\\CuraStack Software.lnk\" >>\"%LOG%\" 2>&1\n"
        "  del /f /q \"%%~P\\Uninstall CuraStack Software.lnk\" >>\"%LOG%\" 2>&1\n"
        "  del /f /q \"%%~P\\Aura Scribe PSY.lnk\" >>\"%LOG%\" 2>&1\n"
        "  del /f /q \"%%~P\\Uninstall Aura Scribe PSY.lnk\" >>\"%LOG%\" 2>&1\n"
        "  del /f /q \"%%~P\\TheraTrak Pro.lnk\" >>\"%LOG%\" 2>&1\n"
        "  del /f /q \"%%~P\\Uninstall TheraTrak Pro.lnk\" >>\"%LOG%\" 2>&1\n"
        "  rmdir /s /q \"%%~P\\CuraStack Software\" >>\"%LOG%\" 2>&1\n"
        "  rmdir /s /q \"%%~P\\Aura Scribe PSY\" >>\"%LOG%\" 2>&1\n"
        "  rmdir /s /q \"%%~P\\TheraTrak Pro\" >>\"%LOG%\" 2>&1\n"
        "  rmdir /s /q \"%%~P\\Thorough Track Pro\" >>\"%LOG%\" 2>&1\n"
        "  rmdir /s /q \"%%~P\\TheraTrak-Pro\" >>\"%LOG%\" 2>&1\n"
        ")\n"
        "del /f /q \"%USERPROFILE%\\Desktop\\CuraStack Software.lnk\" >>\"%LOG%\" 2>&1\n"
        "if defined OneDrive del /f /q \"%OneDrive%\\Desktop\\CuraStack Software.lnk\" >>\"%LOG%\" 2>&1\n"
        "del /f /q \"%USERPROFILE%\\Desktop\\Aura Scribe PSY.lnk\" >>\"%LOG%\" 2>&1\n"
        "if defined OneDrive del /f /q \"%OneDrive%\\Desktop\\Aura Scribe PSY.lnk\" >>\"%LOG%\" 2>&1\n"
        "del /f /q \"%USERPROFILE%\\Desktop\\TheraTrak Pro.lnk\" >>\"%LOG%\" 2>&1\n"
        "if defined OneDrive del /f /q \"%OneDrive%\\Desktop\\TheraTrak Pro.lnk\" >>\"%LOG%\" 2>&1\n"
        "rmdir /s /q \"%LOCALAPPDATA%\\Temp\\CuraStackSoftwareUpdates\" >>\"%LOG%\" 2>&1\n"
        "rmdir /s /q \"%LOCALAPPDATA%\\Temp\\AuraScribePSYUpdates\" >>\"%LOG%\" 2>&1\n"
        "rmdir /s /q \"%LOCALAPPDATA%\\Temp\\TheraTrakUpdates\" >>\"%LOG%\" 2>&1\n"
        "del /f /q \"%LOCALAPPDATA%\\Temp\\run_curastack_software_update.bat\" >>\"%LOG%\" 2>&1\n"
        "del /f /q \"%LOCALAPPDATA%\\Temp\\run_aura_scribe_psy_update.bat\" >>\"%LOG%\" 2>&1\n"
        "del /f /q \"%LOCALAPPDATA%\\Temp\\run_aurascribe_update.bat\" >>\"%LOG%\" 2>&1\n"
        "del /f /q \"%LOCALAPPDATA%\\Temp\\run_theratrak_update.bat\" >>\"%LOG%\" 2>&1\n"
        "reg delete \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\CuraStack Software\" /f >>\"%LOG%\" 2>&1\n"
        "reg delete \"HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\CuraStack Software\" /f >>\"%LOG%\" 2>&1\n"
        "reg delete \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Aura Scribe PSY\" /f >>\"%LOG%\" 2>&1\n"
        "reg delete \"HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Aura Scribe PSY\" /f >>\"%LOG%\" 2>&1\n"
        "reg delete \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\TheraTrak Pro\" /f >>\"%LOG%\" 2>&1\n"
        "reg delete \"HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\TheraTrak Pro\" /f >>\"%LOG%\" 2>&1\n"
        "echo [%date% %time%] Refreshing Start menu host>>\"%LOG%\"\n"
        "taskkill /IM StartMenuExperienceHost.exe /F >>\"%LOG%\" 2>&1\n"
        "taskkill /IM explorer.exe /F >>\"%LOG%\" 2>&1\n"
        "start \"\" explorer.exe\n"
        "set \"TARGET=%~dp0\"\n"
        "set \"CLEANUP=%TEMP%\\curastack_uninstall_cleanup.cmd\"\n"
        ">\"%CLEANUP%\" echo @echo off\n"
        ">>\"%CLEANUP%\" echo set TARGET=%%~1\n"
        ">>\"%CLEANUP%\" echo for /L %%%%i in ^(1,1,20^) do ^(\n"
        ">>\"%CLEANUP%\" echo   rmdir /s /q \"%%TARGET%%\" ^>^>\"%%TEMP%%\\curastack-uninstall.log\" 2^>^&1\n"
        ">>\"%CLEANUP%\" echo   if not exist \"%%TARGET%%\" goto done\n"
        ">>\"%CLEANUP%\" echo   ping 127.0.0.1 -n 2 ^>nul\n"
        ">>\"%CLEANUP%\" echo ^)\n"
        ">>\"%CLEANUP%\" echo :done\n"
        ">>\"%CLEANUP%\" echo del /f /q \"%%~f0\"\n"
        "start \"\" /min cmd /c \"\"%CLEANUP%\" \"%TARGET%\"\"\n"
        "exit /b 0\n"
    )
    uninstall_cmd.write_text(script, encoding="utf-8", newline="\r\n")
    return uninstall_cmd


def write_uninstall_registry(target: Path, uninstall_cmd: Path, version: str) -> None:
    uninstall_path = UNINSTALL_KEY_CURRENT
    app_exe = target / APP_EXE
    app_icon = target / ICON_FILE
    comspec = Path(os.environ.get("ComSpec", r"C:\Windows\System32\cmd.exe"))
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, uninstall_path)
    try:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, version)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "CuraStack Software")
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(target))
        winreg.SetValueEx(
            key,
            "DisplayIcon",
            0,
            winreg.REG_SZ,
            str(app_icon if app_icon.exists() else app_exe),
        )
        winreg.SetValueEx(
            key,
            "UninstallString",
            0,
            winreg.REG_SZ,
            f'"{comspec}" /c ""{uninstall_cmd}""',
        )
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
    finally:
        winreg.CloseKey(key)


def _build_progress_window(
    root: Tk,
    screen_w: int,
    screen_h: int,
    initial_status: str = "Preparing...",
    indeterminate: bool = False,
) -> tuple:
    """Return (window, set_progress) — a styled progress window matching the installer UI."""
    import tkinter as tk

    C_GRAD_TOP = (110, 195, 232)
    C_GRAD_BOT = (58, 140, 195)
    C_BODY_BG = "#f5f7fa"
    C_SUB_FG = "#556070"
    C_BAR_BG = "#d8e8f2"
    C_DIVIDER = "#3a8cc3"
    C_TITLE_FG = "#1a2535"

    WIN_W = min(760, max(620, screen_w - 120))
    HEADER_H = 310 if screen_h >= 900 else 240

    win = Toplevel(root)
    win.title(f"Installing {APP_NAME}")
    win.resizable(False, False)
    win.configure(bg=C_BODY_BG)
    win.attributes("-topmost", True)
    win.attributes("-toolwindow", False)
    win.protocol("WM_DELETE_WINDOW", lambda: None)
    _apply_window_icon(win)

    hdr = tk.Canvas(win, width=WIN_W, height=HEADER_H, highlightthickness=0)
    hdr.pack(fill="x")

    banner_photo = _load_setup_wizard_banner(WIN_W, HEADER_H)
    if banner_photo is not None:
        hdr.create_image(WIN_W // 2, HEADER_H // 2, image=banner_photo, anchor="center")
        hdr.image = banner_photo
        hdr.create_rectangle(0, 0, WIN_W, HEADER_H, outline="#3a8cc3", width=2)
    else:
        r0, g0, b0 = C_GRAD_TOP
        r1, g1, b1 = C_GRAD_BOT
        for i in range(HEADER_H):
            t = i / max(1, HEADER_H - 1)
            r = int(r0 + (r1 - r0) * t)
            g = int(g0 + (g1 - g0) * t)
            b = int(b0 + (b1 - b0) * t)
            hdr.create_line(0, i, WIN_W, i, fill=f"#{r:02x}{g:02x}{b:02x}")
        hdr.create_text(
            WIN_W // 2,
            HEADER_H // 2 - 8,
            text=APP_NAME,
            font=("Segoe UI", 16, "bold"),
            fill="white",
            anchor="center",
        )
        hdr.create_text(
            WIN_W // 2,
            HEADER_H // 2 + 16,
            text="Installing, please wait...",
            font=("Segoe UI", 9),
            fill="#d6eef8",
            anchor="center",
        )

    tk.Frame(win, bg=C_DIVIDER, height=3).pack(fill="x")

    body = tk.Frame(win, bg=C_BODY_BG, padx=24, pady=18)
    body.pack(fill="both", expand=True)

    tk.Label(
        body,
        text=f"Installing {APP_NAME}",
        font=("Segoe UI", 11, "bold"),
        bg=C_BODY_BG,
        fg=C_TITLE_FG,
        anchor="w",
    ).pack(anchor="w", pady=(0, 6))

    status_var = StringVar(value=initial_status)
    tk.Label(body, textvariable=status_var, font=("Segoe UI", 9),
             bg=C_BODY_BG, fg=C_SUB_FG, anchor="w",
             wraplength=WIN_W - 48).pack(anchor="w", pady=(0, 10))

    BAR_W = WIN_W - 48
    BAR_H = 16

    bar_canvas = tk.Canvas(body, width=BAR_W, height=BAR_H,
                           bg=C_BAR_BG, highlightthickness=0)
    bar_canvas.pack(anchor="w")

    if indeterminate:
        _state = {"pos": -(BAR_W // 3), "active": True}
        BLOCK = BAR_W // 4

        def _animate() -> None:
            if not _state["active"]:
                return
            bar_canvas.delete("all")
            bar_canvas.create_rectangle(0, 0, BAR_W, BAR_H, fill=C_BAR_BG, outline="")
            x = _state["pos"]
            x1, x2 = max(0, x), min(x + BLOCK, BAR_W)
            if x1 < x2:
                for px in range(x1, x2):
                    t  = px / max(1, BAR_W - 1)
                    rr = int(110 + (58  - 110) * t)
                    gg = int(195 + (140 - 195) * t)
                    bb = int(232 + (195 - 232) * t)
                    bar_canvas.create_line(px, 0, px, BAR_H,
                                           fill=f"#{rr:02x}{gg:02x}{bb:02x}")
            _state["pos"] = x + 8
            if _state["pos"] > BAR_W:
                _state["pos"] = -BLOCK
            win.after(25, _animate)

        _animate()

        def set_progress(pct: float, status: str) -> None:
            status_var.set(status)
            win.update()

        _orig_destroy = win.destroy

        def _destroy_patched() -> None:
            _state["active"] = False
            _orig_destroy()

        win.destroy = _destroy_patched  # type: ignore[method-assign]

    else:
        pct_label = tk.Label(body, text="0%", font=("Segoe UI", 8),
                             bg=C_BODY_BG, fg=C_SUB_FG, anchor="e")
        pct_label.pack(anchor="e", pady=(3, 0))

        def _draw_bar(pct: float) -> None:
            bar_canvas.delete("all")
            bar_canvas.create_rectangle(0, 0, BAR_W, BAR_H,
                                        fill=C_BAR_BG, outline="")
            filled = int(BAR_W * pct / 100)
            for px in range(filled):
                t  = px / max(1, BAR_W - 1)
                rr = int(110 + (58  - 110) * t)
                gg = int(195 + (140 - 195) * t)
                bb = int(232 + (195 - 232) * t)
                bar_canvas.create_line(px, 0, px, BAR_H,
                                       fill=f"#{rr:02x}{gg:02x}{bb:02x}")

        _draw_bar(0)

        def set_progress(pct: float, status: str) -> None:
            pct = max(0.0, min(100.0, pct))
            _draw_bar(pct)
            pct_label.configure(text=f"{int(pct)}%")
            status_var.set(status)
            win.update()

    win.update_idletasks()
    ww = max(WIN_W, win.winfo_reqwidth())
    wh = win.winfo_reqheight()
    win.geometry(f"{ww}x{wh}+{max(0,(screen_w-ww)//2)}+{max(0,(screen_h-wh)//2)}")
    win.deiconify()
    win.lift()
    win.focus_force()
    win.update()

    return win, set_progress


def main() -> int:
    # Enable per-monitor DPI awareness before creating the Tk root so the
    # installer window is sized correctly on HiDPI displays.
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)   # ensure all dialogs appear in front

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()

    default_target = detect_existing_install_dir() or install_dir()
    target = choose_install_dir(root, default_target)
    if target is None:
        messagebox.showinfo(APP_NAME, "Installation canceled.", parent=root)
        root.destroy()
        return 0

    progress_window, set_progress = _build_progress_window(
        root, screen_w, screen_h, "Preparing installer..."
    )

    source = bundled_dir()

    # If CuraStack Software is currently open, ask the user to let the installer
    # close it.  Attempting to overwrite locked DLLs inside _internal/ causes
    # WinError 32 (sharing violation) on the copy step.
    if _is_app_running():
        progress_window.destroy()
        close_it = messagebox.askyesno(
            APP_NAME,
            "CuraStack Software is currently open.\n\n"
            "It must be closed before the installer can update the files.\n"
            "Click Yes to close it automatically and continue, or No to cancel.",
            parent=root,
        )
        if not close_it:
            messagebox.showinfo(APP_NAME, "Installation canceled.", parent=root)
            root.destroy()
            return 0
        _stop_running_app()
        # Recreate progress window (indeterminate — waiting for app to exit)
        progress_window, _wait_set = _build_progress_window(
            root, screen_w, screen_h,
            "Waiting for CuraStack Software to close...",
            indeterminate=True,
        )
        # Poll until process exits (up to 15 s), keeping the UI alive.
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline and _is_app_running():
            progress_window.update()
            time.sleep(0.25)
        progress_window.destroy()
        if _is_app_running():
            messagebox.showerror(
                APP_NAME,
                "CuraStack Software could not be closed automatically.\n"
                "Please close it manually and run the installer again.",
                parent=root,
            )
            root.destroy()
            return 1
        # Rebuild the real progress window now that the app is gone.
        progress_window, set_progress = _build_progress_window(  # type: ignore[no-redef]
            root, screen_w, screen_h, "Preparing installation folders..."
        )

    set_progress(5, "Preparing installation folders...")
    target.mkdir(parents=True, exist_ok=True)

    app_bundle = source / APP_BUNDLE_DIR
    set_progress(10, "Validating installer payload...")
    python_dll_rel = _find_bundled_python_dll(app_bundle)
    if python_dll_rel is None:
        progress_window.destroy()
        messagebox.showerror(
            APP_NAME,
            "Install failed. Installer payload is incomplete (missing _internal\\python3xx.dll).\n"
            "Please download the installer again.",
        )
        root.destroy()
        return 1

    try:
        if app_bundle.exists() and app_bundle.is_dir():
            def _on_copy_progress(index: int, total: int, file_name: str) -> None:
                set_progress(
                    10 + (50 * (index / total)),
                    f"Copying app files ({index}/{total}): {file_name}",
                )

            _copy_app_bundle_with_progress(app_bundle, target, _on_copy_progress)
            set_progress(60, "Application files copied.")
    except Exception as ex:
        progress_window.destroy()
        messagebox.showerror(
            APP_NAME,
            "Install failed while copying application files.\n"
            "Please close CuraStack Software and retry.\n\n"
            f"Details: {ex}",
        )
        root.destroy()
        return 1

    set_progress(65, "Copying installer support files...")
    for name in (UNINSTALL_EXE, ICON_FILE, VERSION_FILE):
        src = source / name
        if src.exists():
            _copy_with_retries(src, target / name)

    set_progress(68, "Checking existing data...")
    migrated_from = _migrate_legacy_database(target)
    if migrated_from is not None:
        set_progress(70, f"Migrated existing data from: {migrated_from.parent.name}")

    exe_path = target / APP_EXE
    uninstaller_path = target / UNINSTALL_EXE
    icon_path = target / ICON_FILE
    target_python_dll = target / python_dll_rel
    uninstall_cmd_path = target / UNINSTALL_CMD

    # Extra safeguard: if the runtime DLL is still missing, try one focused recopy.
    if not target_python_dll.exists():
        set_progress(70, "Verifying runtime components...")
        src_internal = app_bundle / "_internal"
        if src_internal.exists() and src_internal.is_dir():
            _copy_with_retries(src_internal, target / "_internal")

    required = [
        (APP_EXE, exe_path),
        (UNINSTALL_EXE, uninstaller_path),
        (ICON_FILE, icon_path),
        (str(python_dll_rel).replace("/", "\\"), target_python_dll),
    ]
    missing = [label for label, p in required if not p.exists()]
    if missing:
        progress_window.destroy()
        messagebox.showerror(APP_NAME, f"Install failed. Missing files: {', '.join(missing)}")
        root.destroy()
        return 1

    set_progress(75, "Registering uninstall command...")
    uninstall_cmd_path = write_uninstall_cmd(target)

    set_progress(82, "Cleaning old shortcuts...")
    desktop = desktop_dir()
    programs_dirs = start_menu_program_dirs()
    for programs_dir in programs_dirs:
        for legacy_name in (APP_NAME, *LEGACY_START_MENU_FOLDERS):
            legacy_dir = programs_dir / legacy_name
            if legacy_dir.exists() and legacy_dir.is_dir():
                shutil.rmtree(legacy_dir, ignore_errors=True)
        for shortcut_name in LEGACY_ROOT_SHORTCUTS:
            try:
                (programs_dir / shortcut_name).unlink(missing_ok=True)
            except OSError:
                pass

    start_menu_dir = programs_dirs[0] / APP_NAME
    start_menu_dir.mkdir(parents=True, exist_ok=True)

    set_progress(90, "Creating desktop and Start Menu shortcuts...")
    create_shortcut(desktop / f"{APP_NAME}.lnk", exe_path, icon_path, target)
    create_shortcut(start_menu_dir / f"{APP_NAME}.lnk", exe_path, icon_path, target)
    create_shortcut(
        start_menu_dir / UNINSTALL_SHORTCUT_NAME,
        Path(os.environ.get("ComSpec", r"C:\Windows\System32\cmd.exe")),
        uninstaller_path,
        target,
        arguments=f'/c ""{uninstall_cmd_path}""',
    )
    set_progress(97, "Writing uninstall registry entries...")
    write_uninstall_registry(target, uninstall_cmd_path, get_display_version(target / VERSION_FILE))
    set_progress(100, "Installation complete.")
    progress_window.destroy()

    messagebox.showinfo(
        APP_NAME,
        "CuraStack Software was installed successfully.\n\nDesktop and Start Menu shortcuts were created.\nAn uninstaller was also registered in Installed Apps.",
    )
    root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())