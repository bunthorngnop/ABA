# ABA PAYMENT SPEAKER — MULTI-BANK & CROSS-BORDER KHQR HARDENING
## Codex Master Implementation Prompt

## Mission
Harden the existing, working ABA PAYMENT SPEAKER so genuine incoming payments are not missed because the Cambodian bank, bank alias/code, payer name, amount format, or future cross-border KHQR network is unfamiliar.

This is a parser/bank-normalization/TTS hardening phase, **not a rebuild**. Preserve the working Telegram user-session listener, authorization, duplicate protection, SQLite, dashboard, audio queue, Khmer TTS, and privacy controls.

## KEYWORD INSTRUCTIONS — HARD RULES
`PRESERVE_WORKING_SYSTEM`
`DO_NOT_REBUILD`
`DETERMINISTIC_ONLY`
`NO_AI_LLM`
`AUTHORIZED_SOURCE_FIRST`
`VALID_PAYMENT_INDEPENDENT_OF_BANK_RECOGNITION`
`UNKNOWN_BANK_MUST_NOT_REJECT_VALID_PAYMENT`
`DO_NOT_GUESS_BANK`
`DO_NOT_GUESS_NETWORK`
`RAW_LABEL_TO_CANONICAL_TO_DISPLAY_TO_SPEECH`
`UNICODE_PAYER_NAMES`
`KHR_AND_USD`
`USD_CENTS_SUPPORTED`
`OPTIONAL_REMARK_SUPPORTED`
`BANK_ALIAS_SUPPORT`
`BIC_SWIFT_ALIAS_SUPPORT`
`CROSS_BORDER_READY`
`TOURIST_KHQR_READY`
`REAL_SAMPLES_ARE_REGRESSION_TESTS`
`SILENCE_OVER_FALSE_PAYMENT`
`PRIVACY_FIRST`
`NO_SECRET_LOGGING`
`NO_TEST_DATA_IN_PRODUCTION_TOTALS`
`FULL_REGRESSION_REQUIRED`

If an implementation choice conflicts with a keyword rule, the keyword rule wins.

## 1. Required architecture
Use this separation:

```text
AUTHORIZED PAYWAY SOURCE
→ INCOMING PAYMENT STRUCTURE
→ AMOUNT + CURRENCY + PAYER
→ PAYMENT CHANNEL
→ RAW BANK/NETWORK LABEL
→ SAFE EXACT NORMALIZATION
→ CANONICAL INSTITUTION
→ DISPLAY NAME
→ KHMER SPOKEN NAME
```

Bank recognition is **not** the validity gate. If source/group/sender authorization and the incoming-payment grammar are valid, an unfamiliar bank/network label must not by itself reject the payment.

For unknown institutions: do not guess; preserve an unmapped state; omit the bank clause from TTS (or use the existing equally-safe fallback); keep the payment valid if all authoritative checks pass.

## 2. Parser requirements
Support KHR and USD, exact USD cents, comma-separated amounts, uppercase/mixed-case Latin names, Khmer Unicode names, long names, optional `Remark:`, `ABA PAY`, and `ABA KHQR (LABEL)`.

Extract payer from the payment-specific `paid by NAME (*NNN)` segment. Never confuse the later merchant/staff `by ...` text with the payer.

Never speak masked account fragments, merchant/location, staff/operator, Trx ID, APV, balance, Telegram IDs, or credentials.

Use Decimal/integer minor units for money; do not use binary float for authoritative values.

## 3. User-confirmed spoken-bank dictionary
Use these as preferred shop TTS names **after safe institution identification**:

| Canonical institution | Display | Khmer speech |
|---|---|---|
| ABA Bank | ABA | អេ ប៊ី អេ |
| ACLEDA Bank | ACLEDA | អេស៊ីលីដា |
| Canadia Bank | Canadia | កាណាឌីយ៉ា |
| Wing Bank | Wing | វីង |
| SATHAPANA Bank | SATHAPANA | ស្ថាបនា |
| Chip Mong Bank | Chip Mong Bank | ជីប ម៉ុង |
| Cambodia Post Bank / CP Bank | Cambodia Post Bank | ស៊ី ភី ប៊ែង |
| Vattanac Bank | Vattanac Bank | វឌ្ឍនៈ |
| Foreign Trade Bank / FTB | FTB | អេហ្វ ធី ប៊ី |
| Prince Bank | Prince Bank | ព្រិនស៍ |
| Phillip Bank | Phillip Bank | ហ្វីលីព |
| BRED Bank | BRED Bank | ប្រេដ ប៊ែង |
| Bridge Bank | Bridge Bank | ប្រ៊ីដ |
| SBI LY HOUR Bank | SBI LY HOUR | លី ហួរ |
| Oriental Bank | Oriental Bank | អូរៀនថល |
| KB PRASAC Bank | KB PRASAC | ប្រាសាក់ |
| ARDB | ARDB | ធនាគារអភិវឌ្ឍន៍ជនបទ |
| Cambodian Public Bank / Campu Bank | Campu Bank | ខាំភូ ប៊ែង |
| PPCBank | PPCBank | ភី ភី ស៊ី |
| Bank of China | Bank of China | ធនាគារចិន |
| Maybank | Maybank | មេប៊ែង |
| BIDC Bank | BIDC | ប៊ី អាយ ឌី ស៊ី |
| Union Commercial Bank / UCB | UCB | យូ ស៊ី ប៊ី |
| AEON Specialized Bank | AEON | អ៊ីអន |

Keep aliases separate from spoken names.

## 4. Production-observed aliases
Regression-test these exact raw labels:
- `ABA PAY` → ABA
- `ACLEDA Bank Plc.` → ACLEDA
- `ACLBKHPPXXX` → ACLEDA only if exact mapping is verified
- `KB PRASAC Bank Plc` → KB PRASAC
- `Cambodia Post Bank Plc` → Cambodia Post Bank
- `CPBPKHPPXXX` → Cambodia Post Bank only if exact mapping is verified
- `Sathapana Bank Plc` → SATHAPANA

Use deterministic exact aliases/codes after harmless case/space/punctuation normalization. **No fuzzy bank matching in production.**

Prefer a structured registry with canonical_id, canonical_name, display_name, spoken_khmer, aliases, verified codes, and status (`VERIFIED`, `USER_CONFIRMED`, `UNMAPPED`).

## 5. USD cents
Real production values include `$1.25`, `$3.38`, `$3.25`, `$77.75`, `$100.92`, `$2.50`, and `$7.14`.

Do not round/truncate. `.00` keeps the established natural whole-dollar Khmer speech. For non-zero cents, generate clear natural Khmer dollar-and-cent speech and add exact tests.

## 6. Cross-border/tourist KHQR readiness
Design for future exact labels from cross-border ecosystems such as Alipay+, UnionPay, Weixin/WeChat Pay, India, Singapore, Laos, Malaysia, Korea and future Bakong/KHQR partners.

**Do not pre-guess PayWay wording or identities.** A foreign-looking payer name is never evidence of a network. Only map a network when a real notification exposes an exact label/code and that mapping is verified.

Unknown future network labels remain valid-but-unmapped if the rest of the payment is valid. The registry must allow new verified aliases without changing parser grammar.

## 7. Announcement
Preserve Khmer-only style:

`បានទទួលប្រាក់ {natural_amount} ពីឈ្មោះ {payer_name}, ធនាគារ {spoken_bank_name}។`

If institution is safely unmapped:

`បានទទួលប្រាក់ {natural_amount} ពីឈ្មោះ {payer_name}។`

Never invent the missing bank.

## 8. Diagnostics
Use privacy-safe outcomes such as:
`VALID`
`DUPLICATE`
`SOURCE_NOT_AUTHORIZED`
`CHAT_NOT_ALLOWED`
`AMOUNT_PARSE_FAILED`
`CURRENCY_UNSUPPORTED`
`PAYER_PARSE_FAILED`
`PAYMENT_STRUCTURE_UNSUPPORTED`
`BANK_UNMAPPED`
`NETWORK_UNMAPPED`

`BANK_UNMAPPED`/`NETWORK_UNMAPPED` are enrichment conditions, not automatic rejection reasons.

## 9. Real KHR regression fixtures
Create tests for ALL of these genuine production messages:

```text
៛420,000 paid by SANN SOEUNG (*917) on Aug 29, 07:58 AM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178796508172536, APV: 688246.
៛2,000 paid by Chrean Makara (*002) on Aug 29, 08:25 AM via ABA KHQR (KB PRASAC Bank Plc) at Wing Mart R by S.NHEL. Trx. ID: 178796675151594, APV: 905970.
៛14,000 paid by LAY CHANTHY (*131) on Aug 29, 10:02 AM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178797254345675, APV: 873536.
៛4,000 paid by ស៊ន ភីរម្យ (*090) on Aug 29, 10:02 AM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart R by S.NHEL. Trx. ID: 178797254969210, APV: 188637.
៛20,000 paid by Chhoeun Sreyneang (*819) on Aug 29, 10:23 AM via ABA KHQR (ACLBKHPPXXX) at Wing Mart R by S.NHEL. Trx. ID: 178797382827639, APV: 581582.
៛18,000 paid by CHROE VARIN (*960) on Aug 29, 12:01 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178797966195547, APV: 897922.
៛5,000 paid by SUOS TANGOEUN (*019) on Aug 29, 12:09 PM via ABA KHQR (CPBPKHPPXXX) at Wing Mart R by S.NHEL. Trx. ID: 178798015821796, APV: 114471.
៛85,000 paid by EANG YEK (*030) on Aug 29, 12:17 PM via ABA KHQR (Cambodia Post Bank Plc) at Wing Mart R by S.NHEL. Trx. ID: 178798066672200, APV: 627347.
៛3,500 paid by MUONG CHANTHA (*914) on Aug 29, 12:24 PM via ABA KHQR (Cambodia Post Bank Plc) at Wing Mart R by S.NHEL. Trx. ID: 178798104219421, APV: 829342.
៛1,000 paid by DY CHHOR DA (*948) on Aug 29, 12:33 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178798162164489, APV: 974037.
៛500,000 paid by CHIN CHINDA (*719) on Aug 29, 12:34 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178798167089792, APV: 437290.
៛52,500 paid by នួន រស្មី (*520) on Aug 29, 01:13 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart R by S.NHEL. Trx. ID: 178798401166474, APV: 673680.
៛2,000 paid by LYN RATANA (*581) on Aug 29, 01:52 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178798632388055, APV: 478513.
៛50,000 paid by HORN SOKUN (*848) on Aug 29, 02:41 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178798928474587, APV: 153668.
៛4,500 paid by NHEAN MONYRACHANA (*298) on Aug 29, 03:13 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart R by S.NHEL. Trx. ID: 178799118430413, APV: 887917.
៛250,000 paid by MON DANET (*818) on Aug 29, 03:19 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart R by S.NHEL. Trx. ID: 178799159838389, APV: 204957.
៛4,000 paid by MON DANET (*818) on Aug 29, 03:20 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart R by S.NHEL. Trx. ID: 178799162426106, APV: 583361.
៛10,000 paid by SOEURNG SEY (*587) on Aug 29, 03:53 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178799359598756, APV: 137400.
៛100 paid by NOP BUNTHORNG AND NHEL SOCHENDA (*576) on Aug 29, 04:06 PM via ABA PAY at Wing Mart R by S.NHEL. Remark:  . Trx. ID: 178799438856468, APV: 396346.
៛1,500 paid by SREANG MENGSREI (*401) on Aug 29, 04:44 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart R by S.NHEL. Trx. ID: 178799669756677, APV: 310831.
៛6,000 paid by SRIT RANY (*993) on Aug 29, 04:46 PM via ABA KHQR (ACLBKHPPXXX) at Wing Mart R by S.NHEL. Trx. ID: 178799680332832, APV: 384286.
៛500 paid by RUOS KDEY (*995) on Aug 29, 05:02 PM via ABA KHQR (CPBPKHPPXXX) at Wing Mart R by S.NHEL. Trx. ID: 178799773865151, APV: 951348.
៛100 paid by NOP BUNTHORNG (*201) on Aug 29, 05:05 PM via ABA KHQR (Sathapana Bank Plc) at Wing Mart R by S.NHEL. Trx. ID: 178799794789135, APV: 172938.
```

## 10. Real USD corpus
The supplied historical corpus contains **69 genuine USD PayWay transactions (Aug 23–28, 2026)**. Import the complete supplied corpus into test fixtures if it is present in the workspace. Do not reduce it to only a few examples.

It covers ABA PAY, ACLEDA, Cambodia Post Bank, `ACLBKHPPXXX`, `CPBPKHPPXXX`, whole dollars, cents, optional Remark, and mixed-case names.

At minimum explicitly assert:
```text
$1.25 paid by PRAK MUNINEAK (*784) on Aug 24, 08:47 AM via ABA PAY at Wing Mart D by S.NHEL. Remark:  . Trx. ID: 178753604489705, APV: 985551.
$3.38 paid by SEREY CHAN ROTH (*185) on Aug 24, 11:45 AM via ABA PAY at Wing Mart D by S.NHEL. Trx. ID: 178754672031226, APV: 915281.
$77.75 paid by SAO SAVORN (*778) on Aug 25, 04:27 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart D by S.NHEL. Trx. ID: 178765002138051, APV: 527139.
$100.00 paid by NAT SREYROTH (*341) on Aug 25, 04:27 PM via ABA KHQR (CPBPKHPPXXX) at Wing Mart D by S.NHEL. Trx. ID: 178765005841193, APV: 311239.
$70.00 paid by THAM SREY NOR (*149) on Aug 25, 04:53 PM via ABA KHQR (ACLBKHPPXXX) at Wing Mart D by S.NHEL. Trx. ID: 178765160045999, APV: 636595.
$100.92 paid by SAO SAVORN (*778) on Aug 26, 04:10 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart D by S.NHEL. Trx. ID: 178773544823625, APV: 286480.
$2.50 paid by SORM ROUT (*926) on Aug 27, 04:52 PM via ABA PAY at Wing Mart D by S.NHEL. Trx. ID: 178782434062748, APV: 690888.
$7.14 paid by NOUN SOMNEA (*115) on Aug 28, 08:18 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart D by S.NHEL. Trx. ID: 178792312241160, APV: 891639.
$5.00 paid by NHEAN MONYRACHANA (*298) on Aug 28, 08:55 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart D by S.NHEL. Trx. ID: 178792533376804, APV: 360850.
```

## 11. Unknown-bank safety test
Add TEST-ONLY fixture:
```text
៛12,345 paid by TEST CUSTOMER (*123) on Aug 29, 06:00 PM via ABA KHQR (NEW FUTURE BANK XYZ) at Wing Mart R by S.NHEL. Trx. ID: TESTONLY, APV: 000000.
```
Expected: valid structure, amount/payer/channel parsed, bank UNMAPPED, no guessed bank, safe speech without bank. Never add test data to production history.

Add a similar TEST-ONLY foreign-network fixture using `(UNMAPPED FOREIGN NETWORK)`. Do not claim it is actual PayWay wording.

## 12. Test dimensions
For real samples assert as applicable:
`valid_incoming_payment`, `amount`, `currency`, `payer_name`, `payment_channel`, `raw_bank_label`, `canonical_bank`, `display_bank`, `spoken_bank`, `announcement_text`.

Verify sensitive fields are never spoken and duplicate protection remains intact.

## 13. Security
Do not weaken allowed Telegram session/account, allowed group/chat, verified PayWay sender, source validation, duplicate suppression, database integrity, `.env` security, or session-file security.

Flexible bank recognition must never mean flexible source authorization.

## 14. UI
Preserve dashboard hierarchy:
1. RECEIVED AMOUNT
2. SENDER
3. BANK

Mapped institutions use preferred display name. Unknown institutions use a neutral safe value such as `OTHER BANK` or an approved safe raw label. Dashboard and TTS must consume the same canonical normalization result.

## 15. Implementation sequence
1. Read all authoritative project prompts, README, parser, normalizer, Khmer number/TTS code, Telegram listener, DB, dashboard, tests, and real sample files.
2. Run full baseline tests before changes.
3. Batch-run every supplied real transaction and record exactly which currently fail and why.
4. Implement the smallest safe parser/registry/TTS corrections.
5. Add all supplied KHR and USD production samples as regression fixtures.
6. Add unknown-bank/network, Unicode-name, optional-Remark, and cents tests.
7. Run targeted tests and complete regression suite.
8. Perform a manual GUI/speaker smoke test without manufacturing a live payment.

Do not use a giant permissive regex. Stay anchored to verified PayWay incoming-payment grammar and tolerate only production-evidenced variation.

## 16. Database safety
If schema changes are needed, migrate safely without deleting production history. Prefer no migration if unnecessary.

## 17. Definition of done
Complete only when:
- existing tests pass;
- every supplied structurally valid production sample parses;
- known banks normalize correctly;
- approved Khmer bank pronunciations are used;
- Khmer/mixed-case/long payer names work;
- USD cents are exact;
- optional Remark works;
- unknown bank does not invalidate an otherwise valid payment;
- unknown bank/network is never guessed;
- cross-border registry is extensible;
- security and duplicate suppression are unchanged;
- no secrets are exposed;
- UI and TTS still work.

## 18. Completion report
Report:
1. files changed;
2. baseline result;
3. real samples that failed before changes and reasons;
4. parser changes;
5. registry/aliases added;
6. Khmer speech names added;
7. cents behavior;
8. unknown-bank behavior;
9. cross-border readiness;
10. number of production fixtures/tests added;
11. final regression result;
12. migration status;
13. GUI/speaker smoke-test result;
14. any labels intentionally left UNMAPPED.

Do not proceed to unrelated features. Stop and wait for approval.

# FINAL SAFETY RULE
> **SILENCE IS BETTER THAN A FALSE PAYMENT ANNOUNCEMENT — BUT AN UNKNOWN BANK NAME ALONE IS NOT PROOF THAT A VERIFIED INCOMING PAYMENT IS FALSE.**

Authorization/payment validation remain strict. Institution recognition is a separate enrichment layer.
