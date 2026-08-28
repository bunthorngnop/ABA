import logging
import queue
import threading
from dataclasses import dataclass
from typing import Callable, Optional

from .tts import SpeechProvider

logger = logging.getLogger(__name__)


@dataclass
class AudioItem:
    text: str
    event_key: Optional[str] = None


class AudioQueue:
    def __init__(self, provider: SpeechProvider, status_callback: Optional[Callable[[AudioItem, str], None]] = None):
        self.provider = provider
        self.status_callback = status_callback
        self._items: "queue.Queue[Optional[AudioItem]]" = queue.Queue()
        self._muted = threading.Event()
        self._thread = threading.Thread(target=self._run, name="audio-queue", daemon=True)
        self._thread.start()

    @property
    def muted(self) -> bool:
        return self._muted.is_set()

    def set_muted(self, muted: bool) -> None:
        self._muted.set() if muted else self._muted.clear()

    def enqueue(self, text: str, event_key: Optional[str] = None) -> None:
        self._items.put(AudioItem(text, event_key))

    def _notify(self, item: AudioItem, status: str) -> None:
        if self.status_callback:
            self.status_callback(item, status)

    def _run(self) -> None:
        while True:
            item = self._items.get()
            try:
                if item is None:
                    return
                if self.muted:
                    self._notify(item, "MUTED")
                    continue
                self.provider.speak(item.text)
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

