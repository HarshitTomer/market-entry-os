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
    _write_csv(out / "Target_Accounts.csv",
               ["rank", "name", "crustdata_company_id", "domain", "country",
                "industry", "employee_count", "open_roles", "fit_score",
                "coverage", "wave", "verification_status", "signals", "unknowns"],
               [{"rank": r["rank"], "name": r["company"].name,
                 "crustdata_company_id": r["company"].company_id,
                 "domain": r["company"].domain or "unknown",
                 "country": r["company"].country or "unknown",
                 "industry": r["company"].industry or "unknown",
                 "employee_count": r["company"].employee_count if r["company"].employee_count is not None else "unknown",
                 "open_roles": r["company"].open_roles if r["company"].open_roles is not None else "unknown",
                 "fit_score": r["fit_score"], "coverage": r["coverage"],
                 "wave": r["wave"], "verification_status": r["verification_status"],
                 "signals": "; ".join(r.get("signals", [])),
                 "unknowns": "; ".join(r["unknowns"])} for r in ranked])

    _write_csv(out / "Buyer_Map.csv",
               ["name", "title", "company_name", "company_domain",
                "crustdata_company_id", "verified_employment", "missing_data"],
               [{"name": p.name, "title": p.title or "unknown",
                 "company_name": p.company_name, "company_domain": p.company_domain or "unknown",
                 "crustdata_company_id": p.company_id,
                 "verified_employment": bool(p.company_domain),
                 "missing_data": "email intentionally omitted (never fabricated)"} for p in buyers])

    _write_csv(out / "Competitive_Landscape.csv",
               ["name", "domain", "industry", "employee_count", "classification", "evidence"],
               competitors)

    (out / "Evidence_Log.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    # HTML report
    rows_html = "".join(
        f"<tr><td>{r['rank']}</td><td>{html.escape(r['company'].name)}</td>"
        f"<td>{html.escape(r['company'].domain or 'unknown')}</td>"
        f"<td>{r['fit_score']}</td><td>{r['coverage']}</td><td>{r['wave']}</td></tr>"
        for r in ranked)
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
        mode_banner = ("<p style='background:#fff3cd;padding:10px'><b>SAMPLE DATA — smoke test only.</b> "
                       "These companies are not live Crustdata results. Run with a real "
                       "CRUSTDATA_API_KEY for a genuine mission.</p>")
    elif mode == "no_key":
        mode_banner = ("<p style='background:#f8d7da;padding:10px'><b>NO LIVE DATA.</b> No Crustdata key was set, "
                       "so no live search ran. This packet is empty by design, not by fabrication.</p>")
    decision_html = ""
    if decision:
        top5_html = "".join(f"<li>{html.escape(t['name'])} — fit {t['fit_score']}</li>" for t in decision["top5"])
        risks_html = "".join(f"<li>{html.escape(r)}</li>" for r in decision["risks"]) or "<li>None listed</li>"
        reasons_html = "".join(f"<li>{html.escape(r)}</li>" for r in decision["reasons"])
        decision_html = (f"<div style='border:2px solid #333;padding:16px'>"
                         f"<h2>Decision: {decision['verdict']} (confidence: {decision['confidence']})</h2>"
                         f"<ul>{reasons_html}</ul><h3>Top 5 to contact first</h3><ol>{top5_html}</ol>"
                         f"<h3>Risks / what would change this verdict</h3><ul>{risks_html}</ul>"
                         f"<p><small>Rule: {html.escape(decision['rule'])}</small></p></div>")
    report = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Market Entry Report — {html.escape(brief.product_name)}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:900px;margin:40px auto;padding:0 20px}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:6px;text-align:left}}</style>
</head><body>
<h1>Market Entry Report: {html.escape(brief.product_name)}</h1>
{decision_html}
<p><b>Product:</b> {html.escape(brief.product_description[:300])}</p>
<p><b>Target:</b> {html.escape(brief.target_industry or 'unknown')} in {html.escape(brief.target_country or 'unknown')},
{brief.employee_min or '?'}–{brief.employee_max or '?'} employees. Mission: {mission_id}. Mode: {mode}.</p>
{mode_banner}
<h2>Executive recommendation</h2>
<p>Start with Wave 1 accounts (highest deterministic fit score, best evidence coverage),
then Wave 2. Accounts in Research Needed need buyer or firmographic evidence before
any outreach draft is used. No prospect was contacted: all outreach is an unsent local draft.</p>
<h2>Bottom-up market sizing</h2>{sizing_html}
<h2>Ranked target accounts</h2>
<table><tr><th>Rank</th><th>Company</th><th>Domain</th><th>Fit / 100</th><th>Coverage</th><th>Wave</th></tr>{rows_html}</table>
<h2>Competitors</h2><p>{len(competitors)} competitor records (see Competitive_Landscape.csv).
Classifications are confirmed / possible / insufficient evidence — never stronger than the evidence.</p>
<h2>Buyers</h2><p>{len(buyers)} verified buyers mapped (see Buyer_Map.csv). No email addresses are included.</p>
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
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
                               ("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
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
