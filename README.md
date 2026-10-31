# MarketEntryOS

**The autonomous market-entry consulting firm — ContextCon 03, IIT Bombay.**

Give it a product, a target geography, and a customer profile. It autonomously
researches the market with Crustdata, sizes the addressable account universe
bottom-up, identifies competitors and verified buyers, prioritises target
companies deterministically, and delivers a verified report plus a populated
local CRM — with **no prompts in the middle and no contact to real prospects**.

## What you get from one run

1. `Market_Entry_Report.pdf` **and** `Market_Entry_Report.html` — executive
   recommendation, sizing with the formula shown, ranked accounts, assumptions
   and risks. PDF is generated with reportlab when installed; HTML is always
   written as a fallback.
2. `Target_Accounts.csv` — de-duplicated accounts with Crustdata company ID,
   domain, country, industry, size, fit score, coverage, wave and verification
   status.
3. `Buyer_Map.csv` — verified people only, with employer linkage. **No email
   addresses, ever** — they are not fabricated.
4. `Competitive_Landscape.csv` — competitors classified as confirmed /
   possible / insufficient evidence, never stronger than the evidence.
5. `Evidence_Log.json` — every claim's source, field path, timestamp and
   verification status. Missing data is `unknown`, not invented.
6. `marketentry.db` — a real local SQLite CRM: companies, contacts, evidence,
   tool runs, and **unsent** outreach drafts (`status = unsent_draft`).

## Live-validated against the real Crustdata API (v1.2, 31 Oct 2026)

The public docs and the live API differ, and v1.2 is fixed for the live
one — this was found by a real run, not by reading docs:

- Headcount ranges use `=>` / `=<`, not `between` (rejected live).
- `taxonomy.industry` is not a filter column. Industry is matched by
  semantic search (`{"search": {"query": "<industry> companies"}}`) plus a
  description-keyword search for sizing. Semantic search returns
  `total_count: null`, so sizing uses the keyword count (e.g. UK fintech
  50–500: 195 companies × £12,000 = £2,340,000 serviceable pool).
- Company enrich is plural (`{"crustdata_company_ids": [...]}`) and
  returns a list of matches. Enrich by ID, not domain — the same domain
  matched a different company record live.
- Person search fields are
  `experience.employment_details.current.company_website_domain` /
  `.title`, and `current` is a list. Domain matching is loose, so the
  current employer is verified locally.
- Enrich is burst rate-limited live: calls are spaced 1s apart and
  retried with backoff, or the first 10 enrichments 429.

Live run (spec brief, 10 accounts): 10 accounts, 8 buyers, 12 competitors,
all enrichments succeeding after the fix, sizing as above.

## Also included (v1.1)

- FastAPI surface (`marketentry/api.py`, `uvicorn marketentry.api:app`):
  `POST /missions`, `GET /missions/{id}/accounts`, `/evidence`, `/artifacts/{name}`.
- Competitor enrichment: a competitor is only upgraded to "confirmed" when an
  enrich call observes an industry match; otherwise it stays "possible".
- Buyer enrich where the search record supports it; otherwise the search
  record stands, marked as-is.
- `docs/demo_briefs.md` — 3 unseen briefs + 1 edge case judges can paste in,
  with what to check for each. `docs/submission_checklist.md` — freeze checklist.
- Tests: 9 passing (`pytest tests/ -q`), including mocked real Crustdata
  response shapes (Ramp/Brex docs example), empty results, 429-retry, and
  401-as-error-not-fake-data.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env   # put your Crustdata key in .env — local only, never commit it
python -m marketentry.cli --brief "We sell cybersecurity compliance software for financial technology companies. Evaluate entry into the UK fintech market. Focus on companies with 50-500 employees. Estimate using a £12,000 annual contract value; identify competitors and buyer roles; produce a ranked shortlist."
```

Or the UI (the 2-minute demo surface):

```bash
streamlit run app.py
```

Smoke test without a key (labelled sample data, never presented as live):

```bash
python -m marketentry.cli --brief "We sell software for fintech companies in the UK. Focus on companies with 50-500 employees." --sample
python -m pytest tests/ -q
```

## Crustdata setup — read this before the demo

- Get your key from the Crustdata dashboard you were given at check-in
  ($1,500 in credits per builder at ContextCon check-in).
- Put it in a local `.env` file as `CRUSTDATA_API_KEY=...`, or export it.
- **Never paste a key in chat, in a screenshot, in a demo video, or in this
  repo.** `.env` is gitignored. The code validates that a key is present
  without ever printing it, and the evidence log never contains it.
- Without a key, the mission still completes honestly with warnings and
  **no live data** — it does not fake a Crustdata response. For judging,
  run with a key so the trace shows genuine Company Search / Enrich calls.

## How it works

```
Brief parser -> Company Search (Crustdata) -> Company Enrich (top 10)
  -> Competitor search + Web Search -> Person Search (top 5 accounts)
  -> Deterministic scoring (100 pts: ICP 35, growth 20, hiring 15,
     product-need fit 15, buyer availability 15; coverage shown separately)
  -> Evidence verifier -> SQLite CRM + CSV/JSON/HTML exports
```

- **Sizing is bottom-up only:** observed Crustdata indexed count ×
  *client-supplied* ACV. If ACV is missing, money is omitted, not invented.
  The observed count is coverage-limited — it is not every business in the
  market, and the report says so.
- **Scoring is deterministic Python, not LLM prose.** The report's prose is
  templated from computed numbers, so a fact in the report always traces to
  an evidence record.
- **Filters the API ignores are post-filtered locally** (country, headcount)
  and the removal is logged as a warning.
- **Retries** are bounded with backoff on 429/5xx only. A failed tool step
  becomes a warning + partial results, never a fabricated replacement.
- **Idempotent CRM:** re-running a mission never duplicates an account or
  contact (unique on mission + canonical ID).

## Crustdata endpoints used

Base `https://api.crustdata.com`, headers `Authorization: Bearer <key>` and
`x-api-version: 2025-11-01` (spec §6). Company Search uses the documented
`{filters: {op: "and", conditions: [...]}, limit}` shape
(`taxonomy.industry`, `headcount.total`, `locations.country`); if the
primary endpoint is unavailable, a screener-style fallback is attempted
once and logged. Person Search is company-scoped and title post-filtered.

## Judging map (ContextCon criteria)

| Criterion | Where to see it |
|---|---|
| End-to-end, no human intervention | One CLI/UI run → all 6 deliverables |
| Data integrity / verification | `Evidence_Log.json`, trace tab, coverage column |
| Robustness / edge cases | Missing ACV, no buyers, failed enrich → warnings, not crashes |
| Demo clarity | UI tabs: Intelligence → Trace → Deliverables → CRM |

## Honest limitations

- Crustdata is intelligence infrastructure, not a complete business registry;
  counts under-cover the market.
- Headcount / hiring / funding are indicators, not proof of purchase intent.
- Buyer data can be stale or incomplete; an unmatched buyer stays unmatched.
- Sizing is an illustrative pool, not validated TAM or forecast revenue.
- This replaces a research-and-operations engagement, not legal registration,
  advertising, negotiation or closing.

## Demo storyboard (2 minutes)

0:00 unseen brief → Run. 0:15 genuine Crustdata calls + universe count.
0:35 ranked accounts + buyers. 0:55 sizing formula + competitors.
1:15 drill into one evidence record + one honest unknown. 1:40 report/CSV +
CRM with staged tasks and unsent drafts.
