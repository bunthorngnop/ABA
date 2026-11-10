import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def _integer(name: str) -> Optional[int]:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a numeric Telegram ID") from exc


def _integer_list(*names: str) -> tuple[int, ...]:
    value = ""
    selected_name = names[0]
    for name in names:
        candidate = os.getenv(name, "").strip()
        if candidate:
            value, selected_name = candidate, name
            break
    if not value:
        return ()
    result = []
    for item in value.split(","):
        try:
            number = int(item.strip())
        except ValueError as exc:
            raise ValueError(f"{selected_name} must contain comma-separated numeric Telegram IDs") from exc
        if number not in result:
            result.append(number)
    return tuple(result)


@dataclass(frozen=True)
class Settings:
    telegram_api_id: Optional[int]
    telegram_api_hash: str
    telegram_phone: str
    telegram_session_path: Path
    allowed_chat_ids: tuple[int, ...]
    allowed_aba_sender_id: Optional[int]
    expected_aba_username: str
    diagnostic_mode: bool
    database_path: Path
    tts_voice: str
    tts_volume: str
    integration_enabled: bool = False
    integration_host: str = "127.0.0.1"
    integration_port: int = 8766
    integration_token: str = ""
    rate_group_session_path: Optional[Path] = None
    gold_api_key: str = ""

    @property
    def production_ready(self) -> bool:
        return bool(
            not self.diagnostic_mode
            and self.user_session_configured
            and bool(self.allowed_chat_ids)
            and self.allowed_aba_sender_id is not None
        )

    @property
    def user_session_configured(self) -> bool:
        return not user_session_configuration_errors(self)

    @property
    def allowed_chat_id(self) -> Optional[int]:
        """First configured group, retained for display compatibility."""
        return self.allowed_chat_ids[0] if self.allowed_chat_ids else None


def user_session_configuration_errors(settings: Settings) -> list[str]:
    errors = []
    if settings.telegram_api_id is None or settings.telegram_api_id <= 0:
        errors.append("TELEGRAM_API_ID is missing or invalid")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", settings.telegram_api_hash):
        errors.append("TELEGRAM_API_HASH must be the 32-character value from my.telegram.org")
    phone_digits = re.sub(r"[\s()-]", "", settings.telegram_phone)
    if not re.fullmatch(r"\+[1-9][0-9]{6,14}", phone_digits):
        errors.append("TELEGRAM_PHONE must include its country code, for example +855...")
    return errors


_ENV_KEY = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")


def update_env_file(env_file: str, updates: dict[str, str]) -> None:
    """Update selected non-secret settings while preserving all other .env content."""
    path = Path(env_file)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    output = []
    for line in lines:
        match = _ENV_KEY.match(line)
        key = match.group(1) if match else None
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)
    for key, value in remaining.items():
        output.append(f"{key}={value}")
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text("\n".join(output) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def load_settings(env_file: str = ".env") -> Settings:
    load_dotenv(env_file, override=True)
    default_session = Path(os.getenv("LOCALAPPDATA", "data")) / "ABA Payment Speaker" / "telegram_user.session"
    rate_group_session = Path(os.getenv("LOCALAPPDATA", "data")) / "ABA Payment Speaker" / "rate_group_user.session"
    session_value = os.path.expandvars(os.getenv("TELEGRAM_SESSION_PATH", "").strip())
    default_database = Path(os.getenv("LOCALAPPDATA", "data")) / "ABA Payment Speaker" / "aba_payment_speaker.sqlite3"
    database_value = os.path.expandvars(os.getenv("DATABASE_PATH", "").strip())
    integration_enabled = os.getenv("ABA_INTEGRATION_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    integration_host = os.getenv("ABA_INTEGRATION_HOST", "127.0.0.1").strip()
    try:
        integration_port = int(os.getenv("ABA_INTEGRATION_PORT", "8766"))
    except ValueError:
        integration_port = 0
    integration_token = os.getenv("ABA_INTEGRATION_TOKEN", "").strip()
    return Settings(
        telegram_api_id=_integer("TELEGRAM_API_ID"),
        telegram_api_hash=os.getenv("TELEGRAM_API_HASH", "").strip(),
        telegram_phone=os.getenv("TELEGRAM_PHONE", "").strip(),
        telegram_session_path=Path(session_value) if session_value else default_session,
        allowed_chat_ids=_integer_list("ALLOWED_CHAT_IDS", "ALLOWED_CHAT_ID"),
        allowed_aba_sender_id=_integer("ALLOWED_ABA_SENDER_ID"),
        expected_aba_username=os.getenv("EXPECTED_ABA_USERNAME", "PayWayByABA_bot").strip().lstrip("@"),
        diagnostic_mode=os.getenv("DIAGNOSTIC_MODE", "false").lower() in {"1", "true", "yes", "on"},
        database_path=Path(database_value) if database_value else default_database,
        tts_voice=os.getenv("TTS_VOICE", "km-KH-SreymomNeural"),
        tts_volume=os.getenv("TTS_VOLUME", "+0%"),
        integration_enabled=integration_enabled,
        integration_host=integration_host,
        integration_port=integration_port,
        integration_token=integration_token,
        rate_group_session_path=rate_group_session,
        gold_api_key=os.getenv("GOLD_API_KEY", "").strip(),
    )
