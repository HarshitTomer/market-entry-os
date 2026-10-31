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

from marketentry.history import load_history
from marketentry.mission import run_mission

st.set_page_config(page_title="MarketEntryOS", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
  #MainMenu, footer {visibility: hidden;}
  [data-testid="stSidebar"] {background: #f7f7f8;}
  .block-container {max-width: 780px; padding-top: 2rem;}
  .muted {color: #6b7280; font-size: 0.9rem;}
  .pill {display: inline-block; padding: 2px 12px; border-radius: 999px;
         font-size: 0.85rem; font-weight: 600;}
  .pill-go {background: #dcfce7; color: #166534;}
  .pill-conditional {background: #fef3c7; color: #92400e;}
  .pill-nogo {background: #fee2e2; color: #991b1b;}
  .user-msg {background: #f1f1f1; border-radius: 18px; padding: 12px 18px; margin: 1rem 0;}
  .stTextArea textarea {border-radius: 24px; padding: 14px 18px; font-size: 1.05rem;}
</style>
""", unsafe_allow_html=True)

if "brief_text" not in st.session_state:
    st.session_state["brief_text"] = ""
if "result" not in st.session_state:
    st.session_state["result"] = None
if "sample" not in st.session_state:
    st.session_state["sample"] = False


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
    st.markdown("---")
    st.session_state["sample"] = st.checkbox(
        "Sample mode", value=st.session_state["sample"],
        help="Labelled smoke test, no API key. Off for a live run.")
    has_key = bool(os.environ.get("CRUSTDATA_API_KEY"))
    st.markdown(f"<p class='muted'>Live data: {'on' if has_key else 'off — add CRUSTDATA_API_KEY to .env'}</p>",
                unsafe_allow_html=True)

# ---------------------------------------------------------------- results
result = st.session_state.get("result")
if result:
    brief_text = st.session_state.get("brief_text", "")
    if brief_text:
        st.markdown(f'<div class="user-msg">{brief_text}</div>', unsafe_allow_html=True)
    d = result.get("decision") or {}
    s = result["sizing"]
    if d:
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
