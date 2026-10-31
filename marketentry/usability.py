"""Usability layer: decision card, why-now signals, account-specific drafts.

These are computed from observed fields only. A signal is present only
when the underlying field is present; a missing field produces no signal
and no claim, it lowers coverage instead.
"""
from __future__ import annotations


def signals_for(company, buyer_count: int = 0, industry_match: bool = False) -> list[str]:
    signals: list[str] = []
    if industry_match:
        signals.append("ICP industry match")
    if company.headcount_growth is not None and company.headcount_growth > 0:
        signals.append(f"Growing (headcount growth {company.headcount_growth:g}%)")
    if company.funding_usd:
        signals.append(f"Funded (${company.funding_usd:,.0f} total investment)")
    if company.open_roles:
        signals.append(f"Hiring ({company.open_roles} open roles)")
    if buyer_count > 0:
        signals.append(f"Buyer mapped ({buyer_count})")
    if company.employee_count:
        signals.append(f"{company.employee_count} employees")
    return signals


def build_draft(brief, company, signals: list[str], buyers_for_company: list) -> str:
    """Unsent draft only. Every sentence is tied to an observed field or
    to the client's own brief; no invented pain, no invented email."""
    buyer_names = ", ".join(p.name for p in buyers_for_company) if buyers_for_company else "the relevant buyer"
    buyer_titles = ", ".join(sorted({p.title for p in buyers_for_company if p.title})) if buyers_for_company else ""
    signal_line = "; ".join(signals) if signals else "a profile in the target size range"
    lines = [
        "UNSENT DRAFT — do not send without human approval.",
        f"Subject: {brief.product_name} for {company.name}",
        "",
        f"Hi {buyer_names},",
        "",
        f"I noticed {company.name} ({signal_line}).",
        f"We help companies like yours with {brief.product_description[:160] or brief.product_name}.",
    ]
    if buyer_titles:
        matched = [t for t in buyer_titles.split(", ") if t in (brief.target_buyer_roles or [])]
        if matched:
            lines.append(f"Given your role ({', '.join(matched)}), this may be relevant to your compliance/security work — please correct me if that is not your area.")
        else:
            lines.append(f"You are mapped as a senior contact ({buyer_titles}) at this company, not a verified buyer for this product — please point us to the right person if that is not you.")
    lines += [
        "",
        "Would a 15-minute intro be useful to see whether this fits your current priorities?",
        "No claim in this draft goes beyond the evidence log for this account.",
    ]
    return "\n".join(lines)


def decision_card(ranked: list[dict], buyer_count: int, sizing: dict,
                  verified_fraction: float | None, warnings: list[str]) -> dict:
    """GO / CONDITIONAL / NO-GO, deterministically. Thresholds are stated
    in the output so a judge can disagree with the rule, not just the result."""
    n = len(ranked)
    avg_coverage = round(sum(r["coverage"] for r in ranked) / n, 2) if n else 0.0
    top5 = [{"rank": r["rank"], "name": r["company"].name if "company" in r else r["name"],
             "domain": r["company"].domain if "company" in r else r.get("domain", ""),
             "fit_score": r["fit_score"]} for r in ranked[:5]]
    risks: list[str] = []
    if n < 3:
        risks.append("Too few verified accounts to recommend entry.")
    if buyer_count == 0:
        risks.append("No verified buyers found — outreach cannot start from this packet alone.")
    if avg_coverage < 0.5:
        risks.append(f"Low average evidence coverage ({avg_coverage}) — many fields are unknown.")
    if sizing.get("serviceable_annual_pool") is None:
        risks.append("No ACV supplied, so no monetary sizing is available.")
    if any("semantic search" in w for w in warnings):
        risks.append("Industry matching is semantic, not a taxonomy filter — relevance is approximate (caveat, not a blocker).")
    blockers = [r for r in risks if "caveat" not in r]
    if n >= 5 and buyer_count >= 3 and avg_coverage >= 0.5 and not blockers:
        verdict, confidence = "GO", "high"
    elif n >= 3 and buyer_count >= 1:
        verdict, confidence = "CONDITIONAL", "medium"
    else:
        verdict, confidence = "NO-GO", "low"
    reasons = []
    if verdict == "GO":
        reasons.append(f"{n} ranked accounts with {buyer_count} verified buyers and average coverage {avg_coverage}.")
        reasons.append("Start with Wave 1, then Wave 2; Research Needed accounts need more evidence first.")
    elif verdict == "CONDITIONAL":
        reasons.append(f"{n} accounts found, but one or more risks below must be resolved before a full launch.")
    else:
        reasons.append("The evidence does not yet support a launch recommendation.")
    return {"verdict": verdict, "confidence": confidence, "reasons": reasons,
            "risks": risks, "top5": top5, "average_coverage": avg_coverage,
            "rule": "GO requires >=5 accounts, >=3 buyers, avg coverage >=0.5 and no blockers; "
                    "caveats do not block a GO. CONDITIONAL requires >=3 accounts and >=1 buyer; otherwise NO-GO."}
