import asyncio
import tempfile
from pathlib import Path
from typing import Protocol


class SpeechProvider(Protocol):
    def speak(self, text: str) -> None: ...


class EdgeKhmerSpeech:
    """Khmer neural speech via Microsoft's online Edge speech service."""

    def __init__(self, voice: str = "km-KH-SreymomNeural", volume: str = "+0%"):
        self.voice = voice
        self.volume = volume

    def speak(self, text: str) -> None:
        import edge_tts
        import pygame

        with tempfile.TemporaryDirectory(prefix="aba-speaker-") as folder:
            output = Path(folder) / "speech.mp3"
            asyncio.run(edge_tts.Communicate(text, self.voice, volume=self.volume).save(str(output)))
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(str(output))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.wait(50)
            pygame.mixer.music.unload()

