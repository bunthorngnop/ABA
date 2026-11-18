import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional

from . import tts
from .tts import PlaybackInterrupted, SpeechProvider

logger = logging.getLogger(__name__)

# Owner decision 2026-11-18: time announcements come before payments. They jump ahead of every
# waiting announcement and interrupt one that is being spoken; the interrupted announcement is
# then replayed from the beginning, so nothing is lost.
PRIORITY_PURPOSES = frozenset({"scheduled_time"})


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

    @property
    def priority(self) -> bool:
        return self.purpose in PRIORITY_PURPOSES


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
        self._priority: "deque[AudioItem]" = deque()
        self._regular: "deque[AudioItem]" = deque()
        self._condition = threading.Condition()
        self._current: Optional[AudioItem] = None
        self._unfinished = 0
        self._stopping = False
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
        item = AudioItem(text, event_key, provider, purpose, expires_at, ignore_mute)
        with self._condition:
            if item.priority:
                self._priority.append(item)
                current = self._current
                if current is not None and not current.priority:
                    tts.request_interrupt()  # cut in now; the payment is replayed afterwards
            else:
                self._regular.append(item)
            self._unfinished += 1
            self._condition.notify_all()

    def join(self, timeout: Optional[float] = None) -> bool:
        """Wait until every queued announcement has been handled."""
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            while self._unfinished:
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    return False
                self._condition.wait(remaining)
        return True

    def _notify(self, item: AudioItem, status: str) -> None:
        if self.status_callback:
            self.status_callback(item, status)

    def _next(self) -> Optional[AudioItem]:
        with self._condition:
            while not self._priority and not self._regular and not self._stopping:
                self._condition.wait()
            if self._stopping and not self._priority and not self._regular:
                return None
            item = self._priority.popleft() if self._priority else self._regular.popleft()
            self._current = item
            tts.clear_interrupt()
            return item

    def _finish(self, requeued: bool = False) -> None:
        with self._condition:
            self._current = None
            if not requeued:
                self._unfinished -= 1
            self._condition.notify_all()

    def _run(self) -> None:
        while True:
            item = self._next()
            if item is None:
                return
            requeued = False
            try:
                if item.expires_at is not None and self.clock() > item.expires_at:
                    self._notify(item, "SKIPPED")
                    continue
                if self.muted and not item.ignore_mute:
                    self._notify(item, "MUTED")
                    continue
                (item.provider or self.provider).speak(item.text)
                self._notify(item, "SPOKEN")
            except PlaybackInterrupted:
                # A time announcement cut in: replay this one from the beginning right after it.
                logger.info("Announcement interrupted by a time announcement; it will be replayed")
                with self._condition:
                    self._regular.appendleft(item)
                    self._condition.notify_all()
                requeued = True
            except Exception:
                logger.exception("TTS failed for queued announcement")
                self._notify(item, "FAILED")
            finally:
                self._finish(requeued)

    def stop(self) -> None:
        with self._condition:
            self._stopping = True
            self._condition.notify_all()
        self._thread.join(timeout=10)
