# ABA PAYMENT SPEAKER — UI/UX VISUAL UPGRADE MASTER PROMPT

## Mission

Upgrade the existing, working **ABA PAYMENT SPEAKER** desktop application so its interface closely follows the approved visual reference.

This is a **UI/UX upgrade only**. The payment-monitoring system is already working successfully. Do not rewrite, replace, or unnecessarily refactor working business logic.

The shop owner must be able to glance at the screen and immediately understand:

1. **How much money was received**
2. **Who sent the money**
3. **Which bank the money came from**

These three fields must dominate the visual hierarchy.

## Approved visual direction

Use the approved dashboard screenshot supplied with this project/conversation as the visual reference.

Target appearance:
- modern professional payment-terminal/dashboard style
- dark navy / near-black background
- high contrast
- large readable typography
- clean card-based layout
- restrained but attractive accent colors
- green for successful payment/healthy status
- blue for sender identity
- purple/violet for bank identity
- suitable for continuous display at a shop counter
- uncluttered by developer information

Do not hard-code sample values from the mockup. Real application data must populate the interface.

## 1. Received amount — highest priority

Display the latest received amount extremely prominently, for example:

    ៛ 50,000

or:

    $ 5.00

Requirements:
- largest font on the entire interface
- centered/prominent placement
- bright success-green treatment
- currency symbol clearly visible
- readable from several meters away
- dynamically use the real parsed amount
- support both KHR and USD correctly

## 2. Sender name — second priority

Clearly show:

    FROM (SENDER)
    SOK DARA

Requirements:
- very large bold sender name
- blue visual identity/accent
- person/user icon if appropriate
- dynamically use the real parsed payer name
- never substitute merchant/staff/operator names
- never expose masked account fragments

The existing validated parser remains authoritative.

## 3. Originating bank — third priority

Clearly show:

    FROM BANK
    ACLEDA

Requirements:
- very large bold bank name
- purple/violet accent
- bank/building icon if appropriate
- dynamically use the existing normalized originating-bank result
- preserve current bank-normalization behavior

Examples:
- `via ABA PAY` → display `ABA`
- `via ABA KHQR (ACLEDA Bank Plc.)` → display `ACLEDA`

Do not change established parser/bank rules for presentation.

## Main payment card

Create one dominant card titled approximately:

    LAST PAYMENT RECEIVED

Suggested hierarchy:

    LAST PAYMENT RECEIVED

               ៛ 50,000
             ✓ ANNOUNCED

       FROM (SENDER)        FROM BANK
       SOK DARA             ACLEDA

When a new valid payment arrives:
1. update the main card immediately;
2. visually emphasize the new amount;
3. show sender and bank;
4. reflect announcement state accurately.

A subtle temporary highlight/pulse is acceptable if reliable and not distracting.

Do not show `ANNOUNCED` until the application actually knows the announcement succeeded.

## Header

Create a polished header containing:
- **ABA PAYMENT SPEAKER**
- optional configured shop name
- LIVE / connected state
- current local time
- current date

The LIVE indicator must reflect actual system readiness, not decoration.

Do not hard-code the sample shop name from the visual mockup unless already configured.

## System status

Provide a compact status card showing meaningful existing states such as:
- Telegram/User Session Connected
- Speaker Ready
- PayWay Source Verified

Use:
- green/check = healthy
- amber = waiting/degraded
- red = error/disconnected

Never claim a component is connected/verified unless application state confirms it.

Never expose Telegram credentials, API hashes, session data, login codes, raw payloads, or secrets.

## Today summary

If the existing database can reliably provide the data, create a compact card showing:
- number of accepted/announced payments today
- total KHR received today
- total USD received today

Keep KHR and USD separate. Do not invent exchange-rate conversions and do not combine the currencies.

If current storage cannot safely support a field, do not fabricate it.

## Recent payments

If safely supported by the existing database, show approximately the latest 5 accepted payments:

    AMOUNT | SENDER | BANK | TIME

Use real data only.

Never display:
- masked account numbers
- transaction IDs
- APV
- balances
- merchant/location
- staff/operator names
- Telegram raw messages
- private credentials

## Main controls

Create large, easy controls such as:
- **SPEAKER ON / OFF**
- **TEST SPEAKER**
- **MUTE**
- **SETTINGS**
- **HISTORY** if already supported or inexpensive to expose safely

Every button must perform a real function and reflect real state. Do not create decorative nonfunctional controls.

## Settings / Diagnostics

Move technical/commissioning information away from the main operational screen.

The main dashboard should not be dominated by:
- raw parser JSON
- Telegram IDs
- diagnostic messages
- raw logs
- developer test inputs

Preserve useful diagnostic and safe parser-test capabilities in a secondary **Settings / Diagnostics** area.

## Window behavior

The interface must work well on a normal Windows shop PC:
- support common laptop/desktop resolutions
- avoid clipped/overlapping widgets
- handle long sender names gracefully
- keep bank names readable
- protect layout with a sensible minimum size
- support maximized/full-screen use where practical
- avoid tiny text on high-resolution displays

The amount, sender, and bank must remain visually dominant on smaller supported windows.

If the existing GUI uses Tkinter, remain in the existing framework unless there is a compelling technical reason not to. Do not migrate the whole application to Electron, web, Qt, etc. merely for appearance.

Prefer the lowest-risk modernization.

## Typography and Khmer

Continue supporting:
- Khmer script
- Khmer currency symbol `៛`
- English payer names
- bank names
- numeric values

Do not introduce unsafe/unlicensed font dependencies.

## Color/accessibility

Use color to strengthen meaning, not as the only indicator:
- payment/success: bright green
- sender: blue
- bank: purple/violet
- general text: white/light gray
- background: dark navy/near black
- warning: amber
- error: red

Also use icons/text/check marks so states remain understandable without relying solely on color.

Avoid excessive gradients, flashing, gaming/neon styling.

Target: **professional financial terminal + modern shop dashboard**.

## Payment event behavior

Existing processing/business logic remains authoritative:

    Authorized Telegram message
              ↓
        Existing parser
              ↓
      Existing validation
              ↓
     Existing duplicate check
              ↓
         Valid payment
              ↓
       Update dashboard
              ↓
       Existing TTS queue
              ↓
     Announcement result/status

Do not weaken authorization/validation for UI demonstrations.

Test/sample data must remain separated from live payments.

## Critical: do not change working systems

Do not unnecessarily rewrite or alter:
- Telegram user-session listener
- Telegram authentication
- allowed-group filtering
- verified PayWay sender-ID filtering
- payment parser
- ABA PAY interpretation
- ABA KHQR interpretation
- payer extraction
- bank normalization
- Khmer number conversion
- TTS voice/announcement rules
- audio queue
- duplicate suppression
- SQLite safety logic
- privacy protections
- `.env` security
- Telegram session security

UI code should consume existing application state/services instead of duplicating business logic.

## Confirmed payment behavior must remain valid

KHR example:

    ៛2,000 paid by VAN VET (*571) on Aug 28, 07:34 PM via ABA PAY at Wing Mart R by S.NHEL. Trx. ID: 178792044713371, APV: 761253.

UI result:

    RECEIVED
    ៛ 2,000

    FROM
    VAN VET

    BANK
    ABA

Existing Khmer speech behavior must remain unchanged.

USD/KHQR example:

    $5.00 paid by NHEAN MONYRACHANA (*298) on Aug 28, 08:55 PM via ABA KHQR (ACLEDA Bank Plc.) at Wing Mart D by S.NHEL. Trx. ID: 178792533376804, APV: 360850.

UI result:

    RECEIVED
    $ 5.00

    FROM
    NHEAN MONYRACHANA

    BANK
    ACLEDA

Existing Khmer speech behavior must remain unchanged.

## Safety principle

> **SILENCE IS BETTER THAN A FALSE PAYMENT ANNOUNCEMENT.**

The redesign must never cause:
- rejected messages to appear as successful payments
- unauthorized messages to appear as payments
- duplicates to appear as new payments
- parser-test data to contaminate production totals/history
- failed announcements to be marked successful
- unknown bank information to be guessed

Presentation must accurately reflect validated underlying state.

## Implementation approach

Before coding:
1. inspect the entire existing project;
2. identify GUI framework/dashboard architecture;
3. identify how payment events reach the current dashboard;
4. identify available database methods;
5. identify existing status/state signals;
6. identify existing tests;
7. create a safe UI upgrade plan.

Then implement incrementally.

Prefer:
- reusable UI components
- centralized theme/style definitions
- minimal coupling
- no duplicated parser/database logic
- clear separation between UI and payment services

If a UI feature requires a non-presentation change, make the smallest safe change and explain why.

## Testing

Run the complete existing regression suite.

Add appropriate tests where practical for:
- KHR amount display
- USD amount display
- sender display
- bank display
- long sender names
- unknown/omitted bank behavior
- live status mapping
- summary calculations if added
- recent-payment retrieval if added
- mute/speaker state
- prevention of test data contaminating production statistics

Perform a manual GUI smoke test.

Verify both confirmed ABA samples still produce the established parser and speech results.

Do not remove existing tests merely to make the redesign pass.

## Acceptance criteria

The upgrade is successful only if:

1. real payments still process correctly;
2. the three most visually obvious values are **received amount, sender, originating bank**;
3. the amount is easily readable from a distance;
4. sender and bank are immediately distinguishable;
5. the dashboard looks polished and professional;
6. live status is truthful;
7. no secrets appear in the UI;
8. privacy rules remain intact;
9. diagnostics remain available without cluttering the main screen;
10. all regression tests pass;
11. the application launches normally on the existing Windows setup;
12. no production payment logic is weakened.

## Completion report

When finished, report:
1. files changed;
2. UI components added/modified;
3. how the approved design was implemented;
4. deliberate differences from the reference and why;
5. tests added;
6. full regression results;
7. manual GUI test result;
8. confirmation that parsing/TTS/security behavior was preserved;
9. exact steps to launch and inspect the redesigned application.

Do not proceed into unrelated features.

Stop and wait for approval.

# Final priority

If visual compromises are necessary, prioritize:

**1. RECEIVED AMOUNT**

**2. SENDER NAME**

**3. ORIGINATING BANK**

Everything else is secondary.

The shop owner should need less than one second to glance at the screen and understand:

> **How much came in, who sent it, and from which bank.**
