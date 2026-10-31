"""MarketEntryOS — chat-style UI, like ChatGPT.

One question, one answer. No form with six fields, no tabs full of
controls, no checklist of checkboxes before you can start.

- Left sidebar: New search + recent conversations (history).
- Main area: one search box. Type a market to enter, in plain words.
- The answer is refined, not complex: a verdict in one sentence,
  three numbers, the top accounts, and one next step. Everything
  else — charts, tables, drafts, evidence, files — lives under
  "Details", collapsed by default.

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

from marketentry.history import delete_mission, load_history
from marketentry.mission import run_mission

st.set_page_config(page_title="MarketEntryOS", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
  #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {visibility: hidden; height: 0;}
  [data-testid="stSidebar"] {background: #f9fafb; border-right: 1px solid #e5e7eb;}
  [data-testid="stSidebar"] .stButton button {
    text-align: left; background: transparent; border: none; color: #374151;
    padding: 8px 12px; border-radius: 10px; font-size: 0.92rem; box-shadow: none;}
  [data-testid="stSidebar"] .stButton button:hover {background: #eceef1; color: #111827;}
  .block-container {max-width: 760px; padding-top: 1.5rem; padding-bottom: 3rem;}
  h1, h2, h3 {font-weight: 650; letter-spacing: -0.02em; color: #111827;}
  .muted {color: #6b7280; font-size: 0.9rem;}
  .pill {display: inline-block; padding: 3px 14px; border-radius: 999px;
         font-size: 0.85rem; font-weight: 650;}
  .pill-go {background: #dcfce7; color: #166534;}
  .pill-conditional {background: #fef3c7; color: #92400e;}
  .pill-nogo {background: #fee2e2; color: #991b1b;}
  .user-msg {background: #f3f4f6; border-radius: 18px; padding: 12px 18px; margin: 1rem 0; line-height: 1.5;}
  .stTextArea textarea {border-radius: 20px; padding: 14px 18px; font-size: 1.05rem;
    border: 1px solid #d1d5db; box-shadow: 0 1px 6px rgba(0,0,0,0.06);}
  .stTextArea textarea:focus {border-color: #111827; box-shadow: 0 1px 8px rgba(0,0,0,0.10);}
  .stButton button {border-radius: 999px;}
  [data-testid="stMetric"] {background: #ffffff; border: 1px solid #e5e7eb;
    border-radius: 16px; padding: 14px 16px;}
</style>
""", unsafe_allow_html=True)

if "brief_text" not in st.session_state:
    st.session_state["brief_text"] = ""
if "result" not in st.session_state:
    st.session_state["result"] = None
if "sample" not in st.session_state:
    st.session_state["sample"] = False
if "confirm_delete" not in st.session_state:
    st.session_state["confirm_delete"] = None
if "deleted_notice" not in st.session_state:
    st.session_state["deleted_notice"] = ""


def _verdict_pill(verdict: str) -> str:
    cls = {"GO": "pill-go", "CONDITIONAL": "pill-conditional"}.get(verdict, "pill-nogo")
    return f'<span class="pill {cls}">{verdict}</span>'


def _read_csv(path: Path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _open_history_entry(entry: dict) -> bool:
    result_path = Path(entry["out_dir"]) / "mission_result.json"
    if not result_path.exists():
        return False
    st.session_state["result"] = json.loads(result_path.read_text(encoding="utf-8"))
    st.session_state["out"] = entry["out_dir"]
    st.session_state["brief_text"] = entry.get("brief_text", "")
    return True


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    if st.button("＋  New search", use_container_width=True):
        st.session_state["result"] = None
        st.session_state["brief_text"] = ""
        st.rerun()
    st.markdown("**Recent**")
    entries = load_history("outputs/streamlit-mission")
    if not entries:
        st.markdown('<p class="muted">No past searches yet.</p>', unsafe_allow_html=True)
    for e in entries[:20]:
        label = f"{e.get('product_name') or 'Market entry'} · {e.get('target_country', '')}"
        if st.button(label, key=f"hist_{e['mission_id']}", use_container_width=True):
            if _open_history_entry(e):
                st.rerun()
            else:
                st.error("That mission's output folder is gone.")
    with st.expander("Manage past searches"):
        st.markdown('<p class="muted">Delete permanently removes its report, files, CRM and history entry.</p>',
                    unsafe_allow_html=True)
        for e in entries[:20]:
            if st.button(f"🗑  {e.get('product_name') or 'Market entry'}",
                         key=f"del_{e['mission_id']}", use_container_width=True):
                st.session_state["confirm_delete"] = e["mission_id"]
                st.session_state["confirm_delete_out"] = e["out_dir"]
                st.rerun()
    st.markdown("---")
    st.session_state["sample"] = st.checkbox(
        "Sample mode", value=st.session_state["sample"],
        help="Labelled smoke test, no API key. Off for a live run.")
    has_key = bool(os.environ.get("CRUSTDATA_API_KEY"))
    st.markdown(f"<p class='muted'>Live data: {'on' if has_key else 'off — add CRUSTDATA_API_KEY to .env'}</p>",
                unsafe_allow_html=True)

# ---------------------------------------------------------------- delete confirm
if st.session_state.get("confirm_delete"):
    _del_id = st.session_state["confirm_delete"]
    _del_out = st.session_state.get("confirm_delete_out", "outputs/streamlit-mission")
    with st.container(border=True):
        st.markdown("**Delete this research permanently?**")
        st.write("This removes its report, CSVs, CRM database and history entry. "
                 "It cannot be undone, and it does not send anything to anyone.")
        _c1, _c2 = st.columns(2)
        with _c1:
            if st.button("Yes, delete permanently", type="primary", use_container_width=True):
                if delete_mission(_del_out, _del_id):
                    st.session_state["deleted_notice"] = "Research deleted."
                    if st.session_state.get("result", {}).get("mission_id") == _del_id:
                        st.session_state["result"] = None
                        st.session_state["brief_text"] = ""
                else:
                    st.session_state["deleted_notice"] = "Could not delete that research — its folder was not found."
                st.session_state["confirm_delete"] = None
                st.rerun()
        with _c2:
            if st.button("Keep it", use_container_width=True):
                st.session_state["confirm_delete"] = None
                st.rerun()

if st.session_state.get("deleted_notice"):
    st.success(st.session_state["deleted_notice"])
    st.session_state["deleted_notice"] = ""

# ---------------------------------------------------------------- results
result = st.session_state.get("result")
if result:
    brief_text = st.session_state.get("brief_text", "")
    if brief_text:
        st.markdown(f'<div class="user-msg">{brief_text}</div>', unsafe_allow_html=True)
    _top1, _top2 = st.columns([1, 1])
    with _top1:
        if st.button("↩  New search", use_container_width=True):
            st.session_state["result"] = None
            st.session_state["brief_text"] = ""
            st.rerun()
    with _top2:
        if st.button("🗑  Delete this research", use_container_width=True):
            st.session_state["confirm_delete"] = result["mission_id"]
            st.session_state["confirm_delete_out"] = st.session_state["out"]
            st.rerun()
    d = result.get("decision") or {}
    s = result["sizing"]
    if d:
        with st.container(border=True):
            st.markdown(f"## {_verdict_pill(d['verdict'])}", unsafe_allow_html=True)
            # One sentence, not a card full of rules and risks.
            if d["verdict"] == "GO":
                st.write(f"Yes — enter this market. {len(result['ranked'])} accounts found, "
                         f"starting with {d['top5'][0]['name'] if d['top5'] else 'the top-ranked account'}.")
            elif d["verdict"] == "CONDITIONAL":
                st.write(f"Enter, but carefully — {len(result['ranked'])} accounts found, "
                         f"and the main gap is: {d['risks'][0] if d['risks'] else 'see Details'}.")
            else:
                st.write("Not yet — the evidence doesn't support entering on this brief as written.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Accounts", len(result["ranked"]))
    c2.metric("Market pool",
              f"{s['currency']} {s['serviceable_annual_pool']:,.0f}"
              if s["serviceable_annual_pool"] is not None else "—")
    c3.metric("People mapped", result["buyer_records"])

    st.markdown("### Start with these")
    for t in (d.get("top5") or [])[:5]:
        st.write(f"{t['rank']}. **{t['name']}** — fit {t['fit_score']}")
    if not d.get("top5"):
        for r in result["ranked"][:5]:
            st.write(f"{r['rank']}. **{r['name']}** — fit {r['fit_score']}")

    out = Path(st.session_state["out"])
    pdf = out / "Market_Entry_Report.pdf"
    if pdf.exists():
        st.download_button("Download the report", pdf.read_bytes(),
                           file_name="Market_Entry_Report.pdf", type="primary")

    with st.expander("Details — accounts, charts, drafts, evidence, files"):
        if result["ranked"]:
            st.markdown("**Fit scores**")
            st.bar_chart({r["name"]: r["fit_score"] for r in result["ranked"]})
        rows = [{"Rank": r["rank"], "Company": r["name"], "Domain": r["domain"],
                 "Fit": r["fit_score"], "Coverage": r["coverage"], "Wave": r["wave"],
                 "Signals": "; ".join(r.get("signals", []))} for r in result["ranked"]]
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.markdown("**Outreach drafts (unsent — approve before any use)**")
        for r in result["ranked"][:5]:
            with st.expander(f"{r['rank']}. {r['name']} — {r['wave']}"):
                st.write("; ".join(r.get("signals", [])) or "No observed signals")
                st.code(r.get("draft", ""))
        buyers = _read_csv(out / "Buyer_Map.csv")
        if buyers:
            st.markdown("**People**")
            st.dataframe(buyers, use_container_width=True, hide_index=True)
        comps = _read_csv(out / "Competitive_Landscape.csv")
        if comps:
            st.markdown("**Competitors**")
            st.dataframe(comps, use_container_width=True, hide_index=True)
        st.markdown("**Files**")
        for name in result["artifacts"]:
            p = out / name
            if p.exists() and p.suffix in (".csv", ".json", ".html", ".pdf"):
                st.download_button(f"Download {name}", p.read_bytes(), file_name=name)
        st.markdown("**Warnings**")
        for w in result["warnings"]:
            st.write("•", w)
        st.markdown('<p class="muted">Research only. No prospect has been contacted.</p>',
                    unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------------- landing
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("<h1 style='text-align:center; font-size: 2.6rem;'>MarketEntryOS</h1>",
            unsafe_allow_html=True)
st.markdown("<p class='muted' style='text-align:center;'>Describe a market to enter.</p>",
            unsafe_allow_html=True)

brief = st.text_area(
    "Search",
    value=st.session_state["brief_text"],
    placeholder="e.g. We sell cybersecurity compliance software for fintech companies in the UK, 50–500 employees, £12,000 ACV…",
    height=110,
    label_visibility="collapsed",
)
st.markdown('<p class="muted" style="text-align:center;">Try one:</p>', unsafe_allow_html=True)
_examples = {
    "UK fintech": "We sell cybersecurity compliance software for financial technology companies. Evaluate entry into the UK fintech market. Focus on companies with 50-500 employees. Estimate using a £12,000 annual contract value; buyer roles Head of Compliance, CISO, VP Security.",
    "Netherlands retail": "We sell inventory management software for retail companies. Evaluate entry into the Netherlands retail market. Focus on companies with 50-500 employees. Estimate using a €15,000 annual contract value; buyer roles CTO, Head of Operations.",
    "German manufacturing": "We sell production planning software for manufacturing companies. Evaluate entry into the German manufacturing market. Focus on companies with 100-1000 employees. Estimate using a €20,000 annual contract value; buyer roles CTO, Head of Operations.",
}
_ecols = st.columns(3)
for _col, (_label, _text) in zip(_ecols, _examples.items()):
    with _col:
        if st.button(_label, use_container_width=True):
            st.session_state["brief_text"] = _text
            st.rerun()
_, mid, _ = st.columns([1, 1, 1])
with mid:
    run = st.button("Run research", type="primary", use_container_width=True)

if run:
    brief = (brief or "").strip()
    if not brief:
        st.error("Describe what you're selling and where you want to sell it, then run again.")
        st.stop()
    with st.spinner("Researching…"):
        result = run_mission(brief, "outputs/streamlit-mission",
                             api_key=os.environ.get("CRUSTDATA_API_KEY"),
                             sample=st.session_state["sample"])
    st.session_state["result"] = result
    st.session_state["out"] = "outputs/streamlit-mission"
    st.session_state["brief_text"] = brief
    st.rerun()
