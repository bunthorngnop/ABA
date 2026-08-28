from pathlib import Path

from app.config import Settings
from app.telegram_listener import authorize_message


def settings(sender=123, chat=-999):
    chats = () if chat is None else (chat,)
    return Settings(12345, "a" * 32, "+85510000000", Path("user.session"), chats, sender,
                    "PayWayByABA_bot", False, Path("x"), "voice", "+0%")


def test_authorized_source_requires_group_numeric_id_and_username_sanity():
    assert authorize_message(settings(), -999, 123, "PayWayByABA_bot")[0]
    assert not authorize_message(settings(), -998, 123, "PayWayByABA_bot")[0]
    assert not authorize_message(settings(), -999, 124, "PayWayByABA_bot")[0]
    assert not authorize_message(settings(), -999, 123, "ImpostorBot")[0]
    assert not authorize_message(settings(), -999, 123, None)[0]


def test_production_disabled_without_verified_sender_id():
    assert not authorize_message(settings(sender=None), -999, 123, "PayWayByABA_bot")[0]


def test_same_verified_sender_is_allowed_in_every_allowlisted_group():
    configured = Settings(12345, "a" * 32, "+85510000000", Path("user.session"),
                          (-1001, -1002, -1003, -1004), 123,
                          "PayWayByABA_bot", False, Path("x"), "voice", "+0%")
    for chat_id in configured.allowed_chat_ids:
        assert authorize_message(configured, chat_id, 123, "PayWayByABA_bot")[0]
    assert not authorize_message(configured, -9999, 123, "PayWayByABA_bot")[0]


def test_diagnostic_mode_never_authorizes_payment_speech():
    diagnostic = Settings(12345, "a" * 32, "+85510000000", Path("user.session"), (-999,), 123,
                          "PayWayByABA_bot", True, Path("x"), "voice", "+0%")
    assert not diagnostic.production_ready
    assert authorize_message(diagnostic, -999, 123, "PayWayByABA_bot") == (False, "diagnostic_mode_active")
