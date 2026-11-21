"""Tests for structure-aware Markdown chunking."""

from __future__ import annotations

import json
from pathlib import Path

from chromerag import ChromeRAG, chunk_markdown
from chromerag.chunking import Chunk
from chromerag.cli import main

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "site"


def _words(n: int) -> str:
    return " ".join(f"w{i}" for i in range(n))


def test_heading_path_and_depth() -> None:
    md = f"# Alpha\n\n{_words(60)}\n\n## Beta\n\n{_words(60)}"
    chunks = chunk_markdown(md, title="Page Title", max_words=200, min_words=10)
    assert len(chunks) == 2
    assert chunks[0].heading_path == ("Page Title", "Alpha")
    assert chunks[0].depth == 1
    assert chunks[1].heading_path == ("Page Title", "Alpha", "Beta")
    assert chunks[1].depth == 2
    assert chunks[0].index == 0
    assert chunks[1].index == 1


def test_dedupe_adjacent_title_and_h1() -> None:
    md = f"# Page Title\n\n{_words(60)}"
    chunks = chunk_markdown(md, title="Page Title", max_words=200, min_words=10)
    assert chunks[0].heading_path == ("Page Title",)


def test_strip_yaml_front_matter() -> None:
    md = f"---\ntitle: Ignored\n---\n\n{_words(60)}"
    chunks = chunk_markdown(md, title="Real Title", max_words=200, min_words=10)
    assert len(chunks) == 1
    assert "Ignored" not in chunks[0].text
    assert chunks[0].depth == 0


def test_code_block_never_split() -> None:
    body = _words(40)
    code = "```python\n" + " ".join(f"x{i}" for i in range(250)) + "\n```"
    md = f"{body}\n\n{code}\n\n{body}"
    chunks = chunk_markdown(md, max_words=100, min_words=10)
    code_chunks = [c for c in chunks if "```" in c.text]
    assert len(code_chunks) == 1
    assert code_chunks[0].text.count("```") == 2
    assert code_chunks[0].words > 100


def test_table_block_never_split() -> None:
    rows = "\n".join(f"Row {i} -> col1: val{i} | col2: val{i}b" for i in range(1, 80))
    table = f"[Table: Pricing]\n{rows}"
    md = f"{_words(40)}\n\n{table}\n\n{_words(40)}"
    chunks = chunk_markdown(md, max_words=80, min_words=10)
    table_chunks = [c for c in chunks if c.text.startswith("[Table:")]
    assert len(table_chunks) == 1
    assert "Row 79" in table_chunks[0].text


def test_pipe_table_block_never_split() -> None:
    body = "| Col A | Col B |\n| --- | --- |\n"
    rows = "\n".join(f"| val{i}a | val{i}b |" for i in range(1, 80))
    table = body + rows
    md = f"{_words(40)}\n\n{table}\n\n{_words(40)}"
    chunks = chunk_markdown(md, max_words=80, min_words=10)
    pipe_chunks = [c for c in chunks if c.text.strip().startswith("|")]
    assert len(pipe_chunks) == 1
    assert "| val79a | val79b |" in pipe_chunks[0].text


def test_small_trailing_section_merged_backward() -> None:
    md = f"## Section\n\n{_words(120)}\n\n{_words(20)}"
    chunks = chunk_markdown(md, max_words=200, min_words=50)
    assert len(chunks) == 1
    assert chunks[0].words == 140


def test_small_trailing_section_merged_forward() -> None:
    md = f"## A\n\n{_words(20)}\n\n## B\n\n{_words(60)}"
    chunks = chunk_markdown(md, max_words=200, min_words=50)
    assert len(chunks) == 1
    assert chunks[0].words == 80
    assert chunks[0].heading_path[-1] == "B"


def test_empty_input() -> None:
    assert chunk_markdown("") == []
    assert chunk_markdown("---\ntitle: x\n---\n\n   \n") == []


def test_min_words_fallback_single_chunk() -> None:
    md = _words(30)
    chunks = chunk_markdown(md, min_words=50, max_words=200)
    assert len(chunks) == 1
    assert chunks[0].words == 30


def test_embed_text_and_to_dict() -> None:
    md = f"## Setup\n\n{_words(60)}"
    c = chunk_markdown(md, title="Docs", max_words=200, min_words=10)[0]
    assert c.embed_text.startswith("Docs > Setup\n")
    d = c.to_dict()
    assert d["embed_text"] == c.embed_text
    assert d["heading_path"] == ["Docs", "Setup"]
    assert d["depth"] == 1
    assert d["words"] == c.words
    assert d["index"] == 0


def test_extract_result_chunks() -> None:
    html = (
        "<html><head><title>Widget Guide</title></head><body>"
        "<h1>Install</h1><p>" + "Download the package and run the installer. " * 15
        + "</p><h2>Configure</h2><p>" + "Set your API key in the config file. " * 15
        + "</p></body></html>"
    )
    result = ChromeRAG().extract(html)
    chunks = result.chunks(max_words=200, min_words=10)
    assert chunks
    assert all(isinstance(c, Chunk) for c in chunks)


def test_cli_chunks_jsonl(tmp_path: Path) -> None:
    out = tmp_path / "chunks.jsonl"
    rc = main(["extract", str(EXAMPLES / "pricing.html"), "-o", str(out), "--chunks"])
    assert rc == 0
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines
    for line in lines:
        row = json.loads(line)
        assert "text" in row
        assert "embed_text" in row
        assert "heading_path" in row
        assert "url" in row


def test_cli_chunks_stdout(capsys) -> None:
    rc = main(["extract", str(EXAMPLES / "pricing.html"), "--chunks"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out
    for line in out.splitlines():
        json.loads(line)


def test_short_section_without_merge_partner_is_kept() -> None:
    # 0.1.5 dropped a short h3 section whose only neighbours were full chunks in other sections.
    md = (
        f"# T\n\n## A\n\n{_words(120)}\n\n### B\n\nshort tail text here only\n\n## C\n\n{_words(120)}"
    )
    chunks = chunk_markdown(md, max_words=180, min_words=50)
    assert any("short tail text here only" in c.text for c in chunks)


def test_chunks_keep_every_word() -> None:
    import random

    rng = random.Random(0)
    for _ in range(200):
        parts = ["# Title"]
        expected = 0
        for s in range(rng.randint(1, 8)):
            parts.append("#" * rng.randint(2, 4) + f" S{s}")
            n = rng.choice([3, 10, 40, 90, 250])
            parts.append(_words(n))
            expected += n
        chunks = chunk_markdown("\n\n".join(parts), max_words=180, min_words=50)
        body = " ".join(c.text for c in chunks).split()
        assert sum(1 for w in body if w.startswith("w")) == expected


def test_chunks_keep_reading_order() -> None:
    import random

    rng = random.Random(1)
    heads = ["Intro", "Details", "Notes"]
    for _ in range(300):
        parts = ["# Title"]
        order = []
        for s in range(rng.randint(2, 10)):
            parts.append("#" * rng.randint(2, 4) + " " + rng.choice(heads))
            n = rng.choice([3, 10, 40, 90, 250])
            toks = [f"t{s}x{k}" for k in range(n)]
            order += toks
            parts.append(" ".join(toks))
        chunks = chunk_markdown("\n\n".join(parts), max_words=180, min_words=50)
        seen = [w for c in chunks for w in c.text.split() if w.startswith("t") and "x" in w]
        assert seen == order

