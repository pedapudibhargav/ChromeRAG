"""Unit tests for generic structural chrome removal."""

from __future__ import annotations

import pytest

from chromerag import ChromeRAG, PipelineConfig
from chromerag.density import parse_html
from chromerag.generic_chrome import drop_generic_chrome, infer_page_kind_hint


def _md(html: str, **cfg_overrides) -> str:
    cfg = PipelineConfig(enable_dvdf=False, enable_lbc=False, **cfg_overrides)
    return ChromeRAG(config=cfg).extract(html).markdown.lower()


def _diag(html: str, **cfg_overrides) -> dict:
    cfg = PipelineConfig(enable_dvdf=False, enable_lbc=False, enable_rules=False, **cfg_overrides)
    return ChromeRAG(config=cfg).extract(html).diagnostics["generic_chrome"]


def _long_body() -> str:
    return (
        "Body text with enough words for extraction tests here today and additional "
        "sentences so chrome blocks stay under the twenty percent removal guard on "
        "short fixture pages used throughout these unit tests for generic chrome rules "
        "without triggering the cumulative word budget safety limit during removal."
    )


def _substantive_para(label: str) -> str:
    return (
        f"{label} paragraph with enough words to count as substantive article body "
        "content here today and additional filler words so the trim-tail guard sees "
        "a real block instead of skipping the page for too few substantive sections."
    )


def test_toc_dropped_with_label() -> None:
    html = """<html><body><main>
    <h1>Guide</h1>
    <p>Intro paragraph with enough words to establish real article body content here.</p>
    <h2>On this page</h2>
    <nav><ul>
      <li><a href="#a">Alpha section</a></li>
      <li><a href="#b">Beta section</a></li>
      <li><a href="#c">Gamma section</a></li>
      <li><a href="#d">Delta section</a></li>
      <li><a href="#e">Epsilon section</a></li>
    </ul></nav>
    <h2 id="a">Alpha</h2><p>Alpha body text with enough detail for readers.</p>
    </main></body></html>"""
    md = _md(html)
    assert "on this page" not in md
    assert "alpha section" not in md or "alpha body" in md


def test_toc_like_list_that_is_content_kept() -> None:
    html = """<html><body><main>
    <h1>Index</h1>
    <ul>
      <li><a href="#one">Chapter one explains widgets in depth with many words</a></li>
      <li><a href="#two">Chapter two covers gadgets with long descriptive titles</a></li>
      <li><a href="#three">Chapter three details tools with extended summaries here</a></li>
      <li><a href="#four">Chapter four reviews parts with lengthy chapter names</a></li>
      <li><a href="#five">Chapter five finishes kits with verbose link labels too</a></li>
    </ul>
    </main></body></html>"""
    soup = parse_html(html)
    root = soup.find("main")
    drop_generic_chrome(soup, root, None, cfg=PipelineConfig())
    text = root.get_text(" ", strip=True).lower()
    assert "chapter one" in text
    assert _diag(html)["toc"] == 0


def test_pager_dropped_at_bottom() -> None:
    html = """<html><body><main>
    <h1>Lesson</h1>
    <p>Lesson body with enough words to pass extraction thresholds easily today.</p>
    <nav><a href="/prev">Previous</a> <a href="/next">Go to next lesson</a></nav>
    </main></body></html>"""
    md = _md(html)
    assert "go to next lesson" not in md
    assert "lesson body" in md


def test_pager_mid_page_kept_without_class() -> None:
    html = """<html><body><main>
    <h1>Docs</h1>
    <nav><a href="/prev">Previous</a> <a href="/next">Next</a></nav>
    <p>Middle pager should stay when it is not in the last fifteen percent.</p>
    <p>More body text padding the page so the nav sits early in document order.</p>
    <p>Even more filler paragraphs to push position fraction below the cutoff.</p>
    <p>Final paragraph ensuring the navigation block is not at the page tail.</p>
    </main></body></html>"""
    md = _md(html)
    assert "middle pager should stay" in md


def test_comments_dropped_on_article() -> None:
    html = """<html><body><article>
    <h1>Post title</h1>
    <p>Article body with enough words to represent the main blog content here.</p>
    <section id="comments"><p>User spam comment that should be removed from output.</p></section>
    </article></body></html>"""
    md = _md(html)
    assert "user spam comment" not in md
    assert "article body" in md
    assert _diag(html)["comments"] >= 1


def test_comments_kept_on_forum() -> None:
    html = """<html><body><main itemscope itemtype="https://schema.org/DiscussionForumPosting">
    <h1>Thread</h1>
    <div class="post"><p>Original question about hiking boots and trail conditions.</p></div>
    <div id="comments"><p>Reply from another member with useful trail advice here.</p></div>
    </main></body></html>"""
    md = _md(html)
    assert "reply from another member" in md
    assert infer_page_kind_hint(parse_html(html)) == "forum"
    assert _diag(html)["comments"] == 0


def test_related_posts_dropped() -> None:
    html = """<html><body><article>
    <h1>Story</h1>
    <p>Main story body with enough words to dominate the extracted page text and keep
    the related-post guard from blocking removal of the link list at the bottom of this
    article. Additional sentences expand the narrative so the body clearly outweighs the
    short related links block appended after the primary reading experience for visitors.</p>
    <h3>Related posts</h3>
    <ul>
      <li><a href="/a">Other story alpha</a></li>
      <li><a href="/b">Other story beta</a></li>
      <li><a href="/c">Other story gamma</a></li>
    </ul>
    </article></body></html>"""
    md = _md(html)
    assert "related posts" not in md
    assert "other story alpha" not in md
    assert "main story body" in md
    assert _diag(html)["related"] >= 1


def test_placeholder_dropped() -> None:
    html = """<html><body><main>
    <h1>Page</h1>
    <p>Real content before the template noise appears in this article.</p>
    <p>${user.name}</p>
    <p>Short mixed {{ token }} line</p>
    </main></body></html>"""
    md = _md(html)
    assert "${user.name}" not in md
    assert "real content before" in md
    assert _diag(html)["placeholder"] >= 1


@pytest.mark.parametrize(
    "flag,html,chrome,keep",
    [
        (
            "chrome_drop_toc",
            """<html><body><main><h2>Contents</h2><ol>
            <li><a href="#a">One</a></li><li><a href="#b">Two</a></li>
            <li><a href="#c">Three</a></li><li><a href="#d">Four</a></li>
            <li><a href="#e">Five</a></li></ol>
            <p>Body text with enough words to avoid toc-as-content guard easily.</p>
            </main></body></html>""",
            "contents",
            "body text",
        ),
        (
            "chrome_drop_pager",
            """<html><body><main><p>Body text with enough words for extraction tests here.</p>
            <div class="pagination"><a href="?p=1">Previous</a><a href="?p=3">Next page</a></div>
            </main></body></html>""",
            "next page",
            "body text",
        ),
        (
            "chrome_drop_comments",
            """<html><body><article><h1>T</h1><p>Body text with enough words for extraction.</p>
            <div class="comments"><p>Remove me please from the markdown output.</p></div>
            </article></body></html>""",
            "remove me please",
            "body text",
        ),
        (
            "chrome_drop_related",
            """<html><body><article><h1>T</h1><p>Body text with enough words for extraction and
            a much longer article paragraph so the related links block stays under the word guard.</p>
            <h4>You may also like</h4><ul><li><a href="/x">Link one</a></li><li><a href="/y">Link two</a></li></ul>
            </article></body></html>""",
            "you may also like",
            "body text",
        ),
    ],
)
def test_config_flag_disables_rule(flag: str, html: str, chrome: str, keep: str) -> None:
    soup_on = parse_html(html)
    root_on = soup_on.find("main") or soup_on.find("article") or soup_on.body
    counts_on = drop_generic_chrome(
        soup_on, root_on, infer_page_kind_hint(soup_on), cfg=PipelineConfig(**{flag: True})
    )
    text_on = root_on.get_text(" ", strip=True).lower()

    soup_off = parse_html(html)
    root_off = soup_off.find("main") or soup_off.find("article") or soup_off.body
    counts_off = drop_generic_chrome(
        soup_off, root_off, infer_page_kind_hint(soup_off), cfg=PipelineConfig(**{flag: False})
    )
    text_off = root_off.get_text(" ", strip=True).lower()

    assert chrome not in text_on
    assert chrome in text_off
    assert keep in text_on and keep in text_off
    assert sum(counts_on.values()) > sum(counts_off.values())


def test_drop_generic_chrome_direct() -> None:
    soup = parse_html("<html><body><main><p>${x}</p></main></body></html>")
    root = soup.find("main")
    counts = drop_generic_chrome(soup, root, None, cfg=PipelineConfig())
    assert counts["placeholder"] >= 1


def test_cta_button_dropped() -> None:
    html = """<html><body><main>
    <h1>Services</h1>
    <p>We offer professional landscaping with decades of experience serving local homeowners.</p>
    <a href="/quote">Get a quote</a>
    </main></body></html>"""
    md = _md(html)
    assert "get a quote" not in md
    assert "professional landscaping" in md
    assert _diag(html)["cta"] >= 1


def test_cta_in_sentence_kept() -> None:
    html = """<html><body><main>
    <h1>Guide</h1>
    <p>You should learn more about widgets in the installation guide before starting work.</p>
    </main></body></html>"""
    md = _md(html)
    assert "learn more about widgets" in md
    assert _diag(html)["cta"] == 0


def test_share_strip_dropped() -> None:
    body = _long_body()
    html = f"""<html><body><article>
    <h1>Story</h1>
    <p>{body}</p>
    <ul class="share">
      <li>Facebook</li><li>Twitter</li><li>LinkedIn</li><li>Share</li>
    </ul>
    </article></body></html>"""
    md = _md(html)
    assert "facebook" not in md
    assert "body text with enough words" in md
    assert _diag(html)["share"] >= 1


def test_social_topic_paragraph_kept() -> None:
    html = """<html><body><main>
    <h1>Marketing</h1>
    <p>Social media platforms like Facebook and Twitter changed how brands reach customers online today.</p>
    </main></body></html>"""
    md = _md(html)
    assert "facebook and twitter" in md
    assert _diag(html)["share"] == 0


def test_newsletter_form_dropped() -> None:
    body = _long_body()
    html = f"""<html><body><article>
    <h1>News</h1>
    <p>{body}</p>
    <div class="newsletter"><p>Sign up for our newsletter to receive weekly updates by email.</p></div>
    </article></body></html>"""
    md = _md(html)
    assert "sign up for our newsletter" not in md
    assert "body text with enough words" in md
    assert _diag(html)["newsletter"] >= 1


def test_newsletter_mention_in_article_kept() -> None:
    html = """<html><body><main>
    <h1>Policy</h1>
    <p>Our newsletter explains policy updates each month with detailed analysis for subscribers and partners.</p>
    </main></body></html>"""
    md = _md(html)
    assert "newsletter explains policy" in md
    assert _diag(html)["newsletter"] == 0


def test_author_bio_dropped_after_article() -> None:
    body = _long_body()
    html = f"""<html><body><article>
    <h1>Post</h1>
    <p>{body}</p>
    <div class="about-author"><p>Jane Doe writes about travel. She has visited forty countries.</p></div>
    </article></body></html>"""
    md = _md(html)
    assert "about the author" not in md
    assert "jane doe writes" not in md
    assert "body text with enough words" in md
    assert _diag(html)["author_bio"] >= 1


def test_byline_before_article_kept() -> None:
    body = _long_body()
    html = f"""<html><body><article>
    <h1>Post</h1>
    <p class="byline">By Jane Doe</p>
    <p>{body}</p>
    </article></body></html>"""
    soup = parse_html(html)
    root = soup.find("article")
    drop_generic_chrome(soup, root, infer_page_kind_hint(soup), cfg=PipelineConfig())
    text = root.get_text(" ", strip=True).lower()
    assert "by jane doe" in text
    assert _diag(html)["author_bio"] == 0


def test_back_to_top_dropped() -> None:
    html = """<html><body><main>
    <h1>Page</h1>
    <p>Body text with enough words to pass extraction thresholds easily for this landing page example.</p>
    <a href="#top">Back to top</a>
    </main></body></html>"""
    md = _md(html)
    assert "back to top" not in md
    assert "body text" in md
    assert _diag(html)["nav_misc"] >= 1


def test_language_switcher_dropped() -> None:
    html = """<html><body><main>
    <h1>Global</h1>
    <p>Body text with enough words to pass extraction thresholds easily for this landing page example.</p>
    <ul><li>English</li><li>Français</li><li>Deutsch</li><li>Español</li></ul>
    </main></body></html>"""
    md = _md(html)
    assert "français" not in md
    assert "body text" in md


_BODY = (
    "Body text with enough words for extraction tests here today and additional "
    "sentences so chrome blocks stay under the twenty percent removal guard on "
    "short fixture pages used throughout these unit tests for generic chrome rules "
    "without triggering the cumulative word budget safety limit during removal."
)

@pytest.mark.parametrize(
    "flag,html,chrome,keep,key",
    [
        (
            "chrome_drop_cta",
            f"""<html><body><main><h1>T</h1><p>{_BODY}</p>
            <button>Contact us</button></main></body></html>""",
            "contact us",
            "body text",
            "cta",
        ),
        (
            "chrome_drop_share",
            f"""<html><body><article><h1>T</h1><p>{_BODY}</p>
            <div><a>Facebook</a><a>Twitter</a><a>Share</a></div></article></body></html>""",
            "facebook",
            "body text",
            "share",
        ),
        (
            "chrome_drop_newsletter",
            f"""<html><body><article><h1>T</h1><p>{_BODY}</p>
            <div class="subscribe-box"><p>Sign up for our newsletter today.</p></div></article></body></html>""",
            "sign up for our newsletter",
            "body text",
            "newsletter",
        ),
        (
            "chrome_drop_author_bio",
            f"""<html><body><article><h1>T</h1><p>{_BODY}</p>
            <div class="author-bio"><p>Writer bio with short profile text only.</p></div></article></body></html>""",
            "writer bio",
            "body text",
            "author_bio",
        ),
        (
            "chrome_drop_nav_misc",
            f"""<html><body><main><h1>T</h1><p>{_BODY}</p>
            <a href="#top">Top</a></main></body></html>""",
            "top",
            "body text",
            "nav_misc",
        ),
    ],
)
def test_new_rule_config_flag(flag: str, html: str, chrome: str, keep: str, key: str) -> None:
    soup_on = parse_html(html)
    root_on = soup_on.find("main") or soup_on.find("article") or soup_on.body
    counts_on = drop_generic_chrome(
        soup_on, root_on, infer_page_kind_hint(soup_on), cfg=PipelineConfig(**{flag: True})
    )
    text_on = root_on.get_text(" ", strip=True).lower()

    soup_off = parse_html(html)
    root_off = soup_off.find("main") or soup_off.find("article") or soup_off.body
    counts_off = drop_generic_chrome(
        soup_off, root_off, infer_page_kind_hint(soup_off), cfg=PipelineConfig(**{flag: False})
    )
    text_off = root_off.get_text(" ", strip=True).lower()

    assert chrome not in text_on
    assert chrome in text_off
    assert keep in text_on and keep in text_off
    assert counts_on[key] > counts_off[key]


def test_trim_tail_drops_footer_chrome() -> None:
    body = _long_body()
    html = f"""<html><body><article>
    <h1>Story</h1>
    <p>{body}</p>
    <p>{_substantive_para("Second")}</p>
    <p>{_substantive_para("Third")}</p>
    <p>© 2024 Example Inc. All rights reserved.</p>
    <p>Privacy Policy | Terms of Service</p>
    <ul><li><a href="/a">Related one</a></li><li><a href="/b">Related two</a></li></ul>
    </article></body></html>"""
    soup = parse_html(html)
    root = soup.find("article")
    counts = drop_generic_chrome(soup, root, None, cfg=PipelineConfig())
    text = root.get_text(" ", strip=True).lower()
    assert "privacy policy" not in text
    assert "related one" not in text
    assert "third paragraph" in text
    assert counts["trim_tail"] >= 1


def test_trim_tail_keeps_short_real_conclusion() -> None:
    body = _long_body()
    html = f"""<html><body><article>
    <h1>Story</h1>
    <p>{body}</p>
    <p>{_substantive_para("Second")}</p>
    <p>{_substantive_para("Third")}</p>
    <p>In short, the evidence supports this conclusion.</p>
    </article></body></html>"""
    md = _md(html)
    assert "in short, the evidence" in md
    assert _diag(html)["trim_tail"] == 0


def test_micro_block_drops_stray_glyph() -> None:
    body = _long_body()
    html = f"""<html><body><main>
    <h1>Thread</h1>
    <p>{body}</p>
    <p>0</p>
    <span>A</span>
    <p>Member</p>
    </main></body></html>"""
    md = _md(html, chrome_drop_micro_blocks=True)
    assert "member" not in md
    assert _diag(html, chrome_drop_micro_blocks=True)["micro_blocks"] >= 1


def test_micro_block_keeps_numbered_list_and_code() -> None:
    html = """<html><body><main>
    <h1>Steps</h1>
    <ol>
      <li>First step with enough words to be real instructional content here.</li>
      <li>Second step with enough words to be real instructional content here.</li>
      <li>0</li>
    </ol>
    <pre><code>count = 0</code></pre>
    </main></body></html>"""
    md = _md(html, chrome_drop_micro_blocks=True)
    assert "first step" in md
    assert "count = 0" in md
    assert _diag(html, chrome_drop_micro_blocks=True)["micro_blocks"] == 0


def test_attr_junk_dropped() -> None:
    body = _long_body()
    html = f"""<html><body><main>
    <h1>Post</h1>
    <p>{body}</p>
    <p>alt=hero.jpg class=btn-primary data-id=12 aria-label=close</p>
    <p>Kong Kong Kong Kong alternatives overview</p>
    </main></body></html>"""
    md = _md(html)
    assert "alt=hero.jpg" not in md
    assert "kong kong kong kong" not in md
    assert "body text" in md
    assert _diag(html)["attr_junk"] >= 1


def test_attr_junk_keeps_table() -> None:
    html = """<html><body><main>
    <h1>Specs</h1>
    <table><tr><td>hero.jpg</td><td>data-id=1</td></tr></table>
    </main></body></html>"""
    soup = parse_html(html)
    root = soup.find("main")
    drop_generic_chrome(soup, root, None, cfg=PipelineConfig())
    text = root.get_text(" ", strip=True).lower()
    assert "hero.jpg" in text
    assert _diag(html)["attr_junk"] == 0


@pytest.mark.parametrize(
    "flag,html,chrome,keep,key",
    [
        (
            "chrome_trim_tail",
            f"""<html><body><article><h1>T</h1><p>{_BODY}</p>
            <p>{_substantive_para("Second")}</p>
            <p>{_substantive_para("Third")}</p>
            <p>Tags: widgets, gadgets</p>
            <p>Share on social media</p></article></body></html>""",
            "tags: widgets",
            "third paragraph",
            "trim_tail",
        ),
        (
            "chrome_drop_micro_blocks",
            f"""<html><body><main><h1>T</h1><p>{_BODY}</p><p>|</p></main></body></html>""",
            "|",
            "body text",
            "micro_blocks",
        ),
        (
            "chrome_drop_attr_junk",
            f"""<html><body><main><h1>T</h1><p>{_BODY}</p>
            <p>class=foo-bar data-x=1 aria-hidden=true</p></main></body></html>""",
            "class=foo-bar",
            "body text",
            "attr_junk",
        ),
    ],
)
def test_tail_micro_attr_config_flag(flag: str, html: str, chrome: str, keep: str, key: str) -> None:
    soup_on = parse_html(html)
    root_on = soup_on.find("main") or soup_on.find("article") or soup_on.body
    counts_on = drop_generic_chrome(
        soup_on, root_on, infer_page_kind_hint(soup_on), cfg=PipelineConfig(**{flag: True})
    )
    text_on = root_on.get_text(" ", strip=True).lower()

    soup_off = parse_html(html)
    root_off = soup_off.find("main") or soup_off.find("article") or soup_off.body
    counts_off = drop_generic_chrome(
        soup_off, root_off, infer_page_kind_hint(soup_off), cfg=PipelineConfig(**{flag: False})
    )
    text_off = root_off.get_text(" ", strip=True).lower()

    assert chrome not in text_on
    assert chrome in text_off
    assert keep in text_on and keep in text_off
    assert counts_on[key] > counts_off[key]
