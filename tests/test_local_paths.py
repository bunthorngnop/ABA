from pathlib import Path

from app.config import load_settings


def test_database_path_expands_localappdata(tmp_path, monkeypatch):
    local = tmp_path / "Local App Data"
    env = tmp_path / ".env"
    env.write_text(
        "TELEGRAM_API_ID=12345\n"
        "TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef\n"
        "TELEGRAM_PHONE=+85512345678\n"
        "DATABASE_PATH=%LOCALAPPDATA%/ABA Payment Speaker/state.sqlite3\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LOCALAPPDATA", str(local))

    settings = load_settings(str(env))

    assert settings.database_path == Path(local) / "ABA Payment Speaker" / "state.sqlite3"
    assert settings.rate_group_session_path == Path(local) / "ABA Payment Speaker" / "rate_group_user.session"
