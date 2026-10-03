"""Learned block classifier: features, model file, and end-to-end behaviour."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from chromerag.blockfeatures import FEATURE_NAMES, block_features, find_blocks
from chromerag.density import parse_html, strip_non_content_tags
from chromerag.lbc import default_two_stage
from chromerag.treestats import TreeStats

FIXTURES = Path(__file__).parent / "fixtures"

ARTICLE = """<html><head><title>Backup retention</title></head><body>
<nav class="navbar"><a href="/">Home</a><a href="/blog">Blog</a><a href="/about">About</a></nav>
<main><article><h1>Backup retention</h1>
<p>Backups are kept for thirty days by default, and the retention period can be changed per project in the
settings page. Older copies are removed once a day, after the new copy has been verified.</p>
<p>To restore a backup, pick a date in the list and choose Restore. The restore runs in the background and
sends an email when it has finished, so large projects do not block the console.</p>
<div class="share-bar"><a href="#">Share on Twitter</a> <a href="#">Share on Facebook</a></div>
</article></main>
<footer><p>Copyright 2026 Example Inc. All rights reserved. Privacy Terms Contact</p></footer></body></html>"""


def _blocks(html: str):
    soup = parse_html(html)
    strip_non_content_tags(soup)
    body = soup.body
    stats = TreeStats(body)
    blocks = find_blocks(body, stats)
    return blocks, body, stats


def test_blocks_are_listed_in_document_order_without_nesting() -> None:
    blocks, _, _ = _blocks(ARTICLE)
    texts = [b.text for b in blocks]
    assert texts[0] == "Home" or "Backup retention" in texts
    assert texts.index("Backup retention") < next(i for i, t in enumerate(texts) if t.startswith("To restore"))
    assert len({id(b.tag) for b in blocks}) == len(blocks)


def test_feature_matrix_shape_and_box_ids() -> None:
    blocks, body, stats = _blocks(ARTICLE)
    X, box = block_features(blocks, body, stats, None)
    assert X.shape == (len(blocks), len(FEATURE_NAMES))
    assert box.shape == (len(blocks),)
    assert np.isfinite(X).all()


def test_shipped_model_matches_feature_count() -> None:
    model = default_two_stage()
    assert model is not None
    assert model.first.n_features == len(FEATURE_NAMES)


def test_model_scores_prose_above_chrome() -> None:
    model = default_two_stage()
    blocks, body, stats = _blocks(ARTICLE)
    X, box = block_features(blocks, body, stats, None)
    chars = np.array([len(b.text) for b in blocks])
    p = dict(zip((b.text[:20] for b in blocks), model.predict(X.astype("float64"), chars, box), strict=True))
    assert p["Backups are kept for"] > 0.5
    assert p["Share on Twitter Sha"] < p["Backups are kept for"]


def test_extraction_keeps_article_and_drops_page_furniture() -> None:
    md = ChromeRAG(config=PipelineConfig.from_priority(ContentPriority.BALANCED)).extract(ARTICLE).markdown
    assert "thirty days" in md and "Restore" in md
    assert "All rights reserved" not in md
    assert "Share on Twitter" not in md


def test_classifier_can_be_switched_off() -> None:
    cfg = PipelineConfig.from_priority(ContentPriority.BALANCED, enable_lbc=False)
    assert "thirty days" in ChromeRAG(config=cfg).extract(ARTICLE).markdown


def test_link_targets_are_off_by_default_and_available() -> None:
    html = "<html><body><main><p>Read the <a href='https://example.com/guide'>setup guide</a> before you install " \
           "the agent on a production host, because the installer changes kernel settings.</p></main></body></html>"
    plain = ChromeRAG().extract(html).markdown
    linked = ChromeRAG(config=PipelineConfig(include_links=True)).extract(html).markdown
    assert "setup guide" in plain and "https://example.com" not in plain
    assert "(https://example.com/guide)" in linked


def test_content_after_a_stray_closing_html_tag_is_kept() -> None:
    para = ("The report explains how the new pricing applies to teams that run more than ten projects, "
            "and why the change takes effect in the next billing cycle. ")
    html = ("<html><body><header><p>Site</p></header></body></html>"
            f"<div><p>{para * 3}</p></div></body></html>")
    assert "billing cycle" in ChromeRAG(config=PipelineConfig(enable_lbc=False)).extract(html).markdown


def test_page_wide_form_does_not_swallow_the_article() -> None:
    para = "This paragraph is long enough to count as running text on a page and it describes the product. "
    html = f"<html><body><form id='aspnetForm'><div><h1>Title</h1><p>{para * 3}</p><p>{para * 3}</p></div></form></body></html>"
    assert "describes the product" in ChromeRAG(config=PipelineConfig(enable_lbc=False)).extract(html).markdown


def test_layout_table_is_unwrapped_not_duplicated() -> None:
    para = "Each paragraph here is a sentence that belongs to the page body and should appear exactly one time. "
    html = (f"<html><body><table><tr><td><table><tr><td><p>{para}</p></td></tr></table></td></tr></table>"
            "</body></html>")
    md = ChromeRAG(config=PipelineConfig(enable_lbc=False)).extract(html).markdown
    assert md.count("exactly one time") == 1


def test_highlighted_code_keeps_its_lines() -> None:
    para = "Run the command below to install the package on your machine and verify it works. " * 3
    html = (f"<html><head><title>Install guide</title></head><body><main><h1>Install guide</h1><p>{para}</p>"
            '<pre><code><span class="k">pip</span> <span class="nb">install</span> chromerag\npython -m chromerag --version</code></pre>'
            f"<p>{para}</p></main></body></html>")
    md = ChromeRAG().extract(html).markdown
    assert "pip install chromerag\npython -m chromerag --version" in md


def test_page_title_heading_is_kept() -> None:
    para = "Backups are kept for thirty days and can be restored from the settings page at any time. " * 3
    html = (f"<html><head><title>Backup retention - Docs</title></head><body><main><h1>Backup retention</h1><p>{para}</p>"
            f"<p>{para}</p><p>{para}</p></main></body></html>")
    assert "# Backup retention" in ChromeRAG().extract(html).markdown


def test_ordered_and_nested_lists_keep_their_shape() -> None:
    para = "Follow the steps below to configure the service for production use and review the options. " * 3
    html = (f"<html><head><title>Steps</title></head><body><main><h1>Steps</h1><p>{para}</p><ol><li>Install the package</li>"
            "<li>Configure the service<ul><li>Set the port</li></ul></li><li>Start the service</li></ol>"
            f"<p>{para}</p></main></body></html>")
    md = ChromeRAG().extract(html).markdown
    assert "1. Install the package" in md and "2. Configure the service" in md and "  - Set the port" in md


def test_lbc_rescue_headings_keeps_section_heading_above_body() -> None:
    para = "This paragraph explains the configuration options in detail and should score well above threshold. " * 4
    html = (
        "<html><head><title>Guide</title></head><body>"
        "<nav><a href='/'>Home</a><a href='/docs'>Docs</a><a href='/about'>About</a></nav>"
        f"<main><h1>Guide</h1><h2>Setup steps</h2><p>{para}</p><p>{para}</p></main>"
        "<footer><p>Copyright notice all rights reserved privacy terms contact us today</p></footer></body></html>"
    )
    on = ChromeRAG(config=PipelineConfig(lbc_threshold=0.60, lbc_rescue_lead=False, lbc_title_fallback=False)).extract(html).markdown
    off = ChromeRAG(
        config=PipelineConfig(
            lbc_threshold=0.60, lbc_rescue_headings=False, lbc_rescue_lead=False, lbc_title_fallback=False
        )
    ).extract(html).markdown
    assert "## Setup steps" in on
    assert "## Setup steps" not in off


def test_lbc_title_fallback_keeps_content_root_h1_without_title_match() -> None:
    para = "Backups are kept for thirty days and can be restored from the settings page at any time. " * 4
    toc = "<p>Table of contents introduction setup configuration restore faq related articles guides</p>"
    html = (
        "<html><head><title>Product Guide - Acme Corp</title></head><body>"
        "<nav><a href='/'>Home</a><a href='/docs'>Docs</a><a href='/blog'>Blog</a><a href='/about'>About</a></nav>"
        f"<main><h1>Getting Started</h1>{toc}<p>{para}</p><p>{para}</p></main>"
        "<footer><p>Copyright 2026 Example Inc. All rights reserved. Privacy Terms Contact Support</p></footer>"
        "</body></html>"
    )
    on = ChromeRAG(config=PipelineConfig(lbc_rescue_headings=False, lbc_rescue_lead=False)).extract(html).markdown
    off = ChromeRAG(
        config=PipelineConfig(lbc_rescue_headings=False, lbc_rescue_lead=False, lbc_title_fallback=False)
    ).extract(html).markdown
    assert "# Getting Started" in on
    assert "# Getting Started" not in off


def test_lbc_rescue_lead_keeps_summary_after_title() -> None:
    lead = "Share on Twitter Share on Facebook Copy link Email this page Print PDF Download now"
    para = "The detailed body text continues with more information about the topic and provides examples for readers. " * 4
    html = (
        "<html><head><title>Product Overview</title></head><body>"
        "<nav><a href='/'>Home</a><a href='/docs'>Docs</a><a href='/blog'>Blog</a><a href='/about'>About</a></nav>"
        f"<main><h1>Product Overview</h1><div>{lead}</div><p>{para}</p><p>{para}</p></main>"
        "<footer><p>Copyright 2026 Example Inc. All rights reserved. Privacy Terms Contact Support</p></footer>"
        "</body></html>"
    )
    on = ChromeRAG(
        config=PipelineConfig(lbc_threshold=0.55, lbc_rescue_headings=False, lbc_title_fallback=False)
    ).extract(html).markdown
    off = ChromeRAG(
        config=PipelineConfig(
            lbc_threshold=0.55, lbc_rescue_headings=False, lbc_rescue_lead=False, lbc_title_fallback=False
        )
    ).extract(html).markdown
    assert "Share on Twitter" in on
    assert "Share on Twitter" not in off
