from __future__ import annotations

# --- CuraStack Software - License Key Generator (PRIVATE TOOL - DO NOT DISTRIBUTE) ---
# Uses Ed25519 asymmetric signing.  V3 compact base32 format.
# The private key below stays here ONLY.  The app ships the public key only.

import argparse
import base64
import hashlib
import json
import os
import re
import struct
import uuid
from datetime import UTC, date, datetime, timedelta

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

LICENSE_KEY_PREFIX = "THP1"

# V3 compact format constants
_V3_BASE_DATE = date(2026, 1, 1)   # day-0 for 16-bit day counters
_PLAN_NAMES = {0: "Developer/Test", 1: "Solo Practice", 2: "Group Practice"}
_PLAN_CODES = {"dev": 0, "solo": 1, "group": 2}

# ── Ed25519 key pair ──────────────────────────────────────────────────────────
# Private key – NEVER ship this in the application binary.
_PRIVATE_KEY_RAW: bytes = bytes.fromhex(
    "46fe3a57dac8cd3f25532e2fb1d6ebc6175b3b6c3b9864ca14a8c8b9adf05f14"
)
# Public key – the matching bytes embedded in main.py for verification.
_PUBLIC_KEY_RAW: bytes = bytes.fromhex(
    "557ecad262753de008f00bfba843d01e086344ea13e90afb6b90fd4b601a87d1"
)


def _private_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(_PRIVATE_KEY_RAW)


def _public_key() -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(_PUBLIC_KEY_RAW)


def b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64u_decode(raw: str) -> bytes:
    padded = raw + ("=" * ((4 - len(raw) % 4) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _b32_encode_blocks(raw: bytes, block: int = 6) -> str:
    """Base32-encode bytes and return as dash-separated blocks of `block` chars."""
    b32 = base64.b32encode(raw).decode("ascii").rstrip("=")
    return "-".join(b32[i:i + block] for i in range(0, len(b32), block))


def _b32_decode_key(key_body: str) -> bytes:
    """Strip dashes/whitespace, re-pad, and base32-decode."""
    clean = re.sub(r"[^A-Z2-7]", "", key_body.upper())
    padded = clean + "=" * ((8 - len(clean) % 8) % 8)
    return base64.b32decode(padded)


def _days_from_base(d: date) -> int:
    return max(0, (d - _V3_BASE_DATE).days)


def _date_from_days(n: int) -> date:
    return _V3_BASE_DATE + timedelta(days=n)


def current_machine_code() -> str:
    source = "|".join([
        os.environ.get("COMPUTERNAME", "").strip().upper(),
        hex(uuid.getnode()),
        os.environ.get("PROCESSOR_IDENTIFIER", "").strip().upper(),
    ])
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16].upper()


def build_license_key(
    name: str,
    email: str,
    machine_code: str = "",
    expires: str = "",
    plan: int = 1,
) -> str:
    """
    Build a v3 compact license key.

    Payload layout (18 bytes):
      [0]     version = 3
      [1]     plan: 0=dev, 1=solo, 2=group
      [2-5]   serial: 4 random bytes
      [6-7]   issued: uint16 BE, days from 2026-01-01
      [8-9]   expiry: uint16 BE, 0 = perpetual
      [10-17] machine: first 8 bytes of SHA-256 machine hash, or 0x00*8 if unbound

    Total: 18 payload + 64 Ed25519 sig = 82 bytes
    Base32 -> 132 chars -> 22 blocks of 6 -> "THP1-XXXXXX-...-XXXXXX"

    name / email are for the issuer's records only; NOT embedded in the key.
    """
    serial = os.urandom(4)
    issued = _days_from_base(date.today())

    if expires:
        expiry = _days_from_base(datetime.strptime(expires, "%Y-%m-%d").date())
    else:
        expiry = 0  # perpetual

    mc_bytes = b"\x00" * 8
    if machine_code:
        mc_hex = machine_code.strip().upper()[:16].ljust(16, "0")
        try:
            mc_bytes = bytes.fromhex(mc_hex)
        except ValueError:
            mc_bytes = b"\x00" * 8

    payload = bytes([3, plan & 0xFF]) + serial + struct.pack(">HH", issued, expiry) + mc_bytes
    sig = _private_key().sign(payload)  # 64-byte Ed25519 signature
    body = _b32_encode_blocks(payload + sig, block=6)  # 22 groups of 6
    return f"{LICENSE_KEY_PREFIX}-{body}"


# ── Key verification ──────────────────────────────────────────────────────────

def _validate_v3(license_key: str, machine_code: str) -> tuple[bool, str, dict[str, str]]:
    """Validate a v3 compact base32 key (THP1-XXXXXX-...-XXXXXX)."""
    stripped = re.sub(r"^THP1[-\s]*", "", license_key.strip(), flags=re.IGNORECASE)
    try:
        raw = _b32_decode_key(stripped)
    except Exception:
        return False, "License key could not be decoded.", {}
    if len(raw) < 82:
        return False, "License key is incomplete.", {}
    payload, signature = raw[:18], raw[18:82]
    try:
        _public_key().verify(signature, payload)
    except Exception:
        return False, "License key signature is invalid.", {}
    plan = payload[1]
    expiry_days = struct.unpack(">H", payload[8:10])[0]
    mc_bytes = payload[10:18]
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
        exp_date = _date_from_days(expiry_days)
        if date.today() > exp_date:
            return False, "This license key has expired.", {}
        exp_str = exp_date.isoformat()
    plan_name = _PLAN_NAMES.get(plan, f"Plan {plan}")
    return True, "License key is valid.", {
        "name": plan_name,
        "email": "",
        "machine": mc_bytes.hex().upper() if mc_bytes != b"\x00" * 8 else "",
        "expires": exp_str,
        "plan": plan_name,
    }


def _validate_v2(license_key: str, machine_code: str) -> tuple[bool, str, dict[str, str]]:
    """Validate a legacy v2 JSON+base64url key (THP1.payload.sig)."""
    normalized = re.sub(r"\s+", "", license_key.strip())
    parts = normalized.split(".")
    if len(parts) != 3 or parts[0] != LICENSE_KEY_PREFIX:
        return False, "License key format is invalid.", {}
    try:
        payload_raw = b64u_decode(parts[1])
        sig = b64u_decode(parts[2])
    except Exception:
        return False, "License key payload could not be decoded.", {}
    try:
        _public_key().verify(sig, payload_raw)
    except Exception:
        return False, "License key signature is invalid.", {}
    try:
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception:
        return False, "License key data is unreadable.", {}
    if not isinstance(payload, dict):
        return False, "License key payload is invalid.", {}
    key_machine = str(payload.get("mc") or "").strip().upper()
    if key_machine and key_machine != machine_code.strip().upper():
        return False, "This license key is for a different computer.", {}
    exp_text = str(payload.get("exp") or "").strip()
    if exp_text:
        try:
            exp_date = datetime.strptime(exp_text, "%Y-%m-%d").date()
        except ValueError:
            return False, "Invalid expiration date in key.", {}
        if date.today() > exp_date:
            return False, "This license key has expired.", {}
    return True, "License key is valid.", {
        "name": str(payload.get("n") or "").strip(),
        "email": str(payload.get("e") or "").strip(),
        "machine": key_machine,
        "expires": exp_text,
    }


def validate_license_key(license_key: str, machine_code: str) -> tuple[bool, str, dict[str, str]]:
    """Validate any supported key version (v2 JSON or v3 compact)."""
    stripped = re.sub(r"\s+", "", str(license_key or "").strip())
    if stripped.upper().startswith("THP1."):
        return _validate_v2(license_key, machine_code)
    return _validate_v3(license_key, machine_code)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate and verify CuraStack Software license keys.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Plans: solo (default), group, dev\nExample:\n  python license_key_tool.py --name \"Happy Minds\" --email owner@clinic.com --plan solo",
    )
    parser.add_argument("--name", help="Customer or practice name (for your records).")
    parser.add_argument("--email", help="Customer email (for your records).")
    parser.add_argument("--plan", default="solo", choices=["solo", "group", "dev"], help="License plan.")
    parser.add_argument("--machine", default="", help="Machine code from customer app (optional).")
    parser.add_argument("--expires", default="", help="Expiration date YYYY-MM-DD (optional).")
    parser.add_argument("--verify", default="", help="License key to verify.")
    parser.add_argument("--show-machine", action="store_true", help="Print this machine's code.")
    args = parser.parse_args()

    if args.show_machine:
        print(current_machine_code())

    if args.verify:
        check_machine = (args.machine or current_machine_code()).strip().upper()
        ok, msg, data = validate_license_key(args.verify, check_machine)
        print(msg)
        if data:
            print(json.dumps(data, indent=2))
        return 0 if ok else 1

    if not args.name or not args.email:
        parser.error("--name and --email are required when generating a key.")

    if args.expires:
        try:
            datetime.strptime(args.expires, "%Y-%m-%d")
        except ValueError:
            parser.error("--expires must be in YYYY-MM-DD format.")

    plan_code = _PLAN_CODES.get(args.plan, 1)
    key = build_license_key(args.name, args.email, args.machine, args.expires, plan=plan_code)
    sep = "-" * 72
    print(sep)
    print("LICENSE KEY (copy everything between the dashes):")
    print(sep)
    print(key)
    print(sep)
    print(f"  Name  : {args.name}")
    print(f"  Email : {args.email}")
    print(f"  Plan  : {_PLAN_NAMES[plan_code]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
