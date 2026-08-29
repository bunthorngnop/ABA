from decimal import Decimal

import pytest

from app.payment_parser import build_announcement, parse_payment


KHR_CORPUS = (
    ("៛420,000 paid by SANN SOEUNG (*917) on Aug 29, 07:58 AM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178796508172536, APV: 688246.", "420000", "SANN SOEUNG", "ABA", "អេ ប៊ី អេ"),
    ("៛2,000 paid by Chrean Makara (*002) on Aug 29, 08:25 AM via ABA KHQR (KB PRASAC Bank Plc) at Wing Mart R by S.NHEL. Trx. ID: 178796675151594, APV: 905970.", "2000", "Chrean Makara", "KB PRASAC", "ប្រាសាក់"),
    ("៛14,000 paid by LAY CHANTHY (*131) on Aug 29, 10:02 AM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178797254345675, APV: 873536.", "14000", "LAY CHANTHY", "ABA", "អេ ប៊ី អេ"),
    ("៛4,000 paid by ស៊ន ភីរម្យ (*090) on Aug 29, 10:02 AM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart R by S.NHEL. Trx. ID: 178797254969210, APV: 188637.", "4000", "ស៊ន ភីរម្យ", "ACLEDA", "អេស៊ីលីដា"),
    ("៛20,000 paid by Chhoeun Sreyneang (*819) on Aug 29, 10:23 AM via ABA KHQR (ACLBKHPPXXX) at Wing Mart R by S.NHEL. Trx. ID: 178797382827639, APV: 581582.", "20000", "Chhoeun Sreyneang", "ACLEDA", "អេស៊ីលីដា"),
    ("៛18,000 paid by CHROE VARIN (*960) on Aug 29, 12:01 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178797966195547, APV: 897922.", "18000", "CHROE VARIN", "ABA", "អេ ប៊ី អេ"),
    ("៛5,000 paid by SUOS TANGOEUN (*019) on Aug 29, 12:09 PM via ABA KHQR (CPBPKHPPXXX) at Wing Mart R by S.NHEL. Trx. ID: 178798015821796, APV: 114471.", "5000", "SUOS TANGOEUN", "Cambodia Post Bank", "ស៊ី ភី ប៊ែង"),
    ("៛85,000 paid by EANG YEK (*030) on Aug 29, 12:17 PM via ABA KHQR (Cambodia Post Bank Plc) at Wing Mart R by S.NHEL. Trx. ID: 178798066672200, APV: 627347.", "85000", "EANG YEK", "Cambodia Post Bank", "ស៊ី ភី ប៊ែង"),
    ("៛3,500 paid by MUONG CHANTHA (*914) on Aug 29, 12:24 PM via ABA KHQR (Cambodia Post Bank Plc) at Wing Mart R by S.NHEL. Trx. ID: 178798104219421, APV: 829342.", "3500", "MUONG CHANTHA", "Cambodia Post Bank", "ស៊ី ភី ប៊ែង"),
    ("៛1,000 paid by DY CHHOR DA (*948) on Aug 29, 12:33 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178798162164489, APV: 974037.", "1000", "DY CHHOR DA", "ABA", "អេ ប៊ី អេ"),
    ("៛500,000 paid by CHIN CHINDA (*719) on Aug 29, 12:34 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178798167089792, APV: 437290.", "500000", "CHIN CHINDA", "ABA", "អេ ប៊ី អេ"),
    ("៛52,500 paid by នួន រស្មី (*520) on Aug 29, 01:13 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart R by S.NHEL. Trx. ID: 178798401166474, APV: 673680.", "52500", "នួន រស្មី", "ACLEDA", "អេស៊ីលីដា"),
    ("៛2,000 paid by LYN RATANA (*581) on Aug 29, 01:52 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178798632388055, APV: 478513.", "2000", "LYN RATANA", "ABA", "អេ ប៊ី អេ"),
    ("៛50,000 paid by HORN SOKUN (*848) on Aug 29, 02:41 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178798928474587, APV: 153668.", "50000", "HORN SOKUN", "ABA", "អេ ប៊ី អេ"),
    ("៛4,500 paid by NHEAN MONYRACHANA (*298) on Aug 29, 03:13 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart R by S.NHEL. Trx. ID: 178799118430413, APV: 887917.", "4500", "NHEAN MONYRACHANA", "ACLEDA", "អេស៊ីលីដា"),
    ("៛250,000 paid by MON DANET (*818) on Aug 29, 03:19 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart R by S.NHEL. Trx. ID: 178799159838389, APV: 204957.", "250000", "MON DANET", "ACLEDA", "អេស៊ីលីដា"),
    ("៛4,000 paid by MON DANET (*818) on Aug 29, 03:20 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart R by S.NHEL. Trx. ID: 178799162426106, APV: 583361.", "4000", "MON DANET", "ACLEDA", "អេស៊ីលីដា"),
    ("៛10,000 paid by SOEURNG SEY (*587) on Aug 29, 03:53 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178799359598756, APV: 137400.", "10000", "SOEURNG SEY", "ABA", "អេ ប៊ី អេ"),
    ("៛100 paid by NOP BUNTHORNG AND NHEL SOCHENDA (*576) on Aug 29, 04:06 PM via ABA PAY at Wing Mart R by S.NHEL. Remark:  . Trx. ID: 178799438856468, APV: 396346.", "100", "NOP BUNTHORNG AND NHEL SOCHENDA", "ABA", "អេ ប៊ី អេ"),
    ("៛1,500 paid by SREANG MENGSREI (*401) on Aug 29, 04:44 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart R by S.NHEL. Trx. ID: 178799669756677, APV: 310831.", "1500", "SREANG MENGSREI", "ACLEDA", "អេស៊ីលីដា"),
    ("៛6,000 paid by SRIT RANY (*993) on Aug 29, 04:46 PM via ABA KHQR (ACLBKHPPXXX) at Wing Mart R by S.NHEL. Trx. ID: 178799680332832, APV: 384286.", "6000", "SRIT RANY", "ACLEDA", "អេស៊ីលីដា"),
    ("៛500 paid by RUOS KDEY (*995) on Aug 29, 05:02 PM via ABA KHQR (CPBPKHPPXXX) at Wing Mart R by S.NHEL. Trx. ID: 178799773865151, APV: 951348.", "500", "RUOS KDEY", "Cambodia Post Bank", "ស៊ី ភី ប៊ែង"),
    ("៛100 paid by NOP BUNTHORNG (*201) on Aug 29, 05:05 PM via ABA KHQR (Sathapana Bank Plc) at Wing Mart R by S.NHEL. Trx. ID: 178799794789135, APV: 172938.", "100", "NOP BUNTHORNG", "SATHAPANA", "ស្ថាបនា"),
)


USD_CORPUS = (
    ("$1.25 paid by PRAK MUNINEAK (*784) on Aug 24, 08:47 AM via ABA PAY at Wing Mart D by S.NHEL. Remark:  . Trx. ID: 178753604489705, APV: 985551.", "1.25", "PRAK MUNINEAK", "ABA", "អេ ប៊ី អេ"),
    ("$3.38 paid by SEREY CHAN ROTH (*185) on Aug 24, 11:45 AM via ABA PAY at Wing Mart D by S.NHEL. Trx. ID: 178754672031226, APV: 915281.", "3.38", "SEREY CHAN ROTH", "ABA", "អេ ប៊ី អេ"),
    ("$77.75 paid by SAO SAVORN (*778) on Aug 25, 04:27 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart D by S.NHEL. Trx. ID: 178765002138051, APV: 527139.", "77.75", "SAO SAVORN", "ACLEDA", "អេស៊ីលីដា"),
    ("$100.00 paid by NAT SREYROTH (*341) on Aug 25, 04:27 PM via ABA KHQR (CPBPKHPPXXX) at Wing Mart D by S.NHEL. Trx. ID: 178765005841193, APV: 311239.", "100.00", "NAT SREYROTH", "Cambodia Post Bank", "ស៊ី ភី ប៊ែង"),
    ("$70.00 paid by THAM SREY NOR (*149) on Aug 25, 04:53 PM via ABA KHQR (ACLBKHPPXXX) at Wing Mart D by S.NHEL. Trx. ID: 178765160045999, APV: 636595.", "70.00", "THAM SREY NOR", "ACLEDA", "អេស៊ីលីដា"),
    ("$100.92 paid by SAO SAVORN (*778) on Aug 26, 04:10 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart D by S.NHEL. Trx. ID: 178773544823625, APV: 286480.", "100.92", "SAO SAVORN", "ACLEDA", "អេស៊ីលីដា"),
    ("$2.50 paid by SORM ROUT (*926) on Aug 27, 04:52 PM via ABA PAY at Wing Mart D by S.NHEL. Trx. ID: 178782434062748, APV: 690888.", "2.50", "SORM ROUT", "ABA", "អេ ប៊ី អេ"),
    ("$7.14 paid by NOUN SOMNEA (*115) on Aug 28, 08:18 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart D by S.NHEL. Trx. ID: 178792312241160, APV: 891639.", "7.14", "NOUN SOMNEA", "ACLEDA", "អេស៊ីលីដា"),
    ("$5.00 paid by NHEAN MONYRACHANA (*298) on Aug 28, 08:55 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart D by S.NHEL. Trx. ID: 178792533376804, APV: 360850.", "5.00", "NHEAN MONYRACHANA", "ACLEDA", "អេស៊ីលីដា"),
)


@pytest.mark.parametrize("message,amount,payer,display_bank,spoken_bank", KHR_CORPUS)
def test_all_real_khr_transactions(message, amount, payer, display_bank, spoken_bank):
    _assert_real_payment(message, amount, "KHR", payer, display_bank, spoken_bank)


@pytest.mark.parametrize("message,amount,payer,display_bank,spoken_bank", USD_CORPUS)
def test_all_supplied_real_usd_transactions(message, amount, payer, display_bank, spoken_bank):
    _assert_real_payment(message, amount, "USD", payer, display_bank, spoken_bank)


def _assert_real_payment(message, amount, currency, payer, display_bank, spoken_bank):
    result = parse_payment(message)
    assert result.valid_incoming_payment
    assert result.amount == Decimal(amount)
    assert result.currency == currency
    assert result.sender_name == payer
    assert result.payment_channel in {"ABA PAY", "ABA KHQR"}
    assert result.display_bank == display_bank
    assert result.bank == display_bank
    assert result.spoken_bank == spoken_bank
    assert result.canonical_bank is not None
    assert result.institution_status == "VERIFIED"
    announcement = build_announcement(result)
    assert payer in announcement
    assert spoken_bank in announcement
    for private in ("Trx. ID", "APV", "S.NHEL", "Wing Mart", "(*"):
        assert private not in announcement


def test_corpus_sizes_match_every_real_sample_supplied_in_workspace():
    assert len(KHR_CORPUS) == 23
    assert len(USD_CORPUS) == 9
