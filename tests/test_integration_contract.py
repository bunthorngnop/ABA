from decimal import Decimal

import pytest

from app.integration_contract import ALLOWED_EVENT_FIELDS, amount_to_minor, payment_event


def row(**updates):
    value = {
        "event_key": "opaque", "received_at": "2026-09-03T10:00:00+00:00",
        "amount": "1.25", "currency": "USD", "sender_name": "DISPLAY NAME",
        "bank": "ACLEDA", "bank_mapping_status": "VERIFIED",
        "announcement_status": "SPOKEN", "announced_at": "2026-09-03T10:00:01+00:00",
        "chat_id": -1001, "message_id": 2, "raw_message": "forbidden",
    }
    value.update(updates)
    return value


def test_minor_units_are_exact():
    assert amount_to_minor(Decimal("1.25"), "USD") == 125
    assert amount_to_minor(Decimal("5000"), "KHR") == 5000
    with pytest.raises(ValueError):
        amount_to_minor(Decimal("1.001"), "USD")


def test_contract_is_allowlisted_and_contains_no_private_source_fields():
    event = payment_event(row())
    assert set(event) == ALLOWED_EVENT_FIELDS
    assert event["amount_minor"] == 125
    serialized = repr(event).lower()
    for forbidden in ("chat_id", "message_id", "raw_message", "telegram", "apv", "balance"):
        assert forbidden not in serialized


def test_unknown_bank_is_exported_without_rejecting_payment():
    event = payment_event(row(bank=None, bank_mapping_status="UNMAPPED"))
    assert event["bank_display_name"] == "OTHER BANK"
    assert event["bank_mapping_status"] == "UNMAPPED"
