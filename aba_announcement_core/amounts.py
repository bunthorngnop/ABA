from decimal import Decimal, InvalidOperation

KHMER_DIGITS = str.maketrans("0123456789", "០១២៣៤៥៦៧៨៩")


def khmer_digits(value: int) -> str:
    return str(value).translate(KHMER_DIGITS)


def _natural_integer(value: int) -> str:
    if value < 0:
        raise ValueError("amount cannot be negative")
    if value == 0:
        return "០"
    units = ((1_000_000, "លាន"), (100_000, "សែន"), (10_000, "ម៉ឺន"), (1_000, "ពាន់"))
    parts = []
    remainder = value
    for divisor, label in units:
        count, remainder = divmod(remainder, divisor)
        if count:
            parts.append(f"{_natural_integer(count)} {label}")
    if remainder:
        parts.append(khmer_digits(remainder))
    return " ".join(parts)


def khr_to_speech(amount) -> str:
    try:
        number = Decimal(str(amount))
    except InvalidOperation as exc:
        raise ValueError("invalid KHR amount") from exc
    if number != number.to_integral_value() or number < 0:
        raise ValueError("KHR amount must be a non-negative whole number")
    return f"{_natural_integer(int(number))}រៀល"


def usd_to_speech(amount) -> str:
    try:
        number = Decimal(str(amount)).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError("invalid USD amount") from exc
    if number < 0:
        raise ValueError("USD amount cannot be negative")
    dollars = int(number)
    cents = int((number - dollars) * 100)
    parts = []
    if dollars or not cents:
        parts.append(f"{_natural_integer(dollars)} ដុល្លារ")
    if cents:
        parts.append(f"{_natural_integer(cents)} សេន")
    return " ".join(parts)


def amount_to_speech(amount, currency: str) -> str:
    if currency == "KHR":
        return khr_to_speech(amount)
    if currency == "USD":
        return usd_to_speech(amount)
    raise ValueError("unsupported currency")