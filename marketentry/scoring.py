"""Deterministic scoring + market sizing. No LLM, no learned weights.

Rubric (100 points, spec §5 Step C):
  ICP match            35  industry match (20) + headcount in range (15)
  Growth signals       20  headcount growth / funding / open roles, if observed
  Hiring signals       15  open roles observed
  Product-need fit     15  competitor-keyword / industry overlap, if observed
  Buyer-map availability 15  verified buyers found for the account

Missing evidence contributes 0 to that component AND lowers the
coverage score, which is shown separately. A company is never penalised
twice in prose: the report shows score, coverage and unknowns side by side.
"""
from __future__ import annotations

from .brief import MarketBrief
from .crustdata import Company


def _in_range(v, lo, hi):
    if v is None:
        return None
    if lo is not None and v < lo:
        return False
    if hi is not None and v > hi:
        return False
    return True


def score_company(c: Company, brief: MarketBrief, buyer_count: int = 0,
                  keyword_overlap: bool = False) -> tuple[int, float, list[str], dict]:
    unknowns: list[str] = []
    score = 0
    observed_fields = 0
    total_fields = 5  # industry, headcount, growth, roles, funding
    breakdown: dict[str, int] = {"icp": 0, "growth": 0, "hiring": 0, "fit": 0, "buyer": 0}

    # ICP: industry (20) + headcount in range (15)
    # Partial credit (10) for a shared industry token, e.g. "financial"
    # shared by "Financial technology" and "Financial Services"/"Banking"
    # adjacent sectors — live taxonomy is professional_network_industry,
    # not a clean target-industry label, so exact-only scoring would
    # unfairly zero every real fintech-adjacent company.
    if c.industry:
        observed_fields += 1
        if brief.target_industry and brief.target_industry.lower() in c.industry.lower():
            breakdown["icp"] += 20
        elif brief.target_industry and set(brief.target_industry.lower().split()) & set(c.industry.lower().split()):
            breakdown["icp"] += 10
        elif not brief.target_industry:
            breakdown["icp"] += 10
    else:
        unknowns.append("industry unknown")
    if c.employee_count is not None:
        observed_fields += 1
        if _in_range(c.employee_count, brief.employee_min, brief.employee_max):
            breakdown["icp"] += 15
    else:
        unknowns.append("headcount unknown")

    # Growth (20): growth %, funding, or roles as a growth proxy.
    growth_points = 0
    if c.headcount_growth is not None:
        observed_fields += 1
        growth_points = max(growth_points, 20 if c.headcount_growth > 0 else 5)
    elif c.funding_usd:
        observed_fields += 1
        growth_points = 15
    elif c.open_roles:
        growth_points = 10
    else:
        unknowns.append("growth signals unknown")
    breakdown["growth"] = growth_points

    # Hiring (15)
    if c.open_roles is not None:
        observed_fields += 1
        breakdown["hiring"] = 15 if c.open_roles > 0 else 5
    else:
        unknowns.append("open roles unknown")

    # Product-need fit (15): keyword overlap is a weak, labelled signal.
    if keyword_overlap:
        breakdown["fit"] = 15
    else:
        unknowns.append("product-need fit not evidenced (no keyword overlap observed)")

    # Buyer availability (15) — role-verified buyers only; senior contacts
    # with unverified roles do not earn these points.
    if buyer_count > 0:
        breakdown["buyer"] = 15
    else:
        unknowns.append("no role-verified buyer found yet")

    score = sum(breakdown.values())
    coverage = round(observed_fields / total_fields, 2)
    return min(score, 100), coverage, unknowns, breakdown


def wave_for(rank: int, total: int) -> str:
    if total <= 0:
        return "Research Needed"
    if rank < max(1, total // 3):
        return "Wave 1"
    if rank < max(2, (2 * total) // 3):
        return "Wave 2"
    return "Research Needed"


def size_market(observed_count: int | None, shortlist_count: int,
                acv: float | None, currency: str) -> dict:
    """Bottom-up sizing only. observed_count is the Crustdata indexed
    count (coverage-limited), NOT total businesses in the market.
    If ACV is missing, money fields are None and the report omits them."""
    if acv is None:
        return {
            "observed_eligible_company_count": observed_count,
            "annual_contract_value": None, "currency": currency or "",
            "serviceable_annual_pool": None,
            "shortlist_pipeline_pool": None,
            "shortlist_count": shortlist_count,
            "formula": "No ACV supplied: monetary estimates omitted.",
        }
    pool = observed_count * acv if observed_count is not None else None
    return {
        "observed_eligible_company_count": observed_count,
        "annual_contract_value": acv, "currency": currency,
        "serviceable_annual_pool": pool,
        "shortlist_pipeline_pool": shortlist_count * acv,
        "shortlist_count": shortlist_count,
        "formula": (f"serviceable pool = observed count ({observed_count}) x "
                    f"client-supplied ACV ({currency} {acv:,.0f})"
                    if pool is not None else
                    "Observed count unknown: serviceable pool cannot be computed."),
    }
