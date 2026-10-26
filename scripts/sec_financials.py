"""SEC EDGAR Company Facts annual US-GAAP company financials.

Strictly corporate-wide statements. Not AI revenue, datacenter-only capex,
cloud segment revenue or AI investment ROI. Annual facts carry *actual* filing
start/end, accession, filed date and taxonomy tag. Never derive standalone
quarters from YTD cash flow tags.
"""
from __future__ import annotations
from datetime import date
import json
import math
import re

REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
)
CAPEX_TAGS = (
    "PaymentsToAcquirePropertyPlantAndEquipment",
)
OPERATING_CASH_TAGS = ("NetCashProvidedByUsedInOperatingActivities",)
NET_INCOME_TAGS = ("NetIncomeLoss",)

TAGS = {
    "company.revenue_usd": REVENUE_TAGS,
    "company.capex_ppe_usd": CAPEX_TAGS,
    "company.operating_cashflow_usd": OPERATING_CASH_TAGS,
    "company.net_income_usd": NET_INCOME_TAGS,
}
DESCRIPTIONS = {
    "company.revenue_usd": "Company-wide US-GAAP revenue, not AI-only revenue.",
    "company.capex_ppe_usd": (
        "Company-wide cash payments to acquire property, plant and equipment. "
        "Not datacenter-only, and excludes some leased/financed infrastructure."
    ),
    "company.operating_cashflow_usd": "Company-wide GAAP net cash from operating activities.",
    "company.net_income_usd": "Company-wide US-GAAP net income, not AI contribution margin.",
}


def _annual_duration(fact: dict) -> bool:
    start, end = fact.get("start"), fact.get("end")
    if not isinstance(start, str) or not isinstance(end, str):
        return False
    try:
        d = (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return False
    return 320 <= d <= 385


def _valid(fact: dict) -> bool:
    if not isinstance(fact, dict):
        return False
    if fact.get("form") not in ("10-K", "10-K/A") or not _annual_duration(fact):
        return False
    if not re.fullmatch(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]", str(fact.get("end",""))):
        return False
    if not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", str(fact.get("accn",""))):
        return False
    if not isinstance(fact.get("val"), (int, float)) or isinstance(fact["val"], bool):
        return False
    if not math.isfinite(fact["val"]):
        return False
    # If present, fp must correspond to annual filing period.
    if fact.get("fp") not in (None, "FY"):
        return False
    return True


def annual_financials(payload: bytes, source: dict, fetched_at: str,
                      raw_path: str, raw_sha: str) -> list[dict]:
    doc = json.loads(payload)
    cik = source["cik"]
    if not isinstance(doc, dict) or doc.get("cik") != int(cik):
        raise ValueError("SEC companyfacts CIK mismatch")
    gaap = doc.get("facts", {}).get("us-gaap")
    if not isinstance(gaap, dict):
        raise ValueError("SEC companyfacts missing us-gaap financial facts")
    ticker = source["ticker"]
    # Restrict to annual 10-K durations and last six fiscal reporting years.
    latest_year = date.fromisoformat(fetched_at[:10]).year
    min_year = latest_year - 7
    out = []
    for metric, tags in TAGS.items():
        # XBRL tag aliases are alternatives, not additive components. If
        # different tags are reported for same year, choose preference and
        # the latest accepted filing for the same accounting period.
        eligible = []
        for priority, tag in enumerate(tags):
            block = gaap.get(tag) or {}
            usd = (block.get("units") or {}).get("USD") or []
            if not isinstance(usd, list):
                continue
            for fact in usd:
                if not _valid(fact):
                    continue
                if not (min_year <= int(fact["end"][:4]) <= latest_year):
                    continue
                eligible.append((priority, fact, tag))
        # For each fiscal end, prefer the most recent *filed* revision of the
        # preferred available taxonomy tag; never sum different aliases.
        by_end = {}
        for priority, fact, tag in eligible:
            end = fact["end"]
            previous = by_end.get(end)
            candidate = (priority, -(int(fact.get("filed", "0000-00-00").replace("-", "") or 0)),
                         fact.get("accn", ""), fact, tag)
            if previous is None or candidate[:3] < previous[:3]:
                by_end[end] = candidate
        for end, (_, _, _, fact, tag) in sorted(by_end.items()):
            # Revenue values must be nonnegative for these issuers; net income
            # and operating cash flow may validly be negative.
            value = fact["val"]
            if metric in ("company.revenue_usd", "company.capex_ppe_usd") and value < 0:
                continue
            accession = fact["accn"]
            out.append({
                "source_id": source["id"],
                "entity_id": "sec:" + ticker,
                "ticker": ticker,
                "company_name": doc.get("entityName") or source["title"],
                "cik": cik,
                "metric_id": metric,
                "value": value,
                "unit": "USD",
                "geography": "US-listed issuer, consolidated global operations",
                "period": end,
                "period_type": "fiscal_year_end",
                "reporting_period": str(end),
                "fiscal_year_approx": int(end[:4]),
                "start": fact["start"],
                "end": end,
                "filed_at": fact.get("filed"),
                "form": fact["form"],
                "accession": accession,
                "taxonomy": "us-gaap",
                "xbrl_tag": tag,
                "evidence_type": "sec_xbrl_filing",
                "methodology": DESCRIPTIONS[metric] + " Annual 10-K duration; selected reported tag " + tag + ".",
                "source_url": (
                    "https://www.sec.gov/Archives/edgar/data/"
                    + str(int(cik)) + "/" + accession.replace("-", "") + "/"
                ),
                "raw_path": raw_path, "raw_sha256": raw_sha,
                "observed_at": fetched_at,
                "dataset_version": 1
            })
    if not out:
        raise ValueError("No qualifying annual 10-K US-GAAP revenue/cashflow/capex rows found")
    return sorted(out, key=lambda r: (r["metric_id"], r["period"]))


def annual_financials_adapter(payload: bytes, source: dict, at: str,
                              raw_path: str, sha: str) -> list[dict]:
    if source.get("kind") != "sec_companyfacts_annual":
        raise ValueError("Unknown financial dataset kind")
    return annual_financials(payload, source, at, raw_path, sha)
