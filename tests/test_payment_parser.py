import pytest

from app.models import ParserStatus
from app.payment_parser import parse_payment


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


def test_unconfirmed_channel_is_not_generalized():
    text = "$5.00 paid by SOME NAME (*298) on Aug 28, 08:55 PM via OTHER PAY at Shop by STAFF. Trx. ID: 123, APV: 456."
    assert parse_payment(text).status == ParserStatus.NEEDS_REVIEW

