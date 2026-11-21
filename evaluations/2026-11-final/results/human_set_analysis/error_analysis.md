# Human rating set: qualitative error analysis (post hoc, descriptive)

**Post hoc and descriptive.** Not in the pre-registered plan. One coder (an AI assistant) coded the pages after all ratings were in and after unblinding, knowing which tool produced each output and how the raters voted. There is no second coder and no agreement figure, so the counts below describe these pages; they are not a test. Nothing in the tool, the pages or the ratings was changed.

Clarification (2026-11-20): the coder was a Claude model (Claude Opus 5.5) working as the author's assistant.

## Pages

Listed in `posthoc.json` under `error_analysis_cases` (written by `poc/human_set_posthoc.py`):

- every page where the human majority preferred Trafilatura over ChromeRAG (15);
- every page where the human majority preferred Readability over ChromeRAG (13; 2 pages are in both lists);
- for contrast, 15 pages where the majority preferred ChromeRAG over Trafilatura, drawn with `random.Random(20261120)` from the sorted page ids of the 32 such pages before any page was read.

Material per page: the offline page copy and the three outputs exactly as raters saw them (rating bundle, author-held).

## Coding scheme (fixed before coding)

One primary code per page, for the main reason the preferred output is better; an optional secondary code. For a ChromeRAG loss the code says what ChromeRAG's output did relative to the preferred baseline output. For a contrast win the same codes are applied to Trafilatura's output relative to ChromeRAG's.

| Code | Meaning |
|---|---|
| MISSING_BLOCK | Leaves out a block of main content (one or more paragraphs or sections, the lead, a fact box holding main content) that the preferred output keeps. |
| MISSING_STRUCTURE | Keeps the prose but loses or flattens a table, list, definition list, code block, figure caption or step sequence, or loses its items. |
| TRUNCATED_END | Stops before the end of the main content. |
| KEPT_CHROME | Keeps navigation, menus, breadcrumbs, related links, calls to action, cookie, legal or footer text that the preferred output drops. |
| KEPT_COMMENTS | Keeps comments, reviews or replies outside the main content (not applied to forum threads, where replies are the content). |
| METADATA | The difference lies only in title, byline, date, front matter or header lines. |
| NEAR_IDENTICAL | The outputs carry the same blocks; differences are a few words or formatting only, and raters split or leaned on small differences. |
| OTHER | None of the above; described in words. |

Procedure: for each page, list the text blocks (lines) found in one output and not the other, with word counts and their position (start, middle, end of the output); read those blocks and, where needed, the page copy; assign the code for the largest difference in main content. Raters scored content (main content kept) and chrome (noise removed) separately, so a page can have a content-side and a chrome-side difference; the primary code goes to the one that is larger in words of main content affected.

## Results

Coded on 2026-11-20 after the scheme above was committed. Votes are the raters' pairwise verdicts on the page (ChromeRAG / baseline / tie).

### Counts

| Primary code | ChromeRAG lost to Trafilatura (15) | ChromeRAG lost to Readability (13) | Contrast: Trafilatura lost to ChromeRAG (15) |
|---|---|---|---|
| MISSING_BLOCK | 6 | 2 | 7 |
| MISSING_STRUCTURE | 3 | 0 | 3 |
| TRUNCATED_END | 0 | 0 | 2 |
| KEPT_CHROME | 0 | 2 | 0 |
| KEPT_COMMENTS | 0 | 0 | 0 |
| METADATA | 0 | 5 | 3 |
| NEAR_IDENTICAL | 4 | 4 | 0 |
| OTHER | 2 | 0 | 0 |

Two pages (fda.gov, stanford.edu statement) are losses to both baselines and are coded NEAR_IDENTICAL in both columns.

### What the counts say (descriptive)

- **Against Trafilatura**, the clearest losses are ChromeRAG keeping too little on short hub, landing and product pages: 9 of 15 are MISSING_BLOCK or MISSING_STRUCTURE, 7 of these 9 on corporate marketing, listing or hub pages (two automotive, two manufacturing, an AI vendor, a retail listing, a university hub); the other two are a government challenge page and a research note. One loss (a research note) is the known gap on figure captions and footnote text. Four losses are near-identical outputs where the majority was 2 of 3.
- **Against Readability**, no loss involves ChromeRAG dropping main text except two key-figure blocks on one finance site. Nine of 13 are METADATA (mostly a missing page-title line: Readability's output opens with the page title on all 75 pages, ChromeRAG's on 41) or NEAR_IDENTICAL. Two are kept chrome (a ".gov" banner; promotional teasers).
- **Where ChromeRAG won**, Trafilatura dropped main content: the question or every reply after the first on 4 forum pages (MISSING_BLOCK, TRUNCATED_END), store or program details and FAQ sections on service pages, or list items and headings (MISSING_STRUCTURE). Three wins are METADATA only (date, authors).
- No page in any list was coded KEPT_COMMENTS. Kept chrome explains few human verdicts either way; most decided pages turn on main content kept or lost.

### Examples (anonymized to the site)

- ford.com (automotive hub page): ChromeRAG kept 13 words (the section names); Trafilatura kept the awards and vehicle blocks (620 words). Raters 3 of 3 for Trafilatura.
- jpmorganchase.com (research note): same body text, but ChromeRAG lost the three figure captions and left the footnote numbers empty. Raters 2 of 3 for Trafilatura.
- stanford.edu (university hub): link text inside sentences and lists was dropped, so school names and news headlines are missing ("The (GSB) seeks to ..."). Raters 2 of 2 for Trafilatura.
- federalreserve.gov (publication page): ChromeRAG kept the ".gov official website" banner; Readability gave the title and update date instead. Raters 2 of 3 for Readability.
- discuss.python.org (forum thread, a ChromeRAG win): Trafilatura kept only the first post (332 of about 1,600 words); ChromeRAG kept the whole thread. Raters 2 of 3 for ChromeRAG, 1 tie.

### Coding per page

| Page | Site | Group | Comparison | Votes | Primary | Secondary | Note |
|---|---|---|---|---|---|---|---|
| human-0011 | docs.github.com | technology | lost to Trafilatura | 1/2/0 | NEAR_IDENTICAL | TRUNCATED_END | 243 vs 259 words; last article card missing, stray tag labels kept |
| human-0012 | docs.github.com | technology | lost to Trafilatura | 0/2/1 | NEAR_IDENTICAL | TRUNCATED_END | same pattern, 264 vs 270 words |
| human-0034 | nvidia.com | ai | lost to Trafilatura | 0/2/1 | OTHER | KEPT_CHROME | sign-up form page with no main text; ChromeRAG kept form labels and a raw HTML fragment, Trafilatura 950 words of product-menu descriptions |
| human-0038 | cohere.com | ai | lost to Trafilatura | 0/3/1 | MISSING_BLOCK | KEPT_CHROME | kept only a "Read this next" teaser; lost the article title and summary |
| human-0060 | nih.gov | medical | lost to Trafilatura | 1/2/0 | MISSING_BLOCK | | lost the summary box (prize total, closing date) and closing Contact and Winners sections; otherwise the same 3,700 words |
| human-0062 | fda.gov | medical | lost to Trafilatura and Readability | 0/2/1, 0/2/1 | NEAR_IDENTICAL | | differs by a back link and a report-download line |
| human-0071 | jpmorganchase.com | finance | lost to Trafilatura | 0/2/1 | MISSING_STRUCTURE | MISSING_BLOCK | figure captions and footnote text lost; acknowledgments lost |
| human-0083 | homedepot.com | retail | lost to Trafilatura | 0/2/1 | MISSING_STRUCTURE | | listing: guide titles kept, each one-line description lost; Trafilatura also kept store-menu chrome |
| human-0090 | toyota.com | automotive | lost to Trafilatura | 0/2/0 | MISSING_BLOCK | | 35 words; vehicle descriptions lost |
| human-0092 | ford.com | automotive | lost to Trafilatura | 0/3/0 | MISSING_BLOCK | | 13 words; awards and vehicle blocks lost |
| human-0106 | siemens.com | manufacturing | lost to Trafilatura | 0/2/0 | MISSING_STRUCTURE | METADATA | title and items of an industries list lost (136 vs 153 words) |
| human-0108 | siemens.com | manufacturing | lost to Trafilatura | 0/2/1 | MISSING_BLOCK | | developer section and tabbed feature section lost |
| human-0124 | mit.edu | reference | lost to Trafilatura | 0/5/0 | MISSING_BLOCK | MISSING_STRUCTURE | two lead paragraphs and the section headings lost |
| human-0128 | stanford.edu | reference | lost to Trafilatura and Readability | 0/2/1, 0/2/1 | NEAR_IDENTICAL | | same statement; Trafilatura adds a date line, Readability a title with the site name |
| human-0129 | stanford.edu | reference | lost to Trafilatura | 0/2/0 | OTHER | MISSING_STRUCTURE | inline link text dropped: school names and news headlines missing |
| human-0014 | ibm.com | technology | lost to Readability | 0/2/1 | NEAR_IDENTICAL | | same press release; Readability breaks lines at inline markup |
| human-0024 | openai.com | ai | lost to Readability | 0/2/1 | METADATA | | Readability has the page title; ChromeRAG a "Publication" label |
| human-0048 | digitalrealty.com | data_center | lost to Readability | 0/2/1 | METADATA | | no title line; one joined word |
| human-0054 | vertiv.com | data_center | lost to Readability | 0/3/0 | KEPT_CHROME | METADATA | promotional teasers kept before the news items; news dates missing |
| human-0065 | clevelandclinic.org | medical | lost to Readability | 0/3/0 | NEAR_IDENTICAL | | same episode list; ChromeRAG adds a breadcrumb and episode headings; no main-content difference found |
| human-0074 | goldmansachs.com | finance | lost to Readability | 0/3/2 | METADATA | | title missing; "Related Tags" kept |
| human-0077 | visa.com | finance | lost to Readability | 0/2/1 | MISSING_BLOCK | METADATA | page heading and key-figures block lost |
| human-0078 | visa.com | finance | lost to Readability | 0/3/0 | MISSING_BLOCK | | key-figures block lost, its footnotes kept |
| human-0125 | mit.edu | reference | lost to Readability | 0/2/1 | METADATA | | identical except the title line |
| human-0136 | federalreserve.gov | finance | lost to Readability | 0/2/1 | KEPT_CHROME | METADATA | ".gov" banner kept; no title or update date |
| human-0158 | discourse.ubuntu.com | forum | lost to Readability | 0/3/0 | METADATA | | all posts kept; the original poster's name missing |
| human-0006 | learn.microsoft.com | technology | won vs Trafilatura | 2/1/0 | MISSING_STRUCTURE | KEPT_CHROME | Trafilatura lost the product directory list, kept a browser banner and promos |
| human-0007 | cloud.google.com | technology | won vs Trafilatura | 3/0/0 | MISSING_BLOCK | | Trafilatura 61 words; news items lost |
| human-0029 | deepmind.google | ai | won vs Trafilatura | 2/0/1 | METADATA | | Trafilatura lost date, authors and venue |
| human-0042 | databricks.com | ai | won vs Trafilatura | 3/0/0 | MISSING_STRUCTURE | | Trafilatura lost the key-takeaway list and section headings |
| human-0075 | goldmansachs.com | finance | won vs Trafilatura | 2/1/0 | MISSING_BLOCK | | Trafilatura lost the intro and program sections |
| human-0079 | apple.com | retail | won vs Trafilatura | 3/0/0 | MISSING_BLOCK | KEPT_CHROME | Trafilatura lost store address, hours and services, kept a generic promo |
| human-0096 | energy.gov | energy | won vs Trafilatura | 2/0/1 | MISSING_STRUCTURE | METADATA | list items emptied; title missing |
| human-0109 | verizon.com | telecom | won vs Trafilatura | 2/0/1 | MISSING_BLOCK | MISSING_STRUCTURE | FAQ section and step lists lost |
| human-0110 | verizon.com | telecom | won vs Trafilatura | 2/0/1 | METADATA | | date and webcast lines lost |
| human-0123 | britannica.com | reference | won vs Trafilatura | 3/0/0 | MISSING_BLOCK | | article excerpt and related entries lost (ChromeRAG lacked the title) |
| human-0135 | census.gov | reference | won vs Trafilatura | 3/0/0 | METADATA | | title and date lost; raw superscript markup |
| human-0141 | learn.microsoft.com (Q&A) | forum | won vs Trafilatura | 2/0/1 | MISSING_BLOCK | | Trafilatura lost the question, kept the answer |
| human-0146 | repost.aws | forum | won vs Trafilatura | 2/0/1 | MISSING_BLOCK | | Trafilatura lost the question |
| human-0148 | discuss.python.org | forum | won vs Trafilatura | 3/0/0 | TRUNCATED_END | | Trafilatura kept the first post only |
| human-0150 | discuss.python.org | forum | won vs Trafilatura | 2/0/1 | TRUNCATED_END | | Trafilatura kept the first post only |

For a contrast win the codes describe Trafilatura's output. Votes for the two pages lost to both baselines are given against Trafilatura, then against Readability.
