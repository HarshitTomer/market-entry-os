# Submission checklist — code freeze 15:30 IST, 31 Oct 2026

- [ ] Clone the repo fresh on the demo laptop: `git clone https://github.com/HarshitTomer/market-entry-os`
- [ ] `pip install -r requirements.txt`
- [ ] `.env` with `CRUSTDATA_API_KEY` (local only — never in the repo, video, or screenshots)
- [ ] Live run with an unseen brief: `python -m marketentry.cli --brief "..." --out outputs/demo-mission`
- [ ] Check the trace shows genuine Company Search + Company Enrich calls (not sample/no_key mode)
- [ ] Open `outputs/demo-mission/Market_Entry_Report.html` and `marketentry.db` (CRM rows, unsent drafts)
- [ ] Record the 2-minute demo: brief → trace → ranked accounts → sizing formula →
      one evidence drill-down + one honest unknown → report/CSV → CRM
- [ ] Submit: repo link + 2-minute video, both by 15:30 IST
- [ ] Do NOT send any message to a real prospect, do NOT paste the API key anywhere
      except the local `.env` file, and do NOT claim the sample mode is a live run
