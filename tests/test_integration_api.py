import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app.database import PaymentStore
from app.integration_api import IntegrationRuntimeStatus, IntegrationServer, token_matches
from app.models import ParserStatus, PaymentResult
from app.config import Settings
from main import build_integration_server
from decimal import Decimal


TOKEN = "test-only-token-that-is-at-least-32-characters"


def request(port, path, token=TOKEN):
    return urlopen(Request(f"http://127.0.0.1:{port}{path}", headers={"Authorization": f"Bearer {token}"}), timeout=2)


def test_token_comparison_and_loopback_enforcement(tmp_path):
    assert token_matches(TOKEN, TOKEN)
    assert not token_matches("wrong", TOKEN)
    store = PaymentStore(tmp_path / "db.sqlite3")
    try:
        import pytest
        with pytest.raises(ValueError):
            IntegrationServer("0.0.0.0", 0, TOKEN, store, IntegrationRuntimeStatus(True))
    finally:
        store.close()


def test_authenticated_status_events_cursor_and_status_update(tmp_path):
    store = PaymentStore(tmp_path / "db.sqlite3")
    result = PaymentResult(Decimal("1.25"), "USD", "DISPLAY", "ABA", "ABA PAY", True, ParserStatus.VALID,
                           canonical_bank="ABA Bank", display_bank="ABA", institution_status="VERIFIED")
    key = store.reserve(-1001, 8, None, result)
    server = IntegrationServer("127.0.0.1", 0, TOKEN, store, IntegrationRuntimeStatus(True))
    assert server.start()
    try:
        with request(server.port, "/integration/v1/status") as response:
            assert json.load(response)["service"] == "ABA Payment Speaker"
        with request(server.port, "/integration/v1/events") as response:
            first = json.load(response)
        assert len(first["events"]) == 1
        assert first["events"][0]["announcement_status"] == "QUEUED"
        store.set_announcement_status(key, "SPOKEN")
        with request(server.port, f"/integration/v1/events?after={first['next_cursor']}") as response:
            update = json.load(response)
        assert len(update["events"]) == 1
        assert update["events"][0]["announcement_status"] == "SPOKEN"
        try:
            request(server.port, "/integration/v1/status", "wrong")
            raise AssertionError("authentication should fail")
        except HTTPError as exc:
            assert exc.code == 401
    finally:
        server.stop()
        store.close()


def test_api_bind_failure_is_isolated(tmp_path):
    class FailingServer:
        def __init__(self, *_args): raise OSError("busy")
    store = PaymentStore(tmp_path / "db.sqlite3")
    server = IntegrationServer("127.0.0.1", 8766, TOKEN, store, IntegrationRuntimeStatus(True), FailingServer)
    assert server.start() is False
    store.close()


def test_invalid_integration_configuration_disables_only_api(tmp_path):
    store = PaymentStore(tmp_path / "db.sqlite3")
    settings = Settings(123, "a" * 32, "+85510000000", tmp_path / "user.session", (-1,), 1,
                        "PayWayByABA_bot", False, tmp_path / "db.sqlite3", "voice", "+0%",
                        True, "0.0.0.0", 8766, "short")
    assert build_integration_server(settings, store, IntegrationRuntimeStatus(True)) is None
    store.close()
