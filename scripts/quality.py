"""Evidence quality gate and operations digest (warnings never fabricate data).

The audit is deterministic and uses saved evidence, not external sources.
It never interprets a missing value as zero or silently edits observations.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def _parse_time(s):
    try:
        parsed = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (AttributeError, ValueError, TypeError):
        return None


def quality_report(status, daily_metrics, historical, financials, articles,
                   sources, raw_paths=None, as_of=None):
    as_of = as_of or status.get("generated_at") or datetime.now(timezone.utc).isoformat()
    now = _parse_time(as_of)
    by_source = {x["source_id"]: x for x in status.get("sources", [])}
    registered = [x for section in ("feeds", "apis", "datasets", "financials")
                  for x in sources.get(section, [])]
    warnings = []
    skipped, failed, stale, empty = [], [], [], []
    source_rows = []

    for src in registered:
        record = by_source.get(src["id"], {})
        state = record.get("status", "not_collected")
        last = record.get("last_success_at")
        last_time = _parse_time(last)
        age = (now - last_time).total_seconds() / 86400 if now and last_time else None
        freshness = "never_collected" if last_time is None else (
            "stale" if age is not None and age > 3 else "fresh"
        )
        if state == "skipped_config":
            skipped.append(src["id"])
            warnings.append({"severity":"configuration", "source_id":src["id"],
                             "type":"access_not_configured",
                             "message":record.get("reason", "Required source access configuration missing.")})
        elif state == "failed":
            failed.append(src["id"])
            warnings.append({"severity":"error", "source_id":src["id"],
                             "type":"collection_failed",
                             "message":record.get("error", "Source collection failed.")})
        if freshness == "stale":
            stale.append(src["id"])
            warnings.append({"severity":"warning", "source_id":src["id"],
                             "type":"stale_source",
                             "message":"Last successful response %.1f days before report cutoff." % age})
        if state == "ok" and record.get("records", 0) == 0 and src.get("mode") == "feed":
            empty.append(src["id"])
            # Empty feed records can result from real low publication volume:
            # a non-blocking observation, not a pipeline failure.
        source_rows.append({
            "source_id":src["id"],"mode":src.get("mode"),"status":state,
            "last_success_at":last,"freshness":freshness,
            "records":record.get("records",0),"age_days":round(age,1) if age is not None else None,
            "raw_path":record.get("raw_path")
        })

    # Only compute changes for matching entity+metric+unit across DISTINCT dates.
    # An intraday correction is not time-series growth.
    by_metric = defaultdict(dict)
    for row in daily_metrics:
        key=(row.get("source_id"), row.get("entity_id"), row.get("metric_id"), row.get("unit"))
        day=row.get("period")
        if not day:
            continue
        old=by_metric[key].get(day)
        if old is None or row.get("observed_at","") > old.get("observed_at",""):
            by_metric[key][day]=row
    anomalies=[]
    for key,days in by_metric.items():
        if len(days)<2:
            continue
        last_two=sorted(days)[-2:]
        old,new=days[last_two[0]],days[last_two[1]]
        a,b=old["value"],new["value"]
        # Cumulative GitHub stars/forks should not materially shrink overnight.
        # Repository archiving/deletion or API schema changes can legitimately
        # cause discontinuities; only WARN and preserve both raw facts.
        if (key[2] in ("github.stars","github.forks") and a>100
            and b>=0 and b/a<0.75):
            anomalies.append({"type":"large_cumulative_drop",
                              "metric_id":key[2],"source_id":key[0],
                              "entity_id":key[1],
                              "old":a,"new":b,"previous_period":last_two[0],
                              "current_period":last_two[1],
                              "message":"Selected cumulative GitHub metric dropped >25%; investigate before using as growth."})
    anomalies.sort(key=lambda a:(a["source_id"],a["metric_id"]))
    warnings.extend({"severity":"warning","source_id":a["source_id"],
                     "type":a["type"],"message":a["message"]} for a in anomalies)
    archive_count=len(raw_paths or [])
    if financials and any(r.get("period_type")!="fiscal_year_end" for r in financials):
        warnings.append({"severity":"error","source_id":"sec_edgar",
                         "type":"invalid_fiscal_period", "message":"SEC fiscal period contract mismatch."})
    if historical and any(r.get("period_type")!="calendar_year" for r in historical):
        warnings.append({"severity":"error","source_id":"economic_datasets",
                         "type":"invalid_survey_period", "message":"Survey period must denote original year."})
    return {
        "schema_version":1,"generated_at":as_of,
        "sources":{"registered":len(registered),
                   "ok":sum(s["status"]=="ok" for s in source_rows),
                   "failed":len(failed),"waiting_for_configuration":len(skipped),
                   "stale":len(stale),"empty_feeds":len(empty)},
        "records":{"platform_daily":len(daily_metrics),
                   "historical_survey":len(historical),"sec_financial":len(financials),
                   "indexed_articles":len(articles),
                   "immutable_raw_snapshots":archive_count},
        "sources_detail":source_rows,
        "warnings":warnings,
        "anomalies":anomalies,
        "methodology":"Warnings flag potential quality issues, never overwrite original observations or replace unavailable values with zero.",
        "notes":[
            "Published statistical periods are separate from the collection date.",
            "SEC sources require an identifiable User-Agent with a real contact email.",
            "US Census BTOS wording changed in November/December 2025; do not splice old and new series.",
            "Article counts are feed coverage, not market demand; OpenRouter prices are unweighted listings."
        ],
    }


def markdown_report(report):
    s=report["sources"]; rec=report["records"]
    lines=["# AI Evidence Quality Report — "+report["generated_at"][:10], "",
           "Evidence cutoff: "+report["generated_at"],"",
           "## Coverage", "",
           "- %d/%d automatic sources OK; %d failed, %d awaiting identity/configuration, %d stale." % (
               s["ok"],s["registered"],s["failed"],s["waiting_for_configuration"],s["stale"]),
           "- Daily platform rows: "+str(rec["platform_daily"]),
           "- Historical survey rows: "+str(rec["historical_survey"]),
           "- SEC financial rows: "+str(rec["sec_financial"]),
           "- Indexed articles: "+str(rec["indexed_articles"]),
           "- Immutable raw response snapshots: "+str(rec["immutable_raw_snapshots"]),"",
           "## Follow-up warnings",""]
    if not report["warnings"]:
        lines.append("No outstanding collector/configuration/anomaly warnings.")
    else:
        for w in report["warnings"]:
            lines.append("- **%s** / %s — %s" % (w["severity"],w["source_id"],w["message"]))
    lines.extend(["","## Statistical interpretation guards",""])
    for note in report["notes"]:
        lines.append("- "+note)
    lines.extend(["",report["methodology"],""])
    return "\n".join(lines)
