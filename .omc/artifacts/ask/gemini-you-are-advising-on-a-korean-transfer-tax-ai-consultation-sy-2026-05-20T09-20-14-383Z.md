# gemini advisor artifact

- Provider: gemini
- Exit code: 0
- Created at: 2026-05-20T09:20:14.387Z

## Original task

You are advising on a Korean transfer tax (양도소득세) AI consultation system. It takes structured JSON facts from users and returns a tax verdict with legal citations. The system covers: 1세대1주택 비과세, 고가주택, 단기세율, 다주택 중과, 일시적2주택, 상속주택, 증여이월과세, 상생임대, 분양권/입주권 등.

YOUR TASK: What additional DOMAIN KNOWLEDGE, USER CONTEXT, or EDGE CASE SCENARIOS are still missing to make this system consultation-perfect? Ask every question that exposes gaps in: (1) Korean tax law edge cases not yet covered (법령 사각지대), (2) user intent disambiguation — how real users describe their situations vs. system's fact schema, (3) missing special case types (특례 유형), (4) fact fields that users typically don't know but matter legally, (5) temporal/date edge cases in law application, (6) multi-property household scenarios not modeled, (7) what a Korean tax attorney would ask that the system doesn't. Be exhaustive and practical — focus on real consultation gaps.

## Final prompt

You are advising on a Korean transfer tax (양도소득세) AI consultation system. It takes structured JSON facts from users and returns a tax verdict with legal citations. The system covers: 1세대1주택 비과세, 고가주택, 단기세율, 다주택 중과, 일시적2주택, 상속주택, 증여이월과세, 상생임대, 분양권/입주권 등.

YOUR TASK: What additional DOMAIN KNOWLEDGE, USER CONTEXT, or EDGE CASE SCENARIOS are still missing to make this system consultation-perfect? Ask every question that exposes gaps in: (1) Korean tax law edge cases not yet covered (법령 사각지대), (2) user intent disambiguation — how real users describe their situations vs. system's fact schema, (3) missing special case types (특례 유형), (4) fact fields that users typically don't know but matter legally, (5) temporal/date edge cases in law application, (6) multi-property household scenarios not modeled, (7) what a Korean tax attorney would ask that the system doesn't. Be exhaustive and practical — focus on real consultation gaps.

## Raw output

```text
This is a highly sophisticated domain. In Korean transfer tax (양도소득세), the "devil is in the details" of the **dates**, **household composition**, and **property usage history**.

To bridge the gap between a "functional" RAG system and a "consultation-perfect" one, we must address these specific gaps:

### 1. Household Composition (1세대) & "The Tax Unit" Gaps
In Korea, you don't tax a person; you tax a **household**.
*   **Independent Livelihood:** Does the system ask if family members living at the same address (parents, adult children) have independent income? (Critical for determining if they are "one household").
*   **Separated Spouses:** Does the system account for the fact that spouses are always considered one household, even if they live apart and are registered at different addresses?
*   **De Facto vs. Resident Registration:** How does the system handle cases where the "Resident Register (주민등록)" says one thing, but the "Actual Fact (실질주의)" is different? (e.g., a child living at a parent's house but actually working in another city).

### 2. Property Usage History (실질과세)
*   **The Officetel Trap:** Does the system distinguish between a "Residentially used Officetel" (counts as a house) and an "Office-used Officetel"? Does it ask for evidence like utility bills or business registration?
*   **Commercial-Residential Buildings (상가주택):** For mixed-use buildings, the rules changed recently. If the house area > commercial area, the whole building used to be a house, but now for "High-value houses (>12억)," they are split. Is this modeled?
*   **Unregistered/Illegal Buildings:** Does the system account for rooftop rooms or converted garages? Even if they aren't on the building ledger, they count as a "house" for the tax count.

### 3. Critical "Dates" & Regional Status (조정대상지역)
*   **The "Contract Date" vs. "Acquisition Date":** This is the most common error. For residency requirements in "Adjustment Target Areas," the status **on the date of the contract** (and whether the user was homeless at that time) matters.
*   **The "Final 1 House" Rule (최종 1주택):** While this rule was mostly abolished in May 2022, it still applies to some specific historical calculations for those who sold before the change. Does the system handle historical data correctly?
*   **Holding Period Calculation for Rebuilt Houses:** When a house is demolished and rebuilt, the holding period for the land and the building are different. Does the schema capture both?

### 4. Missing Special Case Types (특례)
*   **Rural House Exemption (농어촌주택특례):** If a user has one house in Seoul and one inherited/rural house in a village, the rural house might be excluded from the count. Does the system ask about the "Eup/Myeon" location?
*   **Work/Medical Relocation:** Does the system account for the exemption when moving due to a job transfer, school, or medical treatment (requiring 1 year+ residency)?
*   **Small-scale Redevelopment (소규모 재건축):** The rules for "Villas" undergoing "Moa-Town" or "Street-unit" redevelopment are slightly different from traditional "Apartment" redevelopment.

### 5. Necessary Expenses (필요경비) - The "Tax Shield"
Users often don't know what they can deduct.
*   **Capital Expenditure vs. Revenue Expenditure:** Does the system distinguish between "Remodeling" (deductible) and "Simple repairs/wallpapering" (not deductible)?
*   **System Air Conditioning & Balcony Expansion:** These are common deductions. Does the system nudge the user to find these receipts?
*   **Brokerage & Legal Fees:** Does it ask for the fees paid during both *acquisition* and *sale*?

### 6. User Intent & Disambiguation (NL vs. Schema)
*   **"Selling" vs. "Transferring":** Users might say "I'm giving my house to my son." The system needs to distinguish between **Gift (증여)**, **Sale (양도)**, and **Burdensome Gift (부담부증여)**.
*   **"My House":** A user might say "I only have one house," but they own a 1/5 share of an inherited house in the countryside. In tax law, **a share is a house**. Does the system cross-examine this?

### 7. What a Tax Attorney (세무사) Would Ask
*   **"Is there any other property, even a piece of land, anywhere in the country?"** (Users often forget non-residential land which can affect "Non-business land" tax rates).
*   **"Did you ever have a business registered at this address?"** (This might invalidate the 1-house exemption if used for business).
*   **"Have you sold any other assets this year?"** (Transfer taxes are cumulative within a calendar year; if you sold two properties, the tax bracket jumps significantly).

### 8. Inheritance & Gift Complexity
*   **The 5/10 Year Rule (이월과세):** If I received a house from my spouse and sell it within 10 years, the tax is calculated based on my **spouse's** original purchase price. This is a massive "Tax Bomb." Is this in your JSON schema?
*   **Order of Inheritance:** Which house did the user live in at the time of inheritance? The "Inherited House Exemption" only applies to the *first* one inherited.

### Strategic Recommendation for your RAG System:
1.  **Add a "Pre-flight Check" Agent:** Before calculating, have an agent ask: "Do you or anyone in your resident register own a share of any other property, including inherited land or officetels?"
2.  **Date Validation:** Ensure the system maps the "Adjustment Target Area" status to the specific **Contract Date** and **Acquisition Date** via a lookup table.
3.  **Document Checklist:** Instead of just a verdict, return a **"Evidence Checklist"** (e.g., "Since you claimed a balcony expansion deduction, you will need the tax invoice or bank transfer record").

Which of these areas (Household, Dates, Property Type, or Expenses) currently has the most "sparse" data in your `fact_input.py` schema? I can help you expand that specific module.


Warning: True color (24-bit) support not detected. Using a terminal with true color enabled will result in a better visual experience.
YOLO mode is enabled. All tool calls will be automatically approved.
YOLO mode is enabled. All tool calls will be automatically approved.
Ripgrep is not available. Falling back to GrepTool.

```

## Concise summary

Provider completed successfully. Review the raw output for details.

## Action items

- Review the response and extract decisions you want to apply.
- Capture follow-up implementation tasks if needed.
