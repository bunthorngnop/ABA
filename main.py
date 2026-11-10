import faulthandler
import logging
import os
import re
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.audio_queue import AudioItem, AudioQueue
from app.config import load_settings, update_env_file
from app.dashboard import Dashboard
from app.database import PaymentStore
from app.exchange_rates import ExchangeRateMonitor, load_rate_rows
from app.integration_api import IntegrationRuntimeStatus, IntegrationServer
from app.rate_group_reader import RateGroupReader
from app.scheduled_announcements import HOURLY_LATE_LIMIT_SECONDS, ScheduledTimeAnnouncementService
from app.single_instance import SingleInstanceLock
from app.system_alerts import ALERT_TEXTS, PaymentHealthAlerts, alert_audio_path
from app.telegram_listener import TelegramListener
from app.tts import EdgeKhmerSpeech, RecordedSpeech


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


_crash_log = None


def enable_crash_log(directory: str = "logs"):
    """Write native-crash stack traces (code locations only) to logs/faulthandler.log.

    pythonw.exe has no console, so without this a hard crash leaves no trace.
    The file records thread stacks only; it never contains payment or chat content.
    """
    global _crash_log
    Path(directory).mkdir(exist_ok=True)
    _crash_log = open(Path(directory) / "faulthandler.log", "a", encoding="utf-8")
    _crash_log.write(f"--- ABA started {datetime.now().isoformat(timespec='seconds')} pid={os.getpid()}\n")
    _crash_log.flush()
    faulthandler.enable(file=_crash_log, all_threads=True)
    return _crash_log


def main() -> int:
    instance_lock = SingleInstanceLock()
    if not instance_lock.acquire():
        print("ABA Payment Speaker is already running.")
        return 1
    try:
        enable_crash_log()
    except OSError:
        pass
    try:
        return _run_application()
    finally:
        instance_lock.release()


def _run_application() -> int:
    settings = load_settings()
    configure_logging((settings.telegram_api_hash, settings.telegram_phone, settings.gold_api_key))
    store = PaymentStore(settings.database_path)
    dashboard = None
    try:
        initial_exchange_rates = load_rate_rows(store)
    except Exception:
        logging.getLogger(__name__).exception("Could not load cached exchange rates at startup")
        initial_exchange_rates = {}
    integration_status = IntegrationRuntimeStatus(settings.production_ready)
    integration_server = build_integration_server(settings, store, integration_status)
    rate_group_reader = RateGroupReader(
        settings,
        lambda event, value: dashboard.publish(event, value) if dashboard else None,
    )

    def audio_status(item: AudioItem, status: str) -> None:
        if item.purpose == "scheduled_time":
            if status == "SPOKEN":
                logging.getLogger(__name__).info("Scheduled time announcement played successfully")
            elif status == "FAILED":
                logging.getLogger(__name__).error("Scheduled time announcement playback failed")
            elif status == "MUTED":
                logging.getLogger(__name__).warning("Scheduled time announcement skipped because the speaker is muted")
            elif status == "SKIPPED":
                logging.getLogger(__name__).warning("Hourly time announcement skipped because it could not start on time")
        elif item.purpose == "system_alert":
            if status == "SPOKEN":
                logging.getLogger(__name__).info("System alert played")
            elif status == "FAILED":
                logging.getLogger(__name__).error("System alert playback failed")
        if item.event_key:
            store.set_announcement_status(item.event_key, status)
        if dashboard:
            dashboard.publish("speaker", "Ready" if status == "SPOKEN" else status.title())
            if item.event_key:
                dashboard.publish("announcement_status", {"event_key": item.event_key, "status": status})
        integration_status.update("speaker", "Ready" if status == "SPOKEN" else status)

    audio = AudioQueue(EdgeKhmerSpeech(settings.tts_voice, settings.tts_volume), audio_status)
    dashboard = Dashboard(
        lambda text: audio.enqueue(text),
        audio.set_muted,
        store.announced_today,
        today_summary=store.today_summary,
        recent_payments=store.announced_today_rows,
        save_settings=lambda updates: update_env_file(".env", updates),
        expected_username=settings.expected_aba_username,
        configured_chat_ids=settings.allowed_chat_ids,
        configured_sender_id=settings.allowed_aba_sender_id,
        diagnostic_mode=settings.diagnostic_mode,
        start_rate_group_reader=rate_group_reader.start,
        stop_rate_group_reader=lambda: rate_group_reader.stop(wait=False),
        initial_exchange_rates=initial_exchange_rates,
        nbc_history=store.load_nbc_history,
    )
    rate_monitor = ExchangeRateMonitor(
        store,
        lambda rates: dashboard.publish("exchange_rates", rates) if dashboard else None,
        gold_api_key=settings.gold_api_key,
    )

    def publish(topic: str, value: object) -> None:
        integration_status.update(topic, value)
        dashboard.publish(topic, value)

    scheduled_voice = EdgeKhmerSpeech("km-KH-PisethNeural", settings.tts_volume)

    def play_system_alert(kind: str) -> None:
        # Pre-recorded files play without internet; fall back to live TTS if a file is missing.
        path = alert_audio_path(kind)
        provider = RecordedSpeech(path) if path else scheduled_voice
        audio.enqueue(ALERT_TEXTS[kind], provider=provider, purpose="system_alert", ignore_mute=True)

    payment_alerts = PaymentHealthAlerts(play_system_alert, enabled=settings.production_ready)
    listener = TelegramListener(
        settings, store, lambda text, key: audio.enqueue(text, key), publish,
        health_callback=payment_alerts.report,
    )
    scheduled_announcements = ScheduledTimeAnnouncementService(
        store.claim_scheduled_announcement,
        lambda text: audio.enqueue(text, provider=scheduled_voice, purpose="scheduled_time"),
        enqueue_hourly=lambda text: audio.enqueue(
            text, provider=scheduled_voice, purpose="scheduled_time",
            expires_at=time.monotonic() + HOURLY_LATE_LIMIT_SECONDS,
        ),
    )
    listener_started = False
    rate_monitor_started = False
    try:
        try:
            rate_monitor.start()
            rate_monitor_started = True
        except Exception:
            logging.getLogger(__name__).exception("Could not start exchange-rate refresh")
        scheduled_announcements.start()
        if integration_server and not integration_server.start():
            integration_status.update("integration", "OFFLINE")
        listener.start()
        listener_started = True
        payment_alerts.start()
        dashboard.run()
    finally:
        payment_alerts.stop()
        rate_group_reader.stop()
        if rate_monitor_started:
            try:
                rate_monitor.stop()
            except Exception:
                logging.getLogger(__name__).exception("Could not stop exchange-rate refresh")
        scheduled_announcements.stop()
        if listener_started:
            listener.stop()
        audio.stop()
        if integration_server:
            integration_server.stop()
        store.close()
    return 0


def build_integration_server(settings, store, status):
    if not settings.integration_enabled:
        return None
    if len(settings.integration_token) < 32 or not 1 <= settings.integration_port <= 65535:
        logging.getLogger(__name__).warning("ABA integration API disabled because local configuration is invalid")
        return None
    try:
        return IntegrationServer(
            settings.integration_host, settings.integration_port, settings.integration_token, store, status,
        )
    except ValueError:
        logging.getLogger(__name__).warning("ABA integration API disabled because loopback configuration is invalid")
        return None


if __name__ == "__main__":
    raise SystemExit(main())
