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
import html
import io
import json
import os
import sqlite3
import zipfile
from pathlib import Path

import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from marketentry.history import delete_mission, load_history, remove_entry
from marketentry.mission import run_mission

st.set_page_config(page_title="MarketEntryOS", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
  /* Dark, low-glare base. No pure white anywhere: surfaces are slate,
     text is soft off-white, borders are one muted line. */
  #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {visibility: hidden; height: 0;}
  .stApp {background-color: #0f172a;}
  [data-testid="stSidebar"] {background: #1e293b; border-right: 1px solid #334155;
    min-width: 290px; max-width: 290px;}
  [data-testid="stSidebar"] > div:first-child {padding-top: 1rem;}
  [data-testid="stSidebar"] .stButton button {
    text-align: left; background: transparent; border: 1px solid transparent;
    color: #e2e8f0; padding: 9px 12px; border-radius: 10px; font-size: 0.92rem;
    box-shadow: none; white-space: normal; word-break: break-word; line-height: 1.35;
    min-height: 42px; display: flex; align-items: center;}
  [data-testid="stSidebar"] .stButton button:hover {background: #334155; color: #f1f5f9; border-color: #475569;}
  .block-container {max-width: 760px; padding-top: 1.25rem; padding-bottom: 3rem;
    margin-left: auto; margin-right: auto;}
  h1, h2, h3 {font-weight: 650; letter-spacing: -0.02em; color: #f1f5f9; line-height: 1.25;}
  h1 {margin-bottom: 0.25rem;}
  .muted {color: #94a3b8; font-size: 0.9rem;}
  .pill {display: inline-block; padding: 3px 14px; border-radius: 999px;
         font-size: 0.85rem; font-weight: 650;}
  .pill-go {background: #14532d; color: #bbf7d0;}
  .pill-conditional {background: #78350f; color: #fde68a;}
  .pill-nogo {background: #7f1d1d; color: #fecaca;}
  .user-msg {background: #1e293b; border: 1px solid #334155; color: #e2e8f0;
    border-radius: 18px; padding: 12px 18px; margin: 1rem 0; line-height: 1.55;}
  .stTextArea textarea {border-radius: 20px; padding: 14px 18px; font-size: 1.05rem;
    background-color: #1e293b !important; color: #e2e8f0 !important;
    border: 1px solid #475569 !important; box-shadow: 0 4px 20px rgba(0,0,0,0.35);}
  .stTextArea textarea:focus {border-color: #818cf8 !important; box-shadow: 0 4px 24px rgba(0,0,0,0.45);}
  .stTextArea textarea::placeholder {color: #64748b;}
  .stButton button {border-radius: 999px; min-height: 42px; font-weight: 500;}
  .stButton button[kind="primary"] {background-color: #818cf8; color: #0f172a; border: none;}
  [data-testid="stMetric"] {background: #1e293b; border: 1px solid #334155;
    border-radius: 16px; padding: 14px 16px;}
  [data-testid="stMetric"] label {color: #94a3b8;}
  [data-testid="stMetric"] [data-testid="stMetricValue"] {color: #f1f5f9;}
  [data-testid="stProgress"] > div > div {background-color: #818cf8;}
  [data-testid="stProgress"] > div {background-color: #334155;}
  .step-done {color: #cbd5e1; font-weight: 600;}
  .step-now {color: #a5b4fc; font-weight: 700; text-decoration: underline;
    text-underline-offset: 4px;}
  .step-next {color: #64748b;}
  /* Bordered cards (verdict, progress, delete confirm): one muted line,
     consistent radius and padding, no double borders. */
  [data-testid="stVerticalBlockBorderWrapper"] {border-color: #334155 !important;
    border-radius: 16px !important;}
  details {border: 1px solid #334155; border-radius: 12px; padding: 8px 12px;}
  summary {color: #e2e8f0;}
  hr {border-color: #334155;}
</style>
""", unsafe_allow_html=True)

if "brief_text" not in st.session_state:
    st.session_state["brief_text"] = ""
if "result" not in st.session_state:
    st.session_state["result"] = None
if "confirm_delete" not in st.session_state:
    st.session_state["confirm_delete"] = None
if "menu_for" not in st.session_state:
    st.session_state["menu_for"] = None
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
    """Open only if the folder's result is actually this mission's.

    Root cause of 'output folder is gone': every Streamlit mission used
    to share one folder, outputs/streamlit-mission, so each new run
    overwrote the previous mission's result, and deleting one mission
    deleted the folder every history entry pointed at. New missions get
    their own folder (see _run_with_progress), and this check stops a
    stale/overwritten entry from silently opening the wrong mission."""
    result_path = Path(entry["out_dir"]) / "mission_result.json"
    if not result_path.exists():
        return False
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if data.get("mission_id") != entry.get("mission_id"):
        return False
    st.session_state["result"] = data
    st.session_state["out"] = entry["out_dir"]
    st.session_state["brief_text"] = entry.get("brief_text", "")
    return True


def _new_mission_dir() -> str:
    """A fresh folder per mission, so one mission can never overwrite
    or delete another's outputs."""
    import uuid
    return f"outputs/streamlit-mission/mission_{uuid.uuid4().hex[:8]}"


_STAGES = ["Understanding your market", "Finding companies in this market",
           "Checking companies in detail", "Comparing competitors",
           "Finding the right people", "Ranking your market and sizing it",
           "Building your report"]


def _run_with_progress(brief_text: str) -> tuple[dict, str]:
    """Clean, visual progress: a card, a bar, and plain stage names.
    No tool names, no API names, no logs, no background logic — just
    what a founder would care to know: where the research is up to."""
    with st.container(border=True):
        st.markdown("**Researching your market**")
        bar = st.progress(0)
        steps = st.empty()
        stage = st.empty()

        def _cb(frac: float, label: str):
            bar.progress(min(1.0, max(0.0, frac)))
            # Strip the "(n of m)" detail for the step row; the bar shows progress.
            base = label.split(" (")[0]
            now = _STAGES.index(base) if base in _STAGES else len(_STAGES) - 1
            if label.startswith("Done"):
                row = " · ".join(f'<span class="step-done">{s} ✓</span>' for s in _STAGES)
            else:
                parts = []
                for i, s in enumerate(_STAGES):
                    cls = "step-done" if i < now else ("step-now" if i == now else "step-next")
                    parts.append(f'<span class="{cls}">{s}</span>')
                row = " → ".join(parts)
            steps.markdown(row, unsafe_allow_html=True)
            stage.markdown(f"<p class='muted'>{html.escape(label)}</p>", unsafe_allow_html=True)

        _out_dir = _new_mission_dir()
        _result = run_mission(brief_text, _out_dir,
                              api_key=os.environ.get("CRUSTDATA_API_KEY"),
                              sample=st.session_state.get("sample_mode", False),
                              progress=_cb)
        return _result, _out_dir


def _display_brief(result: dict, brief_text: str) -> str:
    """Never show raw JSON as the user's message. Older history entries
    (guided builder) stored a JSON brief; show a plain summary instead."""
    text = (brief_text or "").strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
            parts = [data.get("product_name") or "Market entry"]
            if data.get("target_industry"):
                parts.append(data["target_industry"])
            if data.get("target_country"):
                parts.append(f"in {data['target_country']}")
            return " · ".join(parts)
        except Exception:
            pass
    if text:
        return text
    brief = result.get("brief", {})
    return f"{brief.get('product_name', 'Market entry')} · {brief.get('target_industry', '')} in {brief.get('target_country', '')}".strip(" ·")


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    if st.button("＋  New search", use_container_width=True):
        st.session_state["result"] = None
        st.session_state["brief_text"] = ""
        st.rerun()
    st.markdown("**Recent**")
    entries = load_history("outputs/streamlit-mission")
    _q = st.text_input("Search recent", placeholder="Filter by product or country…",
                       label_visibility="collapsed")
    if _q:
        _ql = _q.lower()
        entries = [e for e in entries
                   if _ql in (e.get("product_name") or "").lower()
                   or _ql in (e.get("target_country") or "").lower()
                   or _ql in (e.get("brief_text") or "").lower()]
    if not entries:
        st.markdown('<p class="muted">No past searches yet.</p>', unsafe_allow_html=True)
    for e in entries[:20]:
        label = f"{e.get('product_name') or 'Market entry'} · {e.get('target_country', '')}"
        _row1, _row2 = st.columns([5, 1])
        with _row1:
            if st.button(label, key=f"hist_{e['mission_id']}", use_container_width=True):
                st.session_state["menu_for"] = None
                if _open_history_entry(e):
                    st.rerun()
                else:
                    # Stale entry from the old shared-folder era (or a
                    # folder deleted outside the app): drop it from the
                    # list instead of leaving a permanently dead button.
                    remove_entry("outputs/streamlit-mission", e["mission_id"])
                    st.session_state["deleted_notice"] = (
                        "That research can't be reopened — it was saved before "
                        "each search got its own folder, and its files are gone. "
                        "New searches are saved separately, so this won't happen again.")
                    st.rerun()
        with _row2:
            if st.button("⋮", key=f"menu_{e['mission_id']}", use_container_width=True,
                         help="More options"):
                st.session_state["menu_for"] = (
                    None if st.session_state["menu_for"] == e["mission_id"]
                    else e["mission_id"])
                st.rerun()
        # Three-dot menu for this chat only: Delete lives here, not in a
        # separate Manage list and not as a permanent button per row.
        if st.session_state["menu_for"] == e["mission_id"]:
            _m1, _m2 = st.columns(2)
            with _m1:
                if st.button("🗑 Delete", key=f"del_{e['mission_id']}",
                             use_container_width=True):
                    st.session_state["confirm_delete"] = e["mission_id"]
                    st.session_state["confirm_delete_out"] = e["out_dir"]
                    st.session_state["menu_for"] = None
                    st.rerun()
            with _m2:
                if st.button("Close", key=f"close_{e['mission_id']}",
                             use_container_width=True):
                    st.session_state["menu_for"] = None
                    st.rerun()
    st.markdown("---")
    st.checkbox("Sample mode", key="sample_mode",
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
                    # Folder already gone or overwritten by the old shared
                    # folder: at least remove the dead list entry, and
                    # never delete a folder that now belongs to another mission.
                    remove_entry(_del_out, _del_id)
                    st.session_state["deleted_notice"] = (
                        "Removed from history — its files were already gone or "
                        "belonged to another research, so nothing else was deleted.")
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
    _display = _display_brief(result, brief_text)
    if _display:
        st.markdown(f'<div class="user-msg">{html.escape(_display)}</div>', unsafe_allow_html=True)
    _top1, _top2, _top3 = st.columns(3)
    with _top1:
        if st.button("↩  New search", use_container_width=True):
            st.session_state["result"] = None
            st.session_state["brief_text"] = ""
            st.rerun()
    with _top2:
        if st.button("↻  Run again", use_container_width=True,
                     help="Re-run the same brief with fresh live data."):
            _fresh, _fresh_out = _run_with_progress(brief_text)
            st.session_state["result"] = _fresh
            st.session_state["out"] = _fresh_out
            st.rerun()
    with _top3:
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
        _zip_buf = io.BytesIO()
        with zipfile.ZipFile(_zip_buf, "w", zipfile.ZIP_DEFLATED) as _zf:
            for _p in sorted(out.iterdir()):
                if _p.is_file() and _p.name != "history.json":
                    _zf.write(_p, _p.name)
        st.download_button("Download all as ZIP", _zip_buf.getvalue(),
                           file_name=f"{result['mission_id']}.zip")
        for name in result["artifacts"]:
            p = out / name
            if p.exists() and p.suffix in (".csv", ".json", ".html", ".pdf"):
                st.download_button(f"Download {name}", p.read_bytes(), file_name=name)
        st.markdown("**Copyable summary**")
        _top_lines = "\n".join(
            f"- {t['rank']}. {t['name']} (fit {t['fit_score']})"
            for t in (d.get("top5") or [])[:5]) or "No accounts found."
        _pool = (f"{s['currency']} {s['serviceable_annual_pool']:,.0f}"
                 if s["serviceable_annual_pool"] is not None else "not estimated")
        st.code(f"Verdict: {d.get('verdict', '—')}\n"
                f"Accounts: {len(result['ranked'])} · Market pool: {_pool} · "
                f"People mapped: {result['buyer_records']}\nTop accounts:\n{_top_lines}",
                language="text")
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
    result, _out_dir = _run_with_progress(brief)
    st.session_state["result"] = result
    st.session_state["out"] = _out_dir
    st.session_state["brief_text"] = brief
    st.rerun()
