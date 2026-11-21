# Evaluation coverage (ChromeRAG 0.1.3)

> **Superseded (November 2026).** This file is the original v0.1.3/v0.1.4 record and is kept unchanged below. Its statements that sets were "held out", "scored once" or "run once" are withdrawn: the WCXB test split and the fresh and landing sets were scored repeatedly while rules changed (see `../2026-11-final/SUPPLEMENT.md`, Table S1a, and `HELD_OUT_LEDGER.csv`). Current results and the held-out evidence for version 0.1.5 are in `../2026-11-final/`.

Every page set, how many pages and domains it has, and what it was used for. Domain lists: `evaluation_domains.csv`.

| Set | Role | Pages | Domains | Notes |
|---|---|---|---|---|
| WCXB dev | training and cross-validation (sites grouped by fold) | 1495 | 1294 | 7 page types; {'article': 792, 'service': 165, 'listing': 99, 'forum': 112, 'product': 119, 'documentation': 91, 'collection': 117} |
| WCXB test | final held-out test, scored once | 511 | 472 | 7 page types; {'article': 257, 'collection': 34, 'product': 28, 'listing': 40, 'forum': 51, 'documentation': 42, 'service': 59} |
| Landing dev companies (53) | development (anchor metric) | 212 | 51 | marketing: homepage, pricing, product pages chosen from homepage links before any extractor ran |
| Landing heldout companies (47) | held-out, scored once | 185 | 42 | marketing: homepage, pricing, product pages chosen from homepage links before any extractor ran |
| Fresh companies (51) | fetched after the freeze, scored once | 196 | 47 | sectors: business_saas, cloud_infrastructure, commerce_marketing, communication, data_ai, developer_tools, fintech, healthcare_finance_consumer, industrial, security |
| Documentation/pricing/article corpus | anchor benchmark and BM25 retrieval (development; 242 scoreable) | 268 | 186 | documentation 208 of 242 scoreable pages |
| STCE crawl | site-template learning study | 1791 | 125 site groups | up to 15 same-section pages per documentation site |
| Judge sample: WCXB test | LLM judge, 15 per page type | 105 | 102 | 384 judgements, three baselines |

## Judge samples

* Landing/fresh judge: 100 pages (50 held-out + 50 fresh), 247 judgements (two baselines, 20% position-swapped repeats).
* WCXB-test judge: 105 pages (15 per page type), 384 judgements (three baselines).
