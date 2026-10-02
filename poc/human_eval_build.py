"""Build the blind human-rating set: 40 WCXB test pages, four extractor outputs each, shuffled per page.

Output (git-ignored): data/human_eval/items.json (with the secret tool key per page),
data/human_eval/html/<id>.html (scripts removed), data/human_eval/raw/<id>.html.

Sample: stratified by page type, seeded, taken from the held-out WCXB test split. Outputs are
normalised the same way for every tool (front matter, link targets, images, bold/italic marks removed)
so format cannot give a tool away.

  python -m poc.human_eval_build
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

from bs4 import BeautifulSoup

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from poc.baselines import BASELINES
from poc.wcxb import load_split

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "human_eval"
PER_TYPE = {"article": 8, "forum": 5, "product": 5, "collection": 5, "listing": 5, "documentation": 5, "service": 7}
TOOLS = ("chromerag", "trafilatura", "readability", "markitdown")
SEED = 20261002
_FRONT = re.compile(r"\A---\n.*?\n---\n+", re.S)
_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_EMPH = re.compile(r"(\*\*|__)(.+?)\1")


def normalise(text: str) -> str:
    text = _FRONT.sub("", text)
    text = _IMG.sub("", text)
    text = _LINK.sub(r"\1", text)
    text = _EMPH.sub(r"\2", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def sanitise(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "noscript", "iframe", "object", "embed", "template"]):
        t.decompose()
    for m in soup.find_all("meta", attrs={"http-equiv": re.compile("refresh", re.I)}):
        m.decompose()
    for tag in soup.find_all(True):
        for attr in [a for a in tag.attrs if a.lower().startswith("on")]:
            del tag[attr]
    if soup.head is not None and url:
        base = soup.new_tag("base", href=url)
        soup.head.insert(0, base)
    return str(soup)


def main() -> None:
    rng = random.Random(SEED)
    pages = load_split("test")
    rag = ChromeRAG(config=PipelineConfig.from_priority(ContentPriority.BALANCED))
    (OUT / "html").mkdir(parents=True, exist_ok=True)
    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    items = []
    for ptype, n in PER_TYPE.items():
        pool = sorted((p for p in pages if p.page_type == ptype), key=lambda p: p.id)
        rng.shuffle(pool)
        taken = 0
        for p in pool:
            outs = {"chromerag": rag.extract(p.html, url=p.url or None).markdown}
            for t in TOOLS[1:]:
                try:
                    outs[t] = BASELINES[t](p.html) or ""
                except Exception:  # noqa: BLE001
                    outs[t] = ""
            outs = {t: normalise(v) for t, v in outs.items()}
            if any(len(v.split()) < 15 for v in outs.values()):
                continue  # an empty output would identify itself
            order = list(TOOLS)
            rng.shuffle(order)
            labels = "ABCD"
            key = {labels[i]: t for i, t in enumerate(order)}
            items.append({"id": p.id, "type": ptype, "url": p.url, "key": key,
                          "outputs": {lab: outs[t] for lab, t in key.items()}})
            (OUT / "html" / f"{p.id}.html").write_text(sanitise(p.html, p.url), encoding="utf-8")
            (OUT / "raw" / f"{p.id}.html").write_text(p.html, encoding="utf-8")
            taken += 1
            if taken == n:
                break
    rng.shuffle(items)
    (OUT / "items.json").write_text(json.dumps({"seed": SEED, "items": items}, indent=1), encoding="utf-8")
    print(f"{len(items)} items -> {OUT / 'items.json'}")


if __name__ == "__main__":
    main()
