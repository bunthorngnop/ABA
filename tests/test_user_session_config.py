from pathlib import Path

import pytest

from app.config import Settings, _integer_list, load_settings, user_session_configuration_errors
from app.telegram_listener import group_is_in_scope


def make_settings(*, diagnostic=True, chat=None, sender=None):
    chats = () if chat is None else (chat,)
    return Settings(12345, "a" * 32, "+85510000000", Path("user.session"), chats, sender,
                    "PayWayByABA_bot", diagnostic, Path("state.sqlite3"), "voice", "+0%")


def test_user_session_credentials_control_configuration_state():
    configured = make_settings()
    assert configured.user_session_configured
    missing_hash = Settings(12345, "", "+85510000000", Path("user.session"), (), None,
                            "PayWayByABA_bot", True, Path("state.sqlite3"), "voice", "+0%")
    assert not missing_hash.user_session_configured


def test_user_session_validation_rejects_bad_hash_and_phone():
    invalid = Settings(12345, "short", "0123", Path("user.session"), (), None,
                       "PayWayByABA_bot", True, Path("state.sqlite3"), "voice", "+0%")
    errors = user_session_configuration_errors(invalid)
    assert any("API_HASH" in error for error in errors)
    assert any("TELEGRAM_PHONE" in error for error in errors)


def test_production_requires_credentials_group_sender_and_diagnostic_off():
    assert make_settings(diagnostic=False, chat=-1001, sender=999).production_ready
    assert not make_settings(diagnostic=True, chat=-1001, sender=999).production_ready
    assert not make_settings(diagnostic=False, chat=-1001, sender=None).production_ready


def test_group_scope_is_strict_after_group_configuration():
    configured = make_settings(chat=-1001)
    assert group_is_in_scope(configured, -1001, True)
    assert not group_is_in_scope(configured, -1002, True)
    assert not group_is_in_scope(configured, -1001, False)


def test_diagnostic_can_discover_group_only_when_none_configured():
    assert group_is_in_scope(make_settings(chat=None), -1002, True)
    assert not group_is_in_scope(make_settings(diagnostic=False, chat=None), -1002, True)


def test_invalid_api_id_is_rejected(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("TELEGRAM_API_ID=not-a-number\n", encoding="utf-8")
    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    with pytest.raises(ValueError, match="TELEGRAM_API_ID must be a numeric Telegram ID"):
        load_settings(str(env))


def test_comma_separated_group_allowlist_is_numeric_and_deduplicated(monkeypatch):
    monkeypatch.setenv("ALLOWED_CHAT_IDS", "-1001, -1002, -1001, -1003")
    assert _integer_list("ALLOWED_CHAT_IDS", "ALLOWED_CHAT_ID") == (-1001, -1002, -1003)


def test_invalid_group_allowlist_is_rejected(monkeypatch):
    monkeypatch.setenv("ALLOWED_CHAT_IDS", "-1001,not-an-id")
    with pytest.raises(ValueError, match="comma-separated numeric Telegram IDs"):
        _integer_list("ALLOWED_CHAT_IDS", "ALLOWED_CHAT_ID")
