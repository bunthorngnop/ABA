import re
from decimal import Decimal, InvalidOperation

from .bank_normalizer import bank_from_channel
from .khmer_numbers import amount_to_speech
from .models import ParserStatus, PaymentResult

_CONFIRMED = re.compile(
    r"^(?P<currency>៛|\$)(?P<amount>[0-9][0-9,]*(?:\.[0-9]{2})?) paid by "
    r"(?P<payer>[A-Za-z][A-Za-z .'-]{0,99}?) \(\*[0-9]{3}\) on "
    r"(?P<date>[A-Z][a-z]{2} [0-9]{1,2}), (?P<time>[0-9]{1,2}:[0-9]{2} (?:AM|PM)) via "
    r"(?P<channel>ABA PAY|ABA KHQR)(?: \((?P<bank>[^()]+)\))? at "
    r"(?P<merchant>.+?)(?: by (?P<operator>.+?))?\."
    r"(?: Remark: (?P<remark>.*?) \.)? Trx\. ID: [0-9]+, APV: [0-9]+\.$"
)
_DANGER = re.compile(r"\b(outgoing|sent|transfer(?:red)? to|failed|cancelled|canceled|pending)\b", re.I)


def parse_payment(text: str) -> PaymentResult:
    if not isinstance(text, str) or not text.strip():
        return PaymentResult(reason_if_rejected="empty_message")
    candidate = text.strip()
    if _DANGER.search(candidate):
        return PaymentResult(status=ParserStatus.REJECTED, reason_if_rejected="non_incoming_or_unsuccessful")
    match = _CONFIRMED.fullmatch(candidate)
    if not match:
        payment_like = ("paid by" in candidate.lower()) or candidate.startswith(("$", "៛"))
        return PaymentResult(
            status=ParserStatus.NEEDS_REVIEW if payment_like else ParserStatus.REJECTED,
            reason_if_rejected="unsupported_or_malformed_format" if payment_like else "not_a_payment",
        )
    currency = "KHR" if match.group("currency") == "៛" else "USD"
    try:
        amount = Decimal(match.group("amount").replace(",", ""))
    except InvalidOperation:
        return PaymentResult(status=ParserStatus.NEEDS_REVIEW, reason_if_rejected="invalid_amount")
    if amount <= 0 or (currency == "KHR" and amount != amount.to_integral_value()):
        return PaymentResult(status=ParserStatus.NEEDS_REVIEW, reason_if_rejected="invalid_amount")
    channel = match.group("channel")
    raw_bank = match.group("bank")
    if channel == "ABA PAY" and raw_bank is not None:
        return PaymentResult(status=ParserStatus.NEEDS_REVIEW, reason_if_rejected="contradictory_channel_bank")
    if channel == "ABA KHQR" and raw_bank is None:
        return PaymentResult(status=ParserStatus.NEEDS_REVIEW, reason_if_rejected="missing_khqr_bank")
    bank, bank_known = bank_from_channel(channel, raw_bank)
    return PaymentResult(
        amount=amount,
        currency=currency,
        sender_name=" ".join(match.group("payer").split()),
        bank=bank if bank_known else None,
        payment_channel=channel,
        valid_incoming_payment=True,
        status=ParserStatus.VALID,
    )


def build_announcement(payment: PaymentResult) -> str:
    if not payment.valid_incoming_payment or payment.status != ParserStatus.VALID:
        raise ValueError("cannot announce an invalid payment")
    spoken_amount = amount_to_speech(payment.amount, payment.currency or "")
    base = f"បានទទួលប្រាក់ {spoken_amount} ពីឈ្មោះ {payment.sender_name}"
    if payment.bank:
        return f"{base}, ធនាគារ {payment.bank}។"
    return f"{base}។"
