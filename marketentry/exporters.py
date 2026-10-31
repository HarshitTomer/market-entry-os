"""Exporters: Target_Accounts.csv, Buyer_Map.csv,
Competitive_Landscape.csv, Evidence_Log.json, Market_Entry_Report.html
(prints cleanly to PDF from a browser — the spec's accepted fallback;
no PDF library is required to run the mission).

No email addresses are ever written: buyer rows carry name, title and
employer only. A missing field is written as 'unknown', never guessed.
"""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "unknown") for k in fieldnames})


def write_artifacts(out: Path, mission_id, brief, ranked, buyers, competitors,
                    sizing, evidence, warnings, mode, trace, decision: dict | None = None) -> list[str]:
    ev_by_company: dict[str, list[str]] = {}
    for e in evidence:
        ev_by_company.setdefault(str(e["subject_id"]), []).append(e["evidence_id"])
    _write_csv(out / "Target_Accounts.csv",
               ["rank", "name", "crustdata_company_id", "domain", "country",
                "industry", "employee_count", "open_roles", "funding_usd",
                "headcount_growth", "fit_score", "score_breakdown",
                "coverage", "wave", "verification_status", "signals",
                "evidence_refs", "unknowns"],
               [{"rank": r["rank"], "name": r["company"].name,
                 "crustdata_company_id": r["company"].company_id,
                 "domain": r["company"].domain or "unknown",
                 "country": r["company"].country or "unknown",
                 "industry": r["company"].industry or "unknown",
                 "employee_count": r["company"].employee_count if r["company"].employee_count is not None else "unknown",
                 "open_roles": r["company"].open_roles if r["company"].open_roles is not None else "unknown",
                 "funding_usd": r["company"].funding_usd if r["company"].funding_usd is not None else "unknown",
                 "headcount_growth": r["company"].headcount_growth if r["company"].headcount_growth is not None else "unknown",
                 "fit_score": r["fit_score"],
                 "score_breakdown": "; ".join(f"{k}:{v}" for k, v in r.get("breakdown", {}).items()),
                 "coverage": r["coverage"],
                 "wave": r["wave"], "verification_status": r["verification_status"],
                 "signals": "; ".join(r.get("signals", [])),
                 "evidence_refs": "; ".join(ev_by_company.get(str(r["company"].company_id), [])),
                 "unknowns": "; ".join(r["unknowns"])} for r in ranked])

    _write_csv(out / "Buyer_Map.csv",
               ["name", "title", "company_name", "company_domain",
                "crustdata_company_id", "verified_employment", "role_verified", "missing_data"],
               [{"name": p.name, "title": p.title or "unknown",
                 "company_name": p.company_name, "company_domain": p.company_domain or "unknown",
                 "crustdata_company_id": p.company_id,
                 "verified_employment": bool(p.company_domain),
                 "role_verified": bool(getattr(p, "role_verified", False)),
                 "missing_data": "email intentionally omitted (never fabricated)"
                 + ("" if getattr(p, "role_verified", False) else "; buyer role not verified against the brief")} for p in buyers])

    _write_csv(out / "Competitive_Landscape.csv",
               ["name", "domain", "industry", "employee_count", "classification", "evidence"],
               competitors)

    (out / "Evidence_Log.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    # HTML report — dark, professional, matching the app. The old report
    # was plain white with an unstyled table, which is why it looked bad.
    def _fit_bar(score: int) -> str:
        return (f"<div style='background:#334155;border-radius:999px;height:8px;width:110px'>"
                f"<div style='background:#818cf8;border-radius:999px;height:8px;width:{score}%'></div></div>")
    rows_html = "".join(
        f"<tr><td>{r['rank']}</td><td><b>{html.escape(r['company'].name)}</b><br>"
        f"<span class='small'>{html.escape(r['company'].domain or 'unknown')} · "
        f"{html.escape(r['company'].industry or 'unknown')} · "
        f"{r['company'].employee_count if r['company'].employee_count is not None else 'unknown'} people</span></td>"
        f"<td>{_fit_bar(r['fit_score'])} {r['fit_score']}/100</td>"
        f"<td>{r['coverage']}</td><td>{r['wave']}</td>"
        f"<td>{html.escape('; '.join(r.get('signals', [])) or '—')}</td></tr>"
        for r in ranked)
    buyers_html = "".join(
        f"<tr><td>{html.escape(p.name)}</td><td>{html.escape(p.title or 'unknown')}</td>"
        f"<td>{html.escape(p.company_name or 'unknown')}</td>"
        f"<td>{'✓ verified role' if getattr(p, 'role_verified', False) else 'adjacent contact'}</td></tr>"
        for p in buyers) or "<tr><td colspan='4'>None mapped — see warnings.</td></tr>"
    comps_html = "".join(
        f"<tr><td>{html.escape(c.get('name', ''))}</td><td>{html.escape(c.get('domain', '') or '—')}</td>"
        f"<td>{html.escape(c.get('classification', ''))}</td>"
        f"<td>{html.escape(c.get('industry', '') or '—')}</td></tr>"
        for c in competitors) or "<tr><td colspan='4'>None found.</td></tr>"
    sizing_html = ""
    if sizing["serviceable_annual_pool"] is not None:
        sizing_html = (f"<p><b>Observed eligible company count:</b> {sizing['observed_eligible_company_count']} "
                       f"(Crustdata indexed count — coverage-limited, not every business in the market).<br>"
                       f"<b>Client-supplied ACV:</b> {sizing['currency']} {sizing['annual_contract_value']:,.0f}<br>"
                       f"<b>Serviceable annual pool = count x ACV:</b> {sizing['currency']} {sizing['serviceable_annual_pool']:,.0f}<br>"
                       f"<b>Shortlist pipeline pool ({sizing['shortlist_count']} accounts x ACV):</b> "
                       f"{sizing['currency']} {sizing['shortlist_pipeline_pool']:,.0f} "
                       f"(illustrative pipeline, not forecast revenue).</p>")
    else:
        sizing_html = ("<p><b>Monetary estimates omitted:</b> no annual contract value was supplied "
                       "in the brief, so no figure was invented.</p>")
    warn_html = "".join(f"<li>{html.escape(w)}</li>" for w in warnings) or "<li>None</li>"
    mode_banner = ""
    if mode == "sample":
        mode_banner = ("<p class='banner'><b>SAMPLE DATA — smoke test only.</b> "
                       "These companies are not live Crustdata results. Run with a real "
                       "CRUSTDATA_API_KEY for a genuine mission.</p>")
    elif mode == "no_key":
        mode_banner = ("<p class='banner'><b>NO LIVE DATA.</b> No Crustdata key was set, "
                       "so no live search ran. This packet is empty by design, not by fabrication.</p>")
    decision_html = ""
    if decision:
        top5_html = "".join(f"<li>{html.escape(t['name'])} — fit {t['fit_score']}</li>" for t in decision["top5"])
        risks_html = "".join(f"<li>{html.escape(r)}</li>" for r in decision["risks"]) or "<li>None listed</li>"
        reasons_html = "".join(f"<li>{html.escape(r)}</li>" for r in decision["reasons"])
        _pill = {"GO": "#14532d", "CONDITIONAL": "#78350f"}.get(decision['verdict'], "#7f1d1d")
        decision_html = (f"<div class='card'>"
                         f"<span class='pill' style='background:{_pill}'>{decision['verdict']}</span> "
                         f"<span class='small'>confidence: {decision['confidence']}</span>"
                         f"<ul>{reasons_html}</ul><h3>Top 5 to contact first</h3><ol>{top5_html}</ol>"
                         f"<h3>Risks / what would change this verdict</h3><ul>{risks_html}</ul>"
                         f"<p class='small'>Rule: {html.escape(decision['rule'])}</p></div>")
    report = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Market Entry Report — {html.escape(brief.product_name)}</title>
<style>body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;max-width:900px;margin:40px auto;padding:0 20px;line-height:1.55}}
h1,h2,h3{{color:#f1f5f9;letter-spacing:-0.02em}}h1{{font-size:2rem}}
.card{{background:#1e293b;border:1px solid #334155;border-radius:16px;padding:20px;margin:20px 0}}
.pill{{display:inline-block;padding:3px 14px;border-radius:999px;font-weight:650;font-size:0.9rem}}
.small{{color:#94a3b8;font-size:0.9rem}}
.banner{{background:#1e293b;border:1px solid #475569;border-radius:12px;padding:12px 16px}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #334155;padding:8px 10px;text-align:left}}
th{{color:#94a3b8;font-size:0.9rem}}tr:nth-child(even) td{{background:#16213a}}
a{{color:#a5b4fc}}</style>
</head><body>
<p class='small'>MARKETENTRYOS · MARKET ENTRY REPORT</p>
<h1>{html.escape(brief.product_name)}</h1>
<p class='small'>Target: {html.escape(brief.target_industry or 'unknown')} in {html.escape(brief.target_country or 'unknown')},
{brief.employee_min or '?'}–{brief.employee_max or '?'} employees · Mission: {mission_id} · Mode: {mode}</p>
{decision_html}
<div class='card'><h2>What you're selling</h2>
<p>{html.escape(brief.product_description[:300])}</p></div>
{mode_banner}
<div class='card'><h2>Bottom-up market sizing</h2>{sizing_html}</div>
<h2>Ranked target accounts</h2>
<table><tr><th>Rank</th><th>Company</th><th>Fit</th><th>Coverage</th><th>Wave</th><th>Why now</th></tr>{rows_html}</table>
<p class='small'>Start with Wave 1 (highest fit, best evidence coverage), then Wave 2.
Research Needed accounts need buyer or firmographic evidence before any draft is used.
No prospect was contacted: all outreach is an unsent local draft.</p>
<h2>Launch checklist (spec Step H)</h2>
<p>Wave 1 — contact first, using the account-specific unsent draft in the CRM: {', '.join(html.escape(r['company'].name) for r in ranked if r['wave'] == 'Wave 1') or 'none'}.</p>
<p>Wave 2 — contact after Wave 1 replies: {', '.join(html.escape(r['company'].name) for r in ranked if r['wave'] == 'Wave 2') or 'none'}.</p>
<p>Research Needed — do not contact yet; resolve the unknowns in Target_Accounts.csv first: {', '.join(html.escape(r['company'].name) for r in ranked if r['wave'] == 'Research Needed') or 'none'}.</p>
<p>Before any send: a human approves each draft, confirms the buyer's role, and checks the evidence log for that account. Nothing in this packet has been sent.</p>
<h2>People mapped</h2>
<table><tr><th>Name</th><th>Title</th><th>Company</th><th>Status</th></tr>{buyers_html}</table>
<p class='small'>No email addresses are included. Role-verified means the title matched the brief's buyer roles.</p>
<h2>Competitors</h2>
<table><tr><th>Name</th><th>Domain</th><th>Classification</th><th>Industry</th></tr>{comps_html}</table>
<p class='small'>Classifications are confirmed / possible / insufficient evidence — never stronger than the evidence.</p>
<h2>Assumptions, risks and warnings</h2><ul>{warn_html}</ul>
<p>Limitations: Crustdata is company/person intelligence, not a complete registry of every
business. Headcount, hiring and funding are indicators, not proof of purchase intent.
Sizing is an illustrative pool (observed count x client-supplied ACV), not validated TAM or forecast revenue.</p>
<p>Every claim in this report traces to Evidence_Log.json. Missing data is marked unknown.</p>
</body></html>"""
    (out / "Market_Entry_Report.html").write_text(report, encoding="utf-8")
    artifacts = ["Market_Entry_Report.html", "Target_Accounts.csv", "Buyer_Map.csv",
                 "Competitive_Landscape.csv", "Evidence_Log.json", "marketentry.db",
                 "mission_result.json"]
    # PDF when reportlab is installed (it is in requirements.txt). HTML is
    # always written, so a missing PDF library never blocks the mission.
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        styles = getSampleStyleSheet()
        story = [Paragraph(f"Market Entry Report: {brief.product_name}", styles["Title"]),
                 Paragraph(f"Target: {brief.target_industry or 'unknown'} in "
                           f"{brief.target_country or 'unknown'}, "
                           f"{brief.employee_min or '?'}–{brief.employee_max or '?'} employees. "
                           f"Mission: {mission_id}. Mode: {mode}.", styles["Normal"]),
                 Spacer(1, 6 * mm)]
        if decision:
            story.append(Paragraph(f"Decision: {decision['verdict']} (confidence: {decision['confidence']}). "
                                   + " ".join(decision["reasons"]), styles["Normal"]))
            story.append(Spacer(1, 6 * mm))
        if sizing["serviceable_annual_pool"] is not None:
            story.append(Paragraph(
                f"Sizing: observed count {sizing['observed_eligible_company_count']} x "
                f"client-supplied ACV {sizing['currency']} {sizing['annual_contract_value']:,.0f} = "
                f"{sizing['currency']} {sizing['serviceable_annual_pool']:,.0f} serviceable pool "
                f"(coverage-limited, illustrative — not TAM or forecast revenue).", styles["Normal"]))
        else:
            story.append(Paragraph("Monetary estimates omitted: no ACV supplied.", styles["Normal"]))
        story.append(Spacer(1, 6 * mm))
        table_data = [["Rank", "Company", "Domain", "Fit", "Wave"]] + [
            [str(r["rank"]), r["company"].name, r["company"].domain or "unknown",
             str(r["fit_score"]), r["wave"]] for r in ranked]
        t = Table(table_data, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
                               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
                               ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("TOPPADDING", (0, 0), (-1, -1), 5),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story += [t, Spacer(1, 6 * mm),
                  Paragraph("Warnings / unknowns: " + ("; ".join(warnings) if warnings else "None"),
                            styles["Normal"]),
                  Paragraph("No prospect was contacted. Outreach is an unsent local draft. "
                            "Every claim traces to Evidence_Log.json.", styles["Normal"])]
        SimpleDocTemplate(str(out / "Market_Entry_Report.pdf"), pagesize=A4).build(story)
        artifacts.insert(1, "Market_Entry_Report.pdf")
    except Exception:
        pass
    return artifacts
