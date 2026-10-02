# References for the 0.1.3 paper (status of each check)

Verified = title, authors and venue read on the publisher/arXiv page on 2026-10-02. "Check" = found by search
only; confirm authors and pages before upload (use the `verify-references` step in the manuscript workflow).

| # | Reference | Status |
|---|---|---|
| 1 | Foley, M. *WCXB: A Multi-Type Web Content Extraction Benchmark.* arXiv:2605.21097, 20 May 2026. 2,008 pages, 7 page types, 1,497 dev + 511 test, CC-BY-4.0. | Verified. Note: the benchmark author also builds rs-trafilatura (declared conflict to mention). |
| 2 | Liu, M. et al. *Dripper: Token-Efficient Main HTML Extraction with a Lightweight LM* (MinerU-HTML). arXiv:2511.23119 (v3 Aug 2026). Block-level sequence labelling with a 0.6B model. | Verified. |
| 3 | Leonhardt, J., Anand, A., Khosla, M. *Boilerplate Removal using a Neural Sequence Labeling Model.* WWW '20 Companion, 2020. arXiv:2004.14294. (BoilerNet) | Verified. |
| 4 | Barbaresi, A. *Trafilatura: A Web Scraping Library and Command-Line Tool for Text Discovery and Extraction.* ACL-IJCNLP 2021 System Demonstrations, pp. 122-131. doi:10.18653/v1/2021.acl-demo.15 | Verified. |
| 5 | Wang et al. (Jina AI). *ReaderLM-v2: Small Language Model for HTML to Markdown and JSON.* arXiv:2503.01151, 2025. | Check authors. |
| 6 | Bevendorff, J. et al. *An Empirical Comparison of Web Content Extraction Algorithms.* SIGIR '23. doi:10.1145/3539618.3591920 | Check author list (publisher page returned 403). |
| 7 | Kohlschütter, C., Fankhauser, P., Nejdl, W. *Boilerplate Detection Using Shallow Text Features.* WSDM 2010. | Already in the 0.1.2 paper (ref. 2). |
| 8 | Vogels, T., Ganea, O.-E., Eickhoff, C. *Web2Text: Deep Structured Boilerplate Removal.* ECIR 2018. | Already in the 0.1.2 paper (ref. 3). |
| 9 | Foley, M. rs-trafilatura (Rust, PyO3 bindings), github.com/Murrough-Foley/rs-trafilatura; dev F1 0.859 and test F1 0.903 as reported in ref. 1. Not re-run here (Rust toolchain and crates.io are not reachable from the author's network); quote as reported. | Verified (repository and numbers). |
| 10 | Crawl4AI documentation, *Fit Markdown* (PruningContentFilter: text density, link density, tag weights). docs.crawl4ai.com | Verified (web page). |
| 11 | Mozilla Readability; Resiliparse (Bevendorff et al.); jusText (Pomikálek 2011); Dragnet (Peters & Lecocq 2013); MarkItDown (Microsoft) | Cited in the 0.1.2 paper or to add; confirm. |

## What the related work says that changes how 0.1.3 is argued

* WCXB (ref. 1): top systems converge on articles (F1 about 0.93) and diverge by 20-30 points on forums, products,
  collections, services. The paper's own recommendations (type-aware profiles, JSON-LD fallback for products, merging
  sections for services, class-aware handling of comments on forums) match the failure modes found here.
* Tested here and not useful on WCXB dev (report as negative results): JSON-LD fallback (reference words absent from
  the visible DOM: 0.1-0.8% outside forums, essentially none in JSON-LD); explicit page type as a model input (oracle
  type adds +0.0035 block-level F1); a second stage over neighbouring blocks; a bag-of-words text model.
* Dripper (ref. 2) shows block-level labelling is the right granularity; ChromeRAG replaces the 0.6B language model with
  tree ensembles over about 500 structural and lexical features, which is why it runs on CPU in about 30 ms.
