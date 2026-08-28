from decimal import Decimal

from app.payment_parser import build_announcement, parse_payment

SAMPLE_A = "៛2,000 paid by VAN VET (*571) on Aug 28, 07:34 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178792044713371, APV: 761253."
SAMPLE_B = "$5.00 paid by NHEAN MONYRACHANA (*298) on Aug 28, 08:55 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart D by S.NHEL. Trx. ID: 178792533376804, APV: 360850."


def test_exact_real_khr_sample():
    result = parse_payment(SAMPLE_A)
    assert (result.amount, result.currency, result.sender_name, result.bank, result.payment_channel) == (
        Decimal("2000"), "KHR", "VAN VET", "ABA", "ABA PAY")
    assert result.valid_incoming_payment
    spoken = build_announcement(result)
    assert spoken == "បានទទួលប្រាក់ ២ ពាន់រៀល ពីឈ្មោះ VAN VET, ធនាគារ ABA។"
    for private in ("*571", "Aug 28", "Wing Mart R", "S.NHEL", "Trx. ID", "APV"):
        assert private not in spoken


def test_exact_real_usd_sample():
    result = parse_payment(SAMPLE_B)
    assert (result.amount, result.currency, result.sender_name, result.bank, result.payment_channel) == (
        Decimal("5.00"), "USD", "NHEAN MONYRACHANA", "ACLEDA", "ABA KHQR")
    assert result.valid_incoming_payment
    spoken = build_announcement(result)
    assert spoken == "បានទទួលប្រាក់ ៥ ដុល្លារ ពីឈ្មោះ NHEAN MONYRACHANA, ធនាគារ ACLEDA។"
    assert "S.NHEL" not in spoken and "*298" not in spoken and "APV" not in spoken
