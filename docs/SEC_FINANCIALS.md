# SEC 10-K corporate financial statements integration

## Scope and architecture

Six US-listed issuers: Microsoft (789019), Alphabet (1652044), Amazon (1018724), Meta (1326801), NVIDIA (1045810), Oracle (1341439). Official SEC public [Company Facts API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces): `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`. Identified User-Agent with a real monitored email is mandated by [SEC fair access](https://www.sec.gov/about/developer-resources), and must be configured in GitHub Actions variable `SEC_USER_AGENT`. Configured sources are deliberately **skipped**, visibly, until identification is provided.

Data source is official primary SEC filing extraction. Source path `data/raw/immutable/sec_*-<SHA>.json.gz` retains the fetched response; `data/financials/{TICKER}.jsonl` holds normalized annual facts.

## Fields, temporal semantics and safeguards

- Only `us-gaap` **USD** facts drawn from **10-K / 10-K/A** with valid `start/end` duration roughly one accounting year (320–385 days), **not quarterly or 9-month cash-flow aggregates**. We do not derive quarterly cash-flow changes from year-to-date figures.
- Four metrics: `company.revenue_usd` (preferred appropriate revenue US-GAAP tag with fallbacks), `company.capex_ppe_usd` (`PaymentsToAcquirePropertyPlantAndEquipment`), `company.operating_cashflow_usd`, `company.net_income_usd`.
- Reporting periods are `period=YYYY-MM-DD` **actual fiscal-year end** plus `start`, `end`, `filed_at`, `form`, `accession`, `taxonomy`, `xbrl_tag`, `raw_sha256`, and raw file path. A revised annual filing can replace the current normalized fact without overwriting its original immutable snapshot.
- Equivalent taxonomy tags **must never be summed**. A primary tag is chosen where available and most recently filed valid fact wins for the selected tag / fiscal end. Issuer-specific accounting practices and tags can still differ and must be disclosed.
- Derived cash PPE capex/revenue ratio uses **exactly matched company ticker and fiscal period end**. A metric is absent, not zero, when a source does not report it.
- Cross-company panels present each company's latest available fiscal year, with **fiscal-year-end dates in each bar**. This is not a synchronized cross-company time span; do not sum or annualize different windows as an industry statistic.

## Interpretation limitations

**Do not label these as AI financials.** Corporate revenue includes every business line; company cash capex may include non-AI investment and exclude some leases and financed infrastructure; cloud revenue generally cannot be inferred from SEC US-GAAP consolidated sales. A rising cash capex ratio is not evidence of positive or negative AI-specific return on investment. AI margins, paid model revenue and actual inference spend still need segment-level primary disclosures or licensed datasets.

## Research safeguards

- Verify CIK/issuer, accession, fiscal end and filing provenance; do not invent missing tags.
- Respect access rules and contact; if missing, status reports a visible `skipped_config` instead of fetching.
- Prefer actual future revenue/capex series available through issuer filings; do not forecast in the collector.
- If the SEC blocks requests, source failures are recorded and charts remain sourced from previously collected facts, with freshness noted.

## First live ingestion verified (2026-10-26)

After the GitHub repository variable `SEC_USER_AGENT` was configured, [research run 40283505242](https://github.com/BestNathan/ai-industry-research/actions/runs/40283505242) successfully ingested all **six** issuer Company Facts feeds, adding **165 SEC normalized annual records**. The SEC input snapshots are archived and fiscal facts are auditable by filing accession. The raw-data acquisition is successful even if a specific issuer does not report a particular comparable GAAP concept.

The source audit found that AMZN and NVDA currently lack the preferred standard `PaymentsToAcquirePropertyPlantAndEquipment` concept in the normalized annual Company Facts result. They nevertheless have usable annual revenue and operating cash-flow facts. Dashboard revenue and operating-cash-flow charts **include them**; PPE cash outlay and PPE/revenue ratios **omit them**, explicitly naming missing coverage. Do not inject Amazon's net capital outlays or NVIDIA's PPE-plus-intangibles expenditures into the same metric: they require distinct source-backed definitions and compatible denominators.
