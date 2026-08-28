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

