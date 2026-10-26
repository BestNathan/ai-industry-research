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

- [ ] Data contracts and source adapters as isolated modules with fixture/backfill support.
- [ ] Object storage for large historical raw payloads, content-addressed manifest in Git.
- [ ] A citation-linked quarterly AI industry report and hypotheses board with disconfirming evidence.
- [ ] Licensed market share/traffic integration if and when access is available.
- [ ] Historical revisions, provenance graph and reproducible SQL/Parquet exports.

## Non-goals

No fabricated "live" numbers, no bypassing commercial data licenses, no mirroring full copyrighted articles, and no ungrounded inference of AI market penetration from a narrow sample.
