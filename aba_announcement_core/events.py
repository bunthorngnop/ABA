import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping

from .banks import bank_for_code

EVENT_SCHEMA_VERSION = 1
SOURCE_ANNOUNCEMENT_STATUSES = frozenset({"QUEUED", "MUTED", "SPOKEN", "FAILED"})
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_EVENT_FIELDS = frozenset({
    "schema_version",
    "event_id",
    "source_epoch",
    "source_sequence",
    "source_update_at",
    "occurred_at",
    "amount_minor",
    "currency",
    "sender_display_name",
    "bank_code",
    "bank_display_name",
    "bank_mapping_status",
    "source_announcement_status",
})


class EventValidationError(ValueError):
    pass


def _validate_identifier(value: str, field: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise EventValidationError(f"invalid {field}")


def _validate_utc_timestamp(value: str, field: str) -> None:
    if not isinstance(value, str) or len(value) > 40:
        raise EventValidationError(f"invalid {field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EventValidationError(f"invalid {field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise EventValidationError(f"{field} must be UTC")


def _validate_sender(value: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 100:
        raise EventValidationError("invalid sender_display_name")
    if value != " ".join(value.split()):
        raise EventValidationError("sender_display_name must be normalized")
    if not any(unicodedata.category(char).startswith("L") for char in value):
        raise EventValidationError("sender_display_name must contain a letter")
    if any(unicodedata.category(char)[0] not in {"L", "M"} and char not in " .'-" for char in value):
        raise EventValidationError("sender_display_name contains unsupported characters")


@dataclass(frozen=True)
class PaymentEvent:
    schema_version: int
    event_id: str
    source_epoch: str
    source_sequence: int
    source_update_at: str
    occurred_at: str
    amount_minor: int
    currency: str
    sender_display_name: str
    bank_code: str
    bank_display_name: str
    bank_mapping_status: str
    source_announcement_status: str

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != EVENT_SCHEMA_VERSION:
            raise EventValidationError("unsupported schema_version")
        _validate_identifier(self.event_id, "event_id")
        _validate_identifier(self.source_epoch, "source_epoch")
        if type(self.source_sequence) is not int or self.source_sequence < 1:
            raise EventValidationError("invalid source_sequence")
        _validate_utc_timestamp(self.source_update_at, "source_update_at")
        _validate_utc_timestamp(self.occurred_at, "occurred_at")
        if type(self.amount_minor) is not int or self.amount_minor <= 0:
            raise EventValidationError("amount_minor must be a positive integer")
        if self.currency not in {"KHR", "USD"}:
            raise EventValidationError("unsupported currency")
        _validate_sender(self.sender_display_name)
        if self.source_announcement_status not in SOURCE_ANNOUNCEMENT_STATUSES:
            raise EventValidationError("unsupported source_announcement_status")
        if self.bank_code == "UNMAPPED":
            if self.bank_display_name != "OTHER BANK" or self.bank_mapping_status != "UNMAPPED":
                raise EventValidationError("unmapped bank fields are inconsistent")
        else:
            bank = bank_for_code(self.bank_code)
            if bank is None:
                raise EventValidationError("unsupported bank_code")
            if self.bank_display_name != bank.display_name or self.bank_mapping_status != bank.mapping_status:
                raise EventValidationError("bank fields do not match the approved registry")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PaymentEvent":
        if not isinstance(value, Mapping):
            raise EventValidationError("event must be a mapping")
        if set(value) != _EVENT_FIELDS:
            raise EventValidationError("event fields do not match the privacy-safe schema")
        try:
            return cls(**value)
        except TypeError as exc:
            raise EventValidationError("event fields have invalid types") from exc

    def to_mapping(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in _EVENT_FIELDS}