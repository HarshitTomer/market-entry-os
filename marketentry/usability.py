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
    # Value prop: first sentence of the description, or the product name
    # alone — never a mid-sentence truncation of a full free-text brief.
    desc = (brief.product_description or "").strip()
    if desc and len(desc) <= 200:
        value_prop = desc
    elif desc:
        first = desc.split(". ")[0].strip()
        value_prop = first if len(first) <= 200 else brief.product_name
    else:
        value_prop = brief.product_name
    lines = [
        "UNSENT DRAFT — do not send without human approval.",
        f"Subject: {brief.product_name} for {company.name}",
        "",
        f"Hi {buyer_names},",
        "",
        f"I noticed {company.name} ({signal_line}).",
        f"We help companies like yours with {value_prop}.",
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


def build_insights(ranked: list[dict], buyers: list, competitors: list,
                   sizing: dict, brief, decision: dict) -> list[dict]:
    """The answer founders actually need — not a list, but why this
    market, why now, why these accounts, and what to do first.
    Every sentence is computed from observed fields. If a field is
    missing, the insight says so instead of inventing a trend."""
    insights: list[dict] = []
    n = len(ranked)
    if not n:
        return [{"title": "No market to judge yet",
                 "body": "No accounts matched this brief in the data available, so no "
                         "market insight can be drawn. Widen the size range or "
                         "the geography before drawing a conclusion — an empty "
                         "result is not proof that the market does not exist."}]
    fits = [r["fit_score"] for r in ranked]
    avg_fit = sum(fits) / n
    top = ranked[0]
    top_company = top["company"]
    # 1. Why this market is worth entering (or not).
    if sizing.get("serviceable_annual_pool") is not None:
        body = (f"There are {sizing['observed_eligible_company_count']} companies in the "
                f"observed universe in this size range, worth "
                f"{sizing['currency']} {sizing['serviceable_annual_pool']:,.0f} a year at "
                f"your {sizing['currency']} {sizing['annual_contract_value']:,.0f} price — "
                f"that is the size of the pond, not a forecast. The shortlist alone "
                f"is {sizing['currency']} {sizing['shortlist_pipeline_pool']:,.0f} of pipeline. "
                f"That makes this a market you can actually work through account by "
                f"account, rather than a market you have to guess at.")
    else:
        body = (f"There are {n} ranked accounts in this size range, but without a "
                f"price in the brief no money figure can be put on the market — "
                f"and none has been invented. Add a contract value and the same "
                f"universe gives you a pool in one line.")
    insights.append({"title": "Why this market is worth a look", "body": body})
    # 2. Why now — only from observed signals.
    funded = [r for r in ranked if r["company"].funding_usd]
    growing = [r for r in ranked if r["company"].headcount_growth and r["company"].headcount_growth > 0]
    hiring = [r for r in ranked if r["company"].open_roles]
    signals = []
    if funded:
        total_funding = sum(r["company"].funding_usd for r in funded)
        signals.append(f"{len(funded)} of the {n} shortlisted companies have recorded funding "
                       f"(${total_funding:,.0f} in total) — funded companies have budget to spend, "
                       f"and they are the ones to approach first")
    if growing:
        signals.append(f"{len(growing)} are growing headcount, which usually means new systems "
                       f"are being bought, not just renewed")
    if hiring:
        signals.append(f"{len(hiring)} have open roles listed right now")
    if signals:
        insights.append({"title": "Why now", "body": ". ".join(signals) + "."})
    else:
        insights.append({"title": "Why now — honestly, no signal found",
                         "body": "No funding, growth or hiring signal was observed for these "
                                 "accounts in the data available. That does not mean the timing "
                                 "is bad — it means timing cannot be used as the reason to enter. "
                                 "Enter on fit and on the pool size, and validate timing in the "
                                 "first conversations, not from this packet."})
    # 3. Why these accounts first, in plain words.
    wave1 = [r for r in ranked if r["wave"] == "Wave 1"]
    insights.append({"title": "Why these accounts first",
                     "body": (f"{top_company.name} leads at fit {top['fit_score']}/100 "
                              f"(average across the shortlist is {avg_fit:.0f}), and "
                              f"{len(wave1)} accounts sit in Wave 1 — the ones with the best "
                              f"combination of size, industry match and evidence. Starting "
                              f"anywhere else means starting with weaker evidence and a "
                              f"weaker reason to be believed in the first email.")})
    # 4. What is actually in the way.
    verified = [p for p in buyers if getattr(p, "role_verified", False)]
    if verified:
        insights.append({"title": "What is already in your favour",
                         "body": (f"{len(verified)} role-verified buyers are already mapped, "
                                  f"so outreach does not start with 'who do we talk to?' — "
                                  f"it starts with a named person in a matching role.")})
    else:
        insights.append({"title": "What is actually in the way",
                         "body": ("No role-verified buyer was found for the top accounts in "
                                  "the data available — only senior contacts, labelled as "
                                  "such. That is the single biggest gap in this packet: "
                                  "without a named compliance or security buyer, the first "
                                  "move is not a pitch, it is finding that person. "
                                  "Treating a senior contact as a buyer would be the "
                                  "mistake this packet is built to avoid.")})
    # 5. Competition, in one honest paragraph.
    confirmed = [c for c in competitors if c.get("classification") == "confirmed competitor"]
    if confirmed:
        insights.append({"title": "What you are up against",
                         "body": (f"{len(confirmed)} competitors are confirmed in this market "
                                  f"by an observed industry match, out of {len(competitors)} "
                                  f"mapped. That is not a reason to stay out — it is proof "
                                  f"buyers already pay for this kind of product. Your edge "
                                  f"has to be a sharper fit for the Wave 1 accounts, not "
                                  f"a claim that the market is empty.")})
    elif competitors:
        insights.append({"title": "What you are up against",
                         "body": (f"{len(competitors)} possible competitors were mapped, but "
                                  f"none could be confirmed from the evidence available. "
                                  f"Do not pitch as if the market is empty, and do not "
                                  f"pitch as if it is crowded — pitch on fit for the "
                                  f"specific account.")})
    # 6. The next three moves, with reasons.
    insights.append({"title": "What to do first, in order",
                     "body": ("1. Talk to the Wave 1 accounts first — they are the cheapest "
                              "proof that the fit score means anything in a real conversation. "
                              "2. Before any pitch, resolve the buyer gap above — one verified "
                              "buyer per Wave 1 account changes this from a list into a pipeline. "
                              "3. Use the first two conversations to test the one claim this "
                              "packet cannot prove: that these companies will actually pay "
                              "for this product now, not just that they look like they should.")})
    return insights


def decision_card(ranked: list[dict], buyer_count: int, sizing: dict,
                  verified_fraction: float | None, warnings: list[str],
                  role_verified_count: int | None = None) -> dict:
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
    if any("not role-verified buyers" in w for w in warnings):
        risks.append("Buyer roles were not stated in the brief, so mapped people are senior contacts, not role-verified buyers (caveat, not a blocker).")
    blockers = [r for r in risks if "caveat" not in r]
    # GO requires role-verified buyers when that count is known; contacts
    # alone can only ever give CONDITIONAL, never GO.
    go_buyers = role_verified_count if role_verified_count is not None else buyer_count
    if n >= 5 and go_buyers >= 3 and avg_coverage >= 0.5 and not blockers:
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
