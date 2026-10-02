"""Write the list of every domain and page set used to evaluate ChromeRAG 0.1.3.

Output: evaluations/2026-10-v0.1.3/EVALUATION_COVERAGE.md (counts) and evaluation_domains.csv (set, domain, pages).
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from poc.run_corpus_comparison import RAW as DOCS_RAW
from poc.run_corpus_comparison import load_ok_pages
from poc.wcxb import load_split

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "evaluations" / "2026-10-v0.1.3"


def host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def main() -> None:
    rows: list[tuple[str, str, int]] = []
    lines = ["# Evaluation coverage (ChromeRAG 0.1.3)", "",
             "Every page set, how many pages and domains it has, and what it was used for. Domain lists: `evaluation_domains.csv`.", "",
             "| Set | Role | Pages | Domains | Notes |", "|---|---|---|---|---|"]

    def add(name: str, role: str, urls: list[str], note: str) -> None:
        c = Counter(host(u) for u in urls if u)
        rows.extend((name, d, n) for d, n in sorted(c.items()))
        lines.append(f"| {name} | {role} | {len(urls)} | {len(c)} | {note} |")

    for split, role in (("dev", "training and cross-validation (sites grouped by fold)"), ("test", "final held-out test, scored once")):
        pages = load_split(split)
        add(f"WCXB {split}", role, [p.url for p in pages], f"7 page types; {dict(Counter(p.page_type for p in pages))}")
    split = json.loads((ROOT / "poc" / "landing_split.json").read_text())
    urls = json.loads((ROOT / "poc" / "landing_urls.json").read_text())["companies"]
    for part, role in (("dev", "development (anchor metric)"), ("heldout", "held-out, scored once")):
        us = [pg["url"] for c in split[part] for pg in urls.get(c, {}).get("pages", [])]
        add(f"Landing {part} companies ({len(split[part])})", role, us, "marketing: homepage, pricing, product pages chosen from homepage links before any extractor ran")
    fresh = json.loads((ROOT / "poc" / "landing_urls_fresh.json").read_text())["companies"]
    add(f"Fresh companies ({len(fresh)})", "fetched after the freeze, scored once", [pg["url"] for c in fresh.values() for pg in c["pages"]], "sectors: " + ", ".join(sorted({c['sector'] for c in fresh.values()})))
    docs = [m.get("url", "") for _, _, m in load_ok_pages(DOCS_RAW)]
    add("Documentation/pricing/article corpus", "anchor benchmark and BM25 retrieval (development; 242 scoreable)", docs, "documentation 208 of 242 scoreable pages")
    crawl = list((ROOT / "data" / "stce_crawl").glob("*.meta.json"))
    add("STCE crawl", "site-template learning study", [json.loads(p.read_text()).get("url", "") for p in crawl], "up to 15 same-section pages per documentation site")
    j1 = json.loads((EV / "FINAL" / "llm_judge_final.json").read_text())
    j1_pages = {r["id"] for r in j1["judgements"]}
    p2 = EV / "FINAL" / "llm_judge_wcxb_test.json"
    j2 = json.loads(p2.read_text()) if p2.exists() else None
    if j2:
        add("Judge sample: WCXB test", "LLM judge, 15 per page type", [s["url"] for s in j2["pages"]], f"{j2['n_judgements']} judgements, three baselines")
    lines += ["", "## Judge samples", "",
              f"* Landing/fresh judge: {len(j1_pages)} pages (50 held-out + 50 fresh), {j1['n_judgements']} judgements (two baselines, 20% position-swapped repeats)."]
    if j2:
        lines.append(f"* WCXB-test judge: {j2['n_pages']} pages (15 per page type), {j2['n_judgements']} judgements (three baselines).")
    out = EV / "EVALUATION_COVERAGE.md"
    # rebuild table header position: lines already ordered; write
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (EV / "evaluation_domains.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["set", "domain", "pages"])
        w.writerows(rows)
    print(out.read_text())


if __name__ == "__main__":
    main()
