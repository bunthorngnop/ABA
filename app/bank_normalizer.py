from typing import Optional, Tuple

VERIFIED_BANKS = {
    "ACLEDA Bank Plc.": "ACLEDA",
    "PPCBank": "PPCBank",
}


def normalize_verified_bank(raw_name: str) -> Optional[str]:
    return VERIFIED_BANKS.get(raw_name.strip())


def bank_from_channel(channel: str, parenthesized_bank: Optional[str]) -> Tuple[Optional[str], bool]:
    if channel == "ABA PAY" and parenthesized_bank is None:
        return "ABA", True
    if channel == "ABA KHQR" and parenthesized_bank:
        bank = normalize_verified_bank(parenthesized_bank)
        return bank, bank is not None
    return None, False
