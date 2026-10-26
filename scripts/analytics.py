"""Evidence-based AI industry intelligence aggregates; stdlib only.

Every comparison is confined to a single source, population and metric.
Publication counts measure *this repository's feed coverage*, not industry output.
Never infer growth from a single day of API snapshots.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import statistics


def _latest_day(rows):
    return max((r.get("period", "") for r in rows), default="")


def _trend(rows, preferred_geography=None):
    if preferred_geography is not None:
        rows = [r for r in rows if r.get("geography") == preferred_geography]
    years = {}
    for r in rows:
        if r.get("period_type") == "calendar_year":
            key = r["period"]
            if key not in years or r.get("observed_at", "") > years[key].get("observed_at", ""):
                years[key] = r
    return [years[y] for y in sorted(years)]


def _series(rows):
    return [{"period": x["period"], "value": round(float(x["value"]), 4)}
            for x in rows]


def _growth(rows):
    if len(rows) < 2:
        return None
    a, b = rows[-2], rows[-1]
    return {"previous_period": a["period"], "latest_period": b["period"],
            "previous": a["value"], "latest": b["value"],
            "change_pp": round(b["value"] - a["value"], 2)}


def _display_delta(change):
    if not change:
        return "Insufficient comparable periods"
    return ("%+.2f pp" % change["change_pp"]) + " versus " + change["previous_period"]


def financial_aggregation(rows, registry):
    """Source-linked, issuer-level financials. Missing dimensions stay missing.

    Revenue / operating cash flows are valid independently. PPE cash capex
    needs an exact recognized GAAP tag; capex-to-sales additionally requires
    revenue for the same fiscal year end. Do NOT drop an issuer's available
    revenue merely because its capex XBRL concept is absent.
    """
    by_company = defaultdict(lambda: defaultdict(dict))
    for row in rows:
        if row.get("period_type") != "fiscal_year_end" or row.get("unit") != "USD":
            continue
        ticker, period, metric = row.get("ticker"), row.get("period"), row.get("metric_id")
        if not ticker or not period:
            continue
        previous = by_company[ticker][period].get(metric)
        if previous is None or row.get("filed_at", "") > previous.get("filed_at", ""):
            by_company[ticker][period][metric] = row

    revenue_points, cashflow_points, capex_points, ratio_points = [], [], [], []
    missing_capex, growth = [], []
    for ticker in sorted(by_company):
        periods = by_company[ticker]
        # Each absolute measure uses its independently latest available full year.
        for metric, target in (
            ("company.revenue_usd", revenue_points),
            ("company.operating_cashflow_usd", cashflow_points),
            ("company.capex_ppe_usd", capex_points)
        ):
            candidates = sorted(p for p, values in periods.items() if metric in values)
            if not candidates:
                if metric == "company.capex_ppe_usd":
                    missing_capex.append(ticker)
                continue
            period = candidates[-1]
            row = periods[period][metric]
            if metric in ("company.revenue_usd", "company.capex_ppe_usd") and row["value"] < 0:
                continue
            target.append({
                "label": ticker + " · FY end " + period,
                "value": round(row["value"] / 1e9, 3),
                "period": period, "accession": row["accession"],
                "source_url": row["source_url"]
            })

        # Only paired figures with exactly the same fiscal-year end are
        # eligible for a ratio; never match adjacent year or rolling YTD.
        paired = sorted(p for p, facts in periods.items()
                        if facts.get("company.revenue_usd", {}).get("value", 0) > 0
                        and facts.get("company.capex_ppe_usd", {}).get("value", -1) >= 0)
        if not paired:
            continue
        period = paired[-1]
        rev, cap = periods[period]["company.revenue_usd"], periods[period]["company.capex_ppe_usd"]
        ratio_points.append({
            "label": ticker + " · FY end " + period,
            "value": round(cap["value"] / rev["value"] * 100, 2),
            "period": period, "capex_accession": cap["accession"],
            "revenue_accession": rev["accession"],
            "source_url": cap["source_url"]
        })
        if len(paired) >= 2:
            prev_period = paired[-2]
            previous = periods[prev_period]["company.capex_ppe_usd"]
            if previous["value"] > 0:
                growth.append({
                    "ticker": ticker, "current_period": period,
                    "previous_period": prev_period,
                    "current_capex_usd_b": round(cap["value"] / 1e9, 3),
                    "previous_capex_usd_b": round(previous["value"] / 1e9, 3),
                    "capex_change_pct": round((cap["value"] / previous["value"] - 1) * 100, 2),
                    "source_url": cap["source_url"]
                })

    if not any((revenue_points, cashflow_points, capex_points)):
        return [], [], []
    meta = {
        "source_id": "sec_edgar",
        "source_url": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
        "period_type": "latest_available_fiscal_year_by_issuer"
    }
    charts = []
    if revenue_points:
        charts.append(dict(
            meta, id="sec_company_revenue", type="bar",
            title="Consolidated revenue · latest reported fiscal year",
            unit="USD billions", points=revenue_points,
            caveat="Issuer-wide SEC reported revenue, NOT AI product revenue. Fiscal year ends may differ; original filing and periods are linked."))
    if cashflow_points:
        charts.append(dict(
            meta, id="sec_company_operating_cashflow", type="bar",
            title="Consolidated operating cash flow · latest fiscal year",
            unit="USD billions", points=cashflow_points,
            caveat="Issuer-wide annual cash generated by operating activities (US GAAP). Includes non-AI activities and changes in working capital; not AI profit."))
    missing_note = (" Excluded without an equivalent verified US-GAAP PPE-purchases tag: " +
                    ", ".join(missing_capex) + ".") if missing_capex else ""
    if capex_points:
        charts.append(dict(
            meta, id="sec_company_capex", type="bar",
            title="Cash payments for property & equipment · annual",
            unit="USD billions", points=capex_points,
            omitted_issuers=missing_capex,
            caveat="Company-wide GAAP PaymentsToAcquirePropertyPlantAndEquipment, not AI-only/data-center spend. Excludes some lease financing; missing concept is not zero." + missing_note))
    if ratio_points:
        charts.append(dict(
            meta, id="sec_company_capex_to_sales", type="bar",
            title="PPE cash investment as a share of consolidated revenue",
            unit="percent", points=ratio_points,
            omitted_issuers=missing_capex,
            caveat="PPE cash payments divided by same-year consolidated revenue for the same issuer; not AI ROI. Missing ratios are omitted, never imputed." + missing_note))

    findings = []
    if missing_capex:
        findings.append({
            "kind": "coverage", "topic": "infrastructure",
            "title": "SEC cash PPE coverage: %d of %d tracked issuers" % (
                len(capex_points), len(by_company)),
            "text": "Available revenue and operating cash-flow statements remain visible. "
                    "No directly equivalent US-GAAP PPE-cash-payments concept was captured for " +
                    ", ".join(missing_capex) +
                    "; company-specific cash investment definitions need separate research before comparison.",
            "source_ids": ["sec_edgar"],
            "source_url": meta["source_url"]
        })
    if growth:
        entry = max(growth, key=lambda x: abs(x["capex_change_pct"]))
        findings.append({
            "kind": "observed", "topic": "infrastructure",
            "title": "%s reported PPE cash purchases changed %+.1f%%" % (
                entry["ticker"], entry["capex_change_pct"]),
            "text": "Latest reported fiscal year ended %s versus %s: $%.2fb vs $%.2fb company-wide PPE cash payments. Source: SEC 10-K US-GAAP concept. This is not AI-attributable CAPEX." % (
                entry["current_period"], entry["previous_period"],
                entry["current_capex_usd_b"], entry["previous_capex_usd_b"]),
            "source_ids": ["sec_edgar"],
            "source_url": entry["source_url"]
        })
    return charts, findings, growth


FINANCIAL_METRICS = (
    ("company.revenue_usd", "Revenue"),
    ("company.operating_cashflow_usd", "Operating cash flow"),
    ("company.capex_ppe_usd", "Cash purchases of PPE"),
    ("company.net_income_usd", "Net income"),
)


def build_financial_directory(rows, registry):
    """Issuer -> fiscal-year -> original reported facts; no mixed-year rollups.

    Every issuer in the registry is shown even if a supported metric is missing.
    The latest overview row is anchored to that issuer's latest available
    revenue fiscal period. No unverified capex fields are substituted.
    """
    companies = registry.get("financials", [])
    grouped = defaultdict(lambda: defaultdict(dict))
    allowed = {key for key, _ in FINANCIAL_METRICS}
    for fact in rows:
        ticker = fact.get("ticker")
        period = fact.get("period")
        metric = fact.get("metric_id")
        if not (ticker and period and metric in allowed and
                fact.get("period_type") == "fiscal_year_end" and fact.get("unit") == "USD"):
            continue
        old = grouped[ticker][period].get(metric)
        if old is None or (fact.get("filed_at") or "", fact.get("accession") or "") > (
                old.get("filed_at") or "", old.get("accession") or ""):
            grouped[ticker][period][metric] = fact
    result = []
    for company in companies:
        ticker = company["ticker"]
        periods = grouped.get(ticker, {})
        sorted_periods = sorted(periods)
        fiscal_end = max(
            (p for p in sorted_periods if "company.revenue_usd" in periods[p]),
            default=sorted_periods[-1] if sorted_periods else None)
        history = []
        for period in sorted_periods:
            metrics = {}
            for metric, _ in FINANCIAL_METRICS:
                fact = periods[period].get(metric)
                if fact:
                    metrics[metric] = {
                        "value_usd": fact["value"], "period": period,
                        "start": fact["start"], "filed_at": fact.get("filed_at"),
                        "accession": fact["accession"], "xbrl_tag": fact["xbrl_tag"],
                        "source_url": fact["source_url"]
                    }
            history.append({"period": period, "metrics": metrics})
        latest = next((row["metrics"] for row in history if row["period"] == fiscal_end), {})
        missing = [name for key, name in FINANCIAL_METRICS if key not in latest]
        result.append({
            "ticker": ticker, "name": company["title"].replace(" consolidated SEC financials", ""),
            "source_id": company["id"], "homepage": company.get("homepage"),
            "fiscal_year_end": fiscal_end,
            "metrics": latest, "missing_metrics": missing,
            "history": history[-9:]
        })
    return {
        "schema_version": 1,
        "unit": "USD",
        "metric_dictionary": [
            {"id": metric, "label": label} for metric, label in FINANCIAL_METRICS
        ],
        "companies": result,
        "coverage": {
            "companies_registered": len(result),
            "with_revenue": sum("company.revenue_usd" in c["metrics"] for c in result),
            "with_cash_ppe": sum("company.capex_ppe_usd" in c["metrics"] for c in result),
            "historical_fiscal_rows": sum(len(c["history"]) for c in result)
        },
        "methodology": (
            "Reported issuer-wide 10-K US-GAAP values. Each company table row is pinned "
            "to its latest revenue fiscal-year end; a missing field in that same period "
            "is unavailable, not zero. Different companies' fiscal year ends differ. "
            "Cash purchases of PPE exclude some leased/financed equipment. "
            "This is not AI-only revenue, investment, or ROI."
        )
    }


def make_analysis(snapshot_rows, annual_rows, articles, registry, status,
                  as_of=None, financial_rows=None):
    """Build a pure deterministic report from real stored records.

    as_of defaults to collection health timestamp, not machine/build time.
    This keeps report files stable on reruns without new evidence.
    """
    as_of = as_of or status.get("generated_at") or datetime.now(timezone.utc).isoformat()
    report_date = as_of[:10]
    sources = {s["id"]: s for section in ("feeds", "apis", "datasets", "financials", "research")
               for s in registry.get(section, [])}
    datasets = defaultdict(list)
    for row in annual_rows:
        if row.get("metric_id") == "enterprise.ai_adoption_share_pct":
            datasets[(row["source_id"], row["entity_id"])].append(row)

    def entity_series(source, selector):
        available = [(key, _trend(rows)) for key, rows in datasets.items()
                     if key[0] == source and selector(key[1], rows)]
        if not available:
            return []
        # Take the one with most history; exact names break ties.
        return sorted(available, key=lambda x: (-len(x[1]), x[0][1]))[0][1]

    eu = entity_series("eurostat_enterprise_ai_adoption",
                       lambda entity, rows: "EU27_2020" in entity)
    worldwide = entity_series("owid_business_ai_adoption",
                             lambda entity, rows: "all_geographies" in entity.lower())
    eu_delta, world_delta = _growth(eu), _growth(worldwide)

    adoption_charts = []
    for chart_id, title, rows, source, caveat in [
        ("eurostat_adoption", "EU27 business AI use · Eurostat", eu,
         "eurostat_enterprise_ai_adoption",
         "Official ICT survey, enterprises with 10+ employed persons, percentage using at least one AI technology."),
        ("survey_adoption", "AI use within surveyed organizations · OWID/McKinsey", worldwide,
         "owid_business_ai_adoption",
         "Self-reported AI use in any business function, across surveyed organizations; includes experimentation/pilots. Not the same population as Eurostat."),
    ]:
        if rows:
            adoption_charts.append({
                "id": chart_id, "type": "line", "title": title,
                "unit": "percent", "period_type": "calendar_year",
                "scope": rows[-1]["geography"], "source_id": source,
                "source_url": sources.get(source, {}).get("homepage", rows[-1].get("source_url")),
                "series": [{"label": rows[-1]["geography"], "points": _series(rows)}],
                "caveat": caveat, "delta": _growth(rows)
            })

    # Same survey/definition, same year: a permissible geographic breakdown.
    # These survey geographies overlap (Greater China is within Asia-Pacific);
    # interpret independently; never sum these percentages as market share.
    regional = {}
    if worldwide:
        latest_survey_year = worldwide[-1]["period"]
        for rows in datasets.values():
            for row in _trend(rows):
                if (row["source_id"] == "owid_business_ai_adoption" and
                    row["period"] == latest_survey_year and
                    row["geography"] in ("North America", "Europe", "Asia-Pacific", "Greater China")):
                    regional[row["geography"]] = row["value"]
    regional_chart = None
    if regional:
        regional_chart = {
            "id": "regional_survey_adoption", "type": "bar",
            "title": "Regional AI use · same organization survey",
            "unit": "percent", "period_type": "calendar_year",
            "scope": latest_survey_year + " · McKinsey/OWID",
            "source_id": "owid_business_ai_adoption",
            "source_url": sources.get("owid_business_ai_adoption", {}).get("homepage", ""),
            "points": [{"label": geo, "value": value}
                       for geo, value in sorted(regional.items(), key=lambda x: (-x[1], x[0]))],
            "caveat": "Same survey and year; regions can overlap (Greater China is part of Asia-Pacific). Not a census, not production ROI; regional percentages are not additive."
        }

    snapshots = {}
    for row in snapshot_rows:
        key = (row["entity_id"], row["metric_id"])
        if key not in snapshots or row.get("observed_at", "") > snapshots[key].get("observed_at", ""):
            snapshots[key] = row

    # Model catalog: a non-volume-weighted sample. Count only positive listed prices.
    price_charts = []
    for field, label in (
        ("openrouter.list_price_input_usd_per_million", "Input"),
        ("openrouter.list_price_output_usd_per_million", "Output")
    ):
        by_vendor = defaultdict(list)
        for (_, metric), row in snapshots.items():
            if metric != field:
                continue
            entity = row["entity_id"]
            if not entity.startswith("openrouter:") or "/" not in entity:
                continue
            vendor = entity.split(":", 1)[1].split("/", 1)[0]
            if row["value"] > 0:
                by_vendor[vendor].append(float(row["value"]))
        points = [
            {"label": vendor, "value": round(statistics.median(values), 5), "n": len(values)}
            for vendor, values in sorted(by_vendor.items()) if values
        ]
        if points:
            price_charts.append({
                "id": "price_" + label.lower(), "type": "bar",
                "title": label + " model list prices by provider",
                "unit": "USD per 1M tokens", "source_id": "openrouter_models",
                "source_url": sources.get("openrouter_models", {}).get("homepage", "https://openrouter.ai/models"),
                "period_type": "latest_catalog_snapshot", "points": points,
                "caveat": "Unweighted median of the most recently-created model entries sampled per provider (up to 12), excluding free prices. This is neither realized transaction pricing nor market share, and differs by model mix.",
            })

    # Paired model prices permit a within-model output/input price multiple.
    # No comparison with other vendors' realized volumes or revenue.
    multiples = defaultdict(list)
    input_key = "openrouter.list_price_input_usd_per_million"
    output_key = "openrouter.list_price_output_usd_per_million"
    for (entity, metric), row in snapshots.items():
        if metric != input_key or not entity.startswith("openrouter:"):
            continue
        paired = snapshots.get((entity, output_key))
        if paired is None or row["value"] <= 0 or paired["value"] <= 0:
            continue
        provider = entity.split(":", 1)[1].split("/", 1)[0]
        multiples[provider].append(paired["value"] / row["value"])
    multiple_chart = None
    if multiples:
        multiple_chart = {
            "id": "price_output_to_input", "type": "bar",
            "title": "Model output/input list-price multiples",
            "unit": "times", "period_type": "latest_catalog_snapshot",
            "source_id": "openrouter_models",
            "source_url": sources.get("openrouter_models", {}).get("homepage", "https://openrouter.ai/models"),
            "points": [{"label": name, "value": round(statistics.median(vals), 3), "n": len(vals)}
                       for name, vals in sorted(multiples.items())],
            "caveat": "Median of output price divided by input price for matched model IDs with positive prices. This is a posted tariff asymmetry, not inference cost, usage volume, or company margin."
        }

    latest_stars = [r for (_, metric), r in snapshots.items() if metric == "github.stars"]
    latest_stars.sort(key=lambda x: x["value"], reverse=True)
    repo_chart = None
    if latest_stars:
        repo_chart = {
            "id": "github_stars", "type": "bar",
            "title": "Tracked AI engineering repositories · GitHub stars",
            "unit": "GitHub stars", "period_type": "latest_platform_snapshot",
            "source_id": "github",
            "source_url": "https://github.com/",
            "points": [{"label": r["entity_id"].split(":",1)[-1], "value": r["value"]}
                       for r in latest_stars[:8]],
            "caveat": "Cumulative developer-interest signal in a selected set of repositories, not unique users, adoption, revenue, or an unbiased ecosystem ranking."
        }

    # News/index balance: one publisher can dominate; use core-only summaries.
    feed_counts = Counter()
    core_counts = Counter()
    publisher_counts = Counter()
    for article in articles:
        feed_counts[article.get("primary_category", "other")] += 1
        src = sources.get(article.get("source_id"), {})
        if src.get("priority") == "core":
            core_counts[article.get("primary_category", "other")] += 1
            publisher_counts[article.get("source_id")] += 1
    article_chart = {
        "id": "article_topics", "type": "bar",
        "title": "Research archive coverage by topic",
        "unit": "indexed article records", "period_type": "archive_to_date",
        "source_id": "article_index",
        "source_url": "https://github.com/BestNathan/ai-industry-research/tree/main/data/articles",
        "points": [{"label": k, "value": n} for k, n in core_counts.most_common(10)],
        "all_feed_total": sum(feed_counts.values()), "core_total": sum(core_counts.values()),
        "publisher_count": len(publisher_counts),
        "caveat": "Core-feeds-only article counts are **coverage of configured feeds**. They are not an industry topic-share survey, and publisher publication volume varies.",
    }

    # A daily metric-series change requires at least two different actual collection dates.
    series = defaultdict(dict)
    for row in snapshot_rows:
        key = (row["source_id"], row["entity_id"], row["metric_id"], row["unit"])
        per = row.get("period", "")
        if per not in series[key] or row.get("observed_at", "") > series[key][per].get("observed_at", ""):
            series[key][per] = row
    changes = []
    for key, by_date in series.items():
        if len(by_date) < 2:
            continue
        dates = sorted(by_date)
        before, after = by_date[dates[-2]], by_date[dates[-1]]
        if before["value"] == 0:
            rel = None
        else:
            rel = round((after["value"] / before["value"] - 1) * 100, 2)
        changes.append({
            "source_id": key[0], "entity_id": key[1], "metric_id": key[2], "unit": key[3],
            "previous_period": before["period"], "current_period": after["period"],
            "previous": before["value"], "current": after["value"],
            "absolute_change": round(after["value"] - before["value"], 6),
            "relative_change_pct": rel,
            "caveat": "Same source/metric/entity; a change in platform reporting or selected model mix may affect comparability."
        })
    changes.sort(key=lambda c: (
        0 if c["metric_id"] in ("github.stars", "huggingface.downloads") else 1,
        -abs(c["relative_change_pct"] or 0), c["entity_id"]
    ))
    snapshots_days = len({r.get("period") for r in snapshot_rows if r.get("period")})
    successes = status.get("successful_sources", 0)
    total_sources = len(status.get("sources", [])) or (successes + status.get("failed_sources", 0))
    skipped_sources = status.get("skipped_sources", 0)

    cards = []
    if eu:
        cards.append({"label": "EU enterprise AI use", "value": eu[-1]["value"],
                      "suffix": "%", "period": eu[-1]["period"], "delta": _display_delta(eu_delta),
                      "source_id": "eurostat_enterprise_ai_adoption",
                      "description": "EU27, surveyed businesses with 10+ employed persons; official statistic."})
    if worldwide:
        cards.append({"label": "Surveyed organizations using AI", "value": worldwide[-1]["value"],
                      "suffix": "%", "period": worldwide[-1]["period"], "delta": _display_delta(world_delta),
                      "source_id": "owid_business_ai_adoption",
                      "description": "McKinsey survey across geographies: any-function use, including pilots."})
    cards.append({"label": "Daily data source health", "value": successes, "suffix": "/" + str(total_sources),
                  "period": report_date, "delta": str(status.get("failed_sources", 0)) + " failures · " + str(skipped_sources) + " awaiting setup",
                  "source_id": "collection_status", "description": "Only registered automatic sources, not all AI research websites."})
    cards.append({"label": "Core publication coverage", "value": sum(core_counts.values()), "suffix": " links",
                  "period": "indexed archive", "delta": str(len(publisher_counts)) + " publishers",
                  "source_id": "article_index", "description": "Article index records, not readership or importance."})

    findings = []
    if eu_delta:
        findings.append({
            "kind": "observed", "topic": "enterprise",
            "title": "EU business AI-use share changed " + _display_delta(eu_delta),
            "text": "Eurostat reports %.2f%% in %s versus %.2f%% in %s, an increase of %.2f percentage points. This is adoption, not realized ROI." % (
                eu_delta["latest"], eu_delta["latest_period"], eu_delta["previous"],
                eu_delta["previous_period"], eu_delta["change_pp"]),
            "source_ids": ["eurostat_enterprise_ai_adoption"]
        })
    if world_delta:
        findings.append({
            "kind": "observed", "topic": "enterprise",
            "title": "Surveyed organizations' reported AI use changed " + _display_delta(world_delta),
            "text": "The OWID/McKinsey all-geographies survey reports %.2f%% in %s versus %.2f%% in %s. It covers use in at least one function and is not directly comparable with Eurostat." % (
                world_delta["latest"], world_delta["latest_period"], world_delta["previous"], world_delta["previous_period"]),
            "source_ids": ["owid_business_ai_adoption"]
        })
    if len(regional) >= 2:
        high = max(regional, key=regional.get)
        low = min(regional, key=regional.get)
        findings.append({
            "kind": "observed", "topic": "enterprise",
            "title": "Regional survey spread: %.1f pp in %s" % (regional[high] - regional[low], latest_survey_year),
            "text": "Within the same OWID/McKinsey organization-use survey, %s records %.1f%% and %s records %.1f%%, a %.1f percentage-point observed range. Regional definitions overlap and sampling/weighting differ; this does not establish causality or representative country-level demand." % (
                high, regional[high], low, regional[low], regional[high] - regional[low]),
            "source_ids": ["owid_business_ai_adoption"]
        })
    findings.append({
        "kind": "coverage", "topic": "publications",
        "title": "%d indexed links; %d from core publisher feeds" % (len(articles), sum(core_counts.values())),
        "text": "Counts reflect the configured RSS/Atom feeds and article classifications, not global research investment or market demand. Source-mix changes can alter topic proportions.",
        "source_ids": ["article_index"]
    })
    if changes:
        chosen = next((c for c in changes if c["metric_id"] == "github.stars"), changes[0])
        findings.append({
            "kind": "proxy", "topic": "engineering",
            "title": chosen["entity_id"] + ": " + ("%+.0f" % chosen["absolute_change"]) + " " + chosen["metric_id"],
            "text": "Between %s and %s, this tracked platform measure changed from %s to %s. This is not commercial adoption or company revenue." % (
                chosen["previous_period"], chosen["current_period"], chosen["previous"], chosen["current"]),
            "source_ids": [chosen["source_id"]]
        })
    else:
        findings.append({
            "kind": "insufficient_history", "topic": "usage",
            "title": "No defensible daily usage-growth trend yet",
            "text": "Only %d unique daily snapshot date(s) are stored. At least two comparable dates for the same entity and metric are required to compute changes. List prices and GitHub stars are proxies, not token volume or commercial revenue." % snapshots_days,
            "source_ids": []
        })

    company_charts, company_findings, company_growth = financial_aggregation(financial_rows or [], registry)
    findings.extend(company_findings)
    missing = [
        {"id": "actual_ai_revenue", "title": "Verified AI-specific revenue", "reason": "No audited AI-only revenue series is connected. Cloud segment revenue is not equivalent to AI revenue."},
        {"id": "paid_enterprise_use", "title": "Representative enterprise AI payments", "reason": "Ramp and private purchase/payment data remain licensed or sample-limited."},
        {"id": "agent_transactions", "title": "Completed agent actions and transactions", "reason": "No comparable transaction/fulfillment outcomes dataset is connected."},
        {"id": "infrastructure_roi", "title": "AI infrastructure return on invested capital", "reason": "Even with company-wide audited PPE cash spending, AI-specific expenditure, leasing, contribution profits and segment revenue are not isolated."},
    ]
    health = {
        "registered_automatic": total_sources, "successful": successes,
        "failed": status.get("failed_sources", 0), "skipped_config": skipped_sources,
        "failures": [{"source_id": s["source_id"], "error": s.get("error"), "last_success_at": s.get("last_success_at")}
                     for s in status.get("sources", []) if s["status"] != "ok"],
        "distinct_snapshot_days": snapshots_days
    }
    result = {
        "schema_version": 1, "report_date": report_date,
        "generated_at": as_of, "title": "AI Industry Evidence Monitor",
        "method": "Deterministic, source-bound aggregation. No LLM-generated numeric assertions.",
        "cards": cards, "findings": findings,
        "charts": adoption_charts + ([regional_chart] if regional_chart else []) +
                  company_charts + price_charts + ([multiple_chart] if multiple_chart else []) +
                  [article_chart] + ([repo_chart] if repo_chart else []),
        "company_fiscal_capex_changes": company_growth,
        "daily_changes": changes[:30],
        "coverage_gaps": missing,
        "health": health,
        "research_note": (
            "Adoption surveys, API model list prices, selected repository popularity, and publisher "
            "article counts measure different populations and outcomes. No causal claims or "
            "cross-dataset market shares can be made without compatible denominators."
        )
    }
    return result


def markdown_report(report, registry):
    sources = {s["id"]: s for section in ("feeds", "apis", "datasets", "financials", "research")
               for s in registry.get(section, [])}
    lines = [
        "# AI Industry Evidence Monitor — " + report["report_date"], "",
        "**Evidence cutoff:** " + report["generated_at"] + " (UTC).",
        "This report uses deterministic aggregation of stored observations. Percentages use original survey periods, not collection dates.", "",
        "## Executive observations", ""
    ]
    for f in report["findings"]:
        lines.extend(["### " + f["title"], "", f["text"], ""])
        for source_id in f["source_ids"]:
            src = sources.get(source_id)
            if src:
                lines.append("Source: [" + src["title"] + "](" + src.get("homepage", src.get("url", "")) + ")")
            elif source_id == "sec_edgar":
                lines.append("Source: " + f.get("source_url", "https://www.sec.gov/"))

        if f["source_ids"]:
            lines.append("")
    lines += ["## Comparable observations", ""]
    for chart in report["charts"]:
        lines += ["### " + chart["title"], "", chart["caveat"], ""]
        if chart["type"] == "line":
            lines += ["| Reporting period | Value |", "| --- | ---: |"]
            for row in chart["series"][0]["points"]:
                lines.append("| %s | %s%% |" % (row["period"], row["value"]))
        else:
            lines += ["| Group | Observation |", "| --- | ---: |"]
            for row in chart["points"]:
                lines.append("| %s | %s %s |" % (row["label"], row["value"], chart["unit"]))
        lines += ["", "Source: " + chart["source_url"], ""]
    lines += ["## What cannot yet be concluded", ""]
    for gap in report["coverage_gaps"]:
        lines.append("- **%s:** %s" % (gap["title"], gap["reason"]))
    lines += ["", "## Collection and comparability", "",
              "- Source health: %d/%d succeeded." % (
                  report["health"]["successful"], report["health"]["registered_automatic"]),
              "- Distinct daily API snapshot dates: " + str(report["health"]["distinct_snapshot_days"]) + ".",
              "- " + report["research_note"], "",
              "Full original snapshots and normalized records are tracked in the repository.",
              ""]
    return "\n".join(lines)
