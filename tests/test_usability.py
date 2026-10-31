from marketentry.brief import MarketBrief as Brief
from marketentry.crustdata import Company, normalize_company, role_matches
from marketentry.scoring import score_company
from marketentry.usability import build_draft, decision_card, signals_for


def test_enrich_markets_private_does_not_overwrite_industry():
    c = normalize_company({"basic_info": {"name": "Light", "primary_domain": "light.inc",
                                           "markets": ["PRIVATE"], "description": "fintech software"},
                           "taxonomy": {"professional_network_industry": "Software Development"}})
    assert c.industry == "Software Development"
    c2 = normalize_company({"basic_info": {"name": "X", "primary_domain": "x.com", "markets": ["PRIVATE"]}})
    assert c2.industry == ""


def test_role_keyword_matching():
    assert role_matches("Compliance Manager", ["Head of Compliance"])
    assert role_matches("CISO", ["CISO"])
    assert not role_matches("VP Marketing", ["VP Security", "Head of Compliance"])
    assert not role_matches("", ["CISO"])


def test_person_normalizer_uses_live_response_fields():
    from marketentry.crustdata import normalize_person
    p = normalize_person({"crustdata_person_id": 1, "basic_profile": {"name": "Dave H.", "current_title": "Head of Engineering"},
                          "experience": {"employment_details": {"current": [{"title": "Head of Engineering", "name": "Light",
                                                                             "company_website": "https://light.inc/?utm_source=x",
                                                                             "crustdata_company_id": 703656}]}}})
    assert p.company_domain == "light.inc" and p.company_id == "703656" and p.company_name == "Light"
    p2 = normalize_person({"basic_profile": {"name": "X"},
                           "experience": {"employment_details": {"current": [{"title": "CFO", "name": "Y",
                                                                                "company_website": "https://www.example.com/",
                                                                                "crustdata_company_id": 5}]}}})
    assert p2.company_domain == "example.com"


def test_score_breakdown_sums_to_score():
    brief = Brief(target_industry="Financial technology", employee_min=50, employee_max=500)
    c = Company(company_id="1", name="X", domain="x.com", industry="Financial technology",
                employee_count=200, funding_usd=1000000)
    score, coverage, unknowns, breakdown = score_company(c, brief, buyer_count=1, keyword_overlap=True)
    assert sum(breakdown.values()) == score
    assert breakdown["buyer"] == 15
    score2, _, _, bd2 = score_company(c, brief, buyer_count=0, keyword_overlap=True)
    assert bd2["buyer"] == 0 and score2 < score


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
