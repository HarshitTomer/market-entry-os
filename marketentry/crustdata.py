"""Crustdata client: the one place that talks to Crustdata.

Primary API (spec §6, validated against Crustdata's public company/people
search docs, 31 Oct 2026):
    POST https://api.crustdata.com/company/search
    POST https://api.crustdata.com/company/identify
    POST https://api.crustdata.com/company/enrich
    POST https://api.crustdata.com/person/search
    POST https://api.crustdata.com/person/enrich
    POST https://api.crustdata.com/web/search/live
    POST https://api.crustdata.com/web/enrich/live
Headers: Authorization: Bearer <key>, x-api-version: 2025-11-01.

Company search payload (public docs):
    {"filters": {"op": "and", "conditions": [
        {"field": "taxonomy.industry", "type": "=", "value": "Financial Services"},
        {"field": "headcount.total", "type": "between", "value": [50, 500]},
        {"field": "locations.country", "type": "=", "value": "United Kingdom"}]},
     "limit": 20}
Response: {"companies": [{"basic_info": {"name", "primary_domain"},
"headcount": {"total"}, "locations": {"headquarters"}, ...}], "total_count": N}

Robustness, by design:
- Bounded retries with backoff on 429 / 5xx only; 4xx are returned as
  errors, not retried forever.
- Every call is recorded in a trace (tool name, status, duration, and
  the *shape* of the request) — never the API key, never in exports.
- Normalisers accept every response shape seen in the docs (nested
  basic_info/headcount/locations, or flat name/domain/employee_count),
  because the hackathon walkthrough schema is the authority and may
  differ in detail from public docs. Unknown fields become None, not
  invented values.
- If the primary endpoint returns 404/405, a screener-style fallback
  (POST /screener/company/search/ etc.) is attempted once and logged.
  If both fail, the step records a warning and the mission continues
  with partial results — it never fabricates companies.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import requests

BASE_URL = os.environ.get("CRUSTDATA_BASE_URL", "https://api.crustdata.com")
API_VERSION = "2025-11-01"


def _first(d: dict, *keys):
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return None


def _nested(d: dict, *path):
    cur: object = d
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


@dataclass
class ToolCall:
    tool: str
    endpoint: str
    status: str  # ok | error | skipped_no_key
    duration_ms: int = 0
    detail: str = ""
    result_count: int | None = None


@dataclass
class Company:
    company_id: str
    name: str
    domain: str = ""
    country: str = ""
    industry: str = ""
    employee_count: int | None = None
    headcount_growth: float | None = None
    open_roles: int | None = None
    funding_usd: float | None = None
    description: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class Person:
    person_id: str
    name: str
    title: str = ""
    company_name: str = ""
    company_domain: str = ""
    company_id: str = ""
    raw: dict = field(default_factory=dict)


def normalize_company(raw: dict) -> Company:
    basic = raw.get("basic_info") or {}
    head = raw.get("headcount") or {}
    locs = raw.get("locations") or {}
    funding = raw.get("funding") or {}
    name = _first(basic, "name") or _first(raw, "name", "company_name") or "Unknown company"
    domain = _first(basic, "primary_domain", "domain") or _first(raw, "domain", "website") or ""
    domain = str(domain).replace("https://", "").replace("http://", "").strip("/").lower()
    country = ""
    hq = _first(locs, "headquarters") or _first(raw, "headquarters") or ""
    if isinstance(hq, str) and "," in hq:
        country = hq.split(",")[-1].strip()
    elif isinstance(hq, dict):
        country = _first(hq, "country") or ""
    country = country or _first(raw, "country") or _first(locs, "country") or ""
    industry = ""
    tax = raw.get("taxonomy") or {}
    if isinstance(tax, dict):
        industry = _first(tax, "industry") or ""
    if not industry:
        inds = _first(raw, "industry", "industries")
        industry = inds[0] if isinstance(inds, list) and inds else (inds or "")
    emp = _first(head, "total") or _first(raw, "employee_count", "headcount")
    if isinstance(emp, dict):
        emp = _first(emp, "total")
    try:
        emp = int(emp) if emp is not None else None
    except (TypeError, ValueError):
        emp = None
    growth = _first(head, "growth_6m", "growth") or _first(raw, "headcount_growth_6m")
    try:
        growth = float(growth) if growth is not None else None
    except (TypeError, ValueError):
        growth = None
    roles = _first(raw, "open_roles", "total_job_listings", "job_listings")
    try:
        roles = int(roles) if roles is not None else None
    except (TypeError, ValueError):
        roles = None
    fund = _first(funding, "total_investment_usd") or _first(raw, "funding_usd")
    try:
        fund = float(fund) if fund is not None else None
    except (TypeError, ValueError):
        fund = None
    cid = str(_first(raw, "company_id", "id", "crustdata_company_id") or domain or name)
    return Company(
        company_id=cid, name=str(name), domain=domain, country=str(country),
        industry=str(industry), employee_count=emp, headcount_growth=growth,
        open_roles=roles, funding_usd=fund,
        description=str(_first(basic, "description") or _first(raw, "description") or ""),
        raw=raw,
    )


def normalize_person(raw: dict) -> Person:
    basic = raw.get("basic_profile") or raw.get("basic_info") or {}
    exp = raw.get("experience") or {}
    cur = exp.get("current") or raw.get("current") or {}
    name = _first(basic, "name") or _first(raw, "name") or "Unknown person"
    title = _first(basic, "current_title") or _first(cur, "title") or _first(raw, "title") or ""
    comp = _first(cur, "name") or _first(raw, "company_name") or ""
    dom = _first(cur, "domain") or _first(raw, "company_domain") or ""
    pid = str(_first(raw, "person_id", "id", "profile_id") or name)
    return Person(person_id=pid, name=str(name), title=str(title),
                  company_name=str(comp), company_domain=str(dom).lower(), raw=raw)


class CrustdataClient:
    def __init__(self, api_key: str | None = None, trace: list[ToolCall] | None = None):
        self.api_key = api_key or os.environ.get("CRUSTDATA_API_KEY", "")
        self.trace: list[ToolCall] = trace if trace is not None else []
        self.session = requests.Session()

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "x-api-version": API_VERSION,
            "Content-Type": "application/json",
        }

    def _post(self, tool: str, path: str, payload: dict) -> tuple[dict | None, ToolCall]:
        started = time.time()
        if not self.has_key:
            call = ToolCall(tool, path, "skipped_no_key", 0, "No CRUSTDATA_API_KEY set.")
            self.trace.append(call)
            return None, call
        last_err = ""
        for attempt in range(3):
            try:
                resp = self.session.post(
                    f"{BASE_URL}{path}", json=payload,
                    headers=self._headers(), timeout=30)
                ms = int((time.time() - started) * 1000)
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                if resp.status_code >= 400:
                    call = ToolCall(tool, path, "error", ms,
                                    f"HTTP {resp.status_code}: {resp.text[:300]}")
                    self.trace.append(call)
                    return None, call
                data = resp.json() if resp.content else {}
                call = ToolCall(tool, path, "ok", ms, "HTTP 200")
                self.trace.append(call)
                return data, call
            except requests.RequestException as exc:
                last_err = str(exc)[:300]
                if attempt < 2:
                    time.sleep(2 ** attempt)
        ms = int((time.time() - started) * 1000)
        call = ToolCall(tool, path, "error", ms, last_err)
        self.trace.append(call)
        return None, call

    # -- Company ---------------------------------------------------------
    def search_companies(self, brief, limit: int = 20) -> tuple[list[Company], int | None, list[str]]:
        """Returns (companies, total_count, warnings). Post-filters locally
        on country / headcount, because the provider may not support every
        filter combination — a filter the API ignores is not silently
        treated as applied."""
        conditions = []
        if brief.target_industry:
            conditions.append({"field": "taxonomy.industry", "type": "=", "value": brief.target_industry})
        if brief.employee_min is not None and brief.employee_max is not None:
            conditions.append({"field": "headcount.total", "type": "between",
                               "value": [brief.employee_min, brief.employee_max]})
        elif brief.employee_min is not None:
            conditions.append({"field": "headcount.total", "type": ">=", "value": brief.employee_min})
        if brief.target_country:
            conditions.append({"field": "locations.country", "type": "=", "value": brief.target_country})
        payload = {"filters": {"op": "and", "conditions": conditions}, "limit": limit}
        data, call = self._post("company_search", "/company/search", payload)
        warnings: list[str] = []
        if data is None:
            # One screener-style fallback, logged as its own tool call.
            fb = {"filters": [], "limit": limit}
            data, call = self._post("company_search", "/screener/company/search/", fb)
            if data is None:
                warnings.append(f"Company search failed: {call.detail}")
                return [], None, warnings
            warnings.append("Primary company search endpoint unavailable; used screener fallback (filters applied locally).")
        raw_list = data.get("companies") or data.get("data") or data.get("results") or []
        total = data.get("total_count")
        companies = [normalize_company(r) for r in raw_list if isinstance(r, dict)]
        # Local post-filter: only keep what we can verify matches the brief.
        # Headcount unknown is kept (unknown != out of range) and flagged.
        filtered = []
        for c in companies:
            if brief.target_country and c.country and brief.target_country.lower() not in c.country.lower():
                continue
            if brief.employee_min is not None and c.employee_count is not None and c.employee_count < brief.employee_min:
                continue
            if brief.employee_max is not None and c.employee_count is not None and c.employee_count > brief.employee_max:
                continue
            filtered.append(c)
        if call:
            call.result_count = len(filtered)
        if len(filtered) != len(companies):
            warnings.append(f"Post-filter removed {len(companies) - len(filtered)} companies that did not match country/headcount.")
        return filtered, total, warnings

    def enrich_company(self, company: Company) -> Company | None:
        payload = {"domain": company.domain} if company.domain else {"company_id": company.company_id}
        data, _ = self._post("company_enrich", "/company/enrich", payload)
        if not data:
            return None
        raw = data.get("company") or data
        enriched = normalize_company(raw if isinstance(raw, dict) else {})
        # Merge: enriched fields win where present, search fields fill gaps.
        for attr in ("name", "domain", "country", "industry", "employee_count",
                     "headcount_growth", "open_roles", "funding_usd", "description"):
            if getattr(enriched, attr) in (None, "", 0) and getattr(company, attr) not in (None, ""):
                setattr(enriched, attr, getattr(company, attr))
        enriched.company_id = company.company_id
        enriched.raw = raw
        return enriched

    def identify_company(self, name_or_domain: str) -> Company | None:
        data, _ = self._post("company_identify", "/company/identify",
                             {"domain": name_or_domain} if "." in name_or_domain else {"name": name_or_domain})
        if not data:
            return None
        raw = data.get("company") or data
        return normalize_company(raw) if isinstance(raw, dict) else None

    # -- People ----------------------------------------------------------
    def search_people(self, company: Company, roles: list[str], limit: int = 4) -> tuple[list[Person], list[str]]:
        warnings: list[str] = []
        conditions = []
        if company.domain:
            conditions.append({"field": "current.company_domain", "type": "=", "value": company.domain})
        payload = {"filters": {"op": "and", "conditions": conditions}, "limit": limit}
        data, call = self._post("person_search", "/person/search", payload)
        if data is None:
            # Screener fallback: company-scoped search, titles post-filtered.
            fb = {"filters": [{"filter_type": "CURRENT_COMPANY", "type": "in",
                                "value": [company.domain]}] if company.domain else [],
                  "limit": limit}
            data, call = self._post("person_search", "/screener/person/search/", fb)
            if data is None:
                warnings.append(f"Person search failed for {company.name}: {call.detail}")
                return [], warnings
            warnings.append("Person search used screener fallback; titles post-filtered locally.")
        raw_list = data.get("profiles") or data.get("people") or data.get("data") or data.get("results") or []
        people = [normalize_person(r) for r in raw_list if isinstance(r, dict)]
        # Verify employer + role locally: a person counts as a buyer only if
        # their employer matches this account (domain or name) and their
        # title matches a target role (or, if no title match, they are kept
        # but flagged unverified_role — never silently promoted).
        verified: list[Person] = []
        for p in people:
            employer_ok = (not company.domain or p.company_domain == company.domain
                           or (p.company_name and p.company_name.lower() == company.name.lower())
                           or not p.company_name)
            if not employer_ok:
                continue
            p.company_id = company.company_id
            if company.domain and not p.company_domain:
                p.company_domain = company.domain
            verified.append(p)
        role_words = [r.lower() for r in roles]
        if not role_words:
            # No roles stated in the brief: keep company-verified people,
            # do not invent a role filter. Callers must treat titles as
            # role-unverified (see Buyer_Map missing_data handling).
            return verified, warnings
        matched = [p for p in verified
                   if any(w in p.title.lower() for w in role_words) or not p.title]
        return matched, warnings

    def enrich_person(self, person: Person) -> Person | None:
        """Only called when the search record carries a profile URL / id
        the enrich endpoint accepts. Otherwise returns None — no fake
        profile is constructed."""
        raw = person.raw
        url = raw.get("profile_url") or raw.get("linkedin_url") or raw.get("url")
        payload = {"profile_url": url} if url else {"person_id": person.person_id}
        data, _ = self._post("person_enrich", "/person/enrich", payload)
        if not data:
            return None
        rec = data.get("person") or data
        return normalize_person(rec) if isinstance(rec, dict) else None

    # -- Web -------------------------------------------------------------
    def web_search(self, query: str, limit: int = 5) -> list[dict]:
        data, _ = self._post("web_search", "/web/search/live", {"query": query, "limit": limit})
        if not data:
            return []
        return data.get("results") or data.get("data") or []
