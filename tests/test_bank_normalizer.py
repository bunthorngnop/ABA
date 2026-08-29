from app.bank_normalizer import INSTITUTIONS, normalize_verified_bank, resolve_institution


def test_only_verified_bank_label_is_normalized():
    assert normalize_verified_bank("ACLEDA Bank Plc.") == "ACLEDA"
    assert normalize_verified_bank("PPCBank") == "PPCBank"
    assert normalize_verified_bank("Some Bank Plc.") is None


def test_production_aliases_and_verified_bic_codes_are_exactly_mapped():
    expected = {
        "KB PRASAC Bank Plc": ("KB PRASAC", "ប្រាសាក់"),
        "Cambodia Post Bank Plc": ("Cambodia Post Bank", "ស៊ី ភី ប៊ែង"),
        "CPBPKHPPXXX": ("Cambodia Post Bank", "ស៊ី ភី ប៊ែង"),
        "ACLBKHPPXXX": ("ACLEDA", "អេស៊ីលីដា"),
        "Sathapana Bank Plc": ("SATHAPANA", "ស្ថាបនា"),
    }
    for raw, (display, speech) in expected.items():
        result = resolve_institution("ABA KHQR", raw)
        assert (result.display_name, result.spoken_khmer, result.status) == (display, speech, "VERIFIED")


def test_unknown_label_stays_unmapped_and_is_not_fuzzily_guessed():
    result = resolve_institution("ABA KHQR", "ACLEDA-LIKE FOREIGN NETWORK")
    assert result.raw_label == "ACLEDA-LIKE FOREIGN NETWORK"
    assert result.canonical_id is None
    assert result.display_name is None
    assert result.spoken_khmer is None
    assert result.status == "UNMAPPED"


def test_user_confirmed_registry_contains_every_approved_institution():
    assert len(INSTITUTIONS) == 24
    assert {item.status for item in INSTITUTIONS} <= {"VERIFIED", "USER_CONFIRMED"}
