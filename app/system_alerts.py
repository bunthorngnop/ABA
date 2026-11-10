"""Spoken alerts when payment monitoring is down, so missed payments are never silent.

The payment listener reports its health (a lightweight Telegram ping every 30 seconds).
If it stays unhealthy for 2 minutes the alert is spoken, then repeated every 10 minutes
until it recovers, when a single "reconnected" message is spoken. Alerts play from
pre-recorded files (no internet needed) and are heard even when the speaker is muted.
"""

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

ALERT_DELAY_SECONDS = 120
ALERT_REPEAT_SECONDS = 600
CHECK_INTERVAL_SECONDS = 5.0

NETWORK = "network"
LOGIN = "login"
RECOVERED = "recovered"

# Owner-approved wording (male voice).
ALERT_TEXTS = {
    NETWORK: "សូមជូនដំណឹង ប្រព័ន្ធទទួលប្រាក់ត្រូវបានផ្តាច់ សូមពិនិត្យអ៊ីនធឺណិត",
    LOGIN: "សូមចូល Telegram ឡើងវិញ",
    RECOVERED: "ប្រព័ន្ធទទួលប្រាក់បានភ្ជាប់ឡើងវិញ",
}
ALERT_FILES = {
    NETWORK: "alert_disconnected.mp3",
    LOGIN: "alert_login.mp3",
    RECOVERED: "alert_reconnected.mp3",
}
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def alert_audio_path(kind: str, assets_dir: Path = ASSETS_DIR) -> Optional[Path]:
    path = assets_dir / ALERT_FILES[kind]
    return path if path.is_file() else None


class PaymentHealthAlerts:
    """Turns payment-listener health reports into spoken alerts."""

    def __init__(
        self,
        play: Callable[[str], None],
        enabled: bool = True,
        clock: Callable[[], float] = time.monotonic,
        interval: float = CHECK_INTERVAL_SECONDS,
    ):
        self.play = play
        self.enabled = enabled
        self.clock = clock
        self.interval = interval
        self._lock = threading.Lock()
        # Until the first healthy report arrives, monitoring counts as down (e.g. no internet at startup).
        self._down_since: Optional[float] = clock()
        self._reason = NETWORK
        self._last_alert: Optional[float] = None
        self._alerted = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="payment-health-alerts", daemon=True)

    def report(self, healthy: bool, reason: str = NETWORK) -> None:
        recovered = False
        with self._lock:
            if healthy:
                recovered = self._alerted
                self._down_since = None
                self._last_alert = None
                self._alerted = False
                self._reason = NETWORK
            else:
                if self._down_since is None:
                    self._down_since = self.clock()
                # A login problem stays the reported reason until monitoring is healthy again.
                if reason == LOGIN or self._reason != LOGIN:
                    self._reason = reason if reason in (NETWORK, LOGIN) else NETWORK
        if recovered and self.enabled:
            logger.info("Payment monitoring recovered; announcing reconnection")
            self.play(RECOVERED)

    def check_once(self) -> Optional[str]:
        if not self.enabled:
            return None
        with self._lock:
            if self._down_since is None:
                return None
            now = self.clock()
            if now - self._down_since < ALERT_DELAY_SECONDS:
                return None
            if self._last_alert is not None and now - self._last_alert < ALERT_REPEAT_SECONDS:
                return None
            self._last_alert = now
            self._alerted = True
            kind = self._reason
        logger.warning("Payment monitoring down; speaking %s alert", kind)
        self.play(kind)
        return kind

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.check_once()
            except Exception:
                logger.exception("Could not check payment-monitoring health")
            if self._stop.wait(self.interval):
                break

    def start(self) -> None:
        if self.enabled:
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)
