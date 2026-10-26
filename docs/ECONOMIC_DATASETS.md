# Economic adoption datasets: versioned statistical time series

## Study populations and interpretation

1. **OWID / Stanford / McKinsey enterprise use**: [source chart](https://ourworldindata.org/grapher/share-companies-using-artificial-intelligence) · [API docs](https://docs.owid.io/projects/etl/api/chart-api/). Reports the share of surveyed organizations self-reporting AI used in one or more business functions. `Year` is the survey's reporting year, never the collection day. This survey can include AI experimentation and pilots. Respondent coverage and GDP-based weighting apply. Underlying source includes third-party contributions: follow the chart's attribution/license notes.
2. **Eurostat isoc_eb_ai**: [official dataset](https://ec.europa.eu/eurostat/databrowser/view/isoc_eb_ai/default/table) · [JSON-stat endpoint](https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/isoc_eb_ai?geo=EU27_2020). Specifically tracks the EU27 ICT-in-enterprises survey's **share of enterprises with 10+ persons employed** using at least one AI technology. This is **not the same denominator or survey** as McKinsey/OWID; changes in definitions must be versioned.

## Data contract

Historical entries use `metric_id=enterprise.ai_adoption_share_pct`, `unit=percent`, a source-specific `entity_id`, `geography`, `period=YYYY`, `period_type=calendar_year`, `evidence_type`, `methodology`, `denominator`, `source_url`, `raw_path`, `raw_sha256`, and `observed_at` (the actual fetch time).

`data/raw/immutable/<source>-<sha>.csv.gz` or `.json.gz` archives exact original response content addressed by SHA-256. Unchanged historical observations are not duplicated across daily files or given fake daily values. Dataset revisions update published normalized records; raw hashes remain auditable. Collection errors leave last good dataset intact and show a failed source in the source status.

## Future work

- Import the pinned official [US Census BTOS AI-use data](https://www.census.gov/hfp/btos/data_downloads) and preserve **November 2025 question wording break** when constructing historical series.
- SEC EDGAR companyfacts with **verified filing period, frame, accession, reporting form, and accepted public SEC User-Agent policy**, distinguishing capex/cloud segment revenue from direct AI revenue.
- Eurostat source coverage and revisions, geographic breakdown, confidence interval/quality flags, links to methodology/denominator and comparative chart groups.
- Explicit research review of license and third-party redistribution terms for each source.
