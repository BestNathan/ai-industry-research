# AI industry analytical reporting contract

## Goal

Consolidate provenance-preserving observations into **useful, auditable industrial intelligence**. The analysis layer is a deterministic aggregator, **not** a numerical narrator using an LLM. An output fact must be traceable to compatible raw observations and original source descriptions.

## Data architecture

```text
raw content-addressed evidence
   ├── daily JSONL platform observations (snapshot date)
   ├── datasets JSONL (actual survey/reporting year)
   ├── daily article metadata (publication date & discovery date)
   └── per-source health
            ↓
      scripts/analytics.py
            ↓
 data/reports/analysis/YYYY-MM-DD.json
 data/reports/analysis/YYYY-MM-DD.md
 data/reports/analysis/latest.json
            ↓
     Pages / Data intelligence cards + separate evidence charts
```

Re-running with identical evidence and health timestamps produces identical report files. On an unchanging day, research facts do not gain a new statistical period just because the front end rebuilt.

## The six first analytical views

| Domain | Meaning | Valid conclusion | Forbidden inference |
| --- | --- | --- | --- |
| EU adoption | Eurostat isoc_eb_ai enterprise 10+ employee ICT survey | Survey-year change in percent and percentage points | Comparison to global McKinsey percentage as same denominator |
| Survey organization AI use | OWID/McKinsey/Stanford curated multi-geography surveyed organizations | AI use in >=1 function including pilots, YoY in percentage points | Full production deployment or ROI |
| Model price | OpenRouter catalog latest up-to-12 model records per provider, excluding free offers | Unweighted median *sampled listing* of USD per million input/output tokens | Volume-weighted inference prices, realized ARPU or commercial margins |
| Article coverage | Records ingested from configured **core** feeds | Indexed topics and publisher coverage | True AI industry news share, demand, spending or publication importance |
| Open source | Selected GitHub repository stars | Cumulative platform popularity for selected repos | Revenue, active users or productivity |
| Snapshot delta | Same source / entity / metric / unit from two distinct collection dates | Observed change in that source's published metric | Growth derived from two intraday retries, causality or generalized market share |

## Research memo schema

`schema_version`, `report_date`, `generated_at`, `cards`, `findings`, `charts`, `daily_changes`, `coverage_gaps`, `health`, `research_note`.

- `findings[*].kind`: observed, coverage, proxy, insufficient_history. Each observed point includes source IDs and method caveats.
- `charts[*].type`: line/bar. Line time axes use actual survey years; for percent values, Pages uses a **0–100% scale** to avoid exaggerating changes. Bar panels have a zero baseline and a per-panel unit.
- `charts[*].source_url` links back to original publisher or statistical dataset.
- `daily_changes`: only when 2+ dates exist; no fake first-day momentum.
- `coverage_gaps`: evidence-dependent metrics not yet available, not zeros.

## Interpretation safeguards

1. **Scope-aware comparison:** no averaged survey adoption across Eurostat and McKinsey, no blended global share.
2. **No article-volume causality:** feed coverage and source publishing frequency heavily influence topic proportions.
3. **No paid-market claims:** model catalog price and GitHub stars are proxies; commercial revenue and paying seats are not inferred.
4. **No missing=zero:** failed or unavailable sources show explicit status and history.
5. **No synthetic monthly history:** annual reports stay keyed by original reporting year, daily captures by UTC snapshot date.
6. **Regression tests:** survey-year changes, numeric medians, source populations, one-day guard, article core-vs-bulk logic and absence of invented commercial metrics.

## Next expansions

Add SEC XBRL revenue and capex series with reporting period, issuer and accession IDs; US Census enterprise AI adoption with pinned question/version; verified enterprise spend (where licensed); AI Agent completion, checkout and fulfillment metrics; and curated source-linked qualitative interpretation of material changes. For comparisons, require matching reporting units, population and period.

