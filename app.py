"""Streamlit UI: Request | Live Execution Trace | Market Intelligence |
Deliverables / CRM. This is the 2-minute demo surface.

Run:  streamlit run app.py
Setup: cp .env.example .env and put your Crustdata key in .env (local only).
"""
import os
import sqlite3
from pathlib import Path

import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from marketentry.mission import run_mission

st.set_page_config(page_title="MarketEntryOS", layout="wide")
st.title("MarketEntryOS — Autonomous Market-Entry Consulting")
st.caption("One brief in, one verified research + CRM packet out. No prospect is ever contacted — outreach stays as unsent local drafts.")

DEFAULT_BRIEF = (
    "We sell cybersecurity compliance software for financial technology companies. "
    "Evaluate entry into the UK fintech market. Focus on companies with 50-500 employees. "
    "Estimate the addressable company universe using a £12,000 annual contract value assumption; "
    "identify competitors and buyer roles; produce a ranked target-account shortlist."
)

with st.sidebar:
    st.header("Run a mission")
    brief = st.text_area("Client brief (unseen briefs work too)", DEFAULT_BRIEF, height=160)
    sample = st.checkbox("Sample mode (labelled smoke test, no API key)", value=False)
    has_key = bool(os.environ.get("CRUSTDATA_API_KEY"))
    st.write("Crustdata key set:", "yes" if has_key else "no — set CRUSTDATA_API_KEY in .env for a live run")
    run = st.button("Run mission", type="primary")

if run:
    with st.spinner("Running mission: discovery → enrich → rank → buyers → competitors → verify → CRM…"):
        result = run_mission(brief, "outputs/streamlit-mission",
                             api_key=os.environ.get("CRUSTDATA_API_KEY"), sample=sample)
    st.session_state["result"] = result
    st.session_state["out"] = "outputs/streamlit-mission"

result = st.session_state.get("result")
if not result:
    st.info("Paste a brief and press Run mission. The demo brief above is the spec §3 example; try an unseen sector/geography to prove it is not hard-coded.")
    st.stop()

tab1, tab2, tab3, tab4 = st.tabs(["Market Intelligence", "Live Execution Trace", "Deliverables", "CRM"])
with tab1:
    st.subheader("Bottom-up sizing (observed count × client-supplied ACV — never invented)")
    s = result["sizing"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Observed companies", s["observed_eligible_company_count"] or "unknown")
    c2.metric("Serviceable pool", f"{s['currency']} {s['serviceable_annual_pool']:,.0f}" if s["serviceable_annual_pool"] is not None else "omitted (no ACV)")
    c3.metric("Shortlist pipeline", f"{s['currency']} {s['shortlist_pipeline_pool']:,.0f}" if s["shortlist_pipeline_pool"] is not None else "omitted (no ACV)")
    st.json(s)
    st.subheader("Ranked target accounts")
    st.dataframe(result["ranked"], use_container_width=True)
    if result["ranked"]:
        st.bar_chart({r["name"]: r["fit_score"] for r in result["ranked"]})
with tab2:
    st.subheader("Actual tool calls (trace)")
    st.dataframe(result["trace"], use_container_width=True)
    st.subheader("Warnings / unknowns (honest gaps, not hidden)")
    for w in result["warnings"]:
        st.write("•", w)
with tab3:
    out = Path(st.session_state["out"])
    for name in result["artifacts"]:
        p = out / name
        if p.exists() and p.suffix in (".csv", ".json", ".html", ".pdf"):
            st.download_button(f"Download {name}", p.read_bytes(), file_name=name)
with tab4:
    db = Path(st.session_state["out"]) / "marketentry.db"
    if db.exists():
        conn = sqlite3.connect(str(db))
        st.subheader("CRM companies")
        st.dataframe(conn.execute(
            "SELECT crustdata_company_id, domain, fit_score, verification_status FROM companies").fetchall(),
            use_container_width=True)
        st.subheader("CRM tasks (all unsent_draft)")
        st.dataframe(conn.execute(
            "SELECT company_id, task_type, title, status FROM crm_tasks").fetchall(),
            use_container_width=True)
        conn.close()
