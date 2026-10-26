"""Reproducible, publication-period economic datasets.

Source inputs must be explicit and versioned. The collection date is NEVER the
survey/accounting period. Stdlib-only parsers with fixture tests.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import math
from typing import Any


def record(source: dict, entity: str, geo: str, period: str, value: float,
           observed_at: str, raw_path: str, checksum: str, method: str,
           metric_id: str = "enterprise.ai_adoption_share_pct",
           unit: str = "percent", evidence: str = "survey_estimate") -> dict:
    if not (0 <= value <= 100) and unit == "percent":
        raise ValueError("Invalid percentage value: " + str(value))
    if not math.isfinite(value):
        raise ValueError("Invalid number")
    return {
        "source_id": source["id"], "entity_id": entity,
        "geography": geo, "period": period, "value": value,
        "unit": unit, "metric_id": metric_id,
        "observed_at": observed_at,
        "reporting_period": period, "period_type": "calendar_year",
        "evidence_type": evidence,
        "denominator": "surveyed enterprises / organizations, source-specific",
        "methodology": method,
        "source_url": source["homepage"],
        "raw_path": raw_path, "raw_sha256": checksum,
        "dataset_version": 1
    }


def owid_business_adoption(payload: bytes, source: dict, observed_at: str,
                           raw_path: str, checksum: str) -> list[dict]:
    """McKinsey/AI Index survey series, redistributed through OWID's chart API.

    This is self-reported adoption in >=1 business function, *not* fully scaled
    production deployment, and not a census of all registered businesses.
    """
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
    if not rows or not {"Entity", "Code", "Year"}.issubset(rows[0]):
        raise ValueError("OWID chart lacks Entity, Code, Year")
    cols = [key for key in rows[0] if key not in ("Entity", "Code", "Year")]
    if len(cols) != 1:
        raise ValueError("OWID expected one adoption indicator, got " + str(cols))
    out: list[dict] = []
    for row in rows:
        year = row.get("Year", "")
        if not (len(year) == 4 and year.isdigit() and 2000 <= int(year) <= 2100):
            continue
        value = row.get(cols[0], "").strip()
        if not value:
            continue
        try:
            percentage = float(value)
        except ValueError:
            continue
        geo = row["Entity"].strip()
        if not geo:
            continue
        entity = "owid:ai_adoption:" + (row.get("Code") or geo.lower().replace(" ", "_"))
        out.append(record(
            source, entity, geo, year, percentage, observed_at, raw_path, checksum,
            "McKinsey State of AI self-reported AI use in at least one business function, "
            "curated via Stanford AI Index and Our World in Data; GDP-weighted survey. "
            "Adoption includes experiments and pilots. Not production-scale or official census."
        ))
    if not out:
        raise ValueError("OWID adoption dataset has no valid observations")
    return out


def _index(category: dict) -> dict[str, int]:
    ix = category.get("index", {})
    if isinstance(ix, list):
        return {str(code): i for i, code in enumerate(ix)}
    if isinstance(ix, dict):
        return {str(code): int(i) for code, i in ix.items()}
    raise ValueError("Unsupported JSON-stat dimension index")


def eurostat_business_adoption(payload: bytes, source: dict, observed_at: str,
                               raw_path: str, checksum: str) -> list[dict]:
    """Read JSON-stat 2.0 isoc_eb_ai explicitly using dimensions and labels.

    Only 'all 10+ employee enterprises using >=1 AI technology' is permitted.
    This is a Eurostat ICT-in-enterprises survey (not McKinsey/OWID).
    """
    doc = json.loads(payload)
    dims = doc.get("id")
    sizes = doc.get("size")
    if not isinstance(dims, list) or not isinstance(sizes, list) or len(dims) != len(sizes):
        raise ValueError("Invalid Eurostat JSON-stat shape")
    required = {"time", "geo", "indic_is", "size_emp", "unit"}
    if not required.issubset(dims):
        raise ValueError("Eurostat dimension schema changed")
    dimensions = doc["dimension"]
    cats = {}
    for key in dims:
        cat = dimensions[key]["category"]
        cats[key] = (_index(cat), cat.get("label") or {})
    values = doc.get("value")
    if not isinstance(values, (dict, list)):
        raise ValueError("Eurostat JSON-stat missing values")
    total = math.prod(sizes)
    if total > 200000:
        raise ValueError("Eurostat query too broad")
    accepted = []
    for offset in range(total):
        value = values.get(str(offset)) if isinstance(values, dict) else (values[offset] if offset < len(values) else None)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            continue
        remainder = offset
        codes = {}
        for key, count in reversed(list(zip(dims, sizes))):
            idx = remainder % count
            remainder //= count
            reverse_idx = {v: k for k, v in cats[key][0].items()}
            codes[key] = reverse_idx.get(idx)
        labels = {key: cats[key][1].get(codes[key], codes[key] or "") for key in dims}
        indicator = (labels["indic_is"] or "").lower()
        size_text = (labels["size_emp"] or "").lower()
        unit_text = (labels["unit"] or "").lower()
        # Validate actual labels rather than blindly assuming a time-varying code.
        if "at least one" not in indicator or "ai technolog" not in indicator:
            continue
        if not ("10 persons employed or more" in size_text or codes["size_emp"] in ("GE10", "10_C10_S951_X_K")):
            continue
        if not ("percentage of enterprises" in unit_text or codes["unit"] == "PC_ENT"):
            continue
        year = codes["time"] or ""
        if not (len(year) == 4 and year.isdigit()):
            continue
        # Restrict NACE to the broad nonfinancial business economy, if supplied.
        if "nace_r2" in codes:
            nace_label = (labels.get("nace_r2") or "").lower()
            if not any(term in nace_label for term in ("all activities", "all enterprises", "total")):
                continue
        geo = labels["geo"] or codes["geo"]
        accepted.append(record(
            source, "eurostat:ai_adoption:" + codes["geo"],
            geo, year, float(value), observed_at, raw_path, checksum,
            "Eurostat isoc_eb_ai: % of enterprises with 10+ employed persons "
            "using at least one AI technology in ICT enterprise survey. "
            "Definition/sample differs from McKinsey global survey. "
            "Indicator=" + str(codes["indic_is"]) + "; size=" + str(codes["size_emp"]) + ".",
            evidence="official_statistic"
        ))
    if not accepted:
        raise ValueError("Eurostat query returned no matching enterprise adoption series; inspect dimension labels")
    return sorted(accepted, key=lambda x: (x["entity_id"], x["period"]))


PARSERS = {
    "owid_business_adoption": owid_business_adoption,
    "eurostat_business_adoption": eurostat_business_adoption,
}


def parse_dataset(payload: bytes, source: dict, observed_at: str,
                  raw_path: str, checksum: str) -> list[dict]:
    kind = source.get("kind")
    if kind not in PARSERS:
        raise ValueError("Unknown economic dataset kind: " + str(kind))
    return PARSERS[kind](payload, source, observed_at, raw_path, checksum)
