from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class ParserStatus(str, Enum):
    VALID = "VALID"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass(frozen=True)
class PaymentResult:
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    sender_name: Optional[str] = None
    bank: Optional[str] = None
    payment_channel: Optional[str] = None
    valid_incoming_payment: bool = False
    status: ParserStatus = ParserStatus.REJECTED
    reason_if_rejected: Optional[str] = None

