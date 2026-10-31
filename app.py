"""MarketEntryOS — clean search-first UI.

Design intent: a search box, not a dashboard. The user describes a
market to enter; the product does the consulting work and returns a
decision, ranked accounts, and a CRM-ready packet. Everything else
(filters, trace, files) lives one level down, not on the front page.

Run:  streamlit run app.py
Setup: cp .env.example .env and put your Crustdata key in .env (local only).
"""
import csv
import json
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

st.set_page_config(page_title="MarketEntryOS", layout="centered")

st.markdown("""
<style>
  #MainMenu, footer {visibility: hidden;}
  .block-container {max-width: 880px; padding-top: 2.5rem;}
  h1, h2, h3 {font-weight: 600; letter-spacing: -0.01em;}
  .muted {color: #6b7280; font-size: 0.9rem;}
  .pill {display: inline-block; padding: 2px 12px; border-radius: 999px;
         font-size: 0.85rem; font-weight: 600;}
  .pill-go {background: #dcfce7; color: #166534;}
  .pill-conditional {background: #fef3c7; color: #92400e;}
  .pill-nogo {background: #fee2e2; color: #991b1b;}
  .stTextArea textarea {border-radius: 24px; padding: 14px 18px; font-size: 1.05rem;}
</style>
""", unsafe_allow_html=True)

EXAMPLES = {
    "UK fintech compliance": (
        "We sell cybersecurity compliance software for financial technology companies. "
        "Evaluate entry into the UK fintech market. Focus on companies with 50-500 employees. "
        "Estimate using a £12,000 annual contract value; buyer roles Head of Compliance, CISO, VP Security."
    ),
    "German manufacturing SaaS": (
        "We sell production planning software for manufacturing companies. "
        "Evaluate entry into the German manufacturing market. Focus on companies with 100-1000 employees. "
        "Estimate using a €20,000 annual contract value; buyer roles CTO, Head of Operations."
    ),
    "Indian healthcare software": (
        "We sell clinic management software for healthcare companies. "
        "Evaluate entry into the Indian healthcare market. Focus on companies with 50-500 employees. "
        "Estimate using a ₹500,000 annual contract value; buyer roles CTO, Head of Operations."
    ),
}

if "brief_text" not in st.session_state:
    st.session_state["brief_text"] = ""
if "result" not in st.session_state:
    st.session_state["result"] = None


def _read_csv(path: Path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _verdict_pill(verdict: str) -> str:
    cls = {"GO": "pill-go", "CONDITIONAL": "pill-conditional"}.get(verdict, "pill-nogo")
    return f'<span class="pill {cls}">{verdict}</span>'


# ---------------------------------------------------------------- results
result = st.session_state.get("result")
if result:
    col_a, col_b = st.columns([4, 1])
    with col_a:
        st.markdown("**MarketEntryOS**")
    with col_b:
        if st.button("New search"):
            st.session_state["result"] = None
            st.session_state["brief_text"] = ""
            st.rerun()

    st.markdown('<p class="muted">1 &nbsp;Ask &nbsp;→&nbsp; 2 &nbsp;Research &nbsp;→&nbsp; '
                '<b>3 &nbsp;Decide</b> &nbsp;→&nbsp; 4 &nbsp;Act</p>', unsafe_allow_html=True)
    st.markdown(f"**{result['brief'].get('product_name', 'Market entry')}** — "
                f"{result['brief'].get('target_industry', '')} in "
                f"{result['brief'].get('target_country', '')}")

    d = result.get("decision") or {}
    if d:
        with st.container(border=True):
            st.markdown(f"## {_verdict_pill(d['verdict'])} &nbsp; {d['confidence']} confidence",
                        unsafe_allow_html=True)
            for r in d["reasons"]:
                st.write(r)
            st.markdown("**Start here**")
            for t in d["top5"]:
                st.write(f"{t['rank']}. {t['name']} — fit {t['fit_score']}")
            if d["risks"]:
                st.markdown("**What would change this**")
                for r in d["risks"]:
                    st.write("•", r)

    tab_overview, tab_accounts, tab_people, tab_files = st.tabs(
        ["Overview", "Accounts", "People & competitors", "Files & CRM"])

    with tab_overview:
        s = result["sizing"]
        st.markdown("### Market size")
        st.caption("Observed company count × client-supplied ACV. Illustrative, not a TAM forecast.")
        if s.get("observed_eligible_company_count"):
            scen = st.slider("Try a different annual contract value (no new API call)",
                             1000, 100000, int(s.get("annual_contract_value") or 12000), step=1000)
            st.write(f"{s['observed_eligible_company_count']:,} companies × "
                     f"{s['currency']} {scen:,} = "
                     f"{s['currency']} {s['observed_eligible_company_count'] * scen:,.0f}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Companies observed", s["observed_eligible_company_count"] or "unknown")
        c2.metric("Serviceable pool",
                  f"{s['currency']} {s['serviceable_annual_pool']:,.0f}"
                  if s["serviceable_annual_pool"] is not None else "—")
        c3.metric("Shortlist pipeline",
                  f"{s['currency']} {s['shortlist_pipeline_pool']:,.0f}"
                  if s["shortlist_pipeline_pool"] is not None else "—")
        if result["ranked"]:
            st.markdown("### Fit scores")
            st.bar_chart({r["name"]: r["fit_score"] for r in result["ranked"]})

    with tab_accounts:
        rows = [{"Rank": r["rank"], "Company": r["name"], "Domain": r["domain"],
                 "Fit": r["fit_score"], "Coverage": r["coverage"], "Wave": r["wave"],
                 "Signals": "; ".join(r.get("signals", []))} for r in result["ranked"]]
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.markdown("### Outreach drafts (unsent)")
        st.caption("Approve and edit before any use. Nothing here has been sent.")
        for r in result["ranked"][:5]:
            with st.expander(f"{r['rank']}. {r['name']} — {r['wave']}"):
                st.write("; ".join(r.get("signals", [])) or "No observed signals")
                st.code(r.get("draft", ""))

    with tab_people:
        out = Path(st.session_state["out"])
        buyers = _read_csv(out / "Buyer_Map.csv")
        st.markdown("### People")
        st.caption("Role-verified buyers are marked true. Others are senior contacts, not verified buyers.")
        if buyers:
            st.dataframe(buyers, use_container_width=True, hide_index=True)
        else:
            st.write("No people mapped for this mission.")
        comps = _read_csv(out / "Competitive_Landscape.csv")
        st.markdown("### Competitors")
        if comps:
            st.dataframe(comps, use_container_width=True, hide_index=True)
        else:
            st.write("No competitor records for this mission.")

    with tab_files:
        out = Path(st.session_state["out"])
        for name in result["artifacts"]:
            p = out / name
            if p.exists() and p.suffix in (".csv", ".json", ".html", ".pdf"):
                st.download_button(f"Download {name}", p.read_bytes(), file_name=name)
        with st.expander("How this was researched"):
            st.dataframe(result["trace"], use_container_width=True, hide_index=True)
            for w in result["warnings"]:
                st.write("•", w)
        db = out / "marketentry.db"
        if db.exists():
            conn = sqlite3.connect(str(db))
            st.markdown("### CRM — companies in this mission")
            st.dataframe(conn.execute(
                "SELECT crustdata_company_id, domain, fit_score, verification_status FROM companies").fetchall(),
                use_container_width=True, hide_index=True)
            st.markdown("### CRM — tasks (all unsent)")
            st.dataframe(conn.execute(
                "SELECT company_id, task_type, title, status FROM crm_tasks").fetchall(),
                use_container_width=True, hide_index=True)
            conn.close()

    st.markdown('<p class="muted">Research only. No prospect has been contacted. '
                'Outreach drafts are unsent and need human approval before any use.</p>',
                unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------------- landing
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("<h1 style='text-align:center; font-size: 2.6rem;'>MarketEntryOS</h1>",
            unsafe_allow_html=True)
st.markdown("<p class='muted' style='text-align:center;'>Describe a market to enter. "
            "Get a decision, ranked accounts, and a CRM-ready packet — with sources.</p>",
            unsafe_allow_html=True)

brief = st.text_area(
    "Search",
    value=st.session_state["brief_text"],
    placeholder="e.g. We sell cybersecurity compliance software for fintech companies in the UK, 50–500 employees, £12,000 ACV…",
    height=110,
    label_visibility="collapsed",
)

cols = st.columns(3)
for col, (label, text) in zip(cols, EXAMPLES.items()):
    with col:
        if st.button(label, use_container_width=True):
            st.session_state["brief_text"] = text
            st.rerun()

with st.expander("Refine — country, industry, size, price, buyers"):
    use_filters = st.checkbox("Use these filters instead of the text above", value=False)
    country = st.selectbox("Country", ["United Kingdom", "United States", "Germany", "India",
                                       "France", "Netherlands", "Singapore", "Australia"])
    industry = st.selectbox("Industry", ["Financial technology", "Software", "Manufacturing",
                                         "Healthcare", "Retail", "Logistics"])
    min_hc, max_hc = st.slider("Headcount range", 1, 10000, (50, 500))
    acv = st.number_input("Annual contract value", value=12000, step=1000)
    currency = st.selectbox("Currency", ["GBP", "USD", "EUR", "INR"])
    roles = st.multiselect("Buyer roles", ["Head of Compliance", "CISO", "VP Security",
                                           "CTO", "Head of Engineering", "VP Sales"],
                           default=["Head of Compliance", "CISO"])
    sample = st.checkbox("Sample mode (labelled smoke test, no API key)", value=False)
    has_key = bool(os.environ.get("CRUSTDATA_API_KEY"))
    st.markdown(f"<p class='muted'>Live data: {'on' if has_key else 'off — add CRUSTDATA_API_KEY to .env for a live run'}</p>",
                unsafe_allow_html=True)
if "sample" not in locals():
    sample = False

_, mid, _ = st.columns([1, 1, 1])
with mid:
    run = st.button("Run research", type="primary", use_container_width=True)

if run:
    if use_filters:
        brief = json.dumps({"product_name": "Product", "product_description": brief or "",
                            "target_country": country, "target_industry": industry,
                            "employee_min": int(min_hc), "employee_max": int(max_hc),
                            "annual_contract_value": float(acv), "currency": currency,
                            "target_buyer_roles": roles})
    brief = (brief or "").strip()
    if not brief:
        st.error("Describe what you're selling and where you want to sell it, then run again.")
        st.stop()
    with st.spinner("Researching: finding companies, enriching accounts, mapping people, checking evidence…"):
        result = run_mission(brief, "outputs/streamlit-mission",
                             api_key=os.environ.get("CRUSTDATA_API_KEY"), sample=sample)
    st.session_state["result"] = result
    st.session_state["out"] = "outputs/streamlit-mission"
    st.session_state["brief_text"] = brief
    st.rerun()
