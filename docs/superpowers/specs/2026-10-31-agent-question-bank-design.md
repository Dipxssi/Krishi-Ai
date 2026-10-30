# Agent question bank

## Goal

Each of the 7 agents can recognize at least 1,000 likely farmer questions in English, 1,000 in Hindi (Devanagari), and 1,000 in Kannada script. The bank does two jobs:

1. Choose the agent by matching the latest farmer question to the nearest stored questions.
2. Supply a practical next step when the loan, scheme, or crop record does not already answer the question.

The bank runs beside the existing phrase matcher. It does not replace it.

## Scale

| Item | Count |
|---|---:|
| Agents | 7 |
| Languages | 3 (`en`, `hi`, `kn`) |
| Indexed questions per agent per language | 1,000 |
| Holdout questions per agent per language | 50 |
| Rows on disk | 22,050 |

Agents, in catalog order: `crop_health`, `finance`, `equipment`, `market`, `weather`, `soil`, `knowledge_retriever`.

Hindi rows use Devanagari. Kannada rows use Kannada script. Romanized Hindi and Kannada stay on the existing phrase lists, because language detection follows script.

## Row shape

One JSON object per line:

```json
{
  "id": "finance-en-00001",
  "agent": "finance",
  "language": "en",
  "split": "index",
  "intent": "crop_loan",
  "crop": "tomato",
  "place": "Bengaluru",
  "question": "What agricultural loan options are there for my tomato farm in Bengaluru?",
  "linked_record_id": "kcc-crop-loan",
  "next_step": "Take land records, Aadhaar, a passport photo, and a crop plan to a scheduled commercial bank, cooperative bank, or regional rural bank in Bengaluru. Ask for the Kisan Credit Card crop loan. Confirm the current interest rate and collateral rule at the branch."
}
```

`split` is `index` or `holdout`. Only `index` rows are loaded for live matching. `linked_record_id` is a string or `null`. `crop` and `place` may be `null` when the intent is not crop-specific or place-specific.

`next_step` may name the office, the documents, and the product to ask for. It must not contain a percent, a rupee amount, a dose, a spray interval, or a chemical name. Rates and amounts are read from the linked catalog record at answer time, never copied into `next_step`.

## Files

```
backend/data/question_bank/{agent}.{lang}.jsonl
backend/scripts/generate_question_bank.py
backend/app/orchestrator/question_bank.py
```

`question_bank.py` loads the index once, looks up neighbors, and returns the next step. The generator writes the JSONL files. Agents and the router call the lookup. They do not read the files themselves.

A missing or unreadable bank file logs a warning. Routing then uses the phrase matcher only. One bad line is skipped. The generator test fails if a file is short, duplicated, or unsafe, so a bad line does not ship.

## How questions are produced

`generate_question_bank.py` fills a fixed grid and writes the files. The grid is the source of the 1,000 questions. Hand-written one-off questions are out of scope.

Shared slots:

- Crops, read from `backend/data/knowledge/crop_registry.json`: cotton, maize, onion, potato, rice, tomato, wheat.
- Places: Bengaluru, Mysuru, Belagavi, Hubballi, Mandya, Nashik, Pune, Nagpur, Lucknow, Ludhiana, Warangal, Guntur.

Each agent has its own intent list and 8 wording frames, rendered in English, Hindi, and Kannada. The generator crosses intent × crop × place × frame, drops duplicates after whitespace normalization, and keeps the first 1,050 unique questions per agent per language. The first 1,000 are `index`. The next 50 are `holdout`. The seed order is the grid order, so regeneration is stable.

Intent lists:

- `finance`: crop loan, Kisan Credit Card, gold loan, equipment loan, dairy loan, MUDRA, subsidy, crop insurance, documents, where to apply, repayment, collateral, tenant farmer, interest confirmation.
- `equipment`: tractor, power tiller, sprayer, harvester, drip irrigation, solar pump, rental versus buying, rotavator, thresher, seed drill.
- `crop_health`: leaf spots, blight, pest, yellowing, fungus, treatment steps, whether to spray, spreading on leaves, fruit damage, healthy leaf check.
- `market`: mandi price, sell now, hold, storage, distant market, demand, price forecast, transport to market.
- `weather`: rain this week, heavy rain, drought, temperature, humidity, irrigate or wait, planting window, flood risk.
- `soil`: soil test, nitrogen, phosphorus, potassium, pH, fertilizer timing, organic manure, suitability for the crop.
- `knowledge_retriever`: how to grow, sowing method, seed rate guidance, nursery, spacing, harvesting method, where to get seed, KVK visit.

Finance intents that match an existing loan id set `linked_record_id` to that id: crop loan and Kisan Credit Card → `kcc-crop-loan`, gold loan → `agri-gold-loan`, equipment loan → `farm-mechanization-loan`, dairy loan → `dairy-loan-nabard`, MUDRA → `mudra-agri`. Every other intent leaves `linked_record_id` null. The generator checks that any non-null id exists in `backend/data/knowledge/loans.json`.

Crop-health, market, weather, soil, and knowledge rows leave `linked_record_id` null. Those agents already retrieve crop documents. The bank next step tells the farmer what to do locally when those documents do not cover the question: photograph the leaf, visit the Krishi Vigyan Kendra, carry the soil-test report, or check the local mandi. The office name is Krishi Vigyan Kendra (KVK). The generator must not write "Kisan Vikas Kendra".

## Routing

`route_query` keeps scoring only the text after the last `Farmer question:` marker.

1. The phrase matcher selects agents as it does today, including the finance force-include and the agronomy force-include.
2. `question_bank.neighbors(question, language, k=5)` scores index rows in that language.
3. Tokens are Unicode words. Hindi and Kannada letters count. The Latin-only tokenizer in the phrase matcher is left unchanged.
4. Similarity is the overlap coefficient: shared tokens divided by the smaller token count. Empty questions score 0.
5. Retrieval adds an agent only when the best score is at least 0.55 and at least 3 of the top 5 neighbors share that agent.
6. A best score below 0.35 adds nobody.
7. If the phrase matcher and the bank name different agents, both stay selected.
8. An uploaded image still adds `crop_health`. A question with a finance intent marker still adds `finance`.

Language for the lookup is the detected language of the current question. A Kannada question searches the Kannada index only. It does not borrow an English next step.

## Answers

For the selected agent:

1. If that agent's tools return records, those records are the answer. A rate or amount appears only because it is in the record.
2. If the tools return nothing and the best neighbor for that agent scores at least 0.55, the answer uses that row's `next_step`. When `linked_record_id` is set and the record exists, the record's rate, limit, eligibility, and where-to-apply fields are appended at read time.
3. If the best neighbor scores below 0.55, the answer says what is unknown and points to the local Krishi Vigyan Kendra. It does not attach a weak next step.
4. The final rewrite is told that a listed record or next step is the answer. It must not say the information is missing in that case, and it must not invent an office name.

`finance` is the first agent wired this way, because an empty loan search is the failure farmers already see. The same lookup is then called from `equipment`, `crop_health`, `market`, `weather`, `soil`, and `knowledge_retriever` when their own retrieval is empty.

## Tests

- Each `{agent}.{lang}.jsonl` has 1,000 `index` rows and 50 `holdout` rows.
- Question text is unique within an agent and language.
- No `next_step` matches `%`, `₹`, `Rs`, or `INR`, and none match `UNSAFE_CHEMICAL_PATTERNS` in `backend/app/orchestrator/orchestrator.py`. The generator imports that tuple. It does not keep a second chemical list.
- Every non-null `linked_record_id` exists in `loans.json`.
- The Bengaluru tomato loan question, with an earlier leaf-disease note in memory, selects `finance` and returns the Kisan Credit Card record plus a next step that names Bengaluru and the documents.
- A held-out question is not in the loaded index. For each agent and language, at least 45 of the 50 holdout questions select their labeled agent.
- A Kannada question does not return an English `next_step`.
- A missing bank file leaves `route_query` on the phrase matcher and does not raise.

## Out of scope

- Replacing the phrase matcher.
- A paid or remote embedding API.
- Romanized Hindi and Kannada rows.
- New loan, scheme, or dose facts.
- Frontend changes.
- District-level scheme rules for Karnataka beyond the national records already in `loans.json` and `schemes.json`.
