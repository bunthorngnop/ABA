from app.config import update_env_file


def test_commissioning_updates_preserve_token_and_other_settings(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# private configuration\n"
        "TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef\n"
        "ALLOWED_CHAT_IDS=\n"
        "ALLOWED_ABA_SENDER_ID=\n"
        "EXPECTED_ABA_USERNAME=PayWayByABA_bot\n"
        "DIAGNOSTIC_MODE=true\n",
        encoding="utf-8",
    )
    update_env_file(str(env), {"ALLOWED_CHAT_IDS": "-100123,-100456", "ALLOWED_ABA_SENDER_ID": "456"})
    content = env.read_text(encoding="utf-8")
    assert "TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef" in content
    assert "ALLOWED_CHAT_IDS=-100123,-100456" in content
    assert "ALLOWED_ABA_SENDER_ID=456" in content
    assert "DIAGNOSTIC_MODE=true" in content


def test_switch_to_production_changes_only_requested_value(tmp_path):
    env = tmp_path / ".env"
    env.write_text("TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef\nDIAGNOSTIC_MODE=true\n", encoding="utf-8")
    update_env_file(str(env), {"DIAGNOSTIC_MODE": "false"})
    assert env.read_text(encoding="utf-8") == "TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef\nDIAGNOSTIC_MODE=false\n"
