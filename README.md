# AI Industry Research

**An open, reproducible intelligence repository tracking AI industry adoption, commercialization, usage, models, infrastructure, labor, capital, and the emerging AI-native interface.**

This repository has two equal products:

- **Data** — daily raw source snapshots, normalized indicators, time series, quality metadata, and machine-readable reports.
- **Articles** — a continuously monitored, categorized index of primary-source research, engineering publications, business reports, and industry evidence. We store metadata and brief descriptions with attribution and original links; we do **not** mirror copyrighted articles.

The public website is intended to be published at **https://bestnathan.github.io/ai-industry-research/** via GitHub Pages.

## Research questions

1. Is AI **used**, **paid for**, and **deployed in production**? These are separate measurements.
2. Which organizations capture revenue, gross margin, and decision-making control?
3. Is AI shifting from **answering questions** to **executing work and transactions**?
4. Are capability gains translating into lower per-task costs and improved organizational productivity?
5. How do infrastructure spend, model supply, applications, employment, and regulation interact?
6. Who could control the **intent → recommendation → execution → transaction** interface?

## Coverage taxonomy

| Domain | Focus |
| --- | --- |
| Adoption & enterprise | Firm-level adoption, pilots, production use, ROI |
| Consumer & distribution | MAU/DAU, retention, traffic, distribution, intent entry points |
| Commercialization | Revenue, ARR, paying customers, spend, unit economics |
| Usage & agents | API usage, tokens, agent tasks, workflow automation |
| Models & research | Model capability, cost, inference speed, research progress |
| Infrastructure | GPUs, data centers, cloud spend, power and compute constraints |
| Capital & market | Public financials, venture funding, valuations, competitive shares |
| Workforce & productivity | Job postings, skills, wages, task exposure, measured productivity |
| Vertical industries | Finance, health, industrial, government and case studies |
| China | Chinese application/user statistics, local models, industrial deployment |
| Policy, safety & governance | Regulation, incidents, deployment risk, copyright |
| Engineering ecosystem | Open source, developer adoption, agent platforms, tooling |

A **source directory** catalogs reliable sources even when API access is restricted or paid. An explicit `mode` determines whether a source is collected automatically or simply tracked as a research target. See [config/sources.json](config/sources.json) and [docs/SOURCES.md](docs/SOURCES.md).

## Architecture

```text
Official RSS / Atom         Public APIs                 Licensed/manual reports
       |                        |                                 |
       +------------------------+--------------------------- catalog only
                                |
                 daily GitHub Actions (08:10 Asia/Singapore)
                                |
                  raw/YYYY-MM-DD source snapshots
                                |
                  normalize, dedupe, provenance
                       /                    \
           data/metrics/YYYY-MM-DD.jsonl  data/articles/YYYY-MM-DD.jsonl
                       \                    /
                     daily reports / data quality
                                |
                       static site builder
                                |
                 GitHub Pages: Data | Articles
```

**Pipeline policy:** capture immutable source responses first, then normalize. Never infer revenue from token counts, never compare survey populations without documenting denominators, and never silently zero-fill unavailable observations. Publish report freshness and failures.

## Storage contract

```text
config/sources.json           tracked APIs, feeds and research-only sources
config/taxonomy.json          common article / data categories
data/raw/                    gzip-compressed response snapshots partitioned by date
data/metrics/YYYY-MM-DD.jsonl normalized indicator observations
data/articles/YYYY-MM-DD.jsonl article metadata with source links / tags
data/reports/daily/          JSON + Markdown daily summaries
data/status/latest.json      per-source collection success, freshness and errors
docs/                        source access, research methodology, roadmap
scripts/pipeline.py          collect, validate and static-site build
web/                         zero-server static frontend
.github/workflows/           scheduled updates and GitHub Pages deployment
```

For observations, always preserve **source, entity, metric, observation time, value, unit, methodology, geography, and original snapshot path**. Company-stated ARR, estimates, survey results, and audited revenues are not interchangeable. Article records use stable URL-derived identifiers and categorization; collection timestamps differ from publication timestamps.

## Included automated coverage (MVP)

- **Articles:** OpenAI News, Google DeepMind, Hugging Face Blog, selected engineering/research feeds, and arXiv. An **unofficial** community feed is used for Anthropic Engineering/Research where the publisher does not expose an RSS feed; those records are marked accordingly.
- **Metrics:** GitHub repository public statistics, Hugging Face model download signals, and OpenRouter public model price listings.
- **Tracked / not automatically scraped:** Stanford AI Index, Ramp AI Index, McKinsey, Menlo Ventures, US Census, OECD, Eurostat, Similarweb, Sensor Tower, QuestMobile, CNNIC, CAICT, SEC EDGAR, Epoch AI, IEA, METR, LinkedIn, and other primary sources.

This is a **minimum honest data foundation**, not a claim to comprehensive coverage. Some of the most important commercial indicators require a licensed feed, careful manual publication-level extraction, or explicit permission.

## Run locally

Requires **Python 3.11+**, no third-party Python packages for the baseline collector.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/pipeline.py collect      # network access: fetch raw + normalized + daily report
python3 scripts/pipeline.py build        # offline: build web/data and the _site directory
python3 -m http.server 8000 -d _site
```

Open http://localhost:8000. Set `GITHUB_TOKEN` to raise GitHub API rate limits when running locally; automated workflows use the repository token.

## Automation & Pages

- [Daily collection workflow](.github/workflows/research.yml) runs at **00:10 UTC** (08:10 in Singapore), supports manual execution, and commits changed `data/` files back to `main`.
- The same workflow runs validation, builds the site, and deploys to Pages. Ordinary pushes to `main` rebuild and redeploy without collecting from the network.
- Configure **Settings → Pages → Build and deployment → GitHub Actions** once. Repository Actions must be enabled.
- Scheduled runs on GitHub are *best effort*, not an SLA; use the status panel to identify failures or stale data. GitHub may disable schedules on inactive public repositories.
- Some sources can be blocked, rate-limited, removed, or change schema. Failures are recorded; last-known values are not passed off as fresh data.

## Source ethics and research integrity

- **Attribution first:** always link to the primary publication and record retrieval/publication times.
- **Copyright:** ingest feed metadata and short excerpts only; do not commit full articles, paywalled content or licensed datasets without the appropriate rights.
- **Reproducibility:** keep compressed raw API/feed responses with a SHA-256 checksum in normalized records.
- **Data quality:** distinguish observed data, provider claims, samples/proxies, and estimates. No fake or synthetic production numbers.
- **Costs and scale:** compressed daily snapshots live in Git for the MVP. As volume grows, migrate large historical raw payloads to object storage with content-addressed manifests while retaining public metadata and reproducibility.
- **No hidden access:** adding a source to the catalog does not imply that the data is available through an API.

## Contributing & research workflow

1. Register a source with license/access notes, provenance tier, update frequency and topic tags.
2. Add a collector and a fixture-backed test; prove idempotence and handle partial failures.
3. Keep metric names/units stable; document all definitions or schema changes in [docs/METHODOLOGY.md](docs/METHODOLOGY.md).
4. Validate freshness, expected value ranges, upstream changes and duplicate links.
5. Publish a clear summary of **what changed, why it matters, and what is still uncertain**.

See [docs/ROADMAP.md](docs/ROADMAP.md) for planned research coverage and implementation priorities.

**North star:** an evidence-based account of the AI industry's transition from investment and experimentation to deployment, revenue, and control over the future work/commerce interface.
