"""Regression tests for empty / near-empty balanced extraction failures."""

from __future__ import annotations

import numpy as np
from bs4 import BeautifulSoup

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from chromerag.density import looks_like_noise, parse_html, prune_noise_subtrees
from chromerag.hidden import remove_hidden_nodes
from chromerag.markdown_out import soup_to_markdown
from chromerag.treestats import TreeStats


class _DropAllModel:
    """Classifier that scores every block as chrome."""

    second = object()

    def predict(self, X, chars=None, box=None):  # noqa: ANN001, ARG002
        return np.full(len(X), 0.01)


class _KeepAllModel:
    """Classifier that scores every block as content (drops nothing)."""

    second = object()

    def predict(self, X, chars=None, box=None):  # noqa: ANN001, ARG002
        return np.full(len(X), 0.99)


def test_markdown_walks_main_nested_under_list_shell() -> None:
    html = """<!doctype html><html><body>
    <ul class="menu">
      <li><a href="/">Home</a></li>
      <li><a href="/blog">Blog</a></li>
      <main id="primary">
        <h1>Podcasts for IT leaders</h1>
        <p>In today’s rapidly evolving technology landscape, IT leaders must stay informed about
        industry trends while aligning with executive peers across the business.</p>
      </main>
      <footer><p>Copyright Example Inc</p></footer>
    </ul>
    </body></html>"""
    soup = parse_html(html)
    md = soup_to_markdown(soup, content_root=soup.body)
    assert "rapidly evolving technology landscape" in md
    assert "Podcasts for IT leaders" in md
    assert "Copyright Example Inc" not in md


def test_markdown_walks_main_inside_list_item_shell() -> None:
    html = """<!doctype html><html><body>
    <ul class="menu">
      <li><a href="/">Home</a></li>
      <li><div><div>
        <main id="primary">
          <h1>Tax law changes</h1>
          <p>On July 4, 2025, the legislation known as the One Big Beautiful Bill was signed into law
          and contains significant tax law changes for households and businesses alike.</p>
        </main>
      </div></div></li>
    </ul>
    </body></html>"""
    soup = parse_html(html)
    md = soup_to_markdown(soup, content_root=soup.body)
    assert "significant tax law changes" in md
    assert "One Big Beautiful Bill" in md


def test_markdown_landmark_li_skips_sibling_nav_and_promo() -> None:
    html = """<!doctype html><html><body>
    <ul>
      <li>
        <nav class="side"><a href="/a">Promo nav link one</a><a href="/b">Promo nav link two</a></nav>
        <section class="wrap">
          <main>
            <h1>Billing FAQ</h1>
            <p>Invoices are issued on the first business day of each month for active seats.</p>
          </main>
        </section>
        <aside class="promo">Buy more seats today and save on annual plans.</aside>
      </li>
    </ul>
    </body></html>"""
    soup = parse_html(html)
    md = soup_to_markdown(soup, content_root=soup.body)
    assert "Invoices are issued on the first business day" in md
    assert "Promo nav link one" not in md
    assert "Buy more seats today" not in md


def test_related_article_card_list_is_not_layout_shell() -> None:
    html = """<!doctype html><html><body><main>
    <article><h1>Main story</h1><p>The primary article body explains the release in detail for readers.</p></article>
    <ul class="related">
      <li><article><header><h2>Related one title</h2></header><p>Card blurb one.</p></article></li>
      <li><article><header><h2>Related two title</h2></header><p>Card blurb two.</p></article></li>
    </ul>
    </main></body></html>"""
    soup = parse_html(html)
    md = soup_to_markdown(soup, content_root=soup.find("main"))
    assert "primary article body explains" in md
    # Card list stays list-shaped; full related bodies are not expanded as page content.
    assert md.count("Related one title") <= 1


def test_visibility_hidden_body_dominant_content_kept() -> None:
    prose = (
        "Machine learning models learn patterns from labeled examples and generalize to new inputs. "
        * 40
    )
    links = " ".join(f'<a href="/t/{i}">Topic {i} overview page</a>' for i in range(12))
    html = f"""<!doctype html><html><body>
    <div style="visibility:hidden;min-height:100vh">
      <h1>Supervised learning guide</h1>
      <p>{prose}</p>
      <p>{links}</p>
    </div>
    <nav><a href="/">Home</a></nav>
    </body></html>"""
    soup = parse_html(html)
    remove_hidden_nodes(soup)
    text = soup.get_text(" ", strip=True)
    assert "Machine learning models learn patterns" in text
    md = ChromeRAG(
        config=PipelineConfig.from_priority(ContentPriority.BALANCED, enable_lbc=False)
    ).extract(html).markdown
    assert "Machine learning models learn patterns" in md


def test_hidden_cookie_modal_not_rescued() -> None:
    filler = "Accept cookies to continue browsing our catalog of products and services. " * 80
    html = f"""<!doctype html><html><body>
    <main><h1>Shop</h1><p>Visible product copy about seasonal jackets stays on the page.</p></main>
    <div id="cookie-banner" class="cookie consent modal" style="display:none" role="dialog">
      <p>{filler}</p>
      <a href="/privacy">Privacy</a><a href="/cookies">Cookies</a>
    </div>
    </body></html>"""
    soup = parse_html(html)
    remove_hidden_nodes(soup)
    text = soup.get_text(" ", strip=True)
    assert "Visible product copy" in text
    assert "Accept cookies to continue browsing" not in text


def test_hidden_mega_menu_not_rescued() -> None:
    links = "".join(f'<li><a href="/c/{i}">Category {i} mega menu entry</a></li>' for i in range(60))
    html = f"""<!doctype html><html><body>
    <main><h1>Home</h1><p>Welcome to the storefront with featured seasonal collections today.</p></main>
    <nav id="mega-menu" class="menu navigation" style="display:none" role="navigation">
      <ul>{links}</ul>
    </nav>
    </body></html>"""
    soup = parse_html(html)
    remove_hidden_nodes(soup)
    assert "Welcome to the storefront" in soup.get_text(" ", strip=True)
    assert "mega menu entry" not in soup.get_text(" ", strip=True)


def test_hidden_offcanvas_nav_not_rescued() -> None:
    links = "".join(f'<a href="/p/{i}">Offcanvas destination {i}</a> ' for i in range(50))
    html = f"""<!doctype html><html><body>
    <main><h1>Docs</h1><p>Visible documentation introduction covering install and configure steps.</p></main>
    <aside class="off-canvas drawer" style="visibility:hidden" role="navigation">{links}</aside>
    </body></html>"""
    soup = parse_html(html)
    remove_hidden_nodes(soup)
    assert "Visible documentation introduction" in soup.get_text(" ", strip=True)
    assert "Offcanvas destination" not in soup.get_text(" ", strip=True)


def test_rescued_wrapper_drops_nested_hidden_modal() -> None:
    prose = ("Hidden article prose about distributed systems design patterns and tradeoffs. " * 50)
    html = f"""<!doctype html><html><body>
    <div style="display:none">
      <h1>Distributed systems</h1>
      <p>{prose}</p>
      <div class="modal dialog" style="display:none" role="dialog">
        <p>{"Subscribe to the newsletter modal copy now. " * 40}</p>
      </div>
    </div>
    </body></html>"""
    soup = parse_html(html)
    remove_hidden_nodes(soup)
    text = soup.get_text(" ", strip=True)
    assert "distributed systems design patterns" in text
    assert "newsletter modal copy" not in text


def test_aria_hidden_chrome_not_rescued() -> None:
    html = """<!doctype html><html><body>
    <main><h1>Page</h1><p>Visible body text about the product launch timeline remains.</p></main>
    <div aria-hidden="true" class="cookie consent" role="dialog">
      <p>""" + ("We use cookies for analytics and advertising partners worldwide. " * 40) + """</p>
    </div>
    </body></html>"""
    soup = parse_html(html)
    remove_hidden_nodes(soup)
    assert "product launch timeline" in soup.get_text(" ", strip=True)
    assert "cookies for analytics" not in soup.get_text(" ", strip=True)


def test_article_header_inside_river_card_is_not_pruned() -> None:
    html = """<!doctype html><html><body><main>
    <h1>headphones</h1>
    <section>
      <article class="river-article">
        <header>
          <h2><a href="/a">Beats Solo 4 gains Walmart-exclusive color options today</a></h2>
          <time>1 month ago</time>
        </header>
      </article>
      <article class="river-article">
        <header>
          <h2><a href="/b">AirPods Pro Live Translation is compelling for travelers</a></h2>
          <time>2 months ago</time>
        </header>
      </article>
    </section>
    </main></body></html>"""
    soup = parse_html(html)
    body = soup.body
    stats = TreeStats(body)
    header = soup.find("header")
    assert header is not None
    assert looks_like_noise(header, page_text_len=stats.text_len(body), stats=stats) is False
    md = ChromeRAG(
        config=PipelineConfig.from_priority(ContentPriority.BALANCED, enable_lbc=False)
    ).extract(html).markdown
    assert "Beats Solo 4" in md
    assert "AirPods Pro" in md


def test_site_header_inside_article_is_pruned() -> None:
    html = """<!doctype html><html><body><main>
    <article>
      <header class="global-header" role="banner">
        <nav><a href="/">Home</a><a href="/shop">Shop</a></nav>
        <h1>Site name</h1>
      </header>
      <p>Real article paragraph about firmware updates for the keyboard line.</p>
    </article>
    </main></body></html>"""
    soup = parse_html(html)
    prune_noise_subtrees(soup)
    text = soup.get_text(" ", strip=True)
    assert "firmware updates for the keyboard" in text
    assert "Site name" not in text or soup.find("header") is None


def test_collapsed_lbc_output_retries_without_classifier() -> None:
    # Many separate blocks so the learned filter runs (needs >= 4) and can wipe them all.
    paras = [
        "<p>These are jobs at early-stage startups listed for candidates who want a single index.</p>",
        "<p>Each row lists the company, role, and location so people can scan openings quickly.</p>",
        "<p>Backend engineers build APIs that move data between product services and warehouses.</p>",
        "<p>Designers ship research-backed product work with partners across time zones monthly.</p>",
        "<p>Support leads write clear docs that help customer success teams resolve tickets.</p>",
        "<p>Infrastructure teams keep clusters healthy while developers deploy changes every day.</p>",
    ]
    html = "<!doctype html><html><body>" + "".join(paras) + "</body></html>"
    rag = ChromeRAG(
        config=PipelineConfig.from_priority(ContentPriority.BALANCED),
        lbc_model=_DropAllModel(),  # type: ignore[arg-type]
    )
    result = rag.extract(html)
    assert "early-stage startups" in result.markdown
    assert any("without the learned block filter" in w for w in result.warnings)


def test_partial_retry_keeps_final_quality_warnings() -> None:
    """Retry notes must not early-return past little-Markdown / confidence hooks."""

    class _LowConfKeep(_KeepAllModel):
        def predict(self, X, chars=None, box=None):  # noqa: ANN001, ARG002
            # At keep threshold: blocks stay, but expected F1 stays under LOW_CONFIDENCE_F1.
            return np.full(len(X), 0.50)

    paras = [
        "<h1>Open roles</h1>",
        "<p>These are jobs at early-stage startups listed for candidates who want a single index of openings.</p>",
        "<p>Each row lists the company, role, and location so people can scan openings quickly today.</p>",
        "<p>Backend engineers build APIs that move data between product services and warehouses daily.</p>",
        "<p>Designers ship research-backed product work with partners across time zones every month.</p>",
        "<p>Support leads write clear docs that help customer success teams resolve tickets faster.</p>",
    ]
    html = "<!doctype html><html><body>" + "".join(paras) + "</body></html>"
    rag = ChromeRAG(
        config=PipelineConfig.from_priority(ContentPriority.BALANCED),
        lbc_model=_LowConfKeep(),  # type: ignore[arg-type]
    )
    result = rag.extract(html)
    assert "early-stage startups" in result.markdown
    assert any("Low extraction confidence" in w for w in result.warnings)


def test_real_answer_skips_coverage_retry() -> None:
    html = """<!doctype html><html><body>
    <header>""" + "".join(f'<a href="/n/{i}">Nav item {i}</a> ' for i in range(40)) + """</header>
    <main>
      <h1>Portman Lights P1 Retro Case</h1>
      <p>Special Order. Expected availability two to four weeks from purchase date.</p>
      <p>$1,772.00</p>
    </main>
    <footer>""" + "".join(f'<a href="/f/{i}">Footer link {i}</a> ' for i in range(40)) + """</footer>
    </body></html>"""
    rag = ChromeRAG(
        config=PipelineConfig.from_priority(ContentPriority.BALANCED),
        lbc_model=_KeepAllModel(),  # type: ignore[arg-type]
    )
    result = rag.extract(html)
    assert "Portman Lights P1 Retro Case" in result.markdown
    assert not any("retried with body root" in w for w in result.warnings)


def test_third_pass_skipped_when_lbc_dropped_nothing() -> None:
    # Thin main + huge chrome makes ratio look collapsed, but LBC keeps all blocks.
    chrome = "".join(f"<p><a href='/x/{i}'>Chrome link number {i} with filler words here</a></p>" for i in range(30))
    html = f"""<!doctype html><html><body>
    <nav>{chrome}</nav>
    <main><h1>Note</h1><p>Short visible note.</p></main>
    </body></html>"""
    rag = ChromeRAG(
        config=PipelineConfig.from_priority(ContentPriority.BALANCED),
        lbc_model=_KeepAllModel(),  # type: ignore[arg-type]
    )
    result = rag.extract(html)
    assert not any("without the learned block filter" in w for w in result.warnings)


def test_whitespace_only_emphasis_keeps_word_separation() -> None:
    from chromerag.density import parse_html
    from chromerag.markdown_out import _inline

    bold = _inline(parse_html("<p>Private clouds<b> </b>are cool</p>").find("p"))
    italic = _inline(parse_html("<p>Private clouds<em> </em>are cool</p>").find("p"))
    assert "****" not in bold
    assert "**" not in bold
    assert "clouds are" in bold
    assert italic == "Private clouds are cool" or (
        "clouds are" in italic and italic.count("*") == 0
    )


def test_adjacent_bold_tags_do_not_glue_markers() -> None:
    from chromerag.density import parse_html
    from chromerag.markdown_out import _inline

    text = _inline(parse_html("<p><b>foo</b><b>bar</b></p>").find("p"))
    assert "****" not in text
    assert "foo" in text and "bar" in text


def test_break_span_separates_joined_sentences() -> None:
    from chromerag.density import parse_html
    from chromerag.markdown_out import _inline

    text = _inline(
        parse_html('<p>emotional regulation.<span class="br"></span>The brain can change</p>').find("p")
    )
    assert "regulation.The" not in text
    assert "regulation." in text and "The brain" in text


def test_duplicate_h1_emitted_once() -> None:
    html = """<!doctype html><html><body><main>
    <h1>Same Title Page Heading</h1>
    <p>First body paragraph with enough words for extraction thresholds easily today.</p>
    <h1>Same Title Page Heading</h1>
    <p>Second body paragraph with enough words for extraction thresholds easily today.</p>
    </main></body></html>"""
    md = ChromeRAG(config=PipelineConfig(enable_dvdf=False, enable_lbc=False)).extract(html).markdown
    assert md.count("# Same Title Page Heading") == 1


def test_js_shell_warning_cleared_when_body_has_prose() -> None:
    # Noscript-held article text is extracted, so a JS-shell warning must not stick.
    prose = "Certificate renewal steps for ACME clients that order chains from the authority. " * 20
    html = f"""<!doctype html><html><body>
    <div id="root"></div>
    <noscript><main><h1>Forum topic</h1><p>{prose}</p></main></noscript>
    <script>{"x" * 2000}</script>
    </body></html>"""
    result = ChromeRAG(config=PipelineConfig(enable_dvdf=False, enable_lbc=False)).extract(html)
    assert "Certificate renewal" in result.markdown
    assert not any("JavaScript-rendered shell" in w for w in result.warnings)


def test_empty_body_warns_using_body_words_not_front_matter_tokens() -> None:
    # Chrome-only body still yields body_words before prune; front matter keeps tokens high.
    prose = "Roasted coffee beans sold by the bag since 2012 for fans of bold flavor everywhere. "
    links = " ".join(f'<a href="/p/{i}">Shop product number {i} today</a>' for i in range(50))
    html = f"""<!doctype html><html><head>
    <title>Shop Coffee Collection Storefront</title>
    <meta name="description" content="{prose * 3}">
    <script type="application/ld+json">{{
      "@context":"https://schema.org","@type":"CollectionPage",
      "name":"Shop Coffee Collection Storefront",
      "description":"{prose * 3}",
      "url":"https://example.com/collections/coffee"
    }}</script>
    </head><body>
    <main id="MainContent" class="content-for-layout"></main>
    <nav class="menu" role="navigation">{links}</nav>
    <footer class="site-footer">{links}</footer>
    </body></html>"""
    result = ChromeRAG(
        config=PipelineConfig.from_priority(ContentPriority.BALANCED),
        lbc_model=_DropAllModel(),  # type: ignore[arg-type]
    ).extract(html, url="https://example.com/collections/coffee")
    body = result.markdown
    if body.startswith("---"):
        body = body.split("---", 2)[-1]
    import re

    assert len(re.findall(r"\w+", body)) < 40
    assert result.tokens_estimate >= 40  # front matter alone can look "large"
    assert any("very little Markdown" in w for w in result.warnings)


def test_rules_never_drop_html_body_main_or_content_root() -> None:
    from chromerag.density import parse_html
    from chromerag.rules_engine import Rule, RuleIndex
    from chromerag.treestats import TreeStats

    html = """<!doctype html><html class="evil"><body class="evil"><main class="evil" id="root">
    <p>Keep this article paragraph with enough words for extraction thresholds.</p>
    <div class="evil">Drop me chrome</div>
    </main></body></html>"""
    soup = parse_html(html)
    main = soup.find("main")
    assert main is not None
    rules = [
        Rule(
            id="test.drop_evil",
            action="drop",
            scope="anywhere",
            match=[{"class_token": "evil"}],
            max_chars=100000,
            evidence="synthetic",
            fixture="n/a",
        )
    ]
    idx = RuleIndex(rules)
    idx.apply(soup, content_root=main, page_type="article", stats=TreeStats(soup.body or soup))
    assert soup.find("html") is not None
    assert soup.find("body") is not None
    assert soup.find("main") is not None
    assert "Keep this article paragraph" in soup.get_text(" ", strip=True)


def test_table_rescue_skips_repeat_dropped_duplicate() -> None:
    import numpy as np

    from chromerag.blockfeatures import Block
    from chromerag.density import parse_html
    from chromerag.extractor import ChromeRAG as Extractor
    from chromerag.tables import is_rescueable_data_table
    from chromerag.treestats import TreeStats

    cell = "Team plan with forty nine dollars monthly for shared seats"
    html = f"""<html><body><main>
    <h2>Specs</h2>
    <table><tr><th>Plan</th><th>Price</th></tr><tr><td>{cell}</td><td>49</td></tr></table>
    <h2>Other</h2>
    <table><tr><th>Plan</th><th>Price</th></tr><tr><td>{cell}</td><td>49</td></tr></table>
    </main></body></html>"""
    soup = parse_html(html)
    body = soup.body
    assert body is not None
    tables = soup.find_all("table")
    assert all(is_rescueable_data_table(t) for t in tables)
    blocks = [
        Block(soup.find("h2"), "Specs"),
        Block(tables[0], tables[0].get_text(" ", strip=True)),
        Block(soup.find_all("h2")[1], "Other"),
        Block(tables[1], tables[1].get_text(" ", strip=True)),
    ]
    # First table kept; second identical text was repeat-dropped.
    keep = [True, True, True, False]
    proba = np.array([0.9, 0.2, 0.9, 0.2])
    out, n = Extractor._rescue_data_tables(
        blocks, keep, TreeStats(body), soup.find("main"), proba, PipelineConfig()
    )
    assert out[3] is False
    assert n == 0


def test_main_dl_and_figure_render_in_markdown() -> None:
    html = """<!doctype html><html><body><main>
    <h2>Glossary</h2>
    <dl><dt>Term</dt><dd>Definition with enough words for the block classifier.</dd></dl>
    <figure><img alt="diagram"><figcaption>Figure caption explaining the diagram.</figcaption></figure>
    <p>Supporting paragraph with enough words for extraction thresholds easily today.</p>
    </main></body></html>"""
    md = ChromeRAG(config=PipelineConfig(enable_dvdf=False, enable_lbc=False)).extract(html).markdown
    assert "**Term**" in md and "Definition with enough words" in md
    assert "Figure caption explaining" in md


def _time_limit(seconds: float) -> float:
    """Wall-clock limit for timing tests; shared CI runners set CHROMERAG_TEST_TIME_SCALE (>1)."""
    import os

    return seconds * float(os.environ.get("CHROMERAG_TEST_TIME_SCALE", "1"))


def test_large_main_table_keeps_at_least_thirty_thousand_rows() -> None:
    import time

    rows = "".join(f"<tr><td>A{i}</td><td>B{i}</td></tr>" for i in range(30000))
    html = (
        "<html><body><main><table><tr><th>A</th><th>B</th></tr>"
        + rows
        + "</table></main></body></html>"
    )
    start = time.perf_counter()
    md = ChromeRAG(config=PipelineConfig(enable_dvdf=False, enable_lbc=False)).extract(html).markdown
    assert time.perf_counter() - start < _time_limit(5.0)
    assert "A29999" in md and "B29999" in md
    assert "[Table truncated after" not in md


def _wrapped_page(inner: str) -> str:
    body = "<p>" + "Alpha beta gamma delta epsilon zeta eta theta iota kappa. " * 30 + "</p>"
    return f"<html><body><main><h1>Topic heading</h1>{body}{inner}{body}</main></body></html>"


def test_figure_wrapping_content_keeps_the_content():
    from chromerag.markdown_out import soup_to_markdown

    soup = BeautifulSoup("<figure><p>Wrapped body words here.</p><figcaption>Cap text</figcaption></figure>", "lxml")
    md = soup_to_markdown(soup)
    assert "Wrapped body words here." in md and "Cap text" in md


def test_dl_wrapping_blocks_keeps_every_block():
    from chromerag.markdown_out import soup_to_markdown

    soup = BeautifulSoup("<dl><dd><p>First para here.</p><p>Second para here.</p></dd></dl>", "lxml")
    md = soup_to_markdown(soup)
    assert "First para here." in md and "Second para here." in md


def test_dl_with_paragraph_dd_keeps_all_terms_and_defs():
    from chromerag.markdown_out import soup_to_markdown

    html = "<dl><dt>T1</dt><dd>D1</dd><dt>T2</dt><dd><p>D2</p></dd></dl>"
    md = soup_to_markdown(BeautifulSoup(html, "lxml"))
    assert all(tok in md for tok in ("T1", "D1", "T2", "D2"))


def test_dl_consecutive_dts_keep_both_terms():
    from chromerag.markdown_out import soup_to_markdown

    html = "<dl><dt>T1</dt><dt>T2</dt><dd>D</dd></dl>"
    md = soup_to_markdown(BeautifulSoup(html, "lxml"))
    assert "T1" in md and "T2" in md and "D" in md


def test_long_glossary_dl_not_treated_as_product_metafield():
    from chromerag.extractor import ChromeRAG as Extractor

    entries = "".join(
        f"<dt>Glossary term number {i} with a long label</dt>"
        f"<dd>Detailed definition number {i} explaining the concept with plenty of words for rescue.</dd>"
        for i in range(12)
    )
    soup = BeautifulSoup(f"<dl>{entries}</dl>", "lxml")
    dl = soup.find("dl")
    assert dl is not None
    assert Extractor._is_product_metafield_dl(dl) is False


def test_pre_literal_asterisks_not_broken():
    from chromerag.markdown_out import soup_to_markdown

    md = soup_to_markdown(BeautifulSoup("<main><pre>char ****p;</pre></main>", "lxml"))
    assert "****" in md
    assert "** **" not in md


def test_inline_code_literal_asterisks_not_broken():
    from chromerag.markdown_out import soup_to_markdown

    md = soup_to_markdown(BeautifulSoup("<main><p>x <code>****</code> y</p></main>", "lxml"))
    assert "`****`" in md


def test_large_table_keeps_every_row():
    rows = "".join(f"<tr><td>r{i}</td><td>CELL{i}x</td></tr>" for i in range(5000))
    html = _wrapped_page(f"<h2>Data</h2><table><tr><th>a</th><th>b</th></tr>{rows}</table>")
    md = ChromeRAG().extract(html).markdown
    assert all(f"CELL{i}x" in md for i in (0, 2500, 4999))


def test_dd_with_blocks_keeps_direct_text():
    md = soup_to_markdown(BeautifulSoup("<dl><dt>token</dt><dd>Secret bearer key:<ul><li>Header</li></ul></dd></dl>", "lxml"))
    assert "token" in md and "Secret bearer key:" in md and "Header" in md
