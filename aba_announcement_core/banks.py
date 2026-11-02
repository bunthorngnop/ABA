import re
import unicodedata
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Bank:
    code: str
    canonical_name: str
    display_name: str
    spoken_khmer: str
    aliases: tuple[str, ...]
    verified_codes: tuple[str, ...] = ()
    mapping_status: str = "USER_CONFIRMED"


@dataclass(frozen=True)
class BankResolution:
    raw_label: Optional[str]
    bank_code: Optional[str] = None
    canonical_name: Optional[str] = None
    display_name: Optional[str] = None
    spoken_khmer: Optional[str] = None
    mapping_status: str = "UNMAPPED"


BANKS = (
    Bank("ABA", "ABA Bank", "ABA", "អេ ប៊ី អេ", ("ABA", "ABA Bank"), mapping_status="VERIFIED"),
    Bank("ACLEDA", "ACLEDA Bank", "ACLEDA", "អេស៊ីលីដា", ("ACLEDA", "ACLEDA Bank", "ACLEDA Bank Plc", "ACLEDA Bank Plc."), ("ACLBKHPPXXX",), "VERIFIED"),
    Bank("CANADIA", "Canadia Bank", "Canadia", "កាណាឌីយ៉ា", ("Canadia", "Canadia Bank")),
    Bank("WING", "Wing Bank", "Wing", "វីង", ("Wing", "Wing Bank")),
    Bank("SATHAPANA", "SATHAPANA Bank", "SATHAPANA", "ស្ថាបនា", ("SATHAPANA", "SATHAPANA Bank", "Sathapana Bank Plc"), mapping_status="VERIFIED"),
    Bank("CHIP_MONG", "Chip Mong Bank", "Chip Mong Bank", "ជីប ម៉ុង", ("Chip Mong", "Chip Mong Bank")),
    Bank("CAMBODIA_POST", "Cambodia Post Bank / CP Bank", "Cambodia Post Bank", "ស៊ី ភី ប៊ែង", ("Cambodia Post Bank", "Cambodia Post Bank Plc", "CP Bank"), ("CPBPKHPPXXX",), "VERIFIED"),
    Bank("VATTANAC", "Vattanac Bank", "Vattanac Bank", "វឌ្ឍនៈ", ("Vattanac", "Vattanac Bank")),
    Bank("FTB", "Foreign Trade Bank / FTB", "FTB", "អេហ្វ ធី ប៊ី", ("Foreign Trade Bank", "FTB")),
    Bank("PRINCE", "Prince Bank", "Prince Bank", "ព្រិនស៍", ("Prince", "Prince Bank")),
    Bank("PHILLIP", "Phillip Bank", "Phillip Bank", "ហ្វីលីព", ("Phillip", "Phillip Bank")),
    Bank("BRED", "BRED Bank", "BRED Bank", "ប្រេដ ប៊ែង", ("BRED", "BRED Bank")),
    Bank("BRIDGE", "Bridge Bank", "Bridge Bank", "ប្រ៊ីដ", ("Bridge", "Bridge Bank")),
    Bank("SBI_LY_HOUR", "SBI LY HOUR Bank", "SBI LY HOUR", "លី ហួរ", ("SBI LY HOUR", "SBI LY HOUR Bank")),
    Bank("ORIENTAL", "Oriental Bank", "Oriental Bank", "អូរៀនថល", ("Oriental", "Oriental Bank")),
    Bank("KB_PRASAC", "KB PRASAC Bank", "KB PRASAC", "ប្រាសាក់", ("KB PRASAC", "KB PRASAC Bank", "KB PRASAC Bank Plc"), mapping_status="VERIFIED"),
    Bank("ARDB", "ARDB", "ARDB", "ធនាគារអភិវឌ្ឍន៍ជនបទ", ("ARDB",)),
    Bank("CAMPU", "Cambodian Public Bank / Campu Bank", "Campu Bank", "ខាំភូ ប៊ែង", ("Cambodian Public Bank", "Campu Bank")),
    Bank("PPCBANK", "PPCBank", "PPCBank", "ភី ភី ស៊ី", ("PPCBank",), mapping_status="VERIFIED"),
    Bank("BANK_OF_CHINA", "Bank of China", "Bank of China", "ធនាគារចិន", ("Bank of China",)),
    Bank("MAYBANK", "Maybank", "Maybank", "មេប៊ែង", ("Maybank",)),
    Bank("BIDC", "BIDC Bank", "BIDC", "ប៊ី អាយ ឌី ស៊ី", ("BIDC", "BIDC Bank")),
    Bank("UCB", "Union Commercial Bank / UCB", "UCB", "យូ ស៊ី ប៊ី", ("Union Commercial Bank", "UCB")),
    Bank("AEON", "AEON Specialized Bank", "AEON", "អ៊ីអន", ("AEON", "AEON Specialized Bank")),
)


def _alias_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    normalized = re.sub(r"[.,]+", " ", normalized)
    return " ".join(normalized.split())


_ALIAS_REGISTRY = {
    _alias_key(alias): bank
    for bank in BANKS
    for alias in (*bank.aliases, *bank.verified_codes)
}
_BANKS_BY_CODE = {bank.code: bank for bank in BANKS}


def resolve_bank(channel: str, raw_label: Optional[str]) -> BankResolution:
    if channel == "ABA PAY" and raw_label is None:
        bank = _ALIAS_REGISTRY[_alias_key("ABA")]
        return BankResolution(None, bank.code, bank.canonical_name, bank.display_name, bank.spoken_khmer, bank.mapping_status)
    if channel != "ABA KHQR" or not raw_label:
        return BankResolution(raw_label.strip() if raw_label else None)
    cleaned = raw_label.strip()
    bank = _ALIAS_REGISTRY.get(_alias_key(cleaned))
    if bank is None:
        return BankResolution(cleaned)
    return BankResolution(cleaned, bank.code, bank.canonical_name, bank.display_name, bank.spoken_khmer, bank.mapping_status)


def bank_for_code(code: str) -> Optional[Bank]:
    return _BANKS_BY_CODE.get(code)