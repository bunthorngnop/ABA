from app.bank_normalizer import normalize_verified_bank


def test_only_verified_bank_label_is_normalized():
    assert normalize_verified_bank("ACLEDA Bank Plc.") == "ACLEDA"
    assert normalize_verified_bank("PPCBank") == "PPCBank"
    assert normalize_verified_bank("Some Bank Plc.") is None
