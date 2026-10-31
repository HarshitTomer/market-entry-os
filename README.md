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

## Insights, not just a list (v1.17, 31 Oct 2026)

Founders do not need another table — they need to know why this
market, why now, and what to do first. Every result now opens with
insight cards, computed from observed fields only, before any
account list: why the market is worth a look (pool size, not a
forecast), why now (funding / growth / hiring signals actually
observed — or an honest "no signal found"), why these accounts
first, what is actually in the way (usually: no role-verified
buyer), what you are up against, and what to do first in order.
The same insights are in the HTML report (right after the decision)
and in the PDF, and in mission_result.json for the API. No trend,
figure or buyer is invented to make the story sound better.

## More professional chrome + loading states (v1.16, 31 Oct 2026)

- **Chrome:** every view now has a top bar — MarketEntryOS wordmark
  left, live/sample status and "Research only — no prospect
  contacted" right, separated by one muted line. That one line is
  what makes it read like a product instead of a demo script.
- **Loading states:** the loading view now shows a large percentage
  (not just a bar), a shimmer skeleton preview of the answer's
  shape, and a "coming up" line (verdict · top 5 · market size ·
  report), plus a plain explanation that nothing is shown until it
  is complete, so you never see half-finished numbers.

## Loading that actually shows + a report that looks like a deliverable (v1.15, 31 Oct 2026)

- **Loading, fixed properly:** the old progress card sat *below* the
  search box and examples, so during a run you saw the landing page
  with a small card at the bottom and thought it was stuck. Now
  pressing Run (or Run again) first switches the whole main area to
  a dedicated loading view — centred "Researching your market",
  the 90-second expectation, the bar, the step row, elapsed seconds
  — and nothing else competes with it until the result arrives.
- **Report, rebuilt:** the old HTML report was plain white with an
  unstyled table. It is now dark and professional, matching the app:
  slate surfaces, verdict pill card, sizing card, fit-score bars in
  the accounts table, a "why now" column, and — previously missing —
  full People and Competitors tables instead of just counts. The PDF
  gets an indigo header row and alternating rows instead of flat grey.

## Better loading (v1.14, 31 Oct 2026)

The old progress bar stalled during the long loops — it only moved
at stage boundaries, so a 2-second-spaced check looked frozen. Now
it moves at every item: every company checked, every competitor
compared, every account's people found. The card also shows elapsed
seconds, says up front that a live run usually takes about 90
seconds (so a pause reads as work, not a freeze), and has three
pulsing dots so you can see at a glance that it is still alive.
Still no tool/API/log names — only plain stage labels.

## Dark UI, fixed alignment and borders (v1.13, 31 Oct 2026)

The all-white theme was blinding, so the whole UI is now dark by
default: slate-900 background, slate-800 surfaces, soft off-white
text, muted slate borders — no pure white anywhere, verified by a
test. One indigo accent (softened for dark) for primary buttons,
progress and links. Alignment and borders were cleaned up at the
same time: sidebar buttons are a consistent 42px with a visible
hover border, the main column is centred at 760px, metric cards
share one border/radius/padding, verdict/progress/delete cards
share one muted border, the search box has a dark surface with a
soft shadow and an indigo focus ring, and Details sections have a
single muted border instead of stacked default lines.

## Colour, ⋮ menus, and the "folder is gone" fix (v1.12, 31 Oct 2026)

- **Colour:** a real Streamlit theme (`.streamlit/config.toml`) —
  one indigo accent for primary buttons, progress bar and links,
  neutral grey everywhere else, instead of Streamlit's default red
  clashing with the verdict pills. Progress bar and step colours
  match the theme.
- **Delete via ⋮:** each Recent chat now has a "⋮" button beside it,
  like ChatGPT. Tap it and that chat alone shows Delete / Close.
  The old "Manage past searches" expander is gone. Delete still
  asks once, then deletes files + history entry.
- **"Output folder is gone" — root cause fixed:** every Streamlit
  mission used to share one folder, `outputs/streamlit-mission`, so
  each new run overwrote the last mission's result, and deleting one
  mission deleted the folder *every* history entry pointed at. Now
  each mission gets its own folder
  (`outputs/streamlit-mission/mission_<id>/`), history is unified at
  `outputs/history.json` for CLI and UI alike, opening a past search
  checks the folder's mission_id actually matches, and a stale entry
  (from the old shared-folder era, or a folder deleted outside the
  app) is removed from the list with a plain explanation instead of
  leaving a permanently dead button.

## Visual progress, no background logic (v1.11, 31 Oct 2026)

The old spinner ("Researching…") told you nothing for 90 seconds.
Now a bordered card shows, live: a dark progress bar, the current
stage in plain words, and a step row that fills in as it goes —
Understanding your market → Finding companies → Checking companies
→ Comparing competitors → Finding the right people → Ranking and
sizing → Building your report → Done. No tool names, no API names,
no logs, no "enriching" or "scoring" — the mission calls a progress
callback at each stage, and a test asserts no banned background
word can leak into a frontend label. Same card for Run and Run
again.

## UI bug fixes + functionality (v1.10, 31 Oct 2026)

- **Bugs fixed:** reopening an old guided-builder mission no longer
  shows raw JSON as your message — it shows a plain summary
  ("product · industry in country"); user messages are now HTML-
  escaped; a corrupt history file no longer crashes the open;
  sidebar buttons wrap instead of overflowing, at a fixed 290px
  sidebar width; the sample-mode toggle no longer fights Streamlit
  session state (it now has its own widget key).
- **Functionality:** "↻ Run again" re-runs the same brief with fresh
  live data; "Download all as ZIP" gives every file in one click;
  a copyable text summary (verdict, pool, top 5) sits in Details
  for pasting into a deck or message; sidebar recent searches are
  now filterable by product or country.

## Interface, polished + delete (v1.9, 31 Oct 2026)

- **Look:** tighter typography and spacing, a light-grey sidebar
  with left-aligned recent chats, pill buttons, a rounded search box
  with a soft shadow, verdict and metric cards with borders, and
  Streamlit's own toolbar/menu hidden — so it reads like a product,
  not a default Streamlit demo.
- **User-friendly touches:** a visible "↩ New search" button on
  results (not only in the sidebar), three one-tap example searches
  on the landing page, and a single primary action (Download report).
- **Delete research, for real:** "🗑 Delete this research" on a
  result, or "Manage past searches" in the sidebar, asks once —
  "Delete permanently?" — and on confirmation deletes the mission's
  report, CSVs, CRM database *and* its history entry. A safety guard
  only allows deleting a folder under `outputs/` that contains that
  mission's `mission_result.json`, so a wrong path can never wipe
  an unrelated directory. The old "Remove" only removed the list
  entry; delete is now the real thing.

## Interface, refined (v1.8, 31 Oct 2026)

Chat-style, not form-style. One search box, nothing else to fill
in — the parser infers country, industry, size, ACV and buyer roles
from plain words, so a founder is never asked six questions before
they can start. The sidebar holds New search + recent conversations,
like ChatGPT. The answer is refined: your brief as a message, a
verdict in one sentence, three numbers, the top 5 accounts, and one
button to download the report. Charts, tables, drafts, evidence and
files are still there, but under one collapsed "Details" section —
advanced controls (filters, sliders, checklists, simulators) were
removed from the main view, not from the engine. The CLI and API
still expose everything.

## History (v1.7, 31 Oct 2026)

Every mission — CLI, API, or UI — is recorded in
`outputs/history.json` (local only, gitignored, never committed):
mission, date, mode, product, country, industry, verdict, account /
buyer / competitor counts, and serviceable pool. The front page has a
"Past searches" expander and results have a History tab: search past
queries by text, reopen any mission from its saved result (no new API
calls, no new credits), or remove it from the list (files are left
alone). If a mission's output folder was deleted, reopening says so
plainly instead of showing stale data.

## Interactive results (v1.6, 31 Oct 2026)

The front page stays a clean search box. After a run, the results are
interactive, not just readable — and the user always knows the next
action:

- **What to do next** checklist at the top (review top 5, approve
  Wave 1 drafts, check one claim, download the packet) with a progress
  bar. Plus a **Path to GO** simulator, clearly labelled as a
  simulation: tick "buyers verified" / "coverage above 0.5" to see how
  the verdict would move — ticking a box re-verifies nothing.
- **Charts:** fit scores, fit vs coverage scatter (top-right is best),
  shortlist by wave, pool vs shortlist pipeline, competitor
  classification counts.
- **Account inspector:** filter by minimum fit and wave, pick one
  account, see its score breakdown as a chart, its signals and
  unknowns, edit its outreach draft, and approve it in-session.
  Approval only marks it ready — nothing is sent.
- **Full report readable in the app** (Files & CRM tab), alongside
  downloads, the research trace, and the CRM tables.

## Interface (v1.5, 31 Oct 2026)

Search-first, not dashboard-first. The front page is one large text
box — describe a market to enter — with three example searches
underneath and filters hidden in a "Refine" expander, not a sidebar.
No tagline header, no banners. After a run, the workflow is explicit:
Ask → Research → Decide → Act. The decision card comes first, then
Overview (sizing + ACV scenario), Accounts (with unsent drafts),
People & competitors, and Files & CRM (downloads, trace, warnings).
The audit trail is still there, one level down, not on the front page.

## Audit fixes (v1.4, 31 Oct 2026)

Found by re-reading the live results, not by reading docs:

- **Industry "PRIVATE" bug, fixed:** live enrich records carry
  `basic_info.markets=["PRIVATE"]` (ownership), which overwrote the good
  search taxonomy ("Software Development"). Markets are no longer used
  as an industry, and generic labels are stripped; enrich can no longer
  downgrade a search industry.
- **Buyer roles are now keyword-verified:** "Compliance Manager"
  matches "Head of Compliance", "VP Marketing" does not match
  "VP Security". People with unverified roles are kept as contacts in
  Buyer_Map (`role_verified=false`) but earn no buyer score points and
  are not counted as verified buyers. Buyer enrich is rejected if it
  swaps the person to a different company.
- **Competitor enrich is throttled** (1s spacing, like company enrich)
  after a v1.3 competitor enrich hit a 429.
- **Score breakdown** is now in Target_Accounts.csv (`icp/growth/hiring/
  fit/buyer`) so a fit score can be checked, not just trusted.
- **Launch checklist** (spec Step H) and evidence references per account
  are in the report and CSV; Buyer_Map flags role-unverified contacts.
- **Person normalizer fixed to live response fields:** current jobs
  carry `company_website` and `crustdata_company_id`, not the filter
  field names — domains and company IDs in Buyer_Map were wrong
  before this fix. Enrich no longer overwrites a precise search
  headcount with a range midpoint, and post-enrich headcount filtering
  drops companies actually outside the target range.
- **Honest buyer outcome on the live spec brief:** no top-5 account
  has a compliance/security buyer in Crustdata, so the packet maps
  8 senior contacts (CEO/CFO/heads) labelled adjacent, not compliance
  buyers, scores them 0 buyer points, and the decision is CONDITIONAL
  — not a fabricated GO. Enrich throttling at 2s removed the 429s
  entirely in the final live run (10 accounts, 8 contacts,
  12 competitors, 195 × £12,000 = £2,340,000, zero trace errors).

## Usability (v1.3, 31 Oct 2026)

Built for the question a buyer actually asks — "should we enter, who first,
what do I say?" — not just for a report:

- **Decision card** at the top of every report and the UI: GO / CONDITIONAL /
  NO-GO with a stated rule, the top 5 accounts, and the risks that would
  change the verdict. Caveats (e.g. semantic industry matching) are listed
  but do not block a GO; blockers are too few accounts, no buyers, low
  coverage, or no ACV.
- **Guided brief builder** in the Streamlit sidebar (country / industry /
  headcount / ACV / buyer roles) that emits a structured JSON brief, so an
  unseen brief does not depend on free-text parsing. Free text is still
  available.
- **ACV scenario slider** in Market Intelligence: recomputes sizing from the
  cached observed count — no new API call, no new credits.
- **Why-now signals** per account (ICP match, growth, funding, hiring, buyer
  mapped) in the CSV, report and UI, plus an **account-specific unsent
  outreach draft** per account, built only from that account's observed
  signals and the client's brief. Nothing is ever sent.

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
