import pytest

from app.models import ParserStatus
from app.payment_parser import build_announcement, parse_payment


@pytest.mark.parametrize("text", [
    "You sent $5.00 to VAN VET", "Transfer failed", "Payment pending", "hello everyone",
    "$5 paid by someone", "Your OTP is 123456", "Balance: $500",
])
def test_unsafe_or_unrelated_text_is_silent(text):
    result = parse_payment(text)
    assert not result.valid_incoming_payment
    assert result.status in (ParserStatus.REJECTED, ParserStatus.NEEDS_REVIEW)


def test_unknown_bank_is_not_guessed_but_confirmed_shape_remains_valid():
    text = "$5.00 paid by SOME NAME (*298) on Aug 28, 08:55 PM via ABA KHQR (Unknown Bank Ltd.) at Shop by STAFF. Trx. ID: 123, APV: 456."
    result = parse_payment(text)
    assert result.valid_incoming_payment
    assert result.bank is None
    assert result.raw_bank_label == "Unknown Bank Ltd."
    assert result.institution_status == "UNMAPPED"
    assert "Unknown Bank" not in build_announcement(result)


def test_unconfirmed_channel_is_not_generalized():
    text = "$5.00 paid by SOME NAME (*298) on Aug 28, 08:55 PM via OTHER PAY at Shop by STAFF. Trx. ID: 123, APV: 456."
    assert parse_payment(text).status == ParserStatus.NEEDS_REVIEW


@pytest.mark.parametrize("label", ["NEW FUTURE BANK XYZ", "UNMAPPED FOREIGN NETWORK"])
def test_unknown_bank_or_network_is_valid_but_unmapped(label):
    text = f"៛12,345 paid by TEST CUSTOMER (*123) on Aug 29, 06:00 PM via ABA KHQR ({label}) at Wing Mart R by S.NHEL. Trx. ID: TESTONLY, APV: 000000."
    assert parse_payment(text).reason_if_rejected == "test_fixture_not_production"
    result = parse_payment(text, allow_test_fixture=True)
    assert result.valid_incoming_payment
    assert result.status == ParserStatus.VALID
    assert result.sender_name == "TEST CUSTOMER"
    assert result.raw_bank_label == label
    assert result.canonical_bank is None
    assert result.display_bank is None
    assert result.spoken_bank is None
    assert result.institution_status == "UNMAPPED"
    spoken = build_announcement(result)
    assert spoken == "បានទទួលប្រាក់ ១ ម៉ឺន ២ ពាន់ ៣៤៥រៀល ពីឈ្មោះ TEST CUSTOMER។"
    assert label not in spoken


def test_payer_must_still_be_a_safe_unicode_name():
    text = "៛100 paid by TEST/INJECTED (*123) on Aug 29, 06:00 PM via ABA PAY at Shop. Trx. ID: 123456, APV: 000000."
    result = parse_payment(text)
    assert not result.valid_incoming_payment
    assert result.reason_if_rejected == "invalid_payer"
