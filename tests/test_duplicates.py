from decimal import Decimal

from app.database import PaymentStore
from app.models import ParserStatus, PaymentResult


def test_duplicate_message_is_reserved_once_and_survives_reopen(tmp_path):
    path = tmp_path / "state.sqlite3"
    result = PaymentResult(Decimal("5"), "USD", "NAME", "ABA", "ABA PAY", True, ParserStatus.VALID)
    store = PaymentStore(path)
    assert store.reserve(-1001, 42, 100, result)
    assert store.reserve(-1001, 42, 101, result) is None
    store.close()
    reopened = PaymentStore(path)
    assert reopened.reserve(-1001, 42, 102, result) is None
    reopened.close()

