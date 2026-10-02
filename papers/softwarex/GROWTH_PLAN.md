# Growth plan: views, stars and downloads for ChromeRAG

Researched 2026-10-02 (sources at the end). Status column: done / needs author / blocked.

## What the research says works for a Python library

1. **Be findable where people already look.** GitHub topics, a keyword-rich description and README, PyPI keywords and
   classifiers, awesome lists and "best-of" lists drive most passive discovery.
2. **One launch post per channel, with the proof at the top.** Show HN works for libraries and CLIs that people can try;
   lead with the demo or result, say it is the "open-source alternative to X", include "when not to use this".
   Stagger channels (one per week) instead of one big burst.
3. **Reddit: lead with the problem, not "please star".** r/Python restricts promotion; use the weekly showcase thread or
   a problem-first post, be present in comments for 24 h. Read each subreddit's current rules first.
4. **Newsletters pick up good projects**: PyCoder's Weekly (pycoders.com/submissions), Awesome Python Weekly (libhunt),
   Python Weekly. A short factual blurb with one number gets picked more than a pitch.
5. **Ecosystem integrations carry users**: LlamaIndex now takes readers and tools directly in the `llama_index` repository
   (no separate LlamaHub repo); LangChain lists community loaders; both give a path from "RAG tutorial" to our package.
6. **A demo people can try in 30 seconds** (Hugging Face Space or Colab) beats any README paragraph.

## Plan

| # | Action | Status |
|---|---|---|
| 1 | GitHub description, homepage, 15 topics, Discussions on; issue templates | done 2026-10-02 |
| 2 | PyPI 0.1.3 with 16 keywords and project URLs (CHANGELOG, DOI) | done |
| 3 | README: first sentence names the alternatives; benchmark table; FAQ; integrations; CITATION.cff, codemeta, .zenodo.json | done |
| 4 | Site with SEO tags, JSON-LD, sitemap, WCXB results table | done |
| 5 | Awesome-RAG (Danielskry, 1.4k stars) PR: Danielskry/Awesome-RAG#181 | opened 2026-10-02, maintainer merges slowly (many open PRs) |
| 6 | Submit to PyCoder's Weekly (pycoders.com/submissions) and Awesome Python Weekly: blurb below | needs author (web forms) |
| 7 | Show HN post (title and first comment below), posted Tue-Thu morning US time | needs author (HN account) |
| 8 | r/Python showcase thread, r/LocalLLaMA and r/LangChain problem-first posts, one per week | needs author |
| 9 | Hugging Face Space: paste HTML or a URL, three tools side by side (reuse `apps/ui`) | next engineering task; I can build it |
| 10 | Colab notebook: install from PyPI, compare three tools on three pages | next engineering task; I can build it |
| 11 | LlamaIndex PR: `llama-index-readers-chromerag` package in `llama_index/llama-index-integrations/readers` (reader already written) | next engineering task; needs their package template |
| 12 | LangChain: publish `langchain-chromerag` or PR to the community docs listing | next engineering task |
| 13 | Blog post "Why a learned filter beat hand-tuned rules for RAG ingestion (and where it does not)" with the frontier plot; cross-post dev.to | I can draft; needs author to publish |
| 14 | Ask 3 RAG builders to try it on their own pages; collect failures as issues; quote with consent | needs author |
| 15 | Reply (factually, crediting Trafilatura) in WCXB / Trafilatura benchmark discussions with the held-out numbers | needs author |
| 16 | After SoftwareX acceptance: DOI badge, `preferred-citation` in CITATION.cff, announce | later |

## Metrics to watch (weekly)

PyPI downloads (pypistats.org/packages/chromerag, excluding mirrors), GitHub stars/forks/clones/referrers (repo Insights ->
Traffic), issues opened by others, site visits, citations. Be honest in the paper: report the numbers on the day of
submission, not projections.

## Draft copy

**Show HN title:** Show HN: ChromeRAG, an open-source HTML-to-Markdown filter for RAG that beats Trafilatura on forums, product and category pages

**First comment:** I built ChromeRAG because documentation, product and marketing pages break article-tuned extractors:
nav, related links and comment threads end up in the vector index. It scores every text block with a 150 KB tree model
(NumPy only, about 36 ms per page, no GPU) and can also learn a site's template from a few pages. On the 511 held-out
pages of the WCXB benchmark word-F1 is 0.902 vs 0.860 for Trafilatura (+0.043, CI +0.027 to +0.059); it is a tie on articles and
documentation, and the gains are on forums, product and collection pages. A language-model judge prefers it to MarkItDown on
83-87% of pages but is only tied with Trafilatura on the mixed WCXB sample. Limits: English-centric training, no JavaScript,
label noise on documentation code samples. Code, per-page outputs and the evaluation scripts are in the repo.
`pip install chromerag`. I would like to hear which pages it gets wrong.

**Newsletter blurb (50 words):** ChromeRAG converts scraped HTML into RAG-ready Markdown with a 150 KB learned block filter
that runs on CPU with NumPy. On the held-out WCXB benchmark it reaches word-F1 0.902 against 0.860 for Trafilatura, with
large gains on forums, product and collection pages. LangChain and LlamaIndex loaders included.

## Sources

Show HN and launch advice (syften.com HN guide; markepear.dev dev-tool launch guide), promotion channels
(business.daily.dev open-source promotion guide), Reddit self-promotion rules (rankcow, getdiggit guides; check r/Python rules),
PyCoder's Weekly submissions page (pycoders.com/submissions), LlamaIndex contribution model after v0.10
(llamaindex.ai blog "LlamaIndex v0.10", llama-hub README), LangChain community integrations docs
(docs.langchain.com/oss/python/integrations/document_loaders), awesome-RAG lists on GitHub.
