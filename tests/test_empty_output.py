"""Regression tests for empty / near-empty balanced extraction failures."""

from __future__ import annotations

import numpy as np

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
