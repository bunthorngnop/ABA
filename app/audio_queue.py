import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .tts import SpeechProvider

logger = logging.getLogger(__name__)


@dataclass
class AudioItem:
    text: str
    event_key: Optional[str] = None
    provider: Optional[SpeechProvider] = None
    purpose: str = "regular"
    # time.monotonic() deadline; an item that cannot start by then is skipped, never played late.
    expires_at: Optional[float] = None
    # System alerts must be heard even when the speaker is muted.
    ignore_mute: bool = False


class AudioQueue:
    def __init__(
        self,
        provider: SpeechProvider,
        status_callback: Optional[Callable[[AudioItem, str], None]] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.provider = provider
        self.status_callback = status_callback
        self.clock = clock
        self._items: "queue.Queue[Optional[AudioItem]]" = queue.Queue()
        self._muted = threading.Event()
        self._thread = threading.Thread(target=self._run, name="audio-queue", daemon=True)
        self._thread.start()

    @property
    def muted(self) -> bool:
        return self._muted.is_set()

    def set_muted(self, muted: bool) -> None:
        self._muted.set() if muted else self._muted.clear()

    def enqueue(
        self,
        text: str,
        event_key: Optional[str] = None,
        *,
        provider: Optional[SpeechProvider] = None,
        purpose: str = "regular",
        expires_at: Optional[float] = None,
        ignore_mute: bool = False,
    ) -> None:
        self._items.put(AudioItem(text, event_key, provider, purpose, expires_at, ignore_mute))

    def _notify(self, item: AudioItem, status: str) -> None:
        if self.status_callback:
            self.status_callback(item, status)

    def _run(self) -> None:
        while True:
            item = self._items.get()
            try:
                if item is None:
                    return
                if item.expires_at is not None and self.clock() > item.expires_at:
                    self._notify(item, "SKIPPED")
                    continue
                if self.muted and not item.ignore_mute:
                    self._notify(item, "MUTED")
                    continue
                (item.provider or self.provider).speak(item.text)
                self._notify(item, "SPOKEN")
            except Exception:
                logger.exception("TTS failed for queued announcement")
                if item is not None:
                    self._notify(item, "FAILED")
            finally:
                self._items.task_done()

    def stop(self) -> None:
        self._items.put(None)
        self._thread.join(timeout=10)
