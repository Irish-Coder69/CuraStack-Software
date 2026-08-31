"""
CuraStack Software - Data import from any medical practice management or EHR software.

Accepts CSV files exported from any system (SimplePractice, Kareo, TherapyNotes,
Practice Fusion, Notes 444, etc.).  Column names are matched flexibly — exact
headers are not required.

Import paths:
  import_patients_csv(path)  – patient demographics & insurance
  import_sessions_csv(path)  – therapy session notes
  import_billing_csv(path)   – billing / payment records

Template generators (blank CSV with correct headers):
  write_patients_template(path)
  write_sessions_template(path)
  write_billing_template(path)

Legacy Notes 444 binary extraction (best-effort, partial data only):
  extract_raw_patients(ptinfo_path)
  get_data_files_status([notes444_dir])
"""

import csv
import io
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import database as db


# ─── Constants ─────────────────────────────────────────────────────────────────

FM5_MAGIC = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x02, 0x00, 0x01, 0x00, 0x05])

NOTES444_DEFAULT_PATH = r"H:\Important Files"

DATE_PATTERNS = [
    r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\b",   # MM/DD/YYYY or MM-DD-YYYY
    r"\b(\d{4})[/\-](\d{2})[/\-](\d{2})\b",          # YYYY-MM-DD
]


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _is_fm5(path: str) -> bool:
    """Return True if file starts with FileMaker Pro 5 magic bytes."""
    try:
        with open(path, "rb") as f:
            return f.read(10) == FM5_MAGIC
    except OSError:
        return False


def _extract_strings(path: str, min_len: int = 5) -> list[str]:
    """Extract printable ASCII strings of at least min_len chars from a binary file."""
    strings = []
    buf = []
    try:
        with open(path, "rb") as f:
            for byte in f.read():
                ch = byte
                if 32 <= ch <= 126:  # printable ASCII
                    buf.append(chr(ch))
                else:
                    if len(buf) >= min_len:
                        strings.append("".join(buf))
                    buf.clear()
        if len(buf) >= min_len:
            strings.append("".join(buf))
    except OSError:
        pass
    return strings


def _parse_date(s: str) -> str:
    """Try to parse a date string into YYYY-MM-DD. Returns '' on failure."""
    s = s.strip()
    for pat in DATE_PATTERNS:
        m = re.match(pat, s)
        if m:
            groups = m.groups()
            try:
                if len(groups[0]) == 4:           # YYYY-MM-DD
                    return f"{groups[0]}-{int(groups[1]):02d}-{int(groups[2]):02d}"
                else:
                    y = int(groups[2])
                    if y < 100:
                        y += 2000 if y < 30 else 1900
                    return f"{y}-{int(groups[0]):02d}-{int(groups[1]):02d}"
            except ValueError:
                pass
    return ""


def _looks_like_name(s: str) -> bool:
    """Heuristic: string looks like a person name (2-4 words, mostly alpha)."""
    parts = s.strip().split()
    if not (1 < len(parts) <= 4):
        return False
    return all(re.match(r"^[A-Za-z'\-\.]{1,30}$", p) for p in parts)


def _looks_like_phone(s: str) -> bool:
    return bool(re.match(r"^\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}$", s.strip()))


def _looks_like_email(s: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", s.strip()))


# ─── CSV Import ────────────────────────────────────────────────────────────────

class CSVImportError(Exception):
    pass


def _call_with_sqlite_retry(func, *args, retries: int = 8, base_delay: float = 0.15):
    """Retry transient SQLite lock errors with short backoff."""
    for attempt in range(retries + 1):
        try:
            return func(*args)
        except sqlite3.OperationalError as ex:
            msg = str(ex).lower()
            if "database is locked" not in msg or attempt >= retries:
                raise
            time.sleep(base_delay * (attempt + 1))


def import_patients_csv(path: str) -> tuple[int, list[str]]:
    """
    Import patients from a CSV file exported from Notes 444.
    Expected columns (case-insensitive, flexible):
      Last Name, First Name, DOB, Sex, Address, City, State, Zip,
            Phone, Cell, Email, Insurance, Ins ID, Ins Group, Dx1–Dx12, Status
    Returns (count_imported, list_of_warnings).
    """
    imported = 0
    warnings = []

    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        headers = {h.strip().lower(): h for h in (reader.fieldnames or [])}

        def col(row, *candidates):
            for c in candidates:
                for h in headers:
                    if c.lower() in h:
                        val = row.get(headers[h], "").strip()
                        if val:
                            return val
            return ""

        for line_num, row in enumerate(reader, start=2):
            last = col(row, "last name", "last", "lname", "surname")
            first = col(row, "first name", "first", "fname")
            if not last and not first:
                warnings.append(f"Row {line_num}: skipped – no name found")
                continue

            data = {
                "last_name":   last or "Unknown",
                "first_name":  first or "Unknown",
                "middle_name": col(row, "middle", "mi"),
                "dob":         _parse_date(col(row, "dob", "birth", "birthdate", "date of birth")),
                "sex":         col(row, "sex", "gender")[:1].upper() or "U",
                "ssn":         col(row, "ssn", "social security"),
                "address":     col(row, "address", "addr", "street"),
                "city":        col(row, "city"),
                "state":       col(row, "state"),
                "zip":         col(row, "zip", "postal"),
                "phone_home":  col(row, "phone home", "home phone", "phone", "tel"),
                "phone_cell":  col(row, "cell", "mobile", "cellular"),
                "phone_work":  col(row, "work phone", "work"),
                "email":       col(row, "email", "e-mail"),
                "ins_name":    col(row, "insurance", "ins name", "payer"),
                "ins_id":      col(row, "ins id", "member id", "policy"),
                "ins_group":   col(row, "group", "ins group"),
                "ins_plan":    col(row, "plan", "ins plan"),
                "ins_holder":  col(row, "holder", "subscriber", "insured name"),
                "ins_relation":col(row, "relation", "relationship") or "Self",
                "dx1":         col(row, "dx1", "diagnosis 1", "diag1", "icd 1"),
                "dx2":         col(row, "dx2", "diagnosis 2", "diag2", "icd 2"),
                "dx3":         col(row, "dx3", "diagnosis 3"),
                "dx4":         col(row, "dx4", "diagnosis 4"),
                "dx5":         col(row, "dx5", "diagnosis 5"),
                "dx6":         col(row, "dx6", "diagnosis 6"),
                "dx7":         col(row, "dx7", "diagnosis 7"),
                "dx8":         col(row, "dx8", "diagnosis 8"),
                "dx9":         col(row, "dx9", "diagnosis 9"),
                "dx10":        col(row, "dx10", "diagnosis 10"),
                "dx11":        col(row, "dx11", "diagnosis 11"),
                "dx12":        col(row, "dx12", "diagnosis 12"),
                "intake_date": _parse_date(col(row, "intake", "intake date", "start date")),
                "status":      col(row, "status") or "Active",
                "notes":       col(row, "notes", "comment"),
            }

            try:
                _call_with_sqlite_retry(db.save_patient, data)
                imported += 1
            except sqlite3.IntegrityError as e:
                warnings.append(f"Row {line_num}: DB error – {e}")

    return imported, warnings


def import_sessions_csv(path: str) -> tuple[int, list[str]]:
    """
    Import session notes from a CSV export of PtNotes.444.
    Expected columns: Patient ID (or Last Name/First Name), Session Date,
    Session Type, Duration, CPT Code, Dx1–Dx12, Fee, Notes
    """
    imported = 0
    warnings = []

    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        headers = {h.strip().lower(): h for h in (reader.fieldnames or [])}

        def col(row, *candidates):
            for c in candidates:
                for h in headers:
                    if c.lower() in h:
                        val = row.get(headers[h], "").strip()
                        if val:
                            return val
            return ""

        for line_num, row in enumerate(reader, start=2):
            # Resolve patient
            pid_str = col(row, "patient_id", "patient id", "pt_id", "pt id")
            if not pid_str:
                # Legacy fallback only when a specific patient id column is absent.
                pid_str = col(row, "id")
            pid = int(pid_str) if pid_str.isdigit() else None

            if pid is None:
                last = col(row, "last name", "last")
                first = col(row, "first name", "first")
                if last or first:
                    conn = db.get_connection()
                    pts = conn.execute(
                        "SELECT id FROM patients WHERE last_name LIKE ? AND first_name LIKE ?",
                        (f"%{last}%", f"%{first}%")
                    ).fetchall()
                    conn.close()
                    if len(pts) == 1:
                        pid = pts[0]["id"]
                    elif len(pts) > 1:
                        warnings.append(f"Row {line_num}: multiple patients match '{last}, {first}' – skipped")
                        continue
                    else:
                        warnings.append(f"Row {line_num}: patient '{last}, {first}' not found – skipped")
                        continue

            if pid is None:
                warnings.append(f"Row {line_num}: no patient identified – skipped")
                continue

            fee_str = col(row, "fee", "charge", "amount")
            try:
                fee = float(fee_str.replace("$", "").replace(",", "")) if fee_str else 0.0
            except ValueError:
                fee = 0.0

            dur_str = col(row, "duration", "mins", "minutes", "length")
            dur = int(dur_str) if dur_str.isdigit() else 50

            data = {
                "patient_id":       pid,
                "session_date":     _parse_date(col(row, "session date", "date", "visit date")) or
                                    datetime.today().strftime("%Y-%m-%d"),
                "duration":         dur,
                "session_type":     col(row, "session type", "type", "modality") or "Individual",
                "place_of_service": col(row, "place", "pos", "location") or "11",
                "cpt_code":         col(row, "cpt", "procedure code", "cpt code") or "90834",
                "cpt_modifier":     col(row, "modifier", "mod"),
                "dx1":              col(row, "dx1", "diagnosis 1", "icd1"),
                "dx2":              col(row, "dx2", "diagnosis 2"),
                "dx3":              col(row, "dx3"),
                "dx4":              col(row, "dx4"),
                "dx5":              col(row, "dx5", "diagnosis 5"),
                "dx6":              col(row, "dx6", "diagnosis 6"),
                "dx7":              col(row, "dx7", "diagnosis 7"),
                "dx8":              col(row, "dx8", "diagnosis 8"),
                "dx9":              col(row, "dx9", "diagnosis 9"),
                "dx10":             col(row, "dx10", "diagnosis 10"),
                "dx11":             col(row, "dx11", "diagnosis 11"),
                "dx12":             col(row, "dx12", "diagnosis 12"),
                "fee":              fee,
                "note_text":        col(row, "note", "notes", "progress note", "soap"),
                "goals":            col(row, "goal", "goals"),
                "interventions":    col(row, "intervention", "interventions"),
                "response":         col(row, "response"),
                "plan":             col(row, "plan"),
                "signed":           1 if col(row, "signed").lower() in ("yes", "true", "1") else 0,
            }

            try:
                _call_with_sqlite_retry(db.save_session, data)
                imported += 1
            except sqlite3.IntegrityError as e:
                warnings.append(f"Row {line_num}: DB error – {e}")

    return imported, warnings


def import_billing_csv(path: str) -> tuple[int, list[str]]:
    """
    Import billing/payment records from a CSV export of Payments.444.
    """
    imported = 0
    warnings = []

    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        headers = {h.strip().lower(): h for h in (reader.fieldnames or [])}

        def col(row, *candidates):
            for c in candidates:
                for h in headers:
                    if c.lower() in h:
                        val = row.get(headers[h], "").strip()
                        if val:
                            return val
            return ""

        def money(s):
            try:
                return float(s.replace("$", "").replace(",", "")) if s else 0.0
            except ValueError:
                return 0.0

        for line_num, row in enumerate(reader, start=2):
            pid_str = col(row, "patient_id", "patient id", "pt_id", "pt id")
            if not pid_str:
                # Legacy fallback only when a specific patient id column is absent.
                pid_str = col(row, "id")
            pid = int(pid_str) if pid_str.isdigit() else None

            if pid is None:
                last  = col(row, "last name", "last")
                first = col(row, "first name", "first")
                if last or first:
                    conn = db.get_connection()
                    pts = conn.execute(
                        "SELECT id FROM patients WHERE last_name LIKE ? AND first_name LIKE ?",
                        (f"%{last}%", f"%{first}%")
                    ).fetchall()
                    conn.close()
                    if len(pts) == 1:
                        pid = pts[0]["id"]

            if pid is None:
                warnings.append(f"Row {line_num}: patient not identified – skipped")
                continue

            charge  = money(col(row, "charge", "fee", "amount"))
            payment = money(col(row, "payment", "copay", "patient paid"))
            ins_pay = money(col(row, "insurance payment", "ins payment", "ins paid"))
            adj     = money(col(row, "adjustment", "write off", "writeoff"))

            data = {
                "patient_id":   pid,
                "record_date":  _parse_date(col(row, "date", "record date", "payment date")) or
                                datetime.today().strftime("%Y-%m-%d"),
                "service_date": _parse_date(col(row, "service date", "dos", "date of service")),
                "description":  col(row, "description", "service", "cpt"),
                "charge":       charge,
                "payment":      payment,
                "payment_type": col(row, "payment type", "pay type", "method"),
                "check_number": col(row, "check number", "check #", "ck#"),
                "ins_payment":  ins_pay,
                "adjustment":   adj,
                "balance":      charge - payment - ins_pay - adj,
                "claim_number": col(row, "claim", "claim #", "claim number"),
            }

            try:
                _call_with_sqlite_retry(db.save_billing_record, data)
                imported += 1
            except sqlite3.IntegrityError as e:
                warnings.append(f"Row {line_num}: DB error – {e}")

    return imported, warnings


def import_bookkeeping_csv(path: str) -> tuple[int, list[str]]:
    """
    Import bookkeeping ledger entries from a CSV-like file.
    The file extension is ignored; importer attempts to parse text as CSV.
    """
    imported = 0
    warnings = []

    def _money(s: str) -> float:
        try:
            return float((s or "").replace("$", "").replace(",", "").strip()) if s else 0.0
        except ValueError:
            return 0.0

    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        headers = {h.strip().lower(): h for h in (reader.fieldnames or [])}

        if not headers:
            return 0, ["No header row detected. Ensure the file is CSV-formatted text."]

        def col(row, *candidates):
            for c in candidates:
                c_low = c.lower()
                for h in headers:
                    if c_low in h:
                        return (row.get(headers[h], "") or "").strip()
            return ""

        for line_num, row in enumerate(reader, start=2):
            entry_date = _parse_date(col(row, "entry date", "date", "record date", "transaction date"))
            if not entry_date:
                warnings.append(f"Row {line_num}: missing/invalid date - skipped")
                continue

            data = {
                "entry_date": entry_date,
                "check_number": col(row, "check", "check #", "check number", "ck#"),
                "payee": col(row, "payee", "description", "vendor", "name"),
                "memo": col(row, "memo", "notes", "note", "comment"),
                "is_tax_deductible": 1 if col(row, "tax deductible", "tax", "deductible").lower() in ("yes", "y", "true", "1", "x") else 0,
                "inc_client": _money(col(row, "client fees", "inc_client", "income client", "client")),
                "inc_insurance": _money(col(row, "ins. pay", "insurance", "inc_insurance", "insurance pay")),
                "inc_other": _money(col(row, "other inc", "inc_other", "other income")),
                "exp_rent": _money(col(row, "rent", "exp_rent")),
                "exp_utilities": _money(col(row, "utilities", "exp_utilities")),
                "exp_office": _money(col(row, "office", "office sup", "exp_office")),
                "exp_insurance": _money(col(row, "ins. exp", "expense insurance", "exp_insurance")),
                "exp_phone": _money(col(row, "phone", "exp_phone")),
                "exp_professional": _money(col(row, "professional", "prof. fees", "exp_professional")),
                "exp_advertising": _money(col(row, "advertising", "exp_advertising")),
                "exp_misc": _money(col(row, "misc", "miscellaneous", "exp_misc")),
            }

            has_amount = any(float(data[k] or 0) != 0.0 for k in (
                "inc_client", "inc_insurance", "inc_other",
                "exp_rent", "exp_utilities", "exp_office", "exp_insurance",
                "exp_phone", "exp_professional", "exp_advertising", "exp_misc",
            ))
            if not has_amount and not data["payee"] and not data["memo"]:
                warnings.append(f"Row {line_num}: empty row - skipped")
                continue

            try:
                _call_with_sqlite_retry(db.save_bookkeeping_entry, data)
                imported += 1
            except sqlite3.IntegrityError as ex:
                warnings.append(f"Row {line_num}: DB error - {ex}")

    return imported, warnings


# ─── Raw binary extraction (best-effort) ──────────────────────────────────────

def extract_raw_patients(ptinfo_path: str) -> tuple[int, list[str]]:
    """
    Attempt to extract patient records from PTInfo.444 binary file.
    This is a best-effort heuristic for FileMaker Pro 5 format.
    Results are partial; use CSV import for complete data.
    """
    if not _is_fm5(ptinfo_path):
        return 0, ["File does not appear to be FileMaker Pro 5 format"]

    strings = _extract_strings(ptinfo_path, min_len=4)
    imported = 0
    warnings = ["Note: Raw extraction is partial. Use CSV import for complete data."]

    # Try to find name-like string groups followed by dates and phones
    candidates = []
    i = 0
    while i < len(strings):
        s = strings[i]
        if _looks_like_name(s):
            # Build a candidate record from nearby strings
            candidate = {"raw_name": s}
            j = i + 1
            while j < min(i + 20, len(strings)):
                nx = strings[j].strip()
                if _parse_date(nx):
                    candidate.setdefault("dob", _parse_date(nx))
                elif _looks_like_phone(nx):
                    candidate.setdefault("phone_home", nx)
                elif _looks_like_email(nx):
                    candidate.setdefault("email", nx)
                j += 1
            candidates.append(candidate)
            i = j
        else:
            i += 1

    for cand in candidates:
        name = cand["raw_name"].strip()
        parts = name.split()
        last  = parts[-1] if parts else "Unknown"
        first = parts[0] if len(parts) > 1 else "Unknown"

        data = {
            "last_name":  last,
            "first_name": first,
            "dob":        cand.get("dob", ""),
            "phone_home": cand.get("phone_home", ""),
            "email":      cand.get("email", ""),
            "status":     "Active",
            "notes":      "Imported via raw extraction from Notes 444",
        }
        try:
            db.save_patient(data)
            imported += 1
        except sqlite3.IntegrityError:
            pass

    if imported == 0:
        warnings.append("No recognizable patient records found in binary file.")
    return imported, warnings


# ─── CSV Template Writers ─────────────────────────────────────────────────────

def write_patients_template(path: str) -> None:
    """Write a blank patients CSV template with all supported column headers."""
    headers = [
        "Last Name", "First Name", "Middle Name",
        "DOB",
        "Sex",
        "SSN",
        "Address", "City", "State", "Zip",
        "Phone Home", "Phone Cell", "Phone Work",
        "Email",
        "Insurance", "Ins ID", "Ins Group", "Ins Plan", "Ins Holder", "Ins Relation",
        "Dx1", "Dx2", "Dx3", "Dx4", "Dx5", "Dx6", "Dx7", "Dx8", "Dx9", "Dx10", "Dx11", "Dx12",
        "Intake Date",
        "Status",
        "Notes",
    ]
    example = [
        "Smith", "Jane", "",
        "01/15/1985",
        "F",
        "",
        "123 Main St", "Springfield", "IL", "62701",
        "(217) 555-1234", "(217) 555-5678", "",
        "jane.smith@email.com",
        "BlueCross BlueShield", "XYZ123456", "GRP001", "", "Jane Smith", "Self",
        "F32.1", "", "", "", "", "", "", "", "", "", "", "",
        "03/01/2024",
        "Active",
        "",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerow(example)


def write_sessions_template(path: str) -> None:
    """Write a blank sessions CSV template with all supported column headers."""
    headers = [
        "Patient ID", "Last Name", "First Name",
        "Session Date",
        "Duration",
        "Session Type",
        "Place of Service",
        "CPT Code", "Modifier",
        "Dx1", "Dx2", "Dx3", "Dx4", "Dx5", "Dx6", "Dx7", "Dx8", "Dx9", "Dx10", "Dx11", "Dx12",
        "Fee",
        "Notes",
        "Goals", "Interventions", "Response", "Plan",
        "Signed",
    ]
    example = [
        "", "Smith", "Jane",
        "04/05/2026",
        "50",
        "Individual",
        "11",
        "90837", "",
        "F32.1", "", "", "", "", "", "", "", "", "", "", "",
        "150.00",
        "Patient reported improvement.",
        "", "", "", "",
        "No",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerow(example)


def write_billing_template(path: str) -> None:
    """Write a blank billing CSV template with all supported column headers."""
    headers = [
        "Patient ID", "Last Name", "First Name",
        "Record Date",
        "Service Date",
        "Description",
        "Charge", "Payment", "Payment Type", "Check Number",
        "Insurance Payment",
        "Adjustment",
        "Claim Number",
    ]
    example = [
        "", "Smith", "Jane",
        "04/05/2026",
        "04/05/2026",
        "Individual Therapy – 90837",
        "150.00", "30.00", "Copay", "",
        "120.00",
        "0.00",
        "",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerow(example)


def write_bookkeeping_template(path: str) -> None:
    """Write a blank bookkeeping CSV template with supported column headers."""
    headers = [
        "Entry Date", "Check Number", "Payee", "Memo", "Tax Deductible",
        "Client Fees", "Ins. Pay.", "Other Inc.",
        "Rent", "Utilities", "Office Sup.", "Ins. Exp.", "Phone",
        "Prof. Fees", "Advertising", "Misc",
    ]
    example = [
        "04/05/2026", "", "Office Supplies Co.", "Printer paper", "Yes",
        "0.00", "0.00", "0.00",
        "0.00", "0.00", "45.99", "0.00", "0.00",
        "0.00", "0.00", "0.00",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerow(example)


# ─── Guided import report (legacy Notes 444) ──────────────────────────────────

def get_data_files_status(notes444_dir: str = NOTES444_DEFAULT_PATH) -> list[dict]:
    """
    Return status of each expected Notes 444 data file.
    Used by the UI to guide the user through the migration process.
    """
    files = [
        {"file": "PTInfo.444",           "table": "patients",         "description": "Patient demographics & insurance"},
        {"file": "PtNotes.444",          "table": "session_notes",    "description": "Therapy session notes"},
        {"file": "Payments.444",         "table": "billing_records",  "description": "Billing & payment history"},
        {"file": "ContactInformation.444","table": "patients",        "description": "Contact information"},
        {"file": "DatesOfNote.444",      "table": "session_notes",    "description": "Session dates"},
        {"file": "Lookups.444",          "table": "dsm_codes",        "description": "Lookup tables"},
    ]
    for f in files:
        full = os.path.join(notes444_dir, f["file"])
        f["exists"]  = os.path.exists(full)
        f["is_fm5"]  = _is_fm5(full) if f["exists"] else False
        f["size_kb"] = round(os.path.getsize(full) / 1024) if f["exists"] else 0
    return files
