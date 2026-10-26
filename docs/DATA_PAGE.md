# Data page v2 — domain-oriented research interface

## Intent

The original Data page placed all charts after one large overview, mixing unrelated indicators (revenue, surveys, public model catalog prices, GitHub and articles). This encouraged accidental cross-population comparisons and hid a lot of directly reported SEC financial data.

The redesigned page is **a research workbench with six purpose-specific panels**, not a global metrics dashboard that assumes all indicators share units.

## Screen layout

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ AI Industry Research              Data | Articles                 GitHub │
├─────────────────────────────────────────────────────────────────────────┤
│ Where AI capability becomes economic value.                           │
│                                                                       │
│ Industry intelligence                                  Research brief │
│ [Overview] [Financials] [Adoption] [Model economics] [Ecosystem] [...] │
├─────────────────────────────────────────────────────────────────────────┤
│ FINANCIALS                                                             │
│ [6 issuers] [6 with revenue] [4 with standard cash PPE] [165 SEC facts] │
│                                                                       │
│ Issuer scorecard                  USD billions, latest each-issuer FY  │
│ Ticker  FY ended      Revenue     Operating CF      PPE       Net inc. │
│ GOOGL   2025-12-31    [filing]     [filing]      [filing]     [filing] │
│ META    2025-12-31    [filing]     [filing]      [filing]     [filing] │
│ AMZN    2025-12-31    [filing]     [filing]          —        [filing] │
│ ... (click issuer)                                                     │
│                                                                       │
│ Company deep dive            Company [MSFT ▼] Metric [Revenue ▼]      │
│ [Source-linked historical annual trend]  | [Original filing periods] │
│                                                                       │
│ Compare issuers                                                        │
│ [Revenue] [Operating CF] [Cash PPE] [Cash PPE / Revenue]               │
└─────────────────────────────────────────────────────────────────────────┘
```

The nav and scorecard each scroll horizontally on mobile rather than scaling numbers down until unreadable.

## Information architecture

| Panel | Central question | Primary components | Evidence restrictions |
| --- | --- | --- | --- |
| Overview | What changed and what remains uncertain? | Four domain entries, short KPI strip, interpreted findings and gaps | No claims from unrelated proxies |
| Financials | Which tracked public companies have observable cash-generation and cash-investment capacity? | Public issuer scorecard, fiscal-year metric selector, 9-year history, four issuer comparison charts | All issuer consolidated US GAAP, **not** AI-specific; fiscal years differ |
| Adoption | Who has adopted AI? | Eurostat annual adoption line, OWID/McKinsey survey line and in-sample geography bars | Never blend different survey denominators |
| Model economics | How do listed model tariffs differ? | Provider median input/output price and within-model tariff ratio | OpenRouter sampled catalog, not revenue, costs, market share |
| Ecosystem | What is public developer and editorial attention tracking? | Selected GitHub repository stars, tracked publication taxonomy | Selected repositories & feeds are not unbiased market share |
| Sources & quality | How was each claim measured? | Raw time-series explorer, per-source health, ingestion reports, source directory | Missing, uncollected and failed observations never become zeros |

## Financial scorecard contract

The build step exports `financial_data` in `_site/data/dashboard.json`.

- `financial_data.metric_dictionary`: four supported original reported annual 10-K US-GAAP measures.
- `financial_data.companies[*]`: registry-backed ticker, source name, latest revenue `fiscal_year_end`, source-linked `metrics` only **for exactly that fiscal-year end**, `missing_metrics`, and up to nine actual fiscal-year `history` records.
- `financial_data.coverage`: issuers registered, issuers with compatible revenue and standard cash PPE for selected period, number of source-linked fiscal periods.
- Every metric fact exposes original reporting start and end, accession, selected US-GAAP tag, filed-at and source URL. Values are unscaled USD in JSON; the view formats to USD billions.
- If a company has revenue and cash flow but no matching standard US-GAAP cash-PPE field (e.g. AMZN or NVDA), it **still appears** in the company table and historical explorer, but the PPE cell is `—`. Do not substitute a different capital investment definition or read `—` as zero.

## Visual design

Dark editorial research terminal:
- restrained charcoal surfaces, pale typography, thin separators, high information density;
- finance category = muted amber; enterprise adoption = sage; model economics = lavender; ecosystem = steel blue;
- source identity, reporting period and provenance at the same interaction depth as figures;
- responsive section nav with real accessible tabs, arrow/Home/End keyboard behavior and deep-linkable `#data/<section>`;
- no decorative illustrations, forced charts, artificial growth rates or indiscriminate color-coded good/bad badges.

## Acceptance tests

`python -m unittest discover -s tests -v`, `python scripts/pipeline.py validate`, `python scripts/pipeline.py analyze`, `python scripts/pipeline.py build`, and `node --check web/app.js`.

Page build contracts require six category panels, associated tab controls, each analysis chart category, a six-company SEC directory with source-linked facts, and that each issuer overview metric belongs exactly to its latest revenue fiscal-year period.

## Deferred

Direct SEC segment filing tables, quarter-over-quarter SEC financials, 10-Q derived standalone cashflow, live sector-specific AI revenue, Census BTOS with question-version break, significance tests and real task-completion measures require separate evidence and work. Do not fake these for UI completeness.
