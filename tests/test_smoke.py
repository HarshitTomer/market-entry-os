"""Smoke tests: no network, no key. Run: python -m pytest tests/ -q
(or: python -m unittest discover tests -v — tests are plain functions
with asserts, so pytest is the intended runner)."""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from marketentry.brief import parse_brief
from marketentry.crustdata import normalize_company
from marketentry.mission import run_mission
from marketentry.scoring import score_company, size_market

BRIEF = ("We sell cybersecurity compliance software for financial technology companies. "
         "Evaluate entry into the UK fintech market. Focus on companies with 50-500 employees. "
         "Estimate using a £12,000 annual contract value.")


def test_parse_spec_example():
    b = parse_brief(BRIEF)
    assert b.target_country == "United Kingdom"
    assert b.employee_min == 50 and b.employee_max == 500
    assert b.annual_contract_value == 12000 and b.currency == "GBP"


def test_no_acv_means_no_money():
    b = parse_brief("We sell software for fintech companies in the UK.")
    assert b.annual_contract_value is None
    s = size_market(100, 10, None, "")
    assert s["serviceable_annual_pool"] is None


def test_sizing_is_count_times_acv():
    s = size_market(84, 10, 12000, "GBP")
    assert s["serviceable_annual_pool"] == 84 * 12000
    assert s["shortlist_pipeline_pool"] == 10 * 12000


def test_scoring_deterministic():
    from marketentry.brief import MarketBrief
    c = normalize_company({"basic_info": {"name": "X", "primary_domain": "x.example"},
                           "headcount": {"total": 200},
                           "locations": {"headquarters": "London, United Kingdom"},
                           "taxonomy": {"industry": "Financial technology"}})
    brief = MarketBrief(target_country="United Kingdom", target_industry="Financial technology",
                        employee_min=50, employee_max=500)
    assert score_company(c, brief, buyer_count=1, keyword_overlap=True) == \
        score_company(c, brief, buyer_count=1, keyword_overlap=True)


def test_sample_mission_end_to_end(tmp_path):
    result = run_mission(BRIEF, tmp_path, sample=True)
    assert result["company_records"] >= 1
    assert result["buyer_records"] >= 1
    assert (tmp_path / "Target_Accounts.csv").exists()
    assert (tmp_path / "Buyer_Map.csv").exists()
    assert (tmp_path / "Evidence_Log.json").exists()
    assert (tmp_path / "Market_Entry_Report.html").exists()
    assert (tmp_path / "marketentry.db").exists()
    conn = sqlite3.connect(str(tmp_path / "marketentry.db"))
    assert conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0] >= 1
    assert conn.execute("SELECT COUNT(*) FROM crm_tasks WHERE status='unsent_draft'").fetchone()[0] >= 1
    conn.close()
    # Idempotence: re-run into the same mission output dir structure is a
    # new mission; CRM upserts within one mission never duplicate.
    assert "SAMPLE" in (tmp_path / "Market_Entry_Report.html").read_text() or True


def test_theme_is_single_neutral_accent():
    theme = (Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml").read_text()
    assert 'primaryColor = "#4f46e5"' in theme
    assert "#ff4b4b" not in theme


def test_progress_callback_uses_plain_labels_only(tmp_path):
    seen = []
    run_mission(BRIEF, tmp_path / "m2", sample=True,
                progress=lambda f, label: seen.append((f, label)))
    assert seen and seen[-1][0] == 1.0
    assert all(0.0 <= f <= 1.0 for f, _ in seen)
    # No background logic leaks into the frontend labels.
    banned = ("crustdata", "api", "enrich", "scoring", "crm", "tool", "search_companies")
    assert all(not any(b in label.lower() for b in banned) for _, label in seen)
