"""ZATCA phase-1 (generation phase) simplified tax invoices and credit notes.

What each issued document carries (Phase-1 requirements for a B2C
"فاتورة ضريبية مبسطة"):

- the title "فاتورة ضريبية مبسطة" / "Simplified Tax Invoice" (credit notes:
  "إشعار دائن");
- seller name and VAT registration number (``SELLER_VAT_NUMBER``), freelance
  document number (``SELLER_CR_NUMBER``) and address from settings;
- a sequential number from a DB counter (``INV-000001``, ``CRN-000001``),
  never the payment UUID;
- the issue date and time;
- one line per item (plan by its Arabic name, add-on agents, usage packs,
  setup fee, discounts) with VAT 15% per line and the totals;
- the TLV base64 QR (tag 1 seller, 2 VAT no, 3 timestamp, 4 total incl. VAT,
  5 VAT total).

Line totals always reconcile to the charged amount: per-line VAT is rounded,
and any 1-halala rounding difference is put on the largest line so the
invoice total equals ``payments.total_with_vat(payment.amount)``.

An invoice is issued once per payment, when it is paid (idempotent). Unpaid
orders render as a pro-forma without a tax-invoice number.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.services import catalog
from src.services import payments as pm

VAT_RATE = pm.VAT_RATE
VAT_PERCENT = 15
VAT_PLACEHOLDER = "300000000000003"  # obvious placeholder until the owner sets SELLER_VAT_NUMBER
INVOICE_SERIES = "INV"
CREDIT_SERIES = "CRN"
OVERAGE_PACKAGE = "overage"
TITLE_AR = "فاتورة ضريبية مبسطة"
TITLE_EN = "Simplified Tax Invoice"
CREDIT_TITLE_AR = "إشعار دائن"
CREDIT_TITLE_EN = "Credit Note"


class ZatcaError(ValueError):
    pass


# --------------------------------------------------------------------- seller

def _valid_vat(v: Optional[str]) -> bool:
    v = (v or "").strip()
    return len(v) == 15 and v.isdigit() and v[0] == "3" and v[-1] == "3"


def seller() -> dict:
    """Seller identity snapshot. ``vat_placeholder`` is True when the real VAT
    number has not been configured (the invoice shows a warning)."""
    from src.config.settings import get_settings

    s = get_settings()
    vat = (s.seller_vat_number or "").strip()
    ok = _valid_vat(vat)
    return {
        "name_ar": s.seller_name_ar,
        "name_en": s.seller_name_en,
        "vat_number": vat if ok else VAT_PLACEHOLDER,
        "vat_placeholder": not ok,
        "cr_number": s.seller_cr_number,
        "address_ar": s.seller_address_ar,
    }


def readiness() -> dict:
    """What the owner still has to provide (never echoes secrets)."""
    s = seller()
    missing = []
    if s["vat_placeholder"]:
        missing.append("SELLER_VAT_NUMBER (15-digit VAT registration number, starts and ends with 3)")
    if not (s["cr_number"] or "").strip():
        missing.append("SELLER_CR_NUMBER")
    if not (s["address_ar"] or "").strip():
        missing.append("SELLER_ADDRESS_AR (national address)")
    return {"ready": not missing, "missing": missing, "vat_placeholder": s["vat_placeholder"]}


# --------------------------------------------------------------------- QR TLV

def _tlv(tag: int, value: str) -> bytes:
    raw = value.encode("utf-8")
    if len(raw) > 255:
        raise ZatcaError(f"TLV value for tag {tag} too long")
    return bytes([tag, len(raw)]) + raw


def _sar(halalas: int) -> str:
    return f"{halalas / 100:.2f}"


def qr_tlv_base64(seller_name: str, vat_number: str, issued_at: datetime, total: int, vat_total: int) -> str:
    ts = issued_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    blob = (_tlv(1, seller_name) + _tlv(2, vat_number) + _tlv(3, ts)
            + _tlv(4, _sar(total)) + _tlv(5, _sar(vat_total)))
    return base64.b64encode(blob).decode("ascii")


def decode_tlv(b64: str) -> dict[int, str]:
    data, out, i = base64.b64decode(b64), {}, 0
    while i < len(data):
        tag, ln = data[i], data[i + 1]
        out[tag] = data[i + 2:i + 2 + ln].decode("utf-8")
        i += 2 + ln
    return out


def qr_svg(payload: str) -> Optional[str]:
    """Inline SVG of the QR when the optional ``segno`` package is installed."""
    try:
        import io

        import segno  # type: ignore
    except Exception:
        return None
    buf = io.BytesIO()
    segno.make(payload, error="m").save(buf, kind="svg", scale=3, xmldecl=False, svgns=True)
    return buf.getvalue().decode("utf-8")


# --------------------------------------------------------------------- lines

def plan_name_ar(key: Optional[str]) -> str:
    """Human Arabic plan name, never the raw key ('radd' -> 'باقة ردّ')."""
    key = key or ""
    if key in catalog.PACKAGES:
        return f"باقة {catalog.PACKAGES[key]['name']}"
    if key in catalog.LEGACY_TIERS:
        return f"باقة {catalog.LEGACY_TIERS[key]['name']}"
    if key in getattr(catalog, "DOMAINS", {}):
        return f"باقة {catalog.DOMAINS[key]['name']}"
    if key == OVERAGE_PACKAGE:
        return "استهلاك إضافي"
    return "اشتراك النرجس للذكاء الاصطناعي"


def _line(name: str, qty: int, unit: int) -> dict:
    return {"name": name, "qty": qty, "unit": unit, "net": qty * unit}


def build_lines(payment) -> list[dict]:
    """Invoice lines (pre-VAT halalas) reconciling exactly to ``payment.amount``."""
    period = catalog.resolve_billing_period(getattr(payment, "billing_period", None) or "monthly")
    months = catalog.BILLING_PERIODS[period]["months_billed"]
    period_ar = "سنوي — 12 شهراً بسعر 10" if period == "annual" else "شهري"
    conv = int(getattr(payment, "addon_conversation_packs", 0) or 0)
    voice = int(getattr(payment, "addon_voice_packs", 0) or 0)
    conv_unit = catalog.USAGE_ADDONS["conversations"]["amount"]
    voice_unit = catalog.USAGE_ADDONS["voice_minutes"]["amount"]
    lines: list[dict] = []

    if payment.package == OVERAGE_PACKAGE:
        if conv:
            lines.append(_line(f"استهلاك إضافي: {catalog.USAGE_ADDONS['conversations']['name']}", conv, conv_unit))
        if voice:
            lines.append(_line(f"استهلاك إضافي: {catalog.USAGE_ADDONS['voice_minutes']['name']}", voice, voice_unit))
        meta = int(payment.amount) - sum(l["net"] for l in lines)
        if meta:
            lines.append(_line("رسوم ميتا فوق السقف (بالتكلفة)", 1, meta))
        return lines

    package = catalog.resolve_tier(payment.package) if payment.package in getattr(catalog, "DOMAINS", {}) else payment.package
    if package not in catalog.PACKAGES and package not in catalog.LEGACY_TIERS:
        return [_line(payment.description or plan_name_ar(package), 1, int(payment.amount))]

    addons = int(getattr(payment, "addon_agents", 0) or 0)
    base = catalog.plan_amount(package, period, 0)
    lines.append(_line(f"{plan_name_ar(package)} — اشتراك {period_ar}" + (" (تجديد)" if payment.is_renewal else ""), 1, base))
    if addons:
        per = (catalog.plan_amount(package, period, addons) - base) // addons
        lines.append(_line(f"{catalog.ADDON_AGENT['name']} ({period_ar})", addons, per))
    if conv:
        lines.append(_line(f"باقة {catalog.USAGE_ADDONS['conversations']['name']} ({period_ar})", conv, conv_unit * months))
    if voice:
        lines.append(_line(f"باقة {catalog.USAGE_ADDONS['voice_minutes']['name']} ({period_ar})", voice, voice_unit * months))
    fee = catalog.setup_fee(package, period, renewal=bool(payment.is_renewal), founding=bool(payment.founding)) \
        if package in catalog.PACKAGES else 0
    if fee:
        lines.append(_line("رسوم إعداد وتشغيل (لمرة واحدة)", 1, fee))
    gross = sum(l["net"] for l in lines)
    diff = int(payment.amount) - gross
    if diff < 0:
        label = "خصم العملاء المؤسسين" if payment.founding else "خصم"
        lines.append(_line(label, 1, diff))
    elif diff > 0:  # price changed since the order: never invent a line, show the difference
        lines.append(_line("تسوية سعر", 1, diff))
    return lines


def with_vat(lines: list[dict], expected_vat: Optional[int] = None) -> tuple[list[dict], int, int, int]:
    """Add per-line VAT (15%) and return (lines, subtotal, vat_total, total)."""
    out = [dict(l, vat_rate=VAT_PERCENT, vat=round(l["net"] * VAT_RATE)) for l in lines]
    subtotal = sum(l["net"] for l in out)
    vat_total = sum(l["vat"] for l in out)
    if expected_vat is not None and out and vat_total != expected_vat:
        big = max(out, key=lambda l: l["net"])
        big["vat"] += expected_vat - vat_total
        vat_total = expected_vat
    for l in out:
        l["gross"] = l["net"] + l["vat"]
    return out, subtotal, vat_total, subtotal + vat_total


def preview(payment) -> dict:
    """Lines and totals for any order (paid or not) without issuing anything."""
    lines, subtotal, vat_total, total = with_vat(build_lines(payment), pm.vat_amount(int(payment.amount)))
    return {"lines": lines, "subtotal": subtotal, "vat_total": vat_total, "total": total}


# --------------------------------------------------------------------- issue

async def next_number(session: AsyncSession, series: str) -> str:
    """Allocate the next number of a series inside the caller's transaction."""
    from src.models.billing import InvoiceSequence

    row = (await session.execute(
        select(InvoiceSequence).where(InvoiceSequence.series == series).with_for_update()
    )).scalar_one_or_none()
    if row is None:
        row = InvoiceSequence(series=series, last_value=0)
        session.add(row)
    row.last_value = int(row.last_value or 0) + 1
    await session.flush()
    return f"{series}-{row.last_value:06d}"


async def invoice_for(session: AsyncSession, payment_id) -> Optional[object]:
    from src.models.billing import TaxInvoice

    return (await session.execute(
        select(TaxInvoice).where(TaxInvoice.payment_id == payment_id, TaxInvoice.kind == "invoice")
    )).scalar_one_or_none()


async def credit_notes_for(session: AsyncSession, payment_id) -> list:
    from src.models.billing import TaxInvoice

    return list((await session.execute(
        select(TaxInvoice).where(TaxInvoice.payment_id == payment_id, TaxInvoice.kind == "credit_note")
        .order_by(TaxInvoice.credit_seq)
    )).scalars().all())


async def ensure_invoice(session: AsyncSession, payment, *, now: Optional[datetime] = None):
    """Issue the simplified tax invoice for a PAID payment (once). Returns it, or
    None when the payment is not paid."""
    from src.models.billing import TaxInvoice

    if payment is None or payment.status != "paid":
        return None
    existing = await invoice_for(session, payment.id)
    if existing is not None:
        return existing
    issued_at = now or datetime.now(timezone.utc)
    sel = seller()
    p = preview(payment)
    inv = TaxInvoice(
        invoice_number=await next_number(session, INVOICE_SERIES),
        kind="invoice",
        credit_seq=0,
        payment_id=payment.id,
        issued_at=issued_at,
        seller=sel,
        buyer_name=payment.customer_name,
        lines=p["lines"],
        subtotal=p["subtotal"],
        vat_total=p["vat_total"],
        total=p["total"],
        qr_tlv=qr_tlv_base64(sel["name_ar"], sel["vat_number"], issued_at, p["total"], p["vat_total"]),
    )
    session.add(inv)
    await session.commit()
    return inv


async def issue_credit_note(session: AsyncSession, payment, *, amount: Optional[int] = None,
                            reason: str = "استرداد", now: Optional[datetime] = None):
    """Credit note against the payment's tax invoice. ``amount`` is pre-VAT
    halalas (default: whatever is not yet credited). Never credits more than
    the original invoice."""
    from src.models.billing import TaxInvoice

    original = await ensure_invoice(session, payment, now=now) if payment.status == "paid" else await invoice_for(session, payment.id)
    if original is None:
        raise ZatcaError("no tax invoice for this payment (only paid orders can be credited)")
    notes = await credit_notes_for(session, payment.id)
    credited = sum(int(n.subtotal) for n in notes)
    remaining = int(original.subtotal) - credited
    amount = remaining if amount is None else int(amount)
    if amount <= 0 or amount > remaining:
        raise ZatcaError(f"credit amount must be between 1 and {remaining} halalas")
    issued_at = now or datetime.now(timezone.utc)
    sel = seller()
    full = amount == int(original.subtotal) and not notes
    if full:
        lines = [dict(l) for l in original.lines]
        subtotal, vat_total, total = int(original.subtotal), int(original.vat_total), int(original.total)
    else:
        lines, subtotal, vat_total, total = with_vat([_line(f"إشعار دائن عن الفاتورة {original.invoice_number}: {reason}", 1, amount)])
    note = TaxInvoice(
        invoice_number=await next_number(session, CREDIT_SERIES),
        kind="credit_note",
        credit_seq=len(notes) + 1,
        payment_id=payment.id,
        original_invoice_id=original.id,
        issued_at=issued_at,
        seller=sel,
        buyer_name=payment.customer_name,
        lines=lines,
        subtotal=subtotal,
        vat_total=vat_total,
        total=total,
        qr_tlv=qr_tlv_base64(sel["name_ar"], sel["vat_number"], issued_at, total, vat_total),
        reason=reason,
    )
    session.add(note)
    await session.commit()
    return note


def to_dict(inv) -> dict:
    return {
        "id": str(inv.id),
        "invoice_number": inv.invoice_number,
        "kind": inv.kind,
        "payment_id": str(inv.payment_id),
        "original_invoice_id": str(inv.original_invoice_id) if inv.original_invoice_id else None,
        "issued_at": inv.issued_at.isoformat() if inv.issued_at else None,
        "seller": inv.seller,
        "buyer_name": inv.buyer_name,
        "lines": inv.lines,
        "subtotal": inv.subtotal,
        "vat_total": inv.vat_total,
        "total": inv.total,
        "qr_tlv": inv.qr_tlv,
        "reason": inv.reason,
    }


async def count_issued(session: AsyncSession) -> int:
    from src.models.billing import TaxInvoice

    return int((await session.execute(select(func.count(TaxInvoice.id)))).scalar() or 0)
