import pytest

from app.khmer_numbers import khr_to_speech, usd_to_speech


@pytest.mark.parametrize(("amount", "expected"), [
    (2_000, "២ ពាន់រៀល"), (10_000, "១ ម៉ឺនរៀល"), (20_000, "២ ម៉ឺនរៀល"),
    (50_000, "៥ ម៉ឺនរៀល"), (100_000, "១ សែនរៀល"), (250_000, "២ សែន ៥ ម៉ឺនរៀល"),
    (500_000, "៥ សែនរៀល"), (1_000_000, "១ លានរៀល"),
    (1_500_000, "១ លាន ៥ សែនរៀល"), (2_350_000, "២ លាន ៣ សែន ៥ ម៉ឺនរៀល"),
])
def test_natural_khr(amount, expected):
    assert khr_to_speech(amount) == expected


@pytest.mark.parametrize(("amount", "expected"), [
    ("5.00", "៥ ដុល្លារ"), ("10.00", "១០ ដុល្លារ"), ("25.00", "២៥ ដុល្លារ"),
    ("5.25", "៥ ដុល្លារ ២៥ សេន"), ("0.50", "៥០ សេន"),
    ("1.25", "១ ដុល្លារ ២៥ សេន"), ("3.38", "៣ ដុល្លារ ៣៨ សេន"),
    ("77.75", "៧៧ ដុល្លារ ៧៥ សេន"), ("100.92", "១០០ ដុល្លារ ៩២ សេន"),
    ("2.50", "២ ដុល្លារ ៥០ សេន"), ("7.14", "៧ ដុល្លារ ១៤ សេន"),
])
def test_natural_usd(amount, expected):
    assert usd_to_speech(amount) == expected
