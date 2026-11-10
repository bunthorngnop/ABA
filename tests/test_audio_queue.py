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
    audio._items.join(); audio.stop()
    assert speech.spoken == ["A", "C"]
    assert statuses == [("A", "SPOKEN"), ("B", "FAILED"), ("C", "SPOKEN")]


def test_per_item_voice_override_leaves_default_provider_unchanged():
    default_speech = FakeSpeech()
    male_speech = FakeSpeech()
    audio = AudioQueue(default_speech)
    audio.enqueue("payment")
    audio.enqueue("scheduled time", provider=male_speech, purpose="scheduled_time")
    audio._items.join()
    audio.stop()

    assert default_speech.spoken == ["payment"]
    assert male_speech.spoken == ["scheduled time"]


def test_mute_applies_to_scheduled_voice_override():
    male_speech = FakeSpeech()
    statuses = []
    audio = AudioQueue(FakeSpeech(), lambda item, status: statuses.append((item.purpose, status)))
    audio.set_muted(True)
    audio.enqueue("scheduled time", provider=male_speech, purpose="scheduled_time")
    audio._items.join()
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
    audio._items.join()
    audio.stop()

    assert alert_speech.spoken == ["alert"]
    assert statuses == [("regular", "MUTED"), ("system_alert", "SPOKEN")]


def test_expired_item_is_skipped_never_played_late():
    now = {"t": 100.0}
    speech = FakeSpeech()
    statuses = []
    audio = AudioQueue(speech, lambda item, status: statuses.append((item.text, status)), clock=lambda: now["t"])
    audio.enqueue("on time", expires_at=160.0)
    audio._items.join()
    now["t"] = 161.0
    audio.enqueue("too late", expires_at=160.0)
    audio._items.join()
    audio.stop()

    assert speech.spoken == ["on time"]
    assert statuses == [("on time", "SPOKEN"), ("too late", "SKIPPED")]
