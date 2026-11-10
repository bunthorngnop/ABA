import asyncio
import tempfile
from pathlib import Path
from typing import Protocol


class SpeechProvider(Protocol):
    def speak(self, text: str) -> None: ...


def play_audio_file(path: Path) -> None:
    import pygame

    if not pygame.mixer.get_init():
        pygame.mixer.init()
    pygame.mixer.music.load(str(path))
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.wait(50)
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
            play_audio_file(output)


class RecordedSpeech:
    """Plays a pre-recorded announcement, so it works without an internet connection."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def speak(self, text: str) -> None:
        play_audio_file(self.path)
