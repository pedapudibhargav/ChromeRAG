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


class _MappedBlockModel:
    """Stage-2 stand-in that scores each block from a text→probability map (order-independent)."""

    second = object()

    def __init__(self, scores: dict[str, float], default: float = 0.05) -> None:
        self.scores = scores
        self.default = default
        self.last_texts: list[str] = []

    def predict(self, X, chars=None, box=None):  # noqa: ANN001, ARG002
        assert len(self.last_texts) == len(X)
        out = []
        for text in self.last_texts:
            hit = self.default
            for key, val in self.scores.items():
                if key in text:
                    hit = val
                    break
            out.append(hit)
        return np.asarray(out, dtype=np.float64)


def test_lbc_rescue_headings_keeps_section_heading_above_body(monkeypatch) -> None:
    """Rescue band is fixed by a fake model so a refit cannot move the heading across threshold."""
    import chromerag.extractor as extractor_mod

    para = "This paragraph explains the configuration options in detail and should score well above threshold. " * 4
    html = (
        "<html><head><title>Guide</title></head><body>"
        "<nav><a href='/'>Home</a><a href='/docs'>Docs</a><a href='/about'>About</a></nav>"
        f"<main><h1>Guide</h1><h2>Setup steps</h2><p>{para}</p><p>{para}</p></main>"
        "<footer><p>Copyright notice all rights reserved privacy terms contact us today</p></footer></body></html>"
    )
    # h2 at 0.35 is below threshold 0.60 but inside the [0.08, threshold) rescue band.
    model = _MappedBlockModel(
        {"Setup steps": 0.35, "Guide": 0.85, "This paragraph": 0.92, "Copyright": 0.02, "Home": 0.02},
        default=0.05,
    )
    real_bf = extractor_mod.block_features

    def _capture(blocks, *args, **kwargs):  # noqa: ANN001
        model.last_texts = [b.text for b in blocks]
        return real_bf(blocks, *args, **kwargs)

    monkeypatch.setattr(extractor_mod, "block_features", _capture)
    base = dict(lbc_threshold=0.60, lbc_rescue_lead=False, lbc_title_fallback=False, enable_lbc_stage2=True)
    on = ChromeRAG(config=PipelineConfig(**base), lbc_model=model).extract(html).markdown  # type: ignore[arg-type]
    off = ChromeRAG(
        config=PipelineConfig(**base, lbc_rescue_headings=False),
        lbc_model=model,  # type: ignore[arg-type]
    ).extract(html).markdown
    assert "## Setup steps" in on
    assert "## Setup steps" not in off


def _with_mapped_model(monkeypatch, model: _MappedBlockModel):
    import chromerag.extractor as extractor_mod

    real_bf = extractor_mod.block_features

    def _capture(blocks, *args, **kwargs):  # noqa: ANN001
        model.last_texts = [b.text for b in blocks]
        return real_bf(blocks, *args, **kwargs)

    monkeypatch.setattr(extractor_mod, "block_features", _capture)


def test_lbc_rescue_tables_keeps_pricing_under_kept_heading(monkeypatch) -> None:
    para = "Every plan includes unlimited local runs and hosted minutes billed per compute unit. " * 3
    html = (
        "<html><head><title>Plans</title></head><body>"
        "<nav><a href='/'>Home</a><a href='/docs'>Docs</a><a href='/about'>About</a></nav>"
        f"<main><h1>Plans</h1><p>{para}</p><h2>Reference table</h2>"
        "<table><tr><th>Plan</th><th>Minutes</th><th>Price</th></tr>"
        "<tr><td>Starter</td><td>1000</td><td>0</td></tr>"
        "<tr><td>Team</td><td>20000</td><td>49</td></tr></table></main>"
        "<footer><p>Copyright notice all rights reserved privacy terms contact us today</p></footer></body></html>"
    )
    model = _MappedBlockModel(
        {
            "Plans": 0.90,
            "Every plan": 0.90,
            "Reference table": 0.80,
            "Starter": 0.40,  # below 0.50; rescue should still keep the grid
            "Copyright": 0.02,
            "Home": 0.02,
        }
    )
    _with_mapped_model(monkeypatch, model)
    on = ChromeRAG(
        config=PipelineConfig(lbc_rescue_lead=False, lbc_title_fallback=False),
        lbc_model=model,  # type: ignore[arg-type]
    ).extract(html)
    off = ChromeRAG(
        config=PipelineConfig(lbc_rescue_lead=False, lbc_title_fallback=False, lbc_rescue_tables=False),
        lbc_model=model,  # type: ignore[arg-type]
    ).extract(html).markdown
    assert "| Starter |" in on.markdown and "| 49 |" in on.markdown
    assert on.diagnostics["lbc"]["tables_rescued"] >= 1
    assert "Starter" not in off


def test_lbc_rescue_tables_pair_rescues_near_threshold_heading_and_table(monkeypatch) -> None:
    para = "Every plan includes unlimited local runs and hosted minutes billed per compute unit. " * 3
    html = (
        "<html><head><title>Plans</title></head><body>"
        "<nav><a href='/'>Home</a><a href='/docs'>Docs</a><a href='/about'>About</a></nav>"
        f"<main><h1>Plans</h1><p>{para}</p><h2>Prices</h2>"
        "<table><tr><th>Plan</th><th>Price</th></tr>"
        "<tr><td>Starter</td><td>0</td></tr>"
        "<tr><td>Team</td><td>49</td></tr></table></main>"
        "<footer><p>Copyright notice all rights reserved privacy terms contact us today</p></footer></body></html>"
    )
    model = _MappedBlockModel(
        {
            "Plans": 0.90,
            "Every plan": 0.90,
            "Prices": 0.35,  # [0.08, threshold) — needs the table as body
            "Starter": 0.35,
            "Copyright": 0.02,
            "Home": 0.02,
        }
    )
    _with_mapped_model(monkeypatch, model)
    base = dict(lbc_threshold=0.50, lbc_rescue_lead=False, lbc_title_fallback=False, enable_lbc_stage2=True)
    on = ChromeRAG(config=PipelineConfig(**base), lbc_model=model).extract(html).markdown  # type: ignore[arg-type]
    off = ChromeRAG(
        config=PipelineConfig(**base, lbc_rescue_tables=False),
        lbc_model=model,  # type: ignore[arg-type]
    ).extract(html).markdown
    assert "## Prices" in on and "| Starter |" in on
    assert "## Prices" not in off
    assert "Starter" not in off


def test_lbc_rescue_tables_skips_footer_grid_after_kept_paragraph(monkeypatch) -> None:
    para = "The article body explains the release notes and lists the changes for this version. " * 3
    para2 = "A second paragraph keeps the classifier active with enough blocks on the page. " * 3
    html = (
        "<html><head><title>Notes</title></head><body>"
        "<nav><a href='/'>Home</a><a href='/docs'>Docs</a><a href='/blog'>Blog</a></nav>"
        f"<main><h1>Notes</h1><p>{para}</p><p>{para2}</p></main>"
        # No section heading; neighbour-of-kept-paragraph must not rescue this contact grid.
        "<table><tr><td>Hours</td><td>9-5</td></tr>"
        "<tr><td>Phone</td><td>555-0100</td></tr></table>"
        "<footer><p>Copyright notice all rights reserved privacy terms contact us today</p></footer></body></html>"
    )
    model = _MappedBlockModel(
        {
            "Notes": 0.90,
            "The article body": 0.90,
            "A second paragraph": 0.90,
            "Hours": 0.20,
            "Copyright": 0.02,
            "Home": 0.02,
        }
    )
    _with_mapped_model(monkeypatch, model)
    md = ChromeRAG(
        config=PipelineConfig(lbc_rescue_lead=False, lbc_title_fallback=False, enable_lbc_stage2=True),
        lbc_model=model,  # type: ignore[arg-type]
    ).extract(html).markdown
    assert "555-0100" not in md
    assert "release notes" in md


def test_lbc_rescue_tables_skips_dropped_sponsors_ad_table(monkeypatch) -> None:
    para = "The article body explains the release notes and lists the changes for this version. " * 3
    html = (
        "<html><head><title>Notes</title></head><body>"
        "<nav><a href='/'>Home</a><a href='/docs'>Docs</a><a href='/blog'>Blog</a></nav>"
        f"<main><h1>Notes</h1><p>{para}</p><h2>Sponsors</h2>"
        "<table><tr><th>Partner</th><th>Offer</th></tr>"
        "<tr><td>Acme Ads</td><td>20% off</td></tr>"
        "<tr><td>Beta Co</td><td>Free trial</td></tr></table></main>"
        "<footer><p>Copyright notice all rights reserved privacy terms contact us today</p></footer></body></html>"
    )
    model = _MappedBlockModel(
        {
            "Notes": 0.90,
            "The article body": 0.90,
            "Sponsors": 0.05,  # below heading rescue band
            "Acme Ads": 0.20,
            "Copyright": 0.02,
            "Home": 0.02,
        }
    )
    _with_mapped_model(monkeypatch, model)
    md = ChromeRAG(
        config=PipelineConfig(lbc_rescue_lead=False, lbc_title_fallback=False),
        lbc_model=model,  # type: ignore[arg-type]
    ).extract(html).markdown
    assert "Acme Ads" not in md
    assert "Sponsors" not in md


def test_lbc_rescue_tables_skips_comparison_tiles_and_footer_contact(monkeypatch) -> None:
    para = "The article body explains the release notes and lists the changes for this version. " * 3
    html = (
        "<html><head><title>Notes</title></head><body>"
        "<nav><a href='/'>Home</a><a href='/docs'>Docs</a><a href='/blog'>Blog</a></nav>"
        f"<main><h1>Notes</h1><p>{para}</p><h2>Compare</h2>"
        "<table><tr>"
        "<td><a href='/a'>Alpha plan tile</a></td><td><a href='/b'>Beta plan tile</a></td>"
        "</tr><tr>"
        "<td><a href='/c'>Gamma plan tile</a></td><td><a href='/d'>Delta plan tile</a></td>"
        "</tr></table></main>"
        "<footer><table><tr><td>Hours</td><td>9-5</td></tr>"
        "<tr><td>Tel</td><td>555-0100</td></tr></table>"
        "<p>Copyright notice all rights reserved privacy terms contact us today</p></footer></body></html>"
    )
    model = _MappedBlockModel(
        {
            "Notes": 0.90,
            "The article body": 0.90,
            "Compare": 0.80,
            "Alpha plan": 0.20,
            "Hours": 0.20,
            "Copyright": 0.02,
            "Home": 0.02,
        }
    )
    _with_mapped_model(monkeypatch, model)
    md = ChromeRAG(
        config=PipelineConfig(lbc_rescue_lead=False, lbc_title_fallback=False),
        lbc_model=model,  # type: ignore[arg-type]
    ).extract(html).markdown
    assert "Alpha plan tile" not in md
    assert "555-0100" not in md
    assert "release notes" in md


def test_lbc_rescue_tables_respects_enable_tables_false(monkeypatch) -> None:
    para = "Every plan includes unlimited local runs and hosted minutes billed per compute unit. " * 3
    html = (
        "<html><head><title>Plans</title></head><body>"
        f"<main><h1>Plans</h1><p>{para}</p><h2>Reference table</h2>"
        "<table><tr><th>Plan</th><th>Price</th></tr>"
        "<tr><td>Starter</td><td>0</td></tr>"
        "<tr><td>Team</td><td>49</td></tr></table></main></body></html>"
    )
    model = _MappedBlockModel(
        {"Plans": 0.90, "Every plan": 0.90, "Reference table": 0.80, "Starter": 0.40}
    )
    _with_mapped_model(monkeypatch, model)
    result = ChromeRAG(
        config=PipelineConfig(
            lbc_rescue_lead=False, lbc_title_fallback=False, enable_tables=False, enable_generic_chrome=False
        ),
        lbc_model=model,  # type: ignore[arg-type]
    ).extract(html)
    assert result.diagnostics["lbc"].get("tables_rescued", 0) == 0


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
