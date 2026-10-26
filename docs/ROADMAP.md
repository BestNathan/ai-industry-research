# Research platform roadmap

## P0 — runnable foundation (initial implementation)

- [x] Mission, taxonomy, machine-readable source registry.
- [x] Scheduled collector with independent retries and source health.
- [x] Compressed raw response archive with SHA-256 provenance.
- [x] Typed daily JSONL metrics, metadata-only article index and daily JSON/Markdown report.
- [x] Deduplication and idempotent daily reruns.
- [x] Static Pages build with Data and Articles views and source transparency.
- [x] Fixture tests, validation, and no-secret/default-Python deployment.

**Acceptance:** an actual scheduled run (or `workflow_dispatch`) produces new `data/` files, an unbroken published site, and a status panel with at least one successful source. GitHub Pages must be enabled manually by an admin.

## P1 — economically useful series

- [ ] US Census BTOS adoption time series, pinned question codes/denominators.
- [ ] SEC companyfacts / filings ingestion for revenue, AI segment disclosures and capital expenditure.
- [ ] Our World in Data and Eurostat machine-readable adoption datasets.
- [ ] Automated quality gates: schema/version migration, source staleness thresholds, anomaly review.
- [ ] Metric dictionary, series comparability matrix, geography and period-aware UI.

## P2 — enterprise/consumer/agent adoption

- [ ] Licensing or official datasets for Ramp, Menlo, Anthropic Economic Index, Epoch AI and METR.
- [ ] Chinese primary-source report release tracker: CNNIC, CAICT, QuestMobile, NDA.
- [ ] Curated corporate AI deployment case database with methods, claimed/verified ROI, firm/industry.
- [ ] Agent work completion, distribution control, commerce and transaction evidence.
- [ ] Article alerts based on evidence strength and significance, not keyword volume.

## P3 — durable research intelligence

- [~] Data contracts and source adapters as isolated modules with fixture/backfill support (economic adapter separated; others remain in pipeline).
- [~] Object storage for large historical raw payloads, content-addressed manifest in Git (content-addressed raw snapshots implemented; object storage threshold/migration pending).
- [ ] A citation-linked quarterly AI industry report and hypotheses board with disconfirming evidence.
- [ ] Licensed market share/traffic integration if and when access is available.
- [ ] Historical revisions, provenance graph and reproducible SQL/Parquet exports.

## Non-goals

No fabricated "live" numbers, no bypassing commercial data licenses, no mirroring full copyrighted articles, and no ungrounded inference of AI market penetration from a narrow sample.

## Progress notes (2026-10-26)

- Pages deployment and first live collection succeeded. Full external browser inspection remains a separate verification step.
- Eurostat and OWID enterprise adoption historical series are collected with their actual reporting years. OWID returned lowercase column names in the live CSV and the parser was hardened accordingly.
- All API/feed/dataset raw inputs use content-addressed archives for incremental space savings, and the UI exposes the last successful source collection.
- New official and independent article feeds cover compute, distribution and industry economics (NVIDIA, Google AI, SemiAnalysis, TechCrunch).
- Still open: SEC filings, US Census BTOS, article ranking/China coverage, anomalous values, storage capacity thresholds, and Agent/transaction datasets.

## Analytics convergence — 2026-10-26

- [x] Multi-angle research report generator: primary-source adoption history, model catalog price sample, publisher coverage, selected open-source ecosystem, source health and explicit data gaps.
- [x] One-run JSON + Markdown analytical daily brief, provenance-aware chart records and source-linked deterministic evidence findings.
- [x] Pages Data front page presents industrial insight panels above raw indicator selectors.
- [x] Guard against growth conclusions from a single daily platform snapshot.
- [ ] Audited company-specific AI/cloud financials and capex (#3).
- [ ] Representative consumer/enterprise payment and agent transaction measures (#6).
- [ ] Multi-week snapshot trend significance and data quality anomalies (#5).
- [ ] Independent article importance scoring and primary China market feeds (#4).

## SEC pilot integration (2026-10-26)

- [x] SEC annual 10-K XBRL extractor with original issuer CIK, form, fiscal end/start, filing accession, filed-at, chosen US-GAAP concept and raw archive SHA.
- [x] Six-company revenue / PPE capex / operating cash flow / net income adapters with amended-filing and YTD exclusion tests.
- [x] Converged Pages charts for corporate total sales and cash PPE outlays, conditional on actual SEC source availability.
- [ ] First live SEC ingestion after configuring the real contact `SEC_USER_AGENT` repository variable.
- [ ] Direct official US Census BTOS AI adoption series.
- [ ] Reported AI-only business segments and datacenter capex attribution if consistently disclosed and verifiable.

## Data quality convergence (2026-10-26)

- [x] Daily quality status JSON/Markdown with source-level freshness, failures, missing-contact configuration and evidence counts.
- [x] Expose pending SEC contact setup prominently ahead of successful sources on Pages.
- [x] Non-destructive anomaly warnings for material drops in selected cumulative GitHub measures across distinct collection dates.
- [x] CI validates quality report and static site data contract.
- [ ] Source-level quantitative freshness SLAs beyond fixed 3-day threshold; explicit source cadence profiles.
- [ ] Upstream dataset revision manifest and automated anomaly review workflow.
- [ ] SEC fair-access contact configured and real data collection validated.
- [ ] Census BTOS officially pinned biweekly data import preserving the 2025-12 question wording series break.
