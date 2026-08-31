"""Patient invoice PDF generation helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping


def _as_float(value: object) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _as_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _line(draw_page, x0: float, y: float, x1: float, color=(0.84, 0.86, 0.9), width: float = 0.8) -> None:
    draw_page.draw_line((x0, y), (x1, y), color=color, width=width)


def _patient_name(patient: Mapping[str, object]) -> str:
    first = _as_text(patient.get("first_name"))
    last = _as_text(patient.get("last_name"))
    full = f"{first} {last}".strip()
    return full or "Unknown Patient"


def generate_patient_invoice(
    output_path: str | Path,
    provider: Mapping[str, object],
    patient: Mapping[str, object],
    billing_rows: Iterable[Mapping[str, object]],
) -> str:
    """Create a printable invoice PDF for one patient and return its path."""
    import fitz

    rows = list(billing_rows)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    practice_name = _as_text(provider.get("practice_name")) or "CuraStack Software"
    provider_phone = _as_text(provider.get("phone"))
    provider_email = _as_text(provider.get("email"))
    provider_addr1 = _as_text(provider.get("address"))
    provider_addr2 = " ".join(
        part for part in [_as_text(provider.get("city")), _as_text(provider.get("state")), _as_text(provider.get("zip"))] if part
    ).strip()

    patient_name = _patient_name(patient)
    patient_addr1 = _as_text(patient.get("address"))
    patient_addr2 = " ".join(
        part for part in [_as_text(patient.get("city")), _as_text(patient.get("state")), _as_text(patient.get("zip"))] if part
    ).strip()

    total_charge = sum(_as_float(r.get("charge")) for r in rows)
    total_patient_paid = sum(_as_float(r.get("payment")) for r in rows)
    total_ins_paid = sum(_as_float(r.get("ins_payment")) for r in rows)
    total_adjust = sum(_as_float(r.get("adjustment")) for r in rows)
    total_balance = sum(_as_float(r.get("balance")) for r in rows)
    amount_due = sum(max(_as_float(r.get("balance")), 0.0) for r in rows)

    outstanding_copay = 0.0
    for r in rows:
        text = f"{_as_text(r.get('description'))} {_as_text(r.get('payment_type'))}".lower()
        if "copay" in text or "co-pay" in text:
            outstanding_copay += max(_as_float(r.get("balance")), 0.0)

    now = datetime.now()
    invoice_no = f"INV-{_as_text(patient.get('id')) or 'NA'}-{now.strftime('%Y%m%d')}"
    due_date = now.replace(day=min(now.day, 28))
    if due_date.month == now.month:
        # Net-30 due date.
        from datetime import timedelta

        due_date = now + timedelta(days=30)

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    left = 42
    right = 570
    y = 44

    page.insert_text((left, y), practice_name, fontsize=20, fontname="helv", color=(0.07, 0.16, 0.32))
    y += 18
    if provider_addr1:
        page.insert_text((left, y), provider_addr1, fontsize=10, fontname="helv", color=(0.22, 0.25, 0.30))
        y += 13
    if provider_addr2:
        page.insert_text((left, y), provider_addr2, fontsize=10, fontname="helv", color=(0.22, 0.25, 0.30))
        y += 13
    contact_bits = [x for x in [provider_phone, provider_email] if x]
    if contact_bits:
        page.insert_text((left, y), " | ".join(contact_bits), fontsize=10, fontname="helv", color=(0.22, 0.25, 0.30))

    page.insert_text((right - 92, 44), "INVOICE", fontsize=18, fontname="helv", color=(0.07, 0.16, 0.32))
    page.insert_text((right - 130, 65), f"Invoice #: {invoice_no}", fontsize=10, fontname="helv")
    page.insert_text((right - 130, 79), f"Date: {now.strftime('%m/%d/%Y')}", fontsize=10, fontname="helv")
    page.insert_text((right - 130, 93), f"Due Date: {due_date.strftime('%m/%d/%Y')}", fontsize=10, fontname="helv")

    _line(page, left, 108, right)

    page.insert_text((left, 126), "Bill To", fontsize=11, fontname="helv", color=(0.07, 0.16, 0.32))
    page.insert_text((left, 141), patient_name, fontsize=11, fontname="helv")
    if patient_addr1:
        page.insert_text((left, 155), patient_addr1, fontsize=10, fontname="helv")
    if patient_addr2:
        page.insert_text((left, 169), patient_addr2, fontsize=10, fontname="helv")

    box_x = 355
    page.draw_rect((box_x, 120, right, 186), color=(0.82, 0.84, 0.88), fill=(0.97, 0.98, 1.0), width=0.8)
    page.insert_text((box_x + 10, 138), f"Outstanding Co-Pays: {_money(outstanding_copay)}", fontsize=10, fontname="helv")
    page.insert_text((box_x + 10, 154), f"Remaining Amount Owed: {_money(amount_due)}", fontsize=10, fontname="helv")
    page.insert_text((box_x + 10, 172), f"Current Balance: {_money(total_balance)}", fontsize=10, fontname="helv")

    table_top = 224
    col_x = [left, 98, 248, 316, 384, 452, 516, right]
    headers = ["Date", "Description", "Charge", "Pt Paid", "Ins Paid", "Adj", "Balance"]

    page.draw_rect((left, table_top, right, table_top + 18), color=(0.24, 0.31, 0.48), fill=(0.92, 0.95, 1.0), width=0.8)
    for idx, head in enumerate(headers):
        page.insert_text((col_x[idx] + 4, table_top + 13), head, fontsize=9, fontname="helv", color=(0.07, 0.16, 0.32))

    row_y = table_top + 18
    row_h = 17
    max_rows = 28

    for i, r in enumerate(rows[:max_rows]):
        if i % 2:
            page.draw_rect((left, row_y, right, row_y + row_h), color=None, fill=(0.98, 0.99, 1.0), width=0)

        record_date = _as_text(r.get("record_date"))
        desc = _as_text(r.get("description")) or _as_text(r.get("payment_type")) or "Billing Item"
        vals = [
            record_date,
            desc[:36],
            _money(_as_float(r.get("charge"))),
            _money(_as_float(r.get("payment"))),
            _money(_as_float(r.get("ins_payment"))),
            _money(_as_float(r.get("adjustment"))),
            _money(_as_float(r.get("balance"))),
        ]

        page.insert_text((col_x[0] + 4, row_y + 12), vals[0], fontsize=8.8, fontname="helv")
        page.insert_text((col_x[1] + 4, row_y + 12), vals[1], fontsize=8.8, fontname="helv")
        for c in range(2, 7):
            page.insert_text((col_x[c + 1] - 50, row_y + 12), vals[c], fontsize=8.8, fontname="helv")

        row_y += row_h

    page.draw_rect((left, table_top + 18, right, row_y), color=(0.78, 0.8, 0.85), width=0.8)

    sum_y = row_y + 18
    page.draw_rect((362, sum_y - 8, right, sum_y + 80), color=(0.82, 0.84, 0.88), fill=(0.98, 0.99, 1.0), width=0.8)
    page.insert_text((374, sum_y + 8), f"Total Charges: {_money(total_charge)}", fontsize=10, fontname="helv")
    page.insert_text((374, sum_y + 25), f"Patient Paid: {_money(total_patient_paid)}", fontsize=10, fontname="helv")
    page.insert_text((374, sum_y + 42), f"Insurance Paid: {_money(total_ins_paid)}", fontsize=10, fontname="helv")
    page.insert_text((374, sum_y + 59), f"Adjustments: {_money(total_adjust)}", fontsize=10, fontname="helv")
    page.insert_text((374, sum_y + 76), f"Amount Due: {_money(amount_due)}", fontsize=11, fontname="helv", color=(0.56, 0.05, 0.05))

    terms_y = min(sum_y + 108, 706)
    page.draw_rect((left, terms_y - 12, right, terms_y + 26), color=(0.86, 0.88, 0.92), fill=(0.99, 0.995, 1.0), width=0.7)
    page.insert_text((left + 8, terms_y), "Payment Terms: Due within 30 days. Please include invoice number with payment.", fontsize=8.8, fontname="helv", color=(0.22, 0.25, 0.30))
    page.insert_text((left + 8, terms_y + 14), "Questions? Contact the office using the phone/email listed above.", fontsize=8.8, fontname="helv", color=(0.22, 0.25, 0.30))

    foot_y = 760
    _line(page, left, foot_y - 10, right, color=(0.86, 0.88, 0.92), width=0.7)
    page.insert_text(
        (left, foot_y),
        "Thank you for your prompt payment. Please contact the office if you have billing questions.",
        fontsize=8.5,
        fontname="helv",
        color=(0.34, 0.38, 0.44),
    )

    doc.save(str(output_path))
    doc.close()
    return str(output_path)
