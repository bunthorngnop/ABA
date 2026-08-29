from decimal import Decimal

from app.database import PaymentStore
from app.models import ParserStatus, PaymentResult


def payment(amount, currency, sender="CUSTOMER", bank="ABA"):
    return PaymentResult(Decimal(amount), currency, sender, bank, "ABA PAY", True, ParserStatus.VALID)


def test_summary_and_history_include_only_successfully_spoken_payments(tmp_path):
    store = PaymentStore(tmp_path / "state.sqlite3")
    first = store.reserve(-1001, 1, None, payment("2000", "KHR", "VAN VET"))
    second = store.reserve(-1001, 2, None, payment("5.00", "USD", "NHEAN MONYRACHANA", "ACLEDA"))
    muted = store.reserve(-1001, 3, None, payment("9999", "KHR", "MUTED CUSTOMER"))
    rejected = store.reserve(-1001, 4, None, PaymentResult(reason_if_rejected="safe_test"))
    store.set_announcement_status(first, "SPOKEN")
    store.set_announcement_status(second, "SPOKEN")
    store.set_announcement_status(muted, "MUTED")

    summary = store.today_summary()
    recent = store.recent_announced()

    assert summary == {"count": 2, "KHR": "2000", "USD": "5"}
    assert [row["sender_name"] for row in recent] == ["NHEAN MONYRACHANA", "VAN VET"]
    assert all(row["sender_name"] != "MUTED CUSTOMER" for row in recent)
    assert rejected not in {row["event_key"] for row in recent}
    assert set(recent[0]) == {"event_key", "amount", "currency", "sender_name", "bank", "received_at"}
    store.close()
