from decimal import Decimal

from app.payment_parser import build_announcement, parse_payment


def test_observed_aba_pay_shape_without_staff_fragment_and_with_empty_remark():
    text = "៛100 paid by TEST CUSTOMER (*123) on Aug 29, 04:23 AM via ABA PAY at ហាងសាកល្បង. Remark:  . Trx. ID: 123456, APV: 654321."
    result = parse_payment(text)
    assert result.valid_incoming_payment
    assert (result.amount, result.currency, result.sender_name, result.bank, result.payment_channel) == (
        Decimal("100"), "KHR", "TEST CUSTOMER", "ABA", "ABA PAY")
    assert build_announcement(result) == "បានទទួលប្រាក់ ១០០រៀល ពីឈ្មោះ TEST CUSTOMER, ធនាគារ អេ ប៊ី អេ។"


def test_observed_aba_pay_shape_without_staff_or_remark():
    text = "៛23,000 paid by TEST CUSTOMER (*123) on Aug 28, 08:08 PM via ABA PAY at ហាងសាកល្បង. Trx. ID: 123456, APV: 654321."
    result = parse_payment(text)
    assert result.valid_incoming_payment
    assert result.sender_name == "TEST CUSTOMER"
    assert result.bank == "ABA"


def test_observed_ppcbank_khqr_shape_is_explicitly_normalized():
    text = "៛133,000 paid by TEST CUSTOMER (*123) on Aug 28, 06:37 PM via ABA KHQR (PPCBank) at ហាងសាកល្បង. Trx. ID: 123456, APV: 654321."
    result = parse_payment(text)
    assert result.valid_incoming_payment
    assert result.bank == "PPCBank"
    assert result.payment_channel == "ABA KHQR"
    assert build_announcement(result) == "បានទទួលប្រាក់ ១ សែន ៣ ម៉ឺន ៣ ពាន់រៀល ពីឈ្មោះ TEST CUSTOMER, ធនាគារ ភី ភី ស៊ី។"
