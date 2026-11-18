import asyncio
import tempfile
import threading
from pathlib import Path
from typing import Protocol


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


class EdgeKhmerSpeech:
    """Khmer neural speech via Microsoft's online Edge speech service."""

    def __init__(self, voice: str = "km-KH-SreymomNeural", volume: str = "+0%"):
        self.voice = voice
        self.volume = volume

    def speak(self, text: str) -> None:
        import edge_tts

        with tempfile.TemporaryDirectory(prefix="aba-speaker-") as folder:
            output = Path(folder) / "speech.mp3"
            asyncio.run(edge_tts.Communicate(text, self.voice, volume=self.volume).save(str(output)))
            play_audio_file(output)  # raises PlaybackInterrupted if a time announcement cut in meanwhile


class RecordedSpeech:
    """Plays a pre-recorded announcement, so it works without an internet connection."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def speak(self, text: str) -> None:
        play_audio_file(self.path)
