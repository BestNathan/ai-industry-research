# Research methodology and data contracts

## Daily data record

```json
{
  "source_id": "github_openai_codex",
  "entity_id": "github:openai/codex",
  "metric_id": "github.stars",
  "value": 1234,
  "unit": "count",
  "observed_at": "2026-10-26T00:10:00+00:00",
  "period": "2026-10-26",
  "geography": "global",
  "evidence_type": "platform_observation",
  "methodology": "Public GitHub API repository stargazers_count",
  "raw_path": "data/raw/2026-10-26/github_openai_codex.json.gz",
  "raw_sha256": "..."
}
```

`period` is the collection date in UTC for snapshot metrics. **It is not an event date, accounting period, or source publication date.** A snapshot denotes what the source endpoint returned at `observed_at`.

## Article record

Each record contains `id` (SHA-256 of canonical URL), `title`, `url`, `source_id`, `primary_category`, `tags`, `published_at` (when given), `discovered_at`, `summary` (short feed excerpt only), `official_feed`, `raw_path`, and `raw_sha256`. A source feed being unofficial does not mean the linked original publisher article is unofficial.

## Quality rules

- **No synthetic production values.** Missing fetches are missing, not zero.
- Never sum different geographical coverages, time frames or methodology versions without defining a compatible series.
- Snapshot changes are not automatically market-wide growth rates. GitHub stars, Hugging Face downloads and catalog prices are not AI commercial revenue.
- Never treat actual provider revenue, reported ARR, GMV, estimates and survey percentages as identical units.
- Retain UTC timestamps, original source URLs, raw responses and error/status metadata. Sources can be revised retroactively; archived snapshots permit audit.
- Dates in reports refer to **when data was collected**, not when a statistical survey was conducted.
- The front end never computes invented comparisons across unrelated units. Charts use a single metric/entity time series.

## Reliability

Each feed/API runs independently. Failure of one source produces a recorded per-source error; other sources are still committed. If every enabled source fails, the collector exits non-zero rather than claiming a successful daily update. Tests validate parsers, metric conversion, URL deduplication and generated site artifacts.

## Content policy

Store title/link/publisher/date/tags and a bounded feed excerpt, not complete articles. Respect source licensing, terms, attribution and publisher requests for removal. Research reports are represented through external citations and curated analysis only when permission permits. Attribution is required on every visible record.

## Key leading indicators

1. Adoption: firm-level production deployment, usage by employees, paid adoption and renewals.
2. Economics: audited AI revenue, paid seats, token volumes, realized prices, per-task cost and gross margin.
3. Interfaces: intent origination, recommendation share, successful agent actions, payment conversion and fulfillment.
4. Supply: model capabilities, inference prices/throughput, GPU capacity, power requirements and CAPEX.
5. Labor and value capture: occupational task automation, net productivity and profits by value chain.

Compare these metrics **only with explicit compatible sampling and attribution**.
