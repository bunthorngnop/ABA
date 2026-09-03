from decimal import Decimal
from typing import Any


SCHEMA_VERSION = 1
ALLOWED_EVENT_FIELDS = frozenset({
    "schema_version", "event_id", "occurred_at", "amount_minor", "currency",
    "sender_display_name", "bank_display_name", "bank_mapping_status",
    "announcement_status", "announced_at",
})


def amount_to_minor(amount: str | Decimal, currency: str) -> int:
    value = Decimal(str(amount))
    if currency == "USD":
        minor = value * 100
    elif currency == "KHR":
        minor = value
    else:
        raise ValueError("Unsupported integration currency")
    if minor != minor.to_integral_value():
        raise ValueError("Payment amount cannot be represented in minor units")
    return int(minor)


def payment_event(row: dict[str, Any]) -> dict[str, Any]:
    status = str(row["announcement_status"])
    if status not in {"QUEUED", "SPOKEN", "FAILED"}:
        raise ValueError("Unsupported announcement status")
    mapping = str(row.get("bank_mapping_status") or "UNMAPPED")
    if mapping not in {"VERIFIED", "USER_CONFIRMED", "UNMAPPED"}:
        mapping = "UNMAPPED"
    event = {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(row["event_key"]),
        "occurred_at": str(row["received_at"]),
        "amount_minor": amount_to_minor(row["amount"], str(row["currency"])),
        "currency": str(row["currency"]),
        "sender_display_name": str(row["sender_name"]),
        "bank_display_name": row.get("bank") or ("OTHER BANK" if mapping == "UNMAPPED" else None),
        "bank_mapping_status": mapping,
        "announcement_status": status,
        "announced_at": row.get("announced_at"),
    }
    return {key: event[key] for key in ALLOWED_EVENT_FIELDS}
