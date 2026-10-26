# AI Industry Research

**An open, reproducible intelligence repository tracking AI industry adoption, commercialization, usage, models, infrastructure, labor, capital, and the emerging AI-native interface.**

This repository has two equal products:

- **Data** — daily raw snapshots, normalized time series, multi-angle analytical charts, evidence-labeled findings and reproducible JSON/Markdown reports.
- **Articles** — a continuously monitored, categorized index of primary-source research, engineering publications, business reports, and industry evidence. We store metadata and brief descriptions with attribution and original links; we do **not** mirror copyrighted articles.

The public website is published via GitHub Pages at **https://bestnathan.github.io/ai-industry-research/**.

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
Official RSS/Atom       Public APIs / SEC filings       Licensed/manual reports
       |                        |                                 |
       +------------------------+--------------------------- catalog only
                                |
                 daily GitHub Actions (08:10 Asia/Singapore)
                                |
             immutable content-addressed source snapshots
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
data/raw/immutable/          content-addressed gzip upstream snapshots (no daily duplicates)
data/metrics/YYYY-MM-DD.jsonl normalized daily API snapshots
data/datasets/{source}.jsonl    genuine survey-year observations, no daily duplication
data/financials/{TICKER}.jsonl SEC 10-K company-wide fiscal financial facts (requires SEC identity)
data/articles/YYYY-MM-DD.jsonl article metadata with source links / tags
data/reports/daily/          JSON + Markdown daily acquisition summaries
data/reports/analysis/       JSON + Markdown analytical findings and charts
data/reports/quality/        Per-source freshness, configuration, warnings, quality checks
data/status/latest.json      per-source collection success, freshness and errors
docs/                        source access, research methodology, roadmap
scripts/pipeline.py          collect, validate and static-site build
web/                         zero-server static frontend
.github/workflows/           scheduled updates and GitHub Pages deployment
```

For observations, always preserve **source, entity, metric, observation time, value, unit, methodology, geography, and original snapshot path**. Company-stated ARR, estimates, survey results, and audited revenues are not interchangeable. Article records use stable URL-derived identifiers and categorization; collection timestamps differ from publication timestamps.

## Active coverage and source configuration

- **Articles:** OpenAI News, Google DeepMind, Hugging Face Blog, selected engineering/research feeds, and arXiv. An **unofficial** community feed is used for Anthropic Engineering/Research where the publisher does not expose an RSS feed; those records are marked accordingly.
- **Metrics:** GitHub repository public statistics, Hugging Face model download signals, and OpenRouter public model price listings.
- **SEC annual financials (requires setup):** Six issuer records are configured, but no live SEC financial observations will be collected until `SEC_USER_AGENT` is set to an identifying application plus real contact email.
- **Historical enterprise adoption:** OWID/McKinsey/Stanford AI Index survey series and Eurostat official EU enterprise AI-use statistics, each labeled with its **original survey year** and population caveats. An annual statistic is not refreshed every day just because its CSV is downloaded daily.
- **Tracked / not automatically scraped:** Stanford AI Index, Ramp AI Index, McKinsey, Menlo Ventures, US Census, OECD, Similarweb, Sensor Tower, QuestMobile, CNNIC, CAICT, SEC EDGAR, Epoch AI, IEA, METR, LinkedIn, and other primary sources.

This is a **minimum honest data foundation**, not a claim to comprehensive coverage. Some of the most important commercial indicators require a licensed feed, careful manual publication-level extraction, or explicit permission.

## Run locally

Requires **Python 3.11+**, no third-party Python packages for the baseline collector.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/pipeline.py collect      # network access: fetch raw + normalized + daily report
python3 scripts/pipeline.py analyze      # offline: synthesize source-bound analyses and reports
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

## Economic indicators

Historical enterprise AI-use series are in [`data/datasets/`](data/datasets/) and are normalized by **source reporting year**. The OWID series is based on a McKinsey survey curated via Stanford's AI Index; it includes experimentation and does **not** represent US Census adoption or full production deployment. Eurostat has a different official EU business survey population (enterprises with 10+ employed persons). Do not directly compare their percentages or merge their denominators. See [economic dataset methodology](docs/ECONOMIC_DATASETS.md).

## Publisher coverage and collection health

The feed index includes OpenAI, DeepMind, Hugging Face, Anthropic (explicitly unofficial mirror), AWS, Microsoft, Google Research, **Google AI**, **NVIDIA**, **SemiAnalysis** and AI/industry media. Bulk arXiv records are preserved but are not the default essential-read view. The status JSON includes each source's **last successful collection** alongside current failures. Identical raw responses use the same immutable SHA-256 address across days, avoiding duplicate archives in Git.

## Analysis and charts (evidence-backed, not invented)

The **Data** entry point is organized from interpretation to evidence:

1. **AI adoption:** two deliberately separate trend charts (Eurostat EU official firm survey and the multi-geography OWID/McKinsey organization survey). Display original survey years and **percentage-point** changes; do not overlay incomparable samples.
2. **Model economics:** sampled OpenRouter input/output *listed* prices, by provider, with unweighted medians, model sample counts, and clear warnings against interpreting those as transaction-weighted prices or revenue.
3. **Industry attention:** topic mix of primary-source publication records, excluding bulk arXiv from the default publisher analysis. These counts show *index coverage*, not global market demand.
4. **Engineering ecology:** tracked GitHub repository star counts, clearly labeled selected popularity proxies.
5. **Conclusions & blind spots:** rule-based observations with source evidence, API day-over-day changes **only after two actual comparable collection dates**, unavailable commercial metrics, method and freshness caveats.

The structured report is generated from saved data at `data/reports/analysis/latest.json`; the archived Markdown brief is `data/reports/analysis/YYYY-MM-DD.md`. These data products are committed by GitHub Actions and exposed through Pages, with no generative numerical inference. `python3 scripts/pipeline.py analyze` rebuilds them offline. See [analysis methodology](docs/ANALYSIS.md).

**What this does not prove:** genuine AI revenue, enterprise paying adoption, employment substitution, agent transaction conversion and infrastructure returns still need licensed datasets or audited filings. The site deliberately names these gaps rather than fabricating charts.


## Official SEC financial ingestion (US-listed issuers)

The platform includes a six-company **SEC Company Facts** integration (MSFT, GOOGL, AMZN, META, NVDA, ORCL) for 10-K consolidated revenue, cash payments for property and equipment, operating cash flows, and net income. All years are labeled using the *actual fiscal period end*, not the data fetch date; SEC XBRL fields, filing accession and original snapshot hash remain linked. A company-wide SEC metric is **not AI-only revenue, cloud segment revenue, AI data center capex, or AI ROI**.

**One-time configuration, required by SEC fair access:** Repository **Settings → Secrets and variables → Actions → Variables → New repository variable**, set `SEC_USER_AGENT` to an identifying application name and **a real monitored contact email address** under your control, e.g. `AIIndustryResearch/1.0 researcher@your-domain.example` (replace the example with a real address). Never add contact details or API keys to committed source files. Until this is configured, the 6 SEC sources explicitly show `skipped_config` instead of fabricating observations or violating the SEC's identification requirements. No SEC credentials are needed. SEC permits reasonable requests subject to its fair-access policy; failures leave previous valid filings unchanged. See [SEC integration methodology](docs/SEC_FINANCIALS.md).

## Automated quality checks

Daily research output includes [machine-readable quality status](data/reports/quality/latest.json) and a Markdown quality brief. The quality audit lists every configured source and distinguishes **healthy**, **failed**, **stale**, and **waiting for explicit SEC contact identification**. A source that publishes no recent articles is not automatically considered broken. Archive hashes and source periods remain reproducible. Changes in cumulative GitHub stars/forks exceeding a 25% drop across two distinct days emit a **non-destructive review warning**, never a silent data correction. Unrelated provider price models and yearly survey measures are never blended. Read [quality methodology](docs/QUALITY.md).
