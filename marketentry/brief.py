"""Brief parsing: natural language (or JSON) -> validated MarketBrief.

Rules from the spec, enforced here rather than in prose:
- Missing ACV => monetary estimates are omitted, never invented.
- Missing / unsupported constraints are recorded as warnings, never
  silently ignored.
- Employee range, country, industry and buyer roles are explicit fields
  the rest of the pipeline can filter on, or post-filter on.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# Country aliases -> the country name Crustdata filters expect.
COUNTRIES = {
    "uk": "United Kingdom", "u.k.": "United Kingdom",
    "united kingdom": "United Kingdom", "britain": "United Kingdom",
    "us": "United States", "u.s.": "United States",
    "usa": "United States", "united states": "United States",
    "america": "United States", "american": "United States",
    "india": "India", "indian": "India",
    "germany": "Germany", "german": "Germany",
    "france": "France", "french": "France", "canada": "Canada",
    "canadian": "Canada", "australia": "Australia",
    "australian": "Australia", "netherlands": "Netherlands",
    "dutch": "Netherlands", "singapore": "Singapore",
    "uae": "United Arab Emirates", "spain": "Spain",
    "spanish": "Spain", "italy": "Italy", "italian": "Italy",
    "ireland": "Ireland", "irish": "Ireland", "british": "United Kingdom",
}

# Industry keywords -> a canonical industry label for filtering / display.
# The label is used as a *keyword* filter first; exact Crustdata taxonomy
# matching is validated at search time and post-filtered locally.
INDUSTRIES = [
    ("fintech", "Financial technology"),
    ("financial technology", "Financial technology"),
    ("financial services", "Financial Services"),
    ("healthtech", "Health technology"),
    ("healthcare", "Healthcare"),
    ("saas", "Software"),
    ("software", "Software"),
    ("cybersecurity", "Cybersecurity"),
    ("e-commerce", "E-commerce"),
    ("ecommerce", "E-commerce"),
    ("logistics", "Logistics"),
    ("manufacturing", "Manufacturing"),
    ("retail", "Retail"),
    ("education", "Education"),
    ("energy", "Energy"),
]

BUYER_ROLE_HINTS = [
    "Head of Compliance", "CISO", "Chief Information Security Officer",
    "VP Security", "Head of Security", "Chief Compliance Officer",
    "Head of Risk", "CTO", "Chief Technology Officer", "VP Engineering",
    "Head of Operations", "Chief Operating Officer", "Head of Procurement",
]


@dataclass
class MarketBrief:
    product_name: str = "Unnamed Product"
    product_description: str = ""
    target_country: str = ""
    target_industry: str = ""
    employee_min: int | None = None
    employee_max: int | None = None
    annual_contract_value: float | None = None
    currency: str = ""
    target_buyer_roles: list[str] = field(default_factory=list)
    max_target_accounts: int = 20
    max_company_enrichments: int = 10
    max_contacts_per_company: int = 2
    competitor_keywords: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "product_name": self.product_name,
            "product_description": self.product_description,
            "target_country": self.target_country,
            "target_industry": self.target_industry,
            "employee_min": self.employee_min,
            "employee_max": self.employee_max,
            "annual_contract_value": self.annual_contract_value,
            "currency": self.currency,
            "target_buyer_roles": self.target_buyer_roles,
            "max_target_accounts": self.max_target_accounts,
            "max_company_enrichments": self.max_company_enrichments,
            "max_contacts_per_company": self.max_contacts_per_company,
            "competitor_keywords": self.competitor_keywords,
            "warnings": self.warnings,
        }


def _find_country(text: str) -> str:
    low = text.lower()
    for alias, name in COUNTRIES.items():
        if re.search(rf"\b{re.escape(alias)}\b", low):
            return name
    return ""


def _find_industry(text: str) -> str:
    low = text.lower()
    # Target segment first: "for manufacturing companies" / "into the
    # German manufacturing market" beats the product type ("software"),
    # which also appears in most B2B SaaS briefs and would otherwise win.
    for pat in (r"entry into (?:the )?(.+?) market",
                r"for (.+?) companies",
                r"targeting (.+?) companies"):
        m = re.search(pat, low)
        if m:
            seg = m.group(1)
            for keyword, label in INDUSTRIES:
                if keyword in seg:
                    return label
    # Fallback: scan, with generic product-type words last.
    ordered = [x for x in INDUSTRIES if x[0] not in ("saas", "software")] + \
              [x for x in INDUSTRIES if x[0] in ("saas", "software")]
    for keyword, label in ordered:
        if keyword in low:
            return label
    return ""


def _find_employee_range(text: str) -> tuple[int | None, int | None]:
    m = re.search(r"(\d[\d,]*)\s*(?:-|to|–)\s*(\d[\d,]*)\s*employees", text.lower())
    if m:
        return int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))
    m = re.search(r"(\d[\d,]*)\+\s*employees", text.lower())
    if m:
        return int(m.group(1).replace(",", "")), None
    return None, None


def _find_acv(text: str) -> tuple[float | None, str]:
    # £12,000 / $12,000 / ₹12,000 / 12000 GBP / EUR / USD / INR
    m = re.search(r"([£$€₹])\s*(\d[\d,]*(?:\.\d+)?)", text)
    if m:
        symbol = {"£": "GBP", "$": "USD", "€": "EUR", "₹": "INR"}[m.group(1)]
        return float(m.group(2).replace(",", "")), symbol
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(GBP|USD|EUR|INR)", text, re.I)
    if m:
        return float(m.group(1).replace(",", "")), m.group(2).upper()
    return None, ""


def parse_brief(text: str) -> MarketBrief:
    """Parse a free-text brief. Also accepts a JSON brief object."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty brief: give a product, a geography and a customer profile.")
    if text.startswith("{"):
        try:
            data = json.loads(text)
            brief = MarketBrief(**{k: v for k, v in data.items() if k in MarketBrief.__dataclass_fields__})
            if brief.annual_contract_value is None:
                brief.warnings.append("No annual contract value supplied: monetary estimates omitted.")
            return brief
        except (json.JSONDecodeError, TypeError):
            pass  # fall through to natural-language parsing

    low = text.lower()
    brief = MarketBrief()
    brief.product_description = text
    # Product name: "We sell X for ..." / "ComplianceCloud" style first token
    m = re.search(r"we sell ([^,.]+?)(?: for |\.|,|$)", text, re.I)
    if m:
        brief.product_name = m.group(1).strip().title()
    brief.target_country = _find_country(text)
    brief.target_industry = _find_industry(text)
    brief.employee_min, brief.employee_max = _find_employee_range(text)
    brief.annual_contract_value, brief.currency = _find_acv(text)
    for role in BUYER_ROLE_HINTS:
        if role.lower() in low and role not in brief.target_buyer_roles:
            brief.target_buyer_roles.append(role)
    if not brief.target_buyer_roles:
        # No sector-specific default: inventing a buyer role for an unseen
        # sector would be a fabricated assumption. Buyer search then runs
        # company-scoped and keeps senior titles, flagged as role-unverified.
        brief.warnings.append("No buyer roles stated: buyer search is company-scoped only; titles are not role-verified.")
    if not brief.target_country:
        brief.warnings.append("No target country detected: country filter omitted; results are not country-scoped.")
    if not brief.target_industry:
        brief.warnings.append("No target industry detected: industry filter omitted.")
    if brief.annual_contract_value is None:
        brief.warnings.append("No annual contract value supplied: monetary estimates omitted (no figure invented).")
    # Competitor keywords: product-domain words from the description.
    for kw in ("compliance", "security", "fintech", "payments", "cybersecurity"):
        if kw in low and kw not in brief.competitor_keywords:
            brief.competitor_keywords.append(kw)
    return brief
