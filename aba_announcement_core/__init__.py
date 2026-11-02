"""Offline, privacy-safe Khmer announcement primitives for future viewers."""

from .banks import BankResolution, bank_for_code, resolve_bank
from .events import EVENT_SCHEMA_VERSION, EventValidationError, PaymentEvent
from .speech import announcement_text
from .state import LocalAnnouncementState, transition_state

__version__ = "0.1.0"

__all__ = [
    "BankResolution",
    "EVENT_SCHEMA_VERSION",
    "EventValidationError",
    "LocalAnnouncementState",
    "PaymentEvent",
    "__version__",
    "announcement_text",
    "bank_for_code",
    "resolve_bank",
    "transition_state",
]