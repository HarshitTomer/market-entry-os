"""Mission orchestrator: brief -> Crustdata -> ranking -> verifier ->
CRM -> exports. One call, no intermediate prompts.

Steps (spec §5): A brief, B discovery, C enrich+rank, D competitors,
E buyers, F sizing+recommendation, G verification loop, H deliverables.

Verification model: every client-facing claim gets an Evidence record.
A claim is 'supported' only if a source record actually contains it and
belongs to the right canonical id/domain. Everything else is 'unknown'
or 'unverified' in the report — never silently promoted to a fact.
Numbers (scores, sizing) are recomputed deterministically in Python,
not taken from prose.
"""
from __future__ import annotations

import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .brief import MarketBrief, parse_brief
from . import crm as crm_mod
from .crustdata import Company, CrustdataClient, Person, ToolCall
from .exporters import write_artifacts
from .scoring import score_company, size_market, wave_for


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _evidence(evid: list, subject_id: str, claim: str, source: str,
              pointer: str, field_path: str, status: str, notes: str = ""):
    evid.append({
        "evidence_id": f"ev_{len(evid) + 1:04d}",
        "subject_type": "company", "subject_id": subject_id, "claim": claim,
        "source_kind": source, "source_record_id": pointer, "source_url": None,
        "field_path": field_path, "retrieved_at_utc": _now(),
        "status": status, "notes": notes,
    })


# Sample data is ONLY for --sample smoke tests. It is labelled SAMPLE in
# every output and in the trace, and is never presented as a live result.
SAMPLE_COMPANIES = [
    {"basic_info": {"name": "Sample Fintech Ltd", "primary_domain": "samplefintech.example"},
     "headcount": {"total": 180}, "locations": {"headquarters": "London, United Kingdom"},
     "taxonomy": {"industry": "Financial technology"}, "funding": {"total_investment_usd": 20000000}},
    {"basic_info": {"name": "Sample Pay Ltd", "primary_domain": "samplepay.example"},
     "headcount": {"total": 90}, "locations": {"headquarters": "Manchester, United Kingdom"},
     "taxonomy": {"industry": "Financial technology"}},
]


def run_mission(raw_prompt: str, out_dir: str | Path, api_key: str | None = None,
                sample: bool = False, max_accounts: int | None = None,
                progress=None) -> dict:
    """progress, if given, is called as progress(fraction, label) with
    plain, user-facing stage labels only — never tool names, API names,
    or internal step codes. A failing callback must never break a mission."""
    def _p(frac: float, label: str):
        if progress is None:
            return
        try:
            progress(min(1.0, max(0.0, frac)), label)
        except Exception:
            pass

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    mission_id = f"mission_{uuid.uuid4().hex[:8]}"
    _p(0.05, "Understanding your market")
    brief: MarketBrief = parse_brief(raw_prompt)
    if max_accounts:
        brief.max_target_accounts = max_accounts
    started = _now()
    warnings: list[str] = list(brief.warnings)
    trace: list[ToolCall] = []
    evidence: list[dict] = []
    client = CrustdataClient(api_key=api_key, trace=trace)
    mode = "sample" if sample else ("live" if client.has_key else "no_key")
    if mode == "no_key":
        warnings.append(
            "No CRUSTDATA_API_KEY set: live Crustdata calls were skipped. "
            "Set CRUSTDATA_API_KEY in a local .env file (never commit it) "
            "and re-run for a genuine live mission, or re-run with --sample "
            "for a clearly labelled smoke test.")

    # Step B: discovery
    _p(0.15, "Finding companies in this market")
    if sample:
        from .crustdata import normalize_company
        companies = [normalize_company(r) for r in SAMPLE_COMPANIES]
        total_count = len(companies)
        trace.append(ToolCall("company_search", "sample", "ok", 0,
                              "Sample data (smoke test only, not a live Crustdata call).",
                              result_count=len(companies)))
    elif mode == "live":
        companies, total_count, warns = client.search_companies(brief, limit=brief.max_target_accounts)
        warnings.extend(warns)
    else:
        companies, total_count = [], None
    companies = companies[:brief.max_target_accounts]

    # Step C: enrich top accounts (bounded by credit cap)
    _p(0.35, "Checking companies in detail")
    enriched: list[Company] = []
    _to_check = companies[:brief.max_company_enrichments]
    for _i, c in enumerate(_to_check):
        if _to_check:
            _p(0.35 + 0.20 * (_i + 1) / len(_to_check),
               f"Checking companies in detail ({_i + 1} of {len(_to_check)})")
        if sample:
            enriched.append(c)
            continue
        if mode != "live":
            break
        if enriched:
            # Space enrich calls: the live enrich endpoint rate-limits
            # bursts (31 Oct 2026: back-to-back calls 429'd, and a v1.4
            # run still hit a 429 at 1s spacing, so use 2s).
            import time as _time
            _time.sleep(2.0)
        got = client.enrich_company(c)
        enriched.append(got or c)
        if got is None:
            warnings.append(f"Enrichment failed for {c.name}: keeping search record, marked unverified.")
    enriched.extend(companies[brief.max_company_enrichments:])
    # Post-enrich headcount filter: an enrich range can reveal a company
    # is actually outside the target range (live: a 1–10-person company
    # in a 50–500 brief). Drop it honestly, do not rank it.
    if mode == "live" and (brief.employee_min is not None or brief.employee_max is not None):
        kept_enriched = []
        for c in enriched:
            if c.employee_count is not None and (
                    (brief.employee_min is not None and c.employee_count < brief.employee_min)
                    or (brief.employee_max is not None and c.employee_count > brief.employee_max)):
                warnings.append(f"Removed {c.name} after enrich: headcount {c.employee_count} is outside the target range {brief.employee_min}–{brief.employee_max}.")
                continue
            kept_enriched.append(c)
        enriched = kept_enriched

    # Step D: competitors (keyword company search + web search, best effort)
    _p(0.60, "Comparing competitors")
    competitors: list[dict] = []
    if mode == "live" and brief.competitor_keywords:
        kw = brief.competitor_keywords[0]
        comp_brief = MarketBrief(target_country=brief.target_country,
                                 target_industry=brief.target_industry,
                                 max_target_accounts=5)
        comp_list, _, comp_warns = client.search_companies(comp_brief, limit=5)
        warnings.extend(comp_warns)
        for cc in comp_list:
            if cc.domain and any(cc.domain == e.domain for e in enriched):
                continue
            competitors.append({
                "name": cc.name, "domain": cc.domain, "company_id": cc.company_id,
                "industry": cc.industry, "employee_count": cc.employee_count,
                "classification": "possible competitor",
                "evidence": f"Crustdata company search for keyword/industry '{kw}'",
            })
        web = client.web_search(f"{kw} {brief.target_industry} competitors {brief.target_country}", limit=3)
        for r in web[:3]:
            title = r.get("title") or r.get("url") or "web result"
            competitors.append({"name": title, "domain": "", "company_id": "",
                                "industry": "", "employee_count": None,
                                "classification": "insufficient evidence",
                                "evidence": "Crustdata web search (source page not enriched)"})
    if sample:
        competitors.append({"name": "Sample Competitor Ltd", "domain": "samplecomp.example",
                            "company_id": "sample-comp", "industry": brief.target_industry,
                            "employee_count": 250, "classification": "possible competitor",
                            "evidence": "Sample data (smoke test only)"})
    # Enrich competitors (bounded, throttled like company enrich — the
    # live 429 in v1.3 came from this unthrottled loop) and upgrade
    # classification only on observed evidence.
    if mode == "live":
        import time as _time2
        for _ci, comp in enumerate(competitors):
            if competitors:
                _p(0.60 + 0.10 * (_ci + 1) / len(competitors),
                   f"Comparing competitors ({_ci + 1} of {len(competitors)})")
            if not comp.get("domain"):
                continue
            if _ci:
                _time2.sleep(2.0)
            probe = Company(company_id=comp["company_id"] or comp["domain"],
                            name=comp["name"], domain=comp["domain"])
            got = client.enrich_company(probe)
            if got:
                comp["industry"] = got.industry or comp["industry"]
                comp["employee_count"] = got.employee_count if got.employee_count is not None else comp["employee_count"]
                if brief.target_industry and got.industry and brief.target_industry.lower() in got.industry.lower():
                    comp["classification"] = "confirmed competitor"
                    comp["evidence"] += " + Crustdata company enrich (industry match observed)"

    # Step E: buyers for top 5 accounts. buyer_counts counts
    # role-verified buyers only; contacts with unverified roles are kept
    # in Buyer_Map as contacts, not scored as buyers.
    _p(0.70, "Finding the right people")
    buyers: list[Person] = []
    buyer_counts: dict[str, int] = {}
    _buyer_targets = enriched[:5]
    for _bi, c in enumerate(_buyer_targets):
        if _buyer_targets:
            _p(0.70 + 0.12 * (_bi + 1) / len(_buyer_targets),
               f"Finding the right people ({_bi + 1} of {len(_buyer_targets)})")
        if sample:
            p = Person(person_id=f"sample-{c.company_id}", name="Sample Buyer",
                       title="Head of Compliance", company_name=c.name,
                       company_domain=c.domain, company_id=c.company_id, role_verified=True)
            buyers.append(p); buyer_counts[c.company_id] = 1
            continue
        if mode != "live":
            buyer_counts[c.company_id] = 0
            continue
        people, warns = client.search_people(c, brief.target_buyer_roles,
                                             limit=brief.max_contacts_per_company * 2)
        warnings.extend(warns)
        kept = people[:brief.max_contacts_per_company]
        if not kept and brief.target_buyer_roles:
            # Fallback, labelled not fabricated: no role-verified buyer
            # exists in Crustdata for this account, so surface senior
            # contacts (CEO/CFO/CTO/heads) as adjacent contacts for a
            # human to approve — never relabelled as compliance buyers.
            contacts, _ = client.search_people(c, [], limit=brief.max_contacts_per_company * 2)
            senior = [p for p in contacts if any(k in p.title.lower() for k in
                      ("ceo", "cfo", "cto", "chief", "founder", "head of", "director", "general counsel"))]
            kept = senior[:brief.max_contacts_per_company]
            if kept:
                warnings.append(f"{c.name}: no role-verified buyer found; mapped senior contacts are adjacent contacts, not compliance buyers.")
        buyers.extend(kept)
        buyer_counts[c.company_id] = sum(1 for p in kept if p.role_verified)
        if not kept:
            warnings.append(f"No verified buyer found for {c.name}: marked buyer_not_found, no name fabricated.")
        elif buyer_counts[c.company_id] == 0 and not brief.target_buyer_roles:
            warnings.append(f"{c.name}: mapped people are senior contacts, not role-verified buyers (no buyer roles stated in the brief).")

    # Buyer enrich (best effort, only where the record supports it):
    # accept an enriched record only if it still matches the same
    # company, otherwise the enrichment has swapped the person.
    if mode == "live":
        import time as _time3
        enriched_buyers: list[Person] = []
        for _pi, p in enumerate(buyers[:3]):
            _p(0.82 + 0.03 * (_pi + 1) / max(1, len(buyers[:3])),
               "Finding the right people")
            if _pi:
                _time3.sleep(1.0)
            got = client.enrich_person(p)
            if got and (not got.company_domain or got.company_domain == p.company_domain
                        or (got.company_id and got.company_id == p.company_id)):
                got.company_id = p.company_id or got.company_id
                got.company_domain = p.company_domain or got.company_domain
                got.company_name = p.company_name or got.company_name
                enriched_buyers.append(got)
            else:
                enriched_buyers.append(p)
        if enriched_buyers:
            buyers[:len(enriched_buyers)] = enriched_buyers

    # Step C (scoring, after buyers so buyer availability counts)
    _p(0.85, "Ranking your market and sizing it")
    ranked = []
    for c in enriched:
        desc = (c.description or "").lower()
        kw_overlap = bool(
            (c.industry and brief.target_industry.lower() in c.industry.lower())
            or ("fintech" in desc and "fintech" in brief.target_industry.lower())
            or (brief.target_industry and brief.target_industry.split()[0].lower() in desc))
        score, coverage, unknowns, breakdown = score_company(
            c, brief, buyer_count=buyer_counts.get(c.company_id, 0),
            keyword_overlap=kw_overlap)
        status = "verified" if coverage >= 0.6 and c.domain else "unverified"
        ranked.append({"company": c, "fit_score": score, "coverage": coverage,
                       "unknowns": unknowns, "verification_status": status,
                       "breakdown": breakdown})
    ranked.sort(key=lambda r: (-r["fit_score"], -r["coverage"]))
    from .usability import build_draft, build_insights, decision_card, signals_for
    for i, r in enumerate(ranked):
        r["rank"] = i + 1
        r["wave"] = wave_for(i, len(ranked))
        c = r["company"]
        industry_match = bool(c.industry and brief.target_industry.lower() in c.industry.lower())
        r["signals"] = signals_for(c, buyer_count=buyer_counts.get(c.company_id, 0),
                                   industry_match=industry_match)
        buyers_here = [p for p in buyers if p.company_id == c.company_id or (p.company_domain and p.company_domain == c.domain)]
        r["draft"] = build_draft(brief, c, r["signals"], buyers_here)
        c = r["company"]
        _evidence(evidence, c.company_id,
                  f"{c.name} employs {c.employee_count} people" if c.employee_count else f"{c.name} headcount unknown",
                  "crustdata_company_search" if mode != "sample" else "sample_data",
                  c.company_id, "headcount.total",
                  "supported" if c.employee_count else "unknown")
        _evidence(evidence, c.company_id,
                  f"{c.name} fit score {r['fit_score']}/100 (coverage {r['coverage']})",
                  "deterministic_scoring", c.company_id, "fit_score",
                  "supported", "Recomputed in Python from observed fields; unknowns listed separately.")

    sizing = size_market(total_count, len(ranked), brief.annual_contract_value, brief.currency)
    state = "completed" if not warnings else "completed_with_warnings"
    if mode == "no_key":
        state = "completed_with_warnings"

    # Step H: CRM + exports (SQLite is the operational state)
    _p(0.95, "Building your report")
    db_path = out / "marketentry.db"
    conn = crm_mod.connect(db_path)
    conn.execute("INSERT OR REPLACE INTO missions(id, raw_prompt, normalized_brief_json, status, started_at, finished_at, warnings_json) VALUES(?,?,?,?,?,?,?)",
                 (mission_id, raw_prompt, json.dumps(brief.to_dict()), state, started, _now(), json.dumps(warnings)))
    conn.commit()
    for r in ranked:
        c = r["company"]
        crm_mod.upsert_company(conn, mission_id, c, r["fit_score"], r["coverage"], r["verification_status"])
        crm_mod.add_task(conn, mission_id, c.company_id, "research",
                         f"Research {c.name} ({r['wave']})",
                         f"UNSENT DRAFT — do not send. Research {c.name} before outreach; evidence: fit {r['fit_score']}/100.")
        crm_mod.add_task(conn, mission_id, c.company_id, "outreach_draft",
                         f"Draft outreach to {c.name} ({r['wave']})",
                         r.get("draft", "UNSENT DRAFT — do not send."))
    for p in buyers:
        crm_mod.upsert_person(conn, mission_id, p, verified=bool(p.company_domain))
    for e in evidence:
        conn.execute("INSERT INTO evidence(mission_id, subject_id, claim, source_type, source_pointer, field_path, retrieved_at, status) VALUES(?,?,?,?,?,?,?,?)",
                     (mission_id, e["subject_id"], e["claim"], e["source_kind"], e["source_record_id"], e["field_path"], e["retrieved_at_utc"], e["status"]))
    for t in trace:
        conn.execute("INSERT INTO tool_runs(mission_id, tool_name, request_hash, result_status, duration_ms, credit_cost, error_type) VALUES(?,?,?,?,?,?,?)",
                     (mission_id, t.tool, "", t.status, t.duration_ms, "", t.detail))
    conn.commit()
    conn.close()

    warnings = list(dict.fromkeys(warnings))  # competitor step re-adds the same industry/sizing notes
    verified = sum(1 for e in evidence if e["status"] == "supported")
    verified_fraction = round(verified / len(evidence), 3) if evidence else None
    role_buyer_total = sum(buyer_counts.values())
    decision = decision_card(ranked, len(buyers), sizing, verified_fraction, warnings,
                             role_verified_count=role_buyer_total if brief.target_buyer_roles else None)
    insights = build_insights(ranked, buyers, competitors, sizing, brief, decision)
    artifacts = write_artifacts(out, mission_id, brief, ranked, buyers, competitors, sizing, evidence, warnings, mode, trace, decision=decision, insights=insights)
    _p(1.0, "Done — here's your answer")
    result = {
        "mission_id": mission_id, "state": state, "mode": mode,
        "brief": brief.to_dict(), "sizing": sizing, "decision": decision,
        "insights": insights,
        "company_records": len(ranked), "buyer_records": len(buyers),
        "competitor_records": len(competitors),
        "verified_claim_fraction": round(verified / len(evidence), 3) if evidence else None,
        "artifacts": artifacts, "warnings": warnings,
        "trace": [{"tool": t.tool, "endpoint": t.endpoint, "status": t.status,
                   "duration_ms": t.duration_ms, "detail": t.detail,
                   "result_count": t.result_count} for t in trace],
        "ranked": [{"rank": r["rank"], "name": r["company"].name, "domain": r["company"].domain,
                    "fit_score": r["fit_score"], "coverage": r["coverage"],
                    "wave": r["wave"], "verification_status": r["verification_status"],
                    "breakdown": r.get("breakdown", {}),
                    "signals": r.get("signals", []), "draft": r.get("draft", ""),
                    "unknowns": r["unknowns"]} for r in ranked],
    }
    (out / "mission_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    # History: never breaks the mission if the history file is unavailable.
    try:
        from .history import record_mission
        record_mission(out, raw_prompt, result)
    except Exception:
        pass
    return result
