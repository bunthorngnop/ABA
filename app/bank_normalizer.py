import re
import unicodedata
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Institution:
    canonical_id: str
    canonical_name: str
    display_name: str
    spoken_khmer: str
    aliases: tuple[str, ...]
    verified_codes: tuple[str, ...] = ()
    status: str = "USER_CONFIRMED"


@dataclass(frozen=True)
class InstitutionResolution:
    raw_label: Optional[str]
    canonical_id: Optional[str] = None
    canonical_name: Optional[str] = None
    display_name: Optional[str] = None
    spoken_khmer: Optional[str] = None
    status: str = "UNMAPPED"


INSTITUTIONS = (
    Institution("ABA", "ABA Bank", "ABA", "អេ ប៊ី អេ", ("ABA", "ABA Bank"), status="VERIFIED"),
    Institution("ACLEDA", "ACLEDA Bank", "ACLEDA", "អេស៊ីលីដា", ("ACLEDA", "ACLEDA Bank", "ACLEDA Bank Plc", "ACLEDA Bank Plc."), ("ACLBKHPPXXX",), "VERIFIED"),
    Institution("CANADIA", "Canadia Bank", "Canadia", "កាណាឌីយ៉ា", ("Canadia", "Canadia Bank")),
    Institution("WING", "Wing Bank", "Wing", "វីង", ("Wing", "Wing Bank")),
    Institution("SATHAPANA", "SATHAPANA Bank", "SATHAPANA", "ស្ថាបនា", ("SATHAPANA", "SATHAPANA Bank", "Sathapana Bank Plc"), status="VERIFIED"),
    Institution("CHIP_MONG", "Chip Mong Bank", "Chip Mong Bank", "ជីប ម៉ុង", ("Chip Mong", "Chip Mong Bank")),
    Institution("CAMBODIA_POST", "Cambodia Post Bank / CP Bank", "Cambodia Post Bank", "ស៊ី ភី ប៊ែង", ("Cambodia Post Bank", "Cambodia Post Bank Plc", "CP Bank"), ("CPBPKHPPXXX",), "VERIFIED"),
    Institution("VATTANAC", "Vattanac Bank", "Vattanac Bank", "វឌ្ឍនៈ", ("Vattanac", "Vattanac Bank")),
    Institution("FTB", "Foreign Trade Bank / FTB", "FTB", "អេហ្វ ធី ប៊ី", ("Foreign Trade Bank", "FTB")),
    Institution("PRINCE", "Prince Bank", "Prince Bank", "ព្រិនស៍", ("Prince", "Prince Bank")),
    Institution("PHILLIP", "Phillip Bank", "Phillip Bank", "ហ្វីលីព", ("Phillip", "Phillip Bank")),
    Institution("BRED", "BRED Bank", "BRED Bank", "ប្រេដ ប៊ែង", ("BRED", "BRED Bank")),
    Institution("BRIDGE", "Bridge Bank", "Bridge Bank", "ប្រ៊ីដ", ("Bridge", "Bridge Bank")),
    Institution("SBI_LY_HOUR", "SBI LY HOUR Bank", "SBI LY HOUR", "លី ហួរ", ("SBI LY HOUR", "SBI LY HOUR Bank")),
    Institution("ORIENTAL", "Oriental Bank", "Oriental Bank", "អូរៀនថល", ("Oriental", "Oriental Bank")),
    Institution("KB_PRASAC", "KB PRASAC Bank", "KB PRASAC", "ប្រាសាក់", ("KB PRASAC", "KB PRASAC Bank", "KB PRASAC Bank Plc"), status="VERIFIED"),
    Institution("ARDB", "ARDB", "ARDB", "ធនាគារអភិវឌ្ឍន៍ជនបទ", ("ARDB",)),
    Institution("CAMPU", "Cambodian Public Bank / Campu Bank", "Campu Bank", "ខាំភូ ប៊ែង", ("Cambodian Public Bank", "Campu Bank")),
    Institution("PPCBANK", "PPCBank", "PPCBank", "ភី ភី ស៊ី", ("PPCBank",), status="VERIFIED"),
    Institution("BANK_OF_CHINA", "Bank of China", "Bank of China", "ធនាគារចិន", ("Bank of China",)),
    Institution("MAYBANK", "Maybank", "Maybank", "មេប៊ែង", ("Maybank",)),
    Institution("BIDC", "BIDC Bank", "BIDC", "ប៊ី អាយ ឌី ស៊ី", ("BIDC", "BIDC Bank")),
    Institution("UCB", "Union Commercial Bank / UCB", "UCB", "យូ ស៊ី ប៊ី", ("Union Commercial Bank", "UCB")),
    Institution("AEON", "AEON Specialized Bank", "AEON", "អ៊ីអន", ("AEON", "AEON Specialized Bank")),
)


def _alias_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    normalized = re.sub(r"[.,]+", " ", normalized)
    return " ".join(normalized.split())


_ALIAS_REGISTRY = {
    _alias_key(alias): institution
    for institution in INSTITUTIONS
    for alias in (*institution.aliases, *institution.verified_codes)
}


def resolve_institution(channel: str, raw_label: Optional[str]) -> InstitutionResolution:
    if channel == "ABA PAY" and raw_label is None:
        institution = _ALIAS_REGISTRY[_alias_key("ABA")]
        return InstitutionResolution(
            None, institution.canonical_id, institution.canonical_name,
            institution.display_name, institution.spoken_khmer, institution.status,
        )
    if channel != "ABA KHQR" or not raw_label:
        return InstitutionResolution(raw_label.strip() if raw_label else None)
    cleaned = raw_label.strip()
    institution = _ALIAS_REGISTRY.get(_alias_key(cleaned))
    if institution is None:
        return InstitutionResolution(cleaned)
    return InstitutionResolution(
        cleaned, institution.canonical_id, institution.canonical_name,
        institution.display_name, institution.spoken_khmer, institution.status,
    )


def normalize_verified_bank(raw_name: str) -> Optional[str]:
    """Backward-compatible display-name lookup for a deterministic exact alias."""
    return resolve_institution("ABA KHQR", raw_name).display_name


def bank_from_channel(channel: str, parenthesized_bank: Optional[str]) -> Tuple[Optional[str], bool]:
    resolution = resolve_institution(channel, parenthesized_bank)
    return resolution.display_name, resolution.status != "UNMAPPED"
