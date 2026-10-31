"""Crustdata shape + robustness tests: no network, mocked HTTP.

Covers the judging robustness criterion:
- Real documented response shape (Ramp/Brex example from Crustdata docs)
- Empty results -> empty list, not a crash
- Transient 429 -> retry -> success
- 401 -> error recorded, mission code must handle it upstream (no fake data)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from marketentry.brief import MarketBrief
from marketentry.crustdata import CrustdataClient


class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload or {}
        self.text = text
        self.content = b"{}" if payload is not None else b""

    def json(self):
        return self._payload


class _Session:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def post(self, *args, **kwargs):
        self.calls += 1
        return self._responses.pop(0)


def _client_with(responses):
    c = CrustdataClient(api_key="test-key")
    c.session = _Session(responses)
    return c


def test_docs_shape_ramp_brex():
    payload = {"companies": [
        {"basic_info": {"name": "Ramp", "primary_domain": "ramp.com"},
         "headcount": {"total": 1150},
         "locations": {"headquarters": "New York, United States"},
         "funding": {"total_investment_usd": 1900000000}},
        {"basic_info": {"name": "Brex", "primary_domain": "brex.com"},
         "headcount": {"total": 1200},
         "locations": {"headquarters": "San Francisco, United States"}}],
        "total_count": 84}
    # search_companies makes a second (keyword) call for hybrid candidates
    # when an industry is present; it must not overwrite a real total.
    client = _client_with([_Resp(200, payload), _Resp(200, {"companies": [], "total_count": 12})])
    brief = MarketBrief(target_country="United States", target_industry="Financial Services",
                        employee_min=500, employee_max=5000)
    companies, total, warns = client.search_companies(brief, limit=2)
    assert total == 84
    assert [c.name for c in companies] == ["Ramp", "Brex"]
    assert companies[0].employee_count == 1150
    assert companies[0].domain == "ramp.com"


def test_empty_results():
    client = _client_with([_Resp(200, {"companies": [], "total_count": 0})])
    brief = MarketBrief(target_country="United Kingdom")
    companies, total, _ = client.search_companies(brief, limit=5)
    assert companies == [] and total == 0


def test_transient_429_retries():
    payload = {"companies": [], "total_count": 0}
    client = _client_with([_Resp(429, text="rate limited"), _Resp(200, payload)])
    brief = MarketBrief(target_country="United Kingdom")
    companies, _, _ = client.search_companies(brief, limit=5)
    assert companies == []
    assert client.session.calls == 2


def test_unauthorized_is_error_not_fake_data():
    client = _client_with([_Resp(401, text="unauthorized"),
                           _Resp(404, text="not found")])
    brief = MarketBrief(target_country="United Kingdom")
    companies, _, warns = client.search_companies(brief, limit=5)
    assert companies == []
    assert warns  # failure is surfaced, not hidden
