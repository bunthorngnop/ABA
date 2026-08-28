import logging

from main import SecretRedactingFilter


def test_telegram_token_is_redacted_from_log_message():
    record = logging.LogRecord(
        "httpx", logging.INFO, __file__, 1,
        'POST https://api.telegram.org/bot123456:ABC_secret/getUpdates "%s"',
        ("HTTP/1.1 200 OK",), None,
    )
    assert SecretRedactingFilter().filter(record)
    rendered = record.getMessage()
    assert "123456:ABC_secret" not in rendered
    assert "api.telegram.org/bot<redacted>/getUpdates" in rendered


def test_user_session_credentials_are_redacted():
    record = logging.LogRecord("telethon", logging.ERROR, __file__, 1,
                               "login failed for %s using %s", ("+855123", "private-hash"), None)
    SecretRedactingFilter(("+855123", "private-hash")).filter(record)
    rendered = record.getMessage()
    assert "+855123" not in rendered
    assert "private-hash" not in rendered
