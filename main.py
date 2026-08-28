import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.audio_queue import AudioItem, AudioQueue
from app.config import load_settings, update_env_file
from app.dashboard import Dashboard
from app.database import PaymentStore
from app.telegram_listener import TelegramListener
from app.tts import EdgeKhmerSpeech


class SecretRedactingFilter(logging.Filter):
    """Defensively redact configured Telegram credentials from all logs."""

    _telegram_token = re.compile(r"(?i)(api\.telegram\.org/bot)[^/\s]+")

    def __init__(self, secrets=()):
        super().__init__()
        self.secrets = tuple(value for value in secrets if value)

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        record.msg = self._telegram_token.sub(r"\1<redacted>", message)
        for secret in self.secrets:
            record.msg = record.msg.replace(secret, "<redacted>")
        record.args = ()
        return True


def configure_logging(secrets=()) -> None:
    Path("logs").mkdir(exist_ok=True)
    handler = RotatingFileHandler("logs/aba-speaker.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    console = logging.StreamHandler()
    redactor = SecretRedactingFilter(secrets)
    handler.addFilter(redactor)
    console.addFilter(redactor)
    logging.basicConfig(level=logging.INFO, handlers=[handler, console],
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("telethon").setLevel(logging.WARNING)


def main() -> None:
    settings = load_settings()
    configure_logging((settings.telegram_api_hash, settings.telegram_phone))
    store = PaymentStore(settings.database_path)
    dashboard = None

    def audio_status(item: AudioItem, status: str) -> None:
        if item.event_key:
            store.set_announcement_status(item.event_key, status)
        if dashboard:
            dashboard.publish("speaker", "Ready" if status == "SPOKEN" else status.title())

    audio = AudioQueue(EdgeKhmerSpeech(settings.tts_voice, settings.tts_volume), audio_status)
    dashboard = Dashboard(
        lambda text: audio.enqueue(text),
        audio.set_muted,
        store.announced_today,
        save_settings=lambda updates: update_env_file(".env", updates),
        expected_username=settings.expected_aba_username,
        configured_chat_ids=settings.allowed_chat_ids,
        configured_sender_id=settings.allowed_aba_sender_id,
        diagnostic_mode=settings.diagnostic_mode,
    )
    listener = TelegramListener(settings, store, lambda text, key: audio.enqueue(text, key), dashboard.publish)
    listener.start()
    try:
        dashboard.run()
    finally:
        listener.stop(); audio.stop(); store.close()


if __name__ == "__main__":
    main()
