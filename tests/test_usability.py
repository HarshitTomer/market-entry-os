from marketentry.brief import MarketBrief as Brief
from marketentry.crustdata import Company
from marketentry.usability import build_draft, decision_card, signals_for


def test_signals_only_from_observed_fields():
    c = Company(company_id="1", name="Acme", domain="acme.com", employee_count=120,
                funding_usd=1_000_000, open_roles=3, headcount_growth=10)
    s = signals_for(c, buyer_count=1, industry_match=True)
    assert any("Funded" in x for x in s) and any("Hiring" in x for x in s)
    assert signals_for(Company(company_id="2", name="NoData", domain="")) == []


def test_decision_go_rule_and_no_go():
    ranked = [{"rank": i + 1, "company": Company(company_id=str(i), name=f"C{i}", domain="x.com"),
               "fit_score": 50, "coverage": 0.7} for i in range(6)]
    d = decision_card(ranked, 3, {"serviceable_annual_pool": 100}, 1.0, [])
    assert d["verdict"] == "GO" and len(d["top5"]) == 5
    assert decision_card([], 0, {"serviceable_annual_pool": None}, 0.0, [])["verdict"] == "NO-GO"


def test_draft_is_unsent_and_account_specific():
    brief = Brief(product_name="ComplianceSoft", product_description="Compliance software")
    c = Company(company_id="1", name="Acme", domain="acme.com", employee_count=120)
    draft = build_draft(brief, c, ["Growing"], [])
    assert draft.startswith("UNSENT DRAFT") and "Acme" in draft and "Growing" in draft
