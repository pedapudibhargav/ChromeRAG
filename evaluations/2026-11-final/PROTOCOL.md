# Locked evaluation protocol (ChromeRAG 0.1.5)

Status: fixed **before any page fetch** for this evaluation wave. Git tag `protocol-2026-11` marks this file (and only evaluation metadata committed with it) **after** code tag `freeze-0.1.5` (commit `04cbb05`). No page fetch and no extractor run on the new pages until both tags exist.

## Purpose

Define one held-out page set (~300 pages) for pairwise judging (P05, P06) and continuity checks. WCXB test (511 pages, full benchmark list) and CRAG split 1 are scored **once each** under this protocol, with no tuning on them afterward.

Page-type labels are **rule-based** (URL path and JSON-LD `@type` only, not page content). They can be wrong; page-type breakdowns are descriptive only.

## Target size and page-type quotas

Target **300** successful pages after fetch (report actual *n* if shortfall; do not back-fill from excluded domains).

| Page type     | Quota |
|---------------|------:|
| article       |   119 |
| forum         |    51 |
| listing       |    27 |
| service       |    88 |
| product       |    10 |
| collection    |     5 |
| landing       |    10 |
| **Total**     | **300** |

Landing pages are marketing home, pricing, or product-overview pages (same roles as the landing benchmark), distinct from generic **service** SaaS pages.

## Domain source (mechanical, before fetch)

Single source: the [Tranco](https://tranco-list.eu/) top-1M list.

- Save the downloaded CSV at `data/final/tranco.csv` (git-ignored). Record the Tranco **list id** in `data/final/tranco_list_id.txt` beside it (one line, not committed).
- Keep domains ranked **1–200 000** only. Shuffle that list with fixed seed **`20261101`** (`random.Random(20261101)`).
- Drop registrable domains in the exclusion sets below.
- Drop domains whose registrable name contains any **keyword blocklist** token (case-insensitive substring): `porn`, `xxx`, `adult`, `sexchat`, `escort`, `hentai`, `gambl`, `casino`, `betting`, `poker`, `slot`, `wager`, `onlyfans`.

No hand-picked seed JSON files.

## URL discovery and page-type rules (before fetch)

For each shuffled domain in order, until quotas are fillable or **`MAX_DOMAINS_TRIED = 8000`** domains have been processed:

1. Fetch `robots.txt` and allowed sitemap URLs; collect same-registrable-domain URLs from sitemaps (URL order preserved).
2. Fetch `https://<domain>/` (and `https://www.<domain>/` if different) for **landing** candidates; if the homepage HTML links to `/pricing`, add that URL as a **landing** candidate.
3. Classify other candidates by **path and JSON-LD only** (parse `application/ld+json` blocks; do not read body text for typing):
   - **product** — path matches product URL patterns (`/product`, `/products/`, `/p/`, `/dp/`, `/item/`, …) or JSON-LD `@type` is `Product`.
   - **collection** — path matches `/collections/` or `@type` is `CollectionPage` / `ItemList` with product-like paths.
   - **article** — dated paths (`/YYYY/MM/`) or slug-like paths (same heuristics as `poc/extra_corpus.py` article paths); exclude tag/category/search/login paths.
   - **forum** — path matches thread patterns (`/t/…/id`, `/questions/id/…`, `/topic`, …).
   - **listing** — category/browse/list paths or listing patterns from the same heuristics.
   - **service** — pricing/features/product/solutions/platform/about/services path segments on marketing sites.
   - **landing** — homepage or `/pricing` as above.

Candidate order within a domain: sitemap URLs (sorted), then homepage, then `/pricing` if linked, then other classified links in lexicographic URL order.

## Page acceptance (before freeze)

A candidate **passes** only if all hold:

- HTTP **2xx** after redirects; final registrable domain not excluded.
- `Content-Type` indicates HTML.
- **English:** `<html lang>` starts with `en` (case-insensitive), or `lang` absent and `Content-Language` starts with `en`.
- **Visible word count ≥ 80** after removing `script`, `style`, and `noscript` (whitespace token count).
- `robots.txt` allows the URL for the collector user-agent.

Failed candidates are logged with reason; the **next** candidate in fixed order may replace them **only while the set is unfrozen** (no extractor has run on any held-out page).

## Sampling rule

- Fixed RNG seed: **`20261101`**.
- Pool passed candidates by `page_type`. Shuffle within type with the fixed seed; walk in order and accept a URL if the registrable domain has **< 3** pages already chosen.
- Stop when every quota is met or **`MAX_DOMAINS_TRIED`** is reached. Report quota **shortfalls** in the sampling report.
- Deduplicate by normalized URL (strip fragment, trailing slash, lowercase host) — see `poc.final_collect.normalize_url`.
- After `seed_page_list.json` is written, the list is **frozen**: no URL substitution on fetch failure.

## Domain exclusions

Exclude every **registrable domain** in the author-held inventory CSV (columns: set, id, domain, url, use) for:

- WCXB dev, WCXB test
- extra_raw, extra_raw_final, extra_raw_final2
- golden corpus, landing, landing fresh, site crawl
- CRAG split 0, whose pages informed pre-freeze choices

Also exclude every registrable domain under `data/wcxb/` (WCXB benchmark tree).

Load via `--inventory-csv` (author path, not committed).

## Collection (single entry point)

- Tool: `python -m poc.final_sample --inventory-csv <path>` (samples from Tranco, writes `evaluations/2026-11-final/seed_page_list.json`, then fetches). Fetch-only rerun: `python -m poc.final_collect --seeds evaluations/2026-11-final/seed_page_list.json --inventory-csv <path>`.
- HTML and manifest: `data/final/` (git-ignored). Skipped candidates: `data/final/skipped.jsonl` (reason per line).
- Manifest fields per row: `url`, `domain`, `timestamp`, `status`, `sha256`, plus `id` and `page_type`.
- Default **128** concurrent workers; **one in-flight request per registrable domain** (delay **1.0 s** between requests to the same domain).
- Resumable: successful rows skipped on rerun.
- TLS: optional `--ca-bundle` (no `.env` reads).

## Failed-fetch rule (after freeze)

After the list is frozen, a fetch **fails** under the same rules as acceptance above. Failed rows stay in the manifest with `status` ≠ `ok` and are **not** in the evaluation set. **No substitute URLs**; report shortfall in the ledger.

## Tools and pinned versions

All extractors run on identical HTML. ChromeRAG code must match tag **`freeze-0.1.5`**: the tag must exist; `git diff --quiet freeze-0.1.5 -- src pyproject.toml`; a clean index for `src/` and `pyproject.toml`; and `src/chromerag/assets/lbc_stage1.npz` SHA-256 must match `evaluations/2026-10-v0.1.3/strict_split_manifest.json` (`shipped_lbc_stage1_npz.sha256`). Enforced in `poc.final_run`.

| Tool | Pin / record |
|------|----------------|
| ChromeRAG | tag `freeze-0.1.5` |
| Trafilatura | record `importlib.metadata.version("trafilatura")` at run time |
| readability-lxml | record `importlib.metadata.version("readability-lxml")` at run time |
| MarkItDown | record `importlib.metadata.version("markitdown")` at run time |
| rs-trafilatura | **0.1.1** in CI (separate workflow job; local install blocked on author network). Outputs copied into `evaluations/2026-11-final/cache/<set>/rs_trafilatura/` before `poc.final_run` merges them; live runs use `--tools` without rs-trafilatura when the wheel is absent. |

ChromeRAG modes scored: `chromerag_coverage`, `chromerag` (balanced), `chromerag_precision`. Baselines: Trafilatura, Readability, MarkItDown, rs-trafilatura when available.

## Sets scored exactly once under this protocol

1. **New pages** — frozen sample after successful fetch (`data/final/`).
2. **WCXB test** — all **511** pages (full released test list; seed **not applicable**). Word-level F1, precision, recall, with/without snippet rates; `data/wcxb/evaluate.py` and `poc/run_wcxb_eval.py` / `poc.final_run.py`.
3. **CRAG split 1** — same record filters as split 0 in `poc/crag_answer_eval.py`, **seed 0**, **n = 500** questions; split **1** only (split 0 remains pre-freeze evidence).

Legacy 328-page set may be rejudged once for continuity, labelled **previously consulted**; not part of the primary locked claim.

## Primary metrics (summary)

Pre-declared **primary comparison** for multi-tool tables: ChromeRAG **`chromerag` (balanced)** vs **Trafilatura**; other tool pairs are descriptive.

| Set | Primary |
|-----|---------|
| New ~300 pages | Blinded LLM judge **net preference** (bootstrap CI) |
| New pages (human) | **Separate primary:** net preference from human raters on **75** stratified pages (P05) |
| WCXB test 511 | Word **F1** vs human main content (front matter stripped for ChromeRAG) |
| CRAG split 1 | **Answer score** (accurate − incorrect) from `poc/crag_answer_eval.py`; secondary: retrieved chrome share, indexed context size; **hit@k** on short answers (≤5 words) only |

Secondary: extraction latency, empty-output rate, WCXB snippet rates, P10 retrieval metrics.

## Analysis code paths

- Sample + fetch: `poc/final_sample.py`; fetch only: `poc/final_collect.py`
- Bulk extraction + cache: `poc/final_run.py`
- WCXB: `poc/run_wcxb_eval.py`, `poc/wcxb.py`, `data/wcxb/evaluate.py`
- Judges: `poc/final_page_judge.py` (new pages), rules in `RUBRIC.md`, page list in `page_filter.json`
- CRAG: `poc/crag_answer_eval.py` (split 1 run uses `--split 1` when enabled for the locked wave)
- Human study: `evaluators/` + `poc/human_eval_analyze.py`

Results under `evaluations/2026-11-final/results/`; ledger row per held-out run (P01).

## Post-lock change disclosure

After `freeze-0.1.5`, no pipeline, rule, threshold, or model change for locked claims. If a defect forces a change, report the locked run as executed, disclose it, rerun on **fresh** held-out data, and report both outcomes side by side.

## Order of operations

1. Code tag **`freeze-0.1.5`** (already at commit `04cbb05`).
2. Commit this protocol; tag **`protocol-2026-11`**.
3. Download Tranco list → `data/final/tranco.csv` + list id file.
4. `python -m poc.final_sample --inventory-csv <path>` (sample, freeze list, fetch).
5. `poc.final_run` once per set above (no extractor runs before step 4 completes).
6. P06 judges, P05 humans, manuscript numbers (P14).

## Amendment before any page was kept (2026-11-01)

The first collection attempt was stopped after about 10 minutes. It had written no pages, and no tool had run. It would have fetched every sitemap URL of a site at one per second, one batch of 16 sites at a time. Changes, fixed before restarting: 128 sites at a time; for each site, at most 12 candidate URLs, chosen by a random shuffle seeded with the sampling seed and the domain; at most 150 seconds per site and a 20-second request timeout. The limit of one request per second per site is unchanged.

## Amendment before any judging (2026-11-01)

No judge had scored any new page when this was recorded. Tag: `rubric-2026-11`.

**Grading rules.** Answer grading and page judging follow `RUBRIC.md`. The original CRAG split 1 run remains the planned result. The regrade under `RUBRIC.md` is post hoc, because the rubric was written after that run was seen, and is reported beside it with that label. The grader's agreement with `tests/fixtures/crag_rubric_cases.jsonl` is 96.0% on labels and 88.1% on labels and rule together (101 cases). The rubric was not revised after this check.

**Page filter.** `poc/final_page_filter.py` removes pages with a mechanical rule and writes `page_filter.json`: 11 of 307 removed (8 non-English, 2 JSON bodies, 1 duplicate), 296 kept. The protocol's language check relied on the page's declared language, which proved unreliable. The rule was revised after viewing language signals on these pages, with no tool output in view. A first rule, a floor on English common words, was rejected because it removed English product and menu pages. The Danish forum page `final-0138` is kept by the final rule and is not removed by hand.

**Sample size.** The quota table sums to 310, not the 300 stated earlier; 307 pages were collected.

**Page judging.** Balanced ChromeRAG is compared with Trafilatura (primary) and Readability. MarkItDown is not judged, to stay within budget. rs-trafilatura is judged only if its outputs are obtained. The judge sees up to 24,000 characters of page text and of each extraction. This budget was set after viewing output lengths on these pages, not their text. Every result is also reported on pairs where neither extraction was clipped.

## Amendment after page judging (2026-11-01)

MarkItDown was judged after all, once the author approved more budget. This replaces the statement above that it would not be judged. It was added before any page-judging result had been seen.

## Human rating set (2026-11-01)

Built by `evaluators/author/build_bundle.py` with seed 20261101 from the 296 kept pages: 75 stratified pages, 5 repeats, and 5 practice pages excluded from analysis. Practice pages come from the same set and not from development data, because they need no labels and are never analysed. Outputs: ChromeRAG balanced, Trafilatura, Readability. The primary human comparison is ChromeRAG balanced against Trafilatura, by majority verdict with a page-level bootstrap interval. Raters and their results are recorded as received. Any result, including a tie or a Trafilatura lead, is reported as it comes.

### Amendment: offline pages and safety filter (2026-11-02)

The first page collection reached a site that a network security check flagged as unsafe, and the rating set still held pages that could load live images. No rater had received the set. It was rebuilt before any human rating, for the safety of the raters and with no tool output or score in view.

- Saved pages now have links, images and remote styles removed. The app no longer shows page addresses or a live link, and it connects to no website.
- `poc/final_rater_safety_filter.py` removes pages by mechanical rule: gambling, adult or piracy terms in the domain name or repeated in the page text, a domain ending on our own high-risk list, or two or more digits in the domain name. The digit rule also removes ordinary news sites, and we kept it unchanged after seeing this rather than adjust the rule to its results. It removed 8 of the 296 pages, leaving 288, listed in `rater_safety_filter.json`. It is not a reputation check, and no outside lookup service was used.
- The bundle was drawn again from the 288 pages with the same seed and settings, so its pages differ from the earlier draw. All other evaluations still use the 296 pages. Raters judge text only and do not see images or page styling.

### Amendment: new human rating set from approved sites (2026-11-02)

This replaces the rating set in the two sections above, which no rater ever received. All 288 and 296 page results stay as they are for the other evaluations and do not go to raters. The site list, address checks and page rules below were fixed before any page of the new set was loaded and before any tool output was seen.

- **Sites.** `human_set/sites.json` lists reputable sites in named groups, approved by the author by name. This is a judged list, so results describe reputable mainstream sites and not the open web.
- **Gate.** Each site's robots.txt reply decides what happens next: go on, stop for good on a refusal, wait once if asked to slow down, stop if sent to an unapproved host. Refusals are not worked around. Sites lost this way are reported.
- **Addresses.** Chosen at random from sitemaps or the start page, with recorded seeds. Two independent reviews, one by a separate Claude agent and one by Grok, checked them from their text alone without contacting them. `human_set/approved_addresses.json` is the result, and anything either review doubted is out.
- **Pages.** Loaded in Chrome with Playwright 1.55.1, scripts off first, and with scripts only when a page has too little text and the site is not a forum. Only the site's own hosts and its known content hosts can load, and images, media and fonts never do. Pages are saved unchanged, so every tool gets the same input. Page rules are in `poc/human_set_collect.py`, and the author reviews the final page list before any rater sees it.
- **Forums.** Stack Overflow, Super User and Server Fault refused automated requests, so they are out. Microsoft Q&A was then the only forum source; the next amendment adds more.
- **Draw and blinding.** The bundle no longer drops pages with short tool output, since that selects on results. The seed stays private until rating ends and its hash is recorded here before rating starts. Web addresses in page text and outputs are replaced with one mark, repeats are unmarked, and raters judge saved copies only.

Rating set as built on 2026-11-02: 145 pages loaded from 51 sites, 99 after the limit of 2 per site. A review of the first draw removed 6 more for work safety or usability, on page text and with no scores in view: `human_set/removed_after_review.json` lists them. The seed was then replaced, and a stratified draw from the remaining 93 gave 75 pages, 5 repeats and 5 practice pages. Forum coverage in the human test is minimal. SHA-256 of the file holding the private bundle seed: 1020bf7db0b0013028b6514132a27c2e445e58c33066e6622b1b79234a5f8950.

### Amendment: more forum pages, fixed share (2026-11-02)

No rater has received any set, and no human or AI judge result exists for these pages. Two forum pages could not support any statement about forums, and the three forums first chosen refused automated requests, so the author approved ten more by name, listed under `forum` in `human_set/sites.json`. We know from WCXB that forums are among ChromeRAG's stronger page types, so this choice could favour it. To limit that:

- The share is fixed in advance at 10 of the 75 main pages, whatever the results, with at most 2 pages per site. If fewer than 10 pass the checks, all that passed are used and the count is reported.
- Forum addresses and pages get an extra filter for account, payment and personal topics, and posts showing more than one email address or phone number are removed. No tool output is used.
- Human results are reported overall, for forums alone, and without forums.
- Forum software often places post text inside `noscript`, which only a browser with scripts off shows. Forum pages keep scripts off and are saved with those tags unwrapped, so every tool receives what such a browser displays. This was changed after the first forum load returned too little text, before any tool ran on those pages.
- Final build, 2026-11-02: review found two automated Fedora posts with no person's question, so they were removed by that reason (`human_set/removed_after_review.json`). The bundle seed was then replaced. 10 of 75 main pages are forum pages. The corpus is `human_set/corpus_pages.json`, cut by `poc/human_set_corpus.py`. Microsoft Q&A and AWS pages came from an earlier load and keep empty noscript tags, with no effect on their text. SHA-256 of the file holding the private seed: a9f12a5bfbbf9400c89159909418723f3d3cba5fa857e7238658a50c0f27b5dd.
- Review before release, 2026-11-02 (one Grok review and one separate Claude review, both reading this protocol and the page list): two terms pages were removed because the address rule meant to skip privacy, terms and legal pages missed the word inside a longer name. Pages were not removed for being hubs, menus or listings, since those are real page types and removing them would be choosing pages by expected difficulty. The handout tells raters to judge such pages by the same question and to ignore banners and contact details. Every item carries a random id; a private map links ids to pages. The seed was replaced once more. SHA-256 of the file holding the private seed: 118aabe64e9b390ccd0941c8a711264769ca1b18ff14b048fa16b4fcc8ff1faa.

### Analysis plan for the human rating set (fixed before any rating)

- Primary: ChromeRAG against Trafilatura, share of items where raters prefer each, with a 95% interval from a bootstrap that resamples sites, because each site gives up to two pages. Secondary: the same for Readability, and the 1 to 5 scores.
- Reported overall, for forums only, and without forums, and by page group where a group has at least 8 pages. Agreement between raters and on the 5 repeats is reported.
- What it supports: preference among the three tools on reputable, mainstream, author-approved sites, judged on offline text. It does not stand for the open web or the WCXB benchmark.
- Disclosed: the judged site list, sites lost to refusals, forum sites chosen knowing forums suit ChromeRAG, the fixed forum share, scripts off and noscript handling for forums, every removal with its reason, and every seed replacement, all made before any rating and with no tool score in view.

### Amendment: AI judges on the human rating set (2026-11-02)

Approved by the author before any human rating was returned. The three AI judges run on the same 75 rated pages, using the exact page copy and outputs raters see, so humans and AI judges can be compared item by item. Practice items and repeats are left out.

- Judges: the GPT judge with the frozen rubric (tag `rubric-2026-11`), and Grok and Gemini through a coding-agent tool, with settings we cannot control. ChromeRAG is compared with Trafilatura and with Readability, with blind random A/B order and 10% of pairs swapped, as on the 296 pages.
- All AI verdicts are saved before any human result is read and are not changed afterwards.
- Comparison: for each judge and each pair, the share of pages where the AI judge and the human majority pick the same winner (ties counted as their own outcome), Cohen's kappa, and both figures with a bootstrap that resamples sites. The AI judge length analysis is repeated on these pages. Disagreements are reported, not explained away.

### Amendment: pages with nothing to rate (2026-11-02)

Approved by the author before any rater received the set. A check of the built set, made to spare raters' time, read page and output lengths. Two rules came out of it. Both apply to every page in the pool of 101, and neither depends on which tool did better:

- A page is removed when all three tools return fewer than 80 words. Such a page has little main text to rate.
- The page length limit drops from 15,000 to 8,000 words of page text, because longer pages cannot be read in reasonable time.

Nine pages meet a rule; `human_set/removed_by_rule.json` lists them with their word counts. Five of them were in the drawn set (one is a short page that was already readable, kept out only so the rule stays mechanical). Each was swapped for an unused page of the same group, taken in an order set by the recorded seed; when a group had no unused page left, the next unused non-forum page was taken. Every other item, its id, its label order and the repeats are unchanged, and the seed file is the same as in the last build (hash above).

Pages where only one or two tools failed were kept, because those failures are part of what raters should judge. The check also listed such pages, and none was removed. When the rules were set, the GPT judge had already run on the earlier set and its totals had been seen; the rules use only word counts, not verdicts. The five new pages passed the same address checks before collection and the same two content reviews (one Grok, one separate Claude review) before release.

### Amendment: rating app layout (2026-11-02)

Before any rater received the set, the app was made quicker to use: one top bar with progress and an estimate of time left, the score guide behind a Guide button, and each item opening at the top. The word count shown above each output was removed, because it could lead raters to favour the longer text, the same length effect checked for the AI judges. What raters judge and what is saved are unchanged.

### Amendment: smaller parts and rater-chosen names (2026-11-02)

Before any rater received the set. To shorten each rater's work, the set is also offered in three parts. Five anchor pages, one from each of the five largest page groups, are in every part; the other 70 main pages are dealt to the parts by page group in a seeded order (24, 23 and 23 pages). Each part also holds the 5 practice items and any repeat whose page is in it, giving 34 to 36 items. Items, ids and labels are the same as in the full set, so full and part results are analysed together. Raters may take the full set or one part; the aim is at least three ratings per page, and pages with fewer are reported. Agreement uses Krippendorff's alpha, which allows raters to see different pages; the anchors give a direct check across all raters. Repeats now count only toward repeat consistency, not as extra pages in the majority vote or in agreement, which corrects the analysis code.

Raters pick their own rater name. Two results files with the same name are kept apart in the analysis. Before results are published, every name is replaced with a neutral code (rater-01, rater-02, ...) in a random order, and the map back stays private. The study note raters read before agreeing is inside each package.

### Amendment: careless rating (2026-11-02)

Fixed before any rater received the set. The main human result always includes every rater who returned a results file. A second, sensitivity result leaves out raters who meet any of these checks, and both results are reported side by side:

- the median time per rated item is under 30 seconds, too short to read a page and three outputs;
- among 4 or more repeat pages, fewer than 60% get the same verdict both times (fewer than 3 of 5 in the full set; part raters see only 1 or 2 repeats, so this check does not apply to them);
- one answer, by position on screen, is given on 90% or more of 10 or more rated items.

The checks are mechanical and do not look at which tool a rater preferred. Each flagged rater is named by code with the check that flagged them. No rater is removed from the main result for any reason other than the existing rules on skipped and incomplete items. `evaluators/author/analyze.py` reports the sensitivity result as `sensitivity_without_flagged_raters`.

### Amendment: task explanation and practice notes (2026-11-02)

Before any rating was returned. Some raters had no background in search or AI systems, so the handout and the app's Guide panel now explain in plain words how an AI assistant uses page text, define content and noise in the rubric's terms, and score a small made-up example. They keep the rubric's rule that there is no fixed trade-off between lost content and noise, and that length alone never decides. Each of the 5 practice items now shows a short note after the rater has scored it, describing what a careful rater would notice and the scores the rubric suggests. The author wrote the notes knowing which tool made each output; an independent review by Grok, made without that knowledge, found four factual errors, two of them in notes that favoured ChromeRAG's output, and all were corrected before release. Of the 5 notes, two suggest the Trafilatura output, one the Trafilatura output alone or with ChromeRAG's, one finds the outputs about the same or suggests ChromeRAG's and Readability's together, and one finds them about the same. Practice items stay out of the analysis. All four packages were rebuilt; items, ids, labels and orders are unchanged.

### Amendment: difference highlighting (2026-11-03)

Before any rating was returned. To help raters compare outputs quickly, the app now highlights, inside each output, text found only in that output and text found in it and one other, and lists text that other outputs have and it lacks. Outputs are compared by runs of four words, ignoring case, punctuation and line breaks. The colours mark differences only and say nothing about which text is content; the handout says so, and that text missing from every output is not highlighted. Highlighting is on by default and raters may switch it off. It replaces an earlier box that compared only the first two outputs line by line. The AI judges saw no such aid; they and the raters still judge the same page copy and outputs. The app version sent to raters is 1.1.0 and is saved in every results file.

### Editorial note (2026-11-20)

One sentence in the amendment on the rebuilt rating set was reworded ("a network security check flagged as unsafe" instead of naming who ran the check). The meaning and every decision are unchanged.

### Amendment: re-scoring of the WCXB test split for review (2026-11-20)

Recorded on 2026-11-20, after the runs it describes. The section "Sets scored exactly once under this protocol" held for the new pages and for CRAG split 1: each was scored once. The WCXB test split was scored once on 2026-11-01 as planned (`results/wcxb_test/`). On 2026-11-20 it was scored again, with source code identical to tag `freeze-0.1.5` and the same scorer, to add rows the reviewers asked for: raw and stripped output, the 372-page and domain-absent subsets, the freeze-0.1.3 code with the 0.1.5 model, jusText, BoilerPy3 (outputs from CI), a speed run, and Trafilatura with `favor_recall` and with `favor_precision`. No code, model, rule or setting changed after any of these results, and none of them was used to choose anything. Every run is a row in `results/held_out_runs.jsonl`; the files are in `results/revision_rows/`. Because the split had already been consulted during earlier development, the paper reports it as previously consulted, not as held out. The Trafilatura `favor_recall` and `favor_precision` options had already been looked at on this split on 2026-11-01 (baseline reconciliation with default arguments; see `results/revision_rows/trafilatura_options.md`), so those rows confirm rather than first measure them.

### Editorial note: clarifications after review (2026-11-20)

Recorded on 2026-11-20, after all ratings. Nothing above is reworded; these points correct or complete it. No page, rating, setting, code or decision changes.

- **AI judges before the length rules.** The amendment "pages with nothing to rate" says that the GPT judge had already run on the earlier set and its totals had been seen. In fact all three AI judges (GPT, Grok and Gemini) had judged the approved-site set built on 2026-11-02, and the totals of all three had been seen, before the two length rules were set and the 5 pages were swapped (judge plan commit `4f5ce3a`; swaps in `850cf98` and `5ebf4fb`). The rules use only word counts. The verdicts on the 5 pages swapped out are kept in the `*.progress.jsonl` files and are reported in the supplement (Table S6, post hoc).
- **Who asked for the re-scored rows.** The amendment "re-scoring of the WCXB test split for review" calls every row one that the reviewers asked for. Requested in review: raw and stripped output, the 372-page and domain-absent subsets, the freeze-0.1.3 code with the 0.1.5 model, and BoilerPy3. Added by the author: jusText, the speed run, and Trafilatura with `favor_recall` and with `favor_precision`. The `purpose` field of the two Trafilatura option rows in `results/held_out_runs.jsonl` says "reviewer-requested" in error; the ledger rows are kept as written.
- **Reconstructed ledger rows and a crashed run.** The rows for the planned WCXB test run and for CRAG split 1, both on 2026-11-01, were missing from `results/held_out_runs.jsonl` and were added on 2026-11-20 from the result files and git history (field `added`). One GPT judge run on the 296 new pages crashed on an API timeout at 630 of 643 jobs; no result from it was kept or seen, and the complete run followed.
- **Analysis plan.** The section "Analysis plan for the human rating set" was committed in `70b7d93` on 2026-11-02, before any rating, but was not tagged at the time and was not registered with any third party (its later commit `850cf98` is tagged `human-set-plan-2026-11` at release). Papers based on this protocol call it "fixed in advance", not "pre-registered".
- **Seed.** The section above says the bundle seed stays private until rating ends. Rating has ended; the file whose SHA-256 begins `118aabe6` is published as `human_set_ratings/bundle_seed.txt`.
