from app.audio_queue import AudioQueue


class FakeSpeech:
    def __init__(self): self.spoken = []
    def speak(self, text): self.spoken.append(text)


def test_queue_is_sequential_and_survives_one_failure():
    class SometimesFails(FakeSpeech):
        def speak(self, text):
            if text == "B": raise RuntimeError("expected")
            super().speak(text)
    speech = SometimesFails(); statuses = []
    audio = AudioQueue(speech, lambda item, status: statuses.append((item.text, status)))
    for value in "ABC": audio.enqueue(value)
    audio.join(); audio.stop()
    assert speech.spoken == ["A", "C"]
    assert statuses == [("A", "SPOKEN"), ("B", "FAILED"), ("C", "SPOKEN")]


def test_per_item_voice_override_leaves_default_provider_unchanged():
    default_speech = FakeSpeech()
    male_speech = FakeSpeech()
    audio = AudioQueue(default_speech)
    audio.enqueue("payment")
    audio.enqueue("scheduled time", provider=male_speech, purpose="scheduled_time")
    audio.join()
    audio.stop()

    assert default_speech.spoken == ["payment"]
    assert male_speech.spoken == ["scheduled time"]


def test_mute_applies_to_scheduled_voice_override():
    male_speech = FakeSpeech()
    statuses = []
    audio = AudioQueue(FakeSpeech(), lambda item, status: statuses.append((item.purpose, status)))
    audio.set_muted(True)
    audio.enqueue("scheduled time", provider=male_speech, purpose="scheduled_time")
    audio.join()
    audio.stop()

    assert male_speech.spoken == []
    assert statuses == [("scheduled_time", "MUTED")]


def test_system_alert_plays_even_when_muted():
    alert_speech = FakeSpeech()
    statuses = []
    audio = AudioQueue(FakeSpeech(), lambda item, status: statuses.append((item.purpose, status)))
    audio.set_muted(True)
    audio.enqueue("payment while muted")
    audio.enqueue("alert", provider=alert_speech, purpose="system_alert", ignore_mute=True)
    audio.join()
    audio.stop()

    assert alert_speech.spoken == ["alert"]
    assert statuses == [("regular", "MUTED"), ("system_alert", "SPOKEN")]


def test_expired_item_is_skipped_never_played_late():
    now = {"t": 100.0}
    speech = FakeSpeech()
    statuses = []
    audio = AudioQueue(speech, lambda item, status: statuses.append((item.text, status)), clock=lambda: now["t"])
    audio.enqueue("on time", expires_at=160.0)
    audio.join()
    now["t"] = 161.0
    audio.enqueue("too late", expires_at=160.0)
    audio.join()
    audio.stop()

    assert speech.spoken == ["on time"]
    assert statuses == [("on time", "SPOKEN"), ("too late", "SKIPPED")]


# --- 2026-11-18: time announcements come first and interrupt a payment ---------------------------

import threading as _threading  # noqa: E402

from app import tts as _tts  # noqa: E402
from app.tts import PlaybackInterrupted as _Interrupted  # noqa: E402


class _InterruptibleSpeech:
    """Fake speech: a payment "plays" until a time announcement interrupts it (like pygame)."""

    def __init__(self):
        self.started = []
        self.finished = []
        self.payment_playing = _threading.Event()
        self.first_payment = True

    def speak(self, text):
        self.started.append(text)
        if text.startswith("payment") and self.first_payment:
            self.first_payment = False
            self.payment_playing.set()
            for _ in range(200):  # up to 2 s
                if _tts.PLAYBACK_INTERRUPT.is_set():
                    raise _Interrupted()
                _threading.Event().wait(0.01)
        self.finished.append(text)


def test_time_announcement_interrupts_a_payment_which_is_then_replayed():
    speech = _InterruptibleSpeech()
    statuses = []
    audio = AudioQueue(speech, lambda item, status: statuses.append((item.text, status)))
    audio.enqueue("payment 1", "event-1")
    audio.enqueue("payment 2", "event-2")
    assert speech.payment_playing.wait(2)
    audio.enqueue("time 16:27", purpose="scheduled_time")
    assert audio.join(5)
    audio.stop()
    # The time cut in, then payment 1 was replayed from the start, then payment 2.
    assert speech.started == ["payment 1", "time 16:27", "payment 1", "payment 2"]
    assert speech.finished == ["time 16:27", "payment 1", "payment 2"]
    assert statuses == [("time 16:27", "SPOKEN"), ("payment 1", "SPOKEN"), ("payment 2", "SPOKEN")]


def test_waiting_time_announcement_jumps_ahead_of_waiting_payments():
    gate = _threading.Event()
    spoken = []

    class Slow:
        def speak(self, text):
            if text == "first":
                gate.wait(2)
            spoken.append(text)

    audio = AudioQueue(Slow())
    audio.enqueue("first", purpose="scheduled_time")  # a time announcement is already playing
    audio.enqueue("payment A", "a")
    audio.enqueue("payment B", "b")
    audio.enqueue("time 16:28", purpose="scheduled_time")
    gate.set()
    assert audio.join(5)
    audio.stop()
    assert spoken == ["first", "time 16:28", "payment A", "payment B"]


# --- 2026-11-18: recorded time voice and 429 retry -----------------------------------------------

from pathlib import Path  # noqa: E402

from app.tts import CachedSpeech as _Cached, EdgeKhmerSpeech as _Edge  # noqa: E402


class _RateLimited(Exception):
    status = 429


def test_time_sentence_is_recorded_once_then_played_from_disk(tmp_path, monkeypatch):
    played, synthesized = [], []
    monkeypatch.setattr("app.tts.play_audio_file", lambda path: played.append(path))

    def fake_synthesize(self, text, output, retry=True):
        synthesized.append(text)
        Path(output).write_bytes(b"mp3")

    monkeypatch.setattr(_Edge, "synthesize", fake_synthesize)
    voice = _Cached("km-KH-PisethNeural", "+0%", tmp_path)
    voice.speak("ម៉ោង ៤ និង ២៧ នាទី រសៀល។")
    voice.speak("ម៉ោង ៤ និង ២៧ នាទី រសៀល។")
    assert synthesized == ["ម៉ោង ៤ និង ២៧ នាទី រសៀល។"]  # online only the first time
    assert len(played) == 2 and played[0] == played[1] and played[0].is_file()
    assert voice.prewarm(["a", "ម៉ោង ៤ និង ២៧ នាទី រសៀល។"], spacing_seconds=0) == 1
    assert voice.missing(["a", "b"]) == ["b"]


def test_speech_service_429_is_retried_briefly(monkeypatch):
    attempts = []

    class FakeCommunicate:
        def __init__(self, *args, **kwargs): pass

        async def save(self, path):
            attempts.append(path)
            if len(attempts) < 3:
                raise _RateLimited()

    import edge_tts
    monkeypatch.setattr(edge_tts, "Communicate", FakeCommunicate)
    monkeypatch.setattr("app.tts.TTS_RETRY_DELAYS_SECONDS", (0.01, 0.01))
    _Edge().synthesize("hello", Path("unused.mp3"))
    assert len(attempts) == 3
