#!/usr/bin/env python3
"""AI industry evidence pipeline. Standard-library only; Python 3.11+."""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import email.utils
import gzip
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from economic import parse_dataset
from analytics import make_analysis, markdown_report
from sec_financials import annual_financials_adapter
from quality import quality_report, markdown_report as quality_markdown

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
UTC = dt.timezone.utc
MAX_BYTES = 8_000_000
ATOM = "{http://www.w3.org/2005/Atom}"
DUBLIN = "{http://purl.org/dc/elements/1.1/}"
OPENROUTER_FAMILIES = ("openai", "anthropic", "google", "deepseek", "qwen")
USER_AGENT = "AIIndustryResearch/0.1 (+https://github.com/BestNathan/ai-industry-research)"


def now_utc() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso(t: dt.datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n" for x in rows), encoding="utf-8")


def canonical_url(url: str) -> str:
    raw = html.unescape(url or "").strip()
    p = urlsplit(raw)
    if p.scheme not in ("http", "https") or not p.netloc:
        return ""
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not (k.lower().startswith("utm_") or k.lower() in ("fbclid", "gclid"))]
    path = (p.path.rstrip("/") or "/")
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, urlencode(query), ""))


def article_id(url: str) -> str:
    return hashlib.sha256(canonical_url(url).encode("utf-8")).hexdigest()[:24]


def clean_text(value: str | None, limit: int = 400) -> str:
    value = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", value or "")
    value = re.sub(r"<[^>]*>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()[:limit]


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = email.utils.parsedate_to_datetime(value)
        except (ValueError, TypeError, IndexError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return iso(parsed)


def category_for(title: str, summary: str, source: dict, taxonomy: list[dict]) -> tuple[str, list[str]]:
    text = (title + " " + summary[:180]).lower()
    matches = []
    for cat in taxonomy:
        score = sum(2 if term in title.lower() else 1 for term in cat["keywords"] if term in text)
        if score:
            matches.append((score, cat["id"]))
    matches.sort(key=lambda item: (-item[0], item[1]))
    tags = [x for _, x in matches[:4]]
    if source["category"] not in tags:
        tags.append(source["category"])
    return (matches[0][1] if matches else source["category"], tags[:5])


def parse_feed(payload: bytes, source: dict, checked_at: str, raw_path: str,
               raw_sha256: str, taxonomy: list[dict], max_age_days: int = 30) -> list[dict]:
    root = ET.fromstring(payload)
    entries = root.findall(".//item")
    atom = False
    if not entries:
        entries = root.findall(".//" + ATOM + "entry")
        atom = True
    result = []
    checked_date = dt.datetime.fromisoformat(checked_at)
    for entry in entries[:90]:
        title = clean_text(entry.findtext(ATOM + "title" if atom else "title"), 300)
        if atom:
            link = ""
            for node in entry.findall(ATOM + "link"):
                if node.attrib.get("rel", "alternate") == "alternate":
                    link = node.attrib.get("href", "")
                    break
            pub = entry.findtext(ATOM + "published") or entry.findtext(ATOM + "updated")
            description = entry.findtext(ATOM + "summary") or entry.findtext(ATOM + "content")
        else:
            link = entry.findtext("link") or entry.findtext("guid") or ""
            pub = entry.findtext("pubDate") or entry.findtext(DUBLIN + "date")
            description = entry.findtext("description") or entry.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
        url = canonical_url(link)
        if not title or not url:
            continue
        published = parse_date(pub)
        if published:
            date = dt.datetime.fromisoformat(published)
            if date < checked_date - dt.timedelta(days=max_age_days):
                continue
            if date > checked_date + dt.timedelta(days=2):
                continue
        summary = clean_text(description, 320)
        category, tags = category_for(title, summary, source, taxonomy)
        result.append({
            "id": article_id(url), "title": title, "url": url,
            "source_id": source["id"], "publisher": source["publisher"],
            "primary_category": category, "tags": tags,
            "published_at": published, "discovered_at": checked_at,
            "summary": summary, "official_feed": source["official"],
            "original_publisher_link": url,
            "raw_path": raw_path, "raw_sha256": raw_sha256,
            "content_policy": "metadata_and_short_feed_excerpt"
        })
    return result


def observation(source: dict, entity: str, metric: str, value, unit: str,
                methodology: str, checked_at: str, raw_path: str, raw_sha256: str) -> dict | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return {
        "source_id": source["id"], "entity_id": entity,
        "metric_id": metric, "value": value, "unit": unit,
        "observed_at": checked_at, "period": checked_at[:10],
        "geography": "global", "evidence_type": "platform_observation",
        "methodology": methodology, "raw_path": raw_path, "raw_sha256": raw_sha256
    }


def parse_metrics(payload: bytes, source: dict, checked_at: str,
                  raw_path: str, raw_sha256: str) -> list[dict]:
    doc = json.loads(payload)
    kind = source["kind"]
    result = []

    def add(entity, metric, value, unit, method):
        row = observation(source, entity, metric, value, unit, method, checked_at, raw_path, raw_sha256)
        if row is not None:
            result.append(row)

    if kind == "github_repository":
        repo = source["repo"]
        if not isinstance(doc, dict) or doc.get("full_name", "").lower() != repo.lower():
            raise ValueError("unexpected GitHub repository payload")
        for key, metric in (("stargazers_count", "github.stars"),
                            ("forks_count", "github.forks"),
                            ("open_issues_count", "github.open_issues")):
            add("github:" + repo, metric, doc.get(key), "count", "Public GitHub REST /repos repository field " + key)
    elif kind == "huggingface_models":
        if not isinstance(doc, list):
            raise ValueError("unexpected Hugging Face models payload")
        for model in doc[:20]:
            if not isinstance(model, dict) or not model.get("id"):
                continue
            entity = "huggingface:" + model["id"]
            add(entity, "huggingface.downloads", model.get("downloads"), "downloads",
                "Platform-reported Hugging Face model downloads (rolling window, per API)")
            add(entity, "huggingface.likes", model.get("likes"), "count",
                "Hugging Face platform model likes")
    elif kind == "openrouter_prices":
        models = doc.get("data") if isinstance(doc, dict) else None
        if not isinstance(models, list):
            raise ValueError("unexpected OpenRouter models payload")
        groups = defaultdict(list)
        for model in models:
            if not isinstance(model, dict):
                continue
            provider = str(model.get("id", "")).split("/", 1)[0].lower()
            if provider in OPENROUTER_FAMILIES:
                groups[provider].append(model)
        for provider in OPENROUTER_FAMILIES:
            # The most recently created 12 models per family are representative
            # but are *not* a market-wide weighted-average price.
            selected = sorted(groups[provider], key=lambda x: x.get("created") or 0, reverse=True)[:12]
            for model in selected:
                entity = "openrouter:" + model["id"]
                pricing = model.get("pricing") or {}
                for field, metric in (("prompt", "openrouter.list_price_input_usd_per_million"),
                                      ("completion", "openrouter.list_price_output_usd_per_million")):
                    try:
                        price = float(pricing.get(field))
                    except (TypeError, ValueError, OverflowError):
                        continue
                    if price >= 0:
                        add(entity, metric, round(price * 1_000_000, 8),
                            "USD per 1M tokens", "OpenRouter model catalog " + field + " list price, not realized revenue")
    else:
        raise ValueError("unrecognized API kind " + str(kind))
    return result


def fetch(url: str, user_agent: str | None = None, max_bytes: int = MAX_BYTES) -> bytes:
    headers = {"User-Agent": user_agent or USER_AGENT, "Accept": "application/json, application/rss+xml, application/atom+xml, application/xml, */*"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = "Bearer " + token
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    error = None
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=headers), timeout=20) as response:
                content = response.read(max_bytes + 1)
            if len(content) > max_bytes:
                raise ValueError("response exceeds configured {} MB limit".format(max_bytes // 1_000_000))
            return content
        except (OSError, HTTPError, URLError, ValueError) as exc:
            error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(str(error))


def process_source(source: dict, day: str, checked_at: str,
                   taxonomy: list[dict]) -> tuple[list[dict], list[dict], dict]:
    status = {"source_id": source["id"], "mode": source["mode"],
              "checked_at": checked_at, "status": "ok", "records": 0}
    if source["mode"] == "financial" and not os.environ.get("SEC_USER_AGENT", "").strip():
        status.update({"status": "skipped_config", "reason": "Set Actions variable SEC_USER_AGENT (project name + real contact email) to enable official SEC EDGAR requests."})
        return [], [], status
    try:
        endpoints = [source["url"], *source.get("fallback_urls", [])]
        errors = []
        for url in endpoints:
            try:
                payload = (fetch(url, user_agent=os.environ["SEC_USER_AGENT"], max_bytes=30_000_000)
                           if source["mode"] == "financial" else fetch(url))
                checksum = hashlib.sha256(payload).hexdigest()
                suffix = ("xml.gz" if source["mode"] == "feed" else
                          "csv.gz" if source["mode"] == "dataset" and source["kind"].startswith("owid") else "json.gz")
                # Deduplicate identical upstream evidence across collection days.
                path = DATA / "raw" / "immutable" / (source["id"] + "-" + checksum[:16] + "." + suffix)
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    path.write_bytes(gzip.compress(payload, compresslevel=6, mtime=0))
                raw_path = path.relative_to(ROOT).as_posix()
                if source["mode"] == "feed":
                    articles = parse_feed(payload, source, checked_at, raw_path, checksum, taxonomy)
                    metrics = []
                elif source["mode"] == "dataset":
                    articles = []
                    metrics = parse_dataset(payload, source, checked_at, raw_path, checksum)
                elif source["mode"] == "financial":
                    articles = []
                    metrics = annual_financials_adapter(payload, source, checked_at, raw_path, checksum)
                else:
                    articles = []
                    metrics = parse_metrics(payload, source, checked_at, raw_path, checksum)
                status.update({"records": len(articles) + len(metrics), "raw_path": raw_path,
                               "raw_sha256": checksum, "effective_url": url,
                               "fallback_used": url != source["url"]})
                return articles, metrics, status
            except Exception as exc:
                errors.append(url + ": " + type(exc).__name__ + " " + str(exc)[:130])
        raise RuntimeError(" | ".join(errors))
    except Exception as exc:
        status.update({"status": "failed", "error": (type(exc).__name__ + ": " + str(exc))[:300]})
        return [], [], status


def metric_key(row: dict) -> tuple:
    return row["source_id"], row["entity_id"], row["metric_id"], row["period"]


def collect() -> int:
    checked_at = iso(now_utc())
    day = checked_at[:10]
    sources = read_json(ROOT / "config" / "sources.json")
    taxonomy = read_json(ROOT / "config" / "taxonomy.json")["categories"]
    enabled = sources["feeds"] + sources["apis"] + sources.get("datasets", []) + sources.get("financials", [])
    dataset_ids = {s["id"] for s in sources.get("datasets", [])}
    financial_ids = {s["id"] for s in sources.get("financials", [])}
    old_health = read_json(DATA / "status" / "latest.json", {})
    previous_by_id = {s["source_id"]: s for s in old_health.get("sources", [])}
    statuses, incoming_articles, incoming_metrics, incoming_datasets, incoming_financials = [], [], [], [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:
        futures = [pool.submit(process_source, source, day, checked_at, taxonomy) for source in enabled]
        for source, future in zip(enabled, futures):
            articles, metrics, status = future.result()
            previous_status = previous_by_id.get(source["id"], {})
            status["last_success_at"] = (
                status["checked_at"] if status["status"] == "ok"
                else previous_status.get("last_success_at") or (
                    previous_status.get("checked_at") if previous_status.get("status") == "ok" else None
                )
            )
            if status["last_success_at"]:
                status["age_days"] = round(
                    (dt.datetime.fromisoformat(checked_at) -
                     dt.datetime.fromisoformat(status["last_success_at"])).total_seconds() / 86400, 2)
            else:
                status["age_days"] = None
            status["freshness"] = (
                "fresh" if status["status"] == "ok" else
                "stale" if status["last_success_at"] else "never_collected"
            )
            incoming_articles.extend(articles)
            if source["id"] in dataset_ids:
                incoming_datasets.extend(metrics)
            elif source["id"] in financial_ids:
                incoming_financials.extend(metrics)
            else:
                incoming_metrics.extend(metrics)
            statuses.append(status)
            print("{}: {} ({} records)".format(source["id"], status["status"], status["records"]))

    article_path = DATA / "articles" / (day + ".jsonl")
    historic_ids = set()
    for file in sorted((DATA / "articles").glob("*.jsonl")):
        if file != article_path:
            historic_ids.update(row["id"] for row in read_jsonl(file))
    all_today = read_jsonl(article_path) + incoming_articles
    articles_by_id = {}
    for row in all_today:
        if row["id"] not in historic_ids:
            articles_by_id.setdefault(row["id"], row)
    articles = sorted(articles_by_id.values(),
                      key=lambda x: (x.get("published_at") or x["discovered_at"], x["id"]), reverse=True)

    metric_path = DATA / "metrics" / (day + ".jsonl")
    by_key = {metric_key(row): row for row in read_jsonl(metric_path)}
    by_key.update({metric_key(row): row for row in incoming_metrics})
    metrics = sorted(by_key.values(), key=lambda x: (x["metric_id"], x["entity_id"], x["source_id"]))
    write_jsonl(article_path, articles)
    write_jsonl(metric_path, metrics)

    # Annual data is keyed by its original statistical reporting year.
    # Preserve unchanged records (including first-observed timestamp and raw
    # provenance), and replace only when the provider revises a value.
    datasets_updated = 0
    for source in sources.get("datasets", []):
        fresh = [m for m in incoming_datasets if m["source_id"] == source["id"]]
        if not fresh:
            continue
        dataset_path = DATA / "datasets" / (source["id"] + ".jsonl")
        previous_dataset = {metric_key(m): m for m in read_jsonl(dataset_path)}
        for row in fresh:
            key = metric_key(row)
            old = previous_dataset.get(key)
            if old and old["value"] == row["value"] and old["unit"] == row["unit"] and old["methodology"] == row["methodology"]:
                continue
            previous_dataset[key] = row
            datasets_updated += 1
        updated_rows = sorted(previous_dataset.values(), key=lambda r: (r["metric_id"], r["entity_id"], r["period"]))
        write_jsonl(dataset_path, updated_rows)

    # Preserve immutable original SEC records. Revisions are recorded by
    # accession / filed date with source payload provenance, but the current
    # normalized view contains one chosen filing per fiscal period and tag.
    financials_updated = 0
    for source in sources.get("financials", []):
        fresh = [m for m in incoming_financials if m["source_id"] == source["id"]]
        if not fresh:
            continue
        financial_path = DATA / "financials" / (source["ticker"] + ".jsonl")
        existing = {metric_key(m): m for m in read_jsonl(financial_path)}
        for row in fresh:
            key = metric_key(row)
            previous = existing.get(key)
            if previous and (previous["value"], previous["accession"], previous["xbrl_tag"]) == (
                    row["value"], row["accession"], row["xbrl_tag"]):
                continue
            existing[key] = row
            financials_updated += 1
        write_jsonl(financial_path, sorted(existing.values(), key=lambda r: (r["metric_id"], r["period"])))

    successful = sum(s["status"] == "ok" for s in statuses)
    skipped = [s["source_id"] for s in statuses if s["status"] == "skipped_config"]
    failed = [s["source_id"] for s in statuses if s["status"] == "failed"]
    source_by_id = {s["id"]: s for s in enabled}
    # Prioritize official/primary industry engineering publications in the daily digest.
    # This is deterministic source-based ordering, NOT a model-generated quality claim.
    digest_articles = sorted(
        articles,
        key=lambda a: (
            source_by_id[a["source_id"]].get("priority") != "core",
            a["source_id"] == "arxiv_ai",
            -dt.datetime.fromisoformat(a.get("published_at") or a["discovered_at"]).timestamp()
        )
    )[:20]
    past_files = sorted(f for f in (DATA / "metrics").glob("*.jsonl") if f != metric_path)
    previous = read_jsonl(past_files[-1]) if past_files else []
    previous_by_key = {(m["source_id"], m["entity_id"], m["metric_id"]): m for m in previous}
    changes = []
    for row in metrics:
        key = (row["source_id"], row["entity_id"], row["metric_id"])
        old = previous_by_key.get(key)
        if old is None or old["unit"] != row["unit"]:
            continue
        delta = row["value"] - old["value"]
        changes.append({
            "source_id": row["source_id"], "entity_id": row["entity_id"],
            "metric_id": row["metric_id"], "unit": row["unit"],
            "current": row["value"], "previous": old["value"],
            "previous_period": old["period"], "absolute_change": delta,
            "relative_change_pct": round(100 * delta / old["value"], 4) if old["value"] else None
        })
    report = {
        "date": day, "generated_at": checked_at,
        "source_count": len(enabled), "sources_ok": successful, "sources_failed": len(failed),
        "sources_skipped_configuration": len(skipped), "skipped_source_ids": skipped,
        "failed_source_ids": failed, "new_articles": len(articles),
        "metric_observations": len(metrics),
        "historical_dataset_rows_added_or_revised": datasets_updated,
        "sec_financial_rows_added_or_revised": financials_updated,
        "articles_by_category": dict(sorted(Counter(x["primary_category"] for x in articles).items())),
        "headline_articles": [
            {"title": row["title"], "url": row["url"], "source_id": row["source_id"],
             "category": row["primary_category"]}
            for row in digest_articles
        ],
        "comparable_metric_changes": changes,
        "note": "Metrics are platform/API snapshots collected on this date; articles may have earlier publication dates."
    }
    write_json(DATA / "reports" / "daily" / (day + ".json"), report)
    lines = ["# AI Industry Research — " + day, "",
             "Collected " + checked_at + " (UTC).", "",
             "- Sources: {} succeeded, {} failed".format(successful, len(failed)),
             "- New articles: " + str(len(articles)),
             "- Metric observations: " + str(len(metrics)),
             "- Historical dataset rows added/revised: " + str(datasets_updated),
             "- SEC annual filing rows added/revised: " + str(financials_updated),
             "- SEC sources awaiting configured fair-access User-Agent: " + str(len(skipped)), "",
             "## New article links", ""]
    lines.extend("- [{}]({}) — {}".format(a["title"].replace("[", "").replace("]", ""),
                                            a["url"], a["source_id"]) for a in report["headline_articles"])
    lines += ["", "## Collection problems", ""]
    lines.extend("- " + entry["source_id"] + ": " + entry.get("error", "") for entry in statuses if entry["status"] == "failed")
    lines.extend("- " + entry["source_id"] + ": " + entry.get("reason", "") for entry in statuses if entry["status"] == "skipped_config")
    if not failed:
        lines.append("No source failures.")
    (DATA / "reports" / "daily" / (day + ".md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(DATA / "status" / "latest.json", {
        "generated_at": checked_at, "date": day, "successful_sources": successful,
        "failed_sources": len(failed), "skipped_sources": len(skipped), "sources": statuses
    })
    print("Collected {} articles; {} metric rows; {} source failures".format(len(articles), len(metrics), len(failed)))
    return 0 if successful else 2


def all_rows(section: str) -> list[dict]:
    results = []
    for file in sorted((DATA / section).glob("*.jsonl")):
        results.extend(read_jsonl(file))
    return results


def analyze() -> None:
    """Create versioned, citation-aware analytical reports from historical evidence."""
    sources = read_json(ROOT / "config" / "sources.json")
    status = read_json(DATA / "status" / "latest.json", {})
    metrics = all_rows("metrics")
    annual = all_rows("datasets")
    articles = all_rows("articles")
    financials = all_rows("financials")
    report = make_analysis(metrics, annual, articles, sources, status, financial_rows=financials)
    day = report["report_date"]
    directory = DATA / "reports" / "analysis"
    write_json(directory / "latest.json", report)
    write_json(directory / (day + ".json"), report)
    markdown = markdown_report(report, sources)
    (directory / (day + ".md")).write_text(markdown, encoding="utf-8")
    raw_files = list((DATA / "raw").glob("**/*.gz"))
    quality = quality_report(status, metrics, annual, financials, articles,
                             sources, raw_paths=raw_files)
    quality_dir = DATA / "reports" / "quality"
    write_json(quality_dir / "latest.json", quality)
    write_json(quality_dir / (day + ".json"), quality)
    (quality_dir / (day + ".md")).write_text(quality_markdown(quality), encoding="utf-8")
    print("Analyzed {} findings and {} charts for {}".format(
        len(report["findings"]), len(report["charts"]), day))


def build() -> None:
    website = ROOT / "_site"
    if website.exists():
        shutil.rmtree(website)
    shutil.copytree(ROOT / "web", website)
    (website / "data").mkdir(exist_ok=True)
    sources = read_json(ROOT / "config" / "sources.json")
    taxonomy = read_json(ROOT / "config" / "taxonomy.json")
    status = read_json(DATA / "status" / "latest.json", {})
    analysis = read_json(DATA / "reports" / "analysis" / "latest.json", {})
    quality = read_json(DATA / "reports" / "quality" / "latest.json", {})
    metrics = all_rows("metrics") + all_rows("datasets") + all_rows("financials")
    articles = all_rows("articles")
    article_map = {a["id"]: a for a in articles}
    articles = sorted(article_map.values(),
                      key=lambda a: (a.get("published_at") or a["discovered_at"], a["id"]), reverse=True)

    series_groups = defaultdict(list)
    latest_by_key = {}
    for m in metrics:
        key = (m["metric_id"], m["entity_id"])
        series_groups[key].append({"date": m["period"], "value": m["value"]})
        if key not in latest_by_key or m["period"] > latest_by_key[key]["period"] or (
            m["period"] == latest_by_key[key]["period"] and m["observed_at"] > latest_by_key[key]["observed_at"]
        ):
            latest_by_key[key] = m
    # Limit public page JSON size, but retain every raw and normalized observation in Git.
    prioritized = sorted(latest_by_key, key=lambda k: (
        0 if k[0] == "enterprise.ai_adoption_share_pct" else
        0 if k[0].startswith("company.") else
        1 if k[0] == "github.stars" else
        2 if k[0] == "huggingface.downloads" else
        3 if k[0].startswith("openrouter.") else 4,
        k[1]))
    selected = prioritized[:140]
    series = [{
        "metric_id": key[0], "entity_id": key[1],
        "unit": latest_by_key[key]["unit"],
        "source_id": latest_by_key[key]["source_id"],
        "geography": latest_by_key[key]["geography"],
        "period_type": latest_by_key[key].get("period_type", "collection_day"),
        "evidence_type": latest_by_key[key]["evidence_type"],
        "source_url": latest_by_key[key].get("source_url", ""),
        "methodology": latest_by_key[key]["methodology"],
        "points": sorted(series_groups[key], key=lambda x: x["date"])[-180:]
    } for key in selected]
    reports = []
    for file in sorted((DATA / "reports" / "daily").glob("*.json"), reverse=True)[:60]:
        reports.append(read_json(file))
    payload = {
        "built_at": iso(now_utc()),
        "stats": {"articles": len(articles), "observations": len(metrics),
                  "sources_automated": len(sources["feeds"]) + len(sources["apis"]) + len(sources.get("datasets", [])) + len(sources.get("financials", [])),
                  "sources_reference": len(sources["research"])},
        "taxonomy": taxonomy["categories"], "sources": sources,
        "source_health": status,
        "articles": articles[:1000], "series": series,
        "analysis": analysis, "quality": quality, "reports": reports
    }
    write_json(website / "data" / "dashboard.json", payload)
    (website / ".nojekyll").write_text("", encoding="utf-8")
    print("Built {} ({} articles, {} metric observations)".format(website, len(articles), len(metrics)))


def validate() -> None:
    sources = read_json(ROOT / "config" / "sources.json")
    taxonomy = read_json(ROOT / "config" / "taxonomy.json")
    categories = {c["id"] for c in taxonomy["categories"]}
    registered_ids = set()
    for src in sources["feeds"] + sources["apis"] + sources.get("datasets", []) + sources.get("financials", []) + sources["research"]:
        if src["id"] in registered_ids or src["category"] not in categories:
            raise AssertionError("duplicate source ID or invalid category " + src["id"])
        registered_ids.add(src["id"])
    for file in (sorted((DATA / "metrics").glob("*.jsonl")) +
                 sorted((DATA / "datasets").glob("*.jsonl")) +
                 sorted((DATA / "financials").glob("*.jsonl"))):
        rows = read_jsonl(file)
        keys = set()
        for row in rows:
            key = metric_key(row)
            if key in keys or not isinstance(row["value"], (int, float)) or not math.isfinite(row["value"]):
                raise AssertionError("invalid metric record in " + str(file))
            raw_file = ROOT / row["raw_path"]
            if not raw_file.exists():
                raise AssertionError("raw snapshot missing for " + str(file))
            if file.parent.name == "financials":
                if row.get("period_type") != "fiscal_year_end" or row.get("end") != row.get("period"):
                    raise AssertionError("SEC financial period is invalid")
                if row.get("evidence_type") != "sec_xbrl_filing" or not row.get("accession"):
                    raise AssertionError("SEC filing provenance missing")
            if file.parent.name == "datasets":
                if row.get("period_type") != "calendar_year" or not re.fullmatch(r"20[0-9]{2}", row["period"]):
                    raise AssertionError("dataset reporting year is invalid")
                if hashlib.sha256(gzip.decompress(raw_file.read_bytes())).hexdigest() != row["raw_sha256"]:
                    raise AssertionError("dataset raw provenance mismatch: " + str(raw_file))
            if file.parent.name == "financials":
                if hashlib.sha256(gzip.decompress(raw_file.read_bytes())).hexdigest() != row["raw_sha256"]:
                    raise AssertionError("SEC input archive hash mismatch")
            keys.add(key)
    article_ids = set()
    for file in sorted((DATA / "articles").glob("*.jsonl")):
        for row in read_jsonl(file):
            if row["id"] in article_ids or row["id"] != article_id(row["url"]):
                raise AssertionError("duplicate or invalid article id in " + str(file))
            article_ids.add(row["id"])
    print("Validation passed: {} sources and {} unique articles".format(len(registered_ids), len(article_ids)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["collect", "build", "validate", "analyze", "all"])
    args = parser.parse_args()
    if args.command == "validate":
        validate()
    elif args.command == "build":
        build()
    elif args.command == "collect":
        return collect()
    elif args.command == "analyze":
        analyze()
    else:
        result = collect()
        validate()
        analyze()
        build()
        return result
    return 0


if __name__ == "__main__":
    sys.exit(main())
