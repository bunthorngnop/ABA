import asyncio
import hashlib
import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Iterable, Optional, Protocol

logger = logging.getLogger(__name__)

# Microsoft's free speech service sometimes answers HTTP 429 (too many requests); retry briefly.
TTS_RETRY_DELAYS_SECONDS = (2.0, 5.0)


class SpeechProvider(Protocol):
    def speak(self, text: str) -> None: ...


class PlaybackInterrupted(Exception):
    """Raised when a time announcement interrupts the announcement being spoken."""


# Set by the audio queue when a time announcement must cut in; cleared before each announcement.
PLAYBACK_INTERRUPT = threading.Event()


def request_interrupt() -> None:
    PLAYBACK_INTERRUPT.set()


def clear_interrupt() -> None:
    PLAYBACK_INTERRUPT.clear()


def play_audio_file(path: Path) -> None:
    import pygame

    if PLAYBACK_INTERRUPT.is_set():
        raise PlaybackInterrupted()
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    pygame.mixer.music.load(str(path))
    pygame.mixer.music.play()
    try:
        while pygame.mixer.music.get_busy():
            if PLAYBACK_INTERRUPT.is_set():
                pygame.mixer.music.stop()
                raise PlaybackInterrupted()
            pygame.time.wait(50)
    finally:
        pygame.mixer.music.unload()


def _is_rate_limited(exc: BaseException) -> bool:
    return getattr(exc, "status", None) == 429


class EdgeKhmerSpeech:
    """Khmer neural speech via Microsoft's online Edge speech service."""

    def __init__(self, voice: str = "km-KH-SreymomNeural", volume: str = "+0%"):
        self.voice = voice
        self.volume = volume

    def synthesize(self, text: str, output: Path, retry: bool = True) -> None:
        """Write the spoken text to an mp3, retrying briefly when the service says 429."""
        import edge_tts

        delays = TTS_RETRY_DELAYS_SECONDS if retry else ()
        for attempt in range(len(delays) + 1):
            try:
                asyncio.run(edge_tts.Communicate(text, self.voice, volume=self.volume).save(str(output)))
                return
            except Exception as exc:
                if attempt >= len(delays) or not _is_rate_limited(exc):
                    raise
                logger.info("Speech service busy (429); retrying in %.0f s", delays[attempt])
                if PLAYBACK_INTERRUPT.wait(delays[attempt]):
                    raise PlaybackInterrupted() from exc

    def speak(self, text: str) -> None:
        with tempfile.TemporaryDirectory(prefix="aba-speaker-") as folder:
            output = Path(folder) / "speech.mp3"
            self.synthesize(text, output)
            play_audio_file(output)  # raises PlaybackInterrupted if a time announcement cut in meanwhile


class CachedSpeech(EdgeKhmerSpeech):
    """Edge speech for fixed sentences (time announcements), recorded once and then played from disk.

    A cached sentence plays instantly, without internet and without Microsoft's 429 limit. A
    missing one is spoken live and saved for next time; prewarm() records the known sentences
    slowly in the background.
    """

    def __init__(self, voice: str, volume: str, cache_dir: Path):
        super().__init__(voice, volume)
        self.cache_dir = Path(cache_dir)

    def cache_path(self, text: str) -> Path:
        digest = hashlib.sha256(f"{self.voice}|{self.volume}|{text}".encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{digest}.mp3"

    def _record(self, text: str, retry: bool = True) -> Path:
        path = self.cache_path(text)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(f".{os.getpid()}.part")
        try:
            self.synthesize(text, partial, retry=retry)
            if partial.stat().st_size == 0:
                raise OSError("empty speech file")
            partial.replace(path)
        finally:
            partial.unlink(missing_ok=True)
        return path

    def speak(self, text: str) -> None:
        path = self.cache_path(text)
        if not path.is_file():
            path = self._record(text)
        play_audio_file(path)

    def prewarm(self, texts: Iterable[str], spacing_seconds: float = 20.0,
                stop: Optional[threading.Event] = None) -> int:
        """Record every missing sentence, one at a time and slowly, so the service is not flooded."""
        stop = stop or threading.Event()
        recorded = 0
        for text in texts:
            if stop.is_set():
                break
            if self.cache_path(text).is_file():
                continue
            try:
                self._record(text, retry=False)
                recorded += 1
            except Exception as exc:
                logger.info("Time voice not recorded yet (%s); will retry later", type(exc).__name__)
            if stop.wait(spacing_seconds):
                break
        return recorded

    def missing(self, texts: Iterable[str]) -> list[str]:
        return [text for text in texts if not self.cache_path(text).is_file()]


class RecordedSpeech:
    """Plays a pre-recorded announcement, so it works without an internet connection."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def speak(self, text: str) -> None:
        play_audio_file(self.path)


def wait_seconds(seconds: float) -> None:  # small seam for tests
    time.sleep(seconds)
