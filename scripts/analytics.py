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


def make_analysis(snapshot_rows, annual_rows, articles, registry, status,
                  as_of=None):
    """Build a pure deterministic report from real stored records.

    as_of defaults to collection health timestamp, not machine/build time.
    This keeps report files stable on reruns without new evidence.
    """
    as_of = as_of or status.get("generated_at") or datetime.now(timezone.utc).isoformat()
    report_date = as_of[:10]
    sources = {s["id"]: s for section in ("feeds", "apis", "datasets", "research")
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
    total_sources = successes + status.get("failed_sources", 0)

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
                  "period": report_date, "delta": str(status.get("failed_sources", 0)) + " source failures",
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

    missing = [
        {"id": "actual_ai_revenue", "title": "Verified AI-specific revenue", "reason": "No audited AI-only revenue series is connected. Cloud segment revenue is not equivalent to AI revenue."},
        {"id": "paid_enterprise_use", "title": "Representative enterprise AI payments", "reason": "Ramp and private purchase/payment data remain licensed or sample-limited."},
        {"id": "agent_transactions", "title": "Completed agent actions and transactions", "reason": "No comparable transaction/fulfillment outcomes dataset is connected."},
        {"id": "infrastructure_roi", "title": "AI infrastructure return on invested capital", "reason": "Capex and disclosed revenue/profit series still require audited filing ingestion and segmentation."},
    ]
    health = {
        "registered_automatic": total_sources, "successful": successes,
        "failed": status.get("failed_sources", 0),
        "failures": [{"source_id": s["source_id"], "error": s.get("error"), "last_success_at": s.get("last_success_at")}
                     for s in status.get("sources", []) if s["status"] != "ok"],
        "distinct_snapshot_days": snapshots_days
    }
    result = {
        "schema_version": 1, "report_date": report_date,
        "generated_at": as_of, "title": "AI Industry Evidence Monitor",
        "method": "Deterministic, source-bound aggregation. No LLM-generated numeric assertions.",
        "cards": cards, "findings": findings,
        "charts": adoption_charts + price_charts + [article_chart] + ([repo_chart] if repo_chart else []),
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
    sources = {s["id"]: s for section in ("feeds", "apis", "datasets", "research")
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
