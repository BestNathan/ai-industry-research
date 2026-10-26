# Sources and access policy

The canonical machine-readable registry is [config/sources.json](../config/sources.json).

## Three deliberately different source modes

- **feed**: fetch official RSS/Atom XML and normalize publication metadata. Records are not full-text articles. Anthropic is explicitly labeled **unofficial community feed** and each record links back to the original publication.
- **dataset**: fetch a versioned official or reputable open CSV/JSON-stat publication, archive the payload, normalize by the **actual reporting year**, and update `data/datasets/` only when a value/definition changes.
- **api**: fetch a public JSON endpoint, archive the exact response as gzip and derive typed measurements. GitHub repository counts are developer interest **proxies**, Hugging Face downloads are platform signals, and OpenRouter catalog prices are *list prices*.
- **reference**: monitored as research targets and linked from the website, **not automatically downloaded**. Reports/paywalled data require permission, a real machine-readable endpoint or a licensed integration.

## Primary evidence priority

1. Official regulatory filings, statistical agencies, dataset APIs, company disclosures with traceable methodology.
2. Platform behavioral data with known selection bias (payments, usage, app analytics).
3. Independent surveys or industry research with declared denominators.
4. Estimates, third-party summaries, and social/media signals — label as estimates or proxies.

## What the collector can and cannot see

- **Can:** official OpenAI/DeepMind/Hugging Face RSS; publicly accessible API output; public repo counts; selected engineering/research RSS.
- **Cannot infer:** global AI adoption from a corporate payments sample, model market share from OpenRouter routed volume, AI revenue from Token volume, or a company-wide AI ROI from a selected case study.
- **Does not attempt:** scraping authenticated websites, defeating anti-bot controls, redistributing paywalled PDFs/full copyrighted articles, or calling private APIs without consent.

## Adding a source

Add to the appropriate array in `config/sources.json` with a stable ID. For an **API** source, implement the dedicated adapter in `scripts/pipeline.py` and add sample-based tests before activating it. Each entry must include the access mode, publisher or owner, topic, stable canonical link, and methodology note. Broken sources are visible through `data/status/latest.json`; do not quietly remove failing publishers.

## Acquisition roadmap

- Company financials: SEC companyfacts JSON with ticker/CIK mapping, XBRL taxonomy reconciliation and reproducible filing references.
- Statistical agencies: pinned dataset/indicator codes for Census and Eurostat, with explicit denominator.
- Research datasets: Epoch AI, METR and Anthropic Economic Index, subject to their licenses and approved download formats.
- Paid data: explicit provider API contracts and keys for Similarweb, Sensor Tower, QuestMobile, CB Insights or PitchBook; never rely on unofficial scraping.

## Active enterprise adoption datasets

- OWID grapher `share-companies-using-artificial-intelligence` (McKinsey State of AI via Stanford AI Index), annual self-reported use in any function.
- Eurostat `isoc_eb_ai`, official enterprises-using-at-least-one-AI-technology indicator, nonfinancial business economy and 10+ employee scope.

Both are observation-time vs reporting-time aware and include method notes and original links. See [economic dataset methodology](ECONOMIC_DATASETS.md).

## Expanded publication sources

Official feeds: NVIDIA AI and Google AI product news. Publisher feeds: SemiAnalysis (excerpts only, subscription may be needed for full articles) and TechCrunch AI. These feeds complement engineering posts with compute economics, model distribution, startup financing, and applied AI. The publication index is not proof that claims in those articles are verified; validate commercial figures using primary filings or authorized datasets.
