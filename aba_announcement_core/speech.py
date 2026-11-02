from decimal import Decimal

from .amounts import amount_to_speech
from .banks import bank_for_code
from .events import PaymentEvent


def announcement_text(event: PaymentEvent) -> str:
    if not isinstance(event, PaymentEvent):
        raise TypeError("event must be a validated PaymentEvent")
    if event.currency == "KHR":
        amount = Decimal(event.amount_minor)
    else:
        amount = Decimal(event.amount_minor) / Decimal(100)
    spoken_amount = amount_to_speech(amount, event.currency)
    base = f"បានទទួលប្រាក់ {spoken_amount} ពីឈ្មោះ {event.sender_display_name}"
    bank = bank_for_code(event.bank_code)
    if bank is not None:
        return f"{base}, ធនាគារ {bank.spoken_khmer}។"
    return f"{base}។"