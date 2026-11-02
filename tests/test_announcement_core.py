import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from aba_announcement_core import (
    EVENT_SCHEMA_VERSION,
    EventValidationError,
    LocalAnnouncementState,
    PaymentEvent,
    announcement_text,
    transition_state,
)
from aba_announcement_core.amounts import amount_to_speech
from aba_announcement_core.banks import BANKS, resolve_bank


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "announcement_core_events.json"


@pytest.fixture(scope="module")
def synthetic_events():
    raw_events = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return [PaymentEvent.from_mapping(raw_event) for raw_event in raw_events]


def test_event_schema_accepts_only_synthetic_allowlisted_fixture_events(synthetic_events):
    assert EVENT_SCHEMA_VERSION == 1
    assert [event.event_id for event in synthetic_events] == [
        "synthetic-khr-001", "synthetic-usd-002", "synthetic-unmapped-003",
    ]


def test_announcement_text_preserves_khr_usd_and_unknown_bank_behavior(synthetic_events):
    assert announcement_text(synthetic_events[0]) == "បានទទួលប្រាក់ ២ ពាន់ ៥០០រៀល ពីឈ្មោះ Synthetic User, ធនាគារ អេ ប៊ី អេ។"
    assert announcement_text(synthetic_events[1]) == "បានទទួលប្រាក់ ១ ដុល្លារ ២៥ សេន ពីឈ្មោះ Synthetic Khmer, ធនាគារ អេស៊ីលីដា។"
    assert announcement_text(synthetic_events[2]) == "បានទទួលប្រាក់ ៥ ពាន់រៀល ពីឈ្មោះ Sample Payer។"


@pytest.mark.parametrize("field,value", [
    ("schema_version", 2),
    ("event_id", "raw message text"),
    ("source_sequence", True),
    ("amount_minor", True),
    ("amount_minor", 0),
    ("currency", "EUR"),
    ("sender_display_name", "Synthetic\nUser"),
    ("source_update_at", "2026-10-19T10:00:00"),
    ("bank_code", "UNAPPROVED_BANK"),
    ("source_announcement_status", "PENDING"),
])
def test_event_schema_rejects_invalid_values(synthetic_events, field, value):
    event = synthetic_events[0].to_mapping()
    event[field] = value
    with pytest.raises(EventValidationError):
        PaymentEvent.from_mapping(event)


def test_event_schema_rejects_extra_private_fields(synthetic_events):
    event = synthetic_events[0].to_mapping()
    event["raw_message"] = "synthetic private content"
    with pytest.raises(EventValidationError, match="privacy-safe schema"):
        PaymentEvent.from_mapping(event)


def test_event_mapping_round_trip_is_stable(synthetic_events):
    assert PaymentEvent.from_mapping(synthetic_events[0].to_mapping()) == synthetic_events[0]


def test_all_approved_bank_aliases_match_existing_registry():
    from app.bank_normalizer import INSTITUTIONS, resolve_institution

    assert len(BANKS) == len(INSTITUTIONS) == 24
    for institution in INSTITUTIONS:
        for alias in (*institution.aliases, *institution.verified_codes):
            existing = resolve_institution("ABA KHQR", alias)
            core = resolve_bank("ABA KHQR", alias)
            assert (core.bank_code, core.canonical_name, core.display_name, core.spoken_khmer, core.mapping_status) == (
                institution.canonical_id,
                existing.canonical_name,
                existing.display_name,
                existing.spoken_khmer,
                existing.status,
            )


def test_unknown_bank_is_not_guessed_and_aba_pay_remains_aba():
    unknown = resolve_bank("ABA KHQR", "synthetic unknown network")
    assert unknown.bank_code is None
    assert unknown.display_name is None
    assert unknown.spoken_khmer is None
    assert resolve_bank("ABA PAY", None).bank_code == "ABA"


@pytest.mark.parametrize(("currency", "amount"), [
    ("KHR", "0"), ("KHR", "2500"), ("KHR", "2350000"),
    ("USD", "0.00"), ("USD", "0.01"), ("USD", "1.25"), ("USD", "100.92"),
])
def test_amount_pronunciation_matches_existing_helper(currency, amount):
    from app.khmer_numbers import amount_to_speech as existing_amount_to_speech

    assert amount_to_speech(amount, currency) == existing_amount_to_speech(amount, currency)


def test_local_state_model_prevents_automatic_replay_after_claim():
    claimed = transition_state(LocalAnnouncementState.QUEUED, LocalAnnouncementState.CLAIMED)
    assert transition_state(claimed, LocalAnnouncementState.SPOKEN) is LocalAnnouncementState.SPOKEN
    with pytest.raises(ValueError):
        transition_state(LocalAnnouncementState.SPOKEN, LocalAnnouncementState.CLAIMED)
    with pytest.raises(ValueError):
        transition_state(LocalAnnouncementState.FAILED, LocalAnnouncementState.CLAIMED)


@pytest.mark.parametrize("terminal_state", [
    LocalAnnouncementState.MUTED,
    LocalAnnouncementState.FAILED,
    LocalAnnouncementState.EXPIRED,
])
def test_local_terminal_states_cannot_be_reopened(terminal_state):
    with pytest.raises(ValueError):
        transition_state(terminal_state, LocalAnnouncementState.CLAIMED)


def test_package_imports_without_application_or_network_database_modules():
    script = (
        "import sys; import aba_announcement_core; "
        "blocked = {'app', 'telethon', 'sqlite3', 'socket', 'http', 'urllib', 'requests', 'pygame', 'edge_tts'}; "
        "assert not any(name.split('.')[0] in blocked for name in sys.modules), sys.modules.keys()"
    )
    subprocess.run([sys.executable, "-S", "-c", script], cwd=ROOT, check=True, capture_output=True, text=True)


def test_package_source_imports_only_stdlib_and_its_own_modules():
    package_dir = ROOT / "aba_announcement_core"
    for source_path in package_dir.glob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                roots = [(node.module or "").split(".", 1)[0]]
            else:
                continue
            assert all(root in sys.stdlib_module_names or root == "aba_announcement_core" for root in roots), (
                source_path.name,
                roots,
            )