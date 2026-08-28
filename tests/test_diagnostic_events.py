import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.config import Settings
from app.telegram_listener import TelegramListener


def test_ordinary_group_message_emits_safe_discovery_metadata():
    events = []
    settings = Settings(12345, "a" * 32, "+85510000000", Path("user.session"), (), None,
                        "PayWayByABA_bot", True, Path("x"), "voice", "+0%")
    listener = TelegramListener(settings, object(), lambda text, key: None, lambda event, value: events.append((event, value)))
    update = SimpleNamespace(
        chat_id=-100123, sender_id=111, is_group=True, raw_text="hello", id=7,
        get_chat=lambda: asyncio.sleep(0, result=SimpleNamespace(title="Payment Group")),
        get_sender=lambda: asyncio.sleep(0, result=SimpleNamespace(id=111, username="Operator")),
    )
    asyncio.run(listener._handle(update))
    assert events[0] == ("diagnostic", {
        "chat_id": -100123,
        "chat_title": "Payment Group",
        "chat_type": "group",
        "sender_id": 111,
        "username": "Operator",
        "message_type": "text",
        "expected_username": "PayWayByABA_bot",
        "expected_source_detected": False,
    })
    assert events[1] == ("setup", "Groups detected")


def test_expected_source_event_includes_numeric_sender_and_match():
    events = []
    settings = Settings(12345, "a" * 32, "+85510000000", Path("user.session"), (), None,
                        "PayWayByABA_bot", True, Path("x"), "voice", "+0%")
    listener = TelegramListener(settings, object(), lambda text, key: None, lambda event, value: events.append((event, value)))
    update = SimpleNamespace(
        chat_id=-100456, sender_id=987654, is_group=True, raw_text="notification", id=8,
        get_chat=lambda: asyncio.sleep(0, result=SimpleNamespace(title="ABA Group")),
        get_sender=lambda: asyncio.sleep(0, result=SimpleNamespace(id=987654, username="PayWayByABA_bot")),
    )
    asyncio.run(listener._handle(update))
    diagnostic = events[0][1]
    assert diagnostic["chat_title"] == "ABA Group"
    assert diagnostic["chat_id"] == -100456
    assert diagnostic["sender_id"] == 987654
    assert diagnostic["username"] == "PayWayByABA_bot"
    assert diagnostic["expected_source_detected"] is True
    assert events[1] == ("setup", "PayWay source detected")
    assert events[2] == ("source", "Detected")
