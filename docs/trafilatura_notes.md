# Trafilatura techniques (study notes)

Trafilatura 2.2.0 uses layered XPath discard lists before extraction. OVERALL_DISCARD
targets share/social, newsletter, tags, sidebar/banner/breadcrumb, author/byline, footer,
nav/menu, related stories, ads (outbrain/taboola), consent/modal, and meta chrome (ratings,
timestamps, overlays). PRECISION_DISCARD drops bare headers and link-heavy footers. TEASER and
COMMENTS lists remove teaser blocks and comment widgets (Disqus, respond forms). DISCARD_IMAGE
drops caption wrappers. Content-finding BODY_XPATH is separate (already adapted in content_root).

htmlprocessing applies those XPaths via prune_unwanted_nodes (optional backup if too much text
vanishes). link_density_test drops blocks where link text exceeds 80% of visible text when the
block is short (threshold varies by tag/position). delete_by_link_density walks p/div items.
link_density_test_tables does the same for tables over 200 chars. tree_cleaning strips script,
style, and empty nodes; convert_tags normalizes links and inline markup. text_chars_test and
textfilter drop empty or whitespace-only nodes during extraction.

main_extractor discards non-catalog tags in handle_other_elements, filters short titles via
text_chars_test, and runs link-density pruning on paragraphs. Tail text is preserved when
deleting nodes so prose after removed chrome survives. handle_paragraphs unwraps inline
formatting and drops empty paragraphs.

deduplication uses Simhash bag-of-words hashing plus an LRU counter: repeated text over
min_duplcheck_size that appears more than max_repetitions times is dropped (not ported; ChromeRAG
uses LBC and density instead).

## Adapted into ChromeRAG

- XPath discard token groups → `src/chromerag/rules/trafilatura_inspired.yaml` (class/id
  patterns for share, related/teasers, comments, newsletter, sidebar, ads, author, pagination,
  skip/back-to-top, footer, print tools, tag lists). Not ported: BODY_XPATH, metadata XPaths,
  deduplication, or raw cookie-id matching (too broad).
- link_density_test short-block rule → `trafilatura_link_blocks` in trafilatura_ideas.py.
- text_chars_test / micro-empty leaves → `trafilatura_micro` in trafilatura_ideas.py.
