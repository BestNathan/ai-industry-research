# Automated research evidence quality (v1)

Source and metric quality is a first-class daily report, stored under `data/reports/quality/` as JSON and Markdown, and linked from the Pages Data → Source transparency panel.

## Operational status

Every registered feed, API, official statistical dataset or SEC issuer financial source gets an independent health status:
- `ok`: successful latest fetch and parser; a zero *article count* may simply indicate low publication volume.
- `failed`: an attempted fetch, upstream format or parser failed; last successful snapshot is retained.
- `skipped_config`: a required contact/access variable is missing (e.g. SEC `SEC_USER_AGENT`); no network request is issued. This is never counted as a source failure or missing=zero.
- `not_collected`: newly registered source has not been checked.
- `stale`: >3 days since last successful observation; a warning, independent of current source status. Future versions will account for distinct publisher cadences.

## Report invariants

`sources.registered` includes *all* configured automated sources. `ok`, `failed`, `waiting_for_configuration`, and `stale` are reported separately; some states can overlap (a failing source may also be stale). `records` counts raw normalized observations by semantic class and distinct content-addressed gzip files (not inferred economic values).

## Numerical anomaly warnings

Do not compare within a single UTC day: retries can update that day's source snapshot. For each source/entity/metric/unit with two distinct dates, a >25% drop in cumulative GitHub `stars` or `forks` emits `large_cumulative_drop` **warning only**. These are platform popularity proxies, and account deletion/rename/revision can produce legitimate changes. No automatic quarantine, source manipulation or revision replacement is carried out.

## Sampling/methodology breaks

The [Census Bureau BTOS](https://www.census.gov/hfp/btos/help) changed its AI-use question in late November 2025 from "producing goods or services" to "any business function", creating a new series beginning December 2025. This change must be preserved for any future BTOS import. Separate 2025 series must **never** be concatenated into a single artificial growth curve. Suppressed BTOS estimates are missing, not zero, and Census API period/geographic strata require an explicit data contract.

## Acceptance status

This quality layer **does not yet** implement automated source-level SLO escalation, a dataset revision ledger, provenance DAG, object-storage migrations, or statistical significance testing for changes. These remain tracked by #5.
