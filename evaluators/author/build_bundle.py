"""Build a blind rating bundle + separate key.json for the author.

  python -m evaluators.author.build_bundle \\
    --pages pages.json \\
    --out evaluators/bundle/bundle.json \\
    --out-key /path/outside/evaluators/key.json

pages.json is a list of {id, url, html, page_type} where html is a file path.
Outputs are normalised the same way for every tool so format cannot reveal a tool.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import string
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from poc.baselines import BASELINES

ROOT = Path(__file__).resolve().parents[2]
EVAL = Path(__file__).resolve().parents[1]
DEFAULT_TOOLS = ("chromerag", "trafilatura", "readability")
_FRONT = re.compile(r"\A---\n.*?\n---\n+", re.S)
_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_EMPH = re.compile(r"(\*\*|__)(.+?)\1")
_MIN_WORDS = 15


def normalise(text: str) -> str:
    text = _FRONT.sub("", text or "")
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


def labels_for(n: int) -> list[str]:
    return list(string.ascii_uppercase[:n])


def extract_outputs(html: str, url: str, tools: list[str], rag: ChromeRAG) -> dict[str, str]:
    outs: dict[str, str] = {}
    for t in tools:
        if t == "chromerag":
            outs[t] = rag.extract(html, url=url or None).markdown
        else:
            try:
                outs[t] = BASELINES[t](html) or ""
            except Exception:  # noqa: BLE001
                outs[t] = ""
    return {t: normalise(v) for t, v in outs.items()}


def forbid_key_path(path: Path) -> None:
    resolved = path.resolve()
    banned = [(EVAL / "bundle").resolve(), (EVAL / "results").resolve()]
    for b in banned:
        try:
            resolved.relative_to(b)
            raise SystemExit(
                f"Refusing to write key.json under {b}. "
                "Pass --out-key to a path outside evaluators/bundle and evaluators/results."
            )
        except ValueError:
            continue


def make_item(
    *,
    item_id: str,
    url: str,
    page_html: str,
    outs: dict[str, str],
    tools: list[str],
    rng: random.Random,
) -> tuple[dict, dict]:
    order = list(tools)
    rng.shuffle(order)
    labs = labels_for(len(order))
    key = {labs[i]: order[i] for i in range(len(order))}
    item = {
        "item_id": item_id,
        "source_url": url,
        "page_html": page_html,
        "outputs": {lab: outs[tool] for lab, tool in key.items()},
    }
    return item, key


def load_pages(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("pages JSON must be a list of {id, url, html, page_type}")
    return raw


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Build blind rating bundle + key")
    p.add_argument("--pages", type=Path, required=True, help="JSON list of pages")
    p.add_argument("--calibration", type=Path, default=None, help="JSON list of calibration pages")
    p.add_argument("--tools", nargs="+", default=list(DEFAULT_TOOLS))
    p.add_argument("--seed", type=int, default=20261002)
    p.add_argument("--repeats", type=int, default=5, help="Duplicate each page under new item ids")
    p.add_argument("--bundle-id", default=None)
    p.add_argument("--out", type=Path, default=EVAL / "bundle" / "bundle.json")
    p.add_argument("--out-key", type=Path, required=True, help="Path for key.json (outside bundle/results)")
    args = p.parse_args(argv)

    forbid_key_path(args.out_key)
    if args.out_key.name != "key.json" and args.out_key.suffix != ".json":
        # allow any .json name; still never under banned dirs
        pass

    rng = random.Random(args.seed)
    tools = list(args.tools)
    rag = ChromeRAG(config=PipelineConfig.from_priority(ContentPriority.BALANCED))
    pages = load_pages(args.pages)
    cal_pages = load_pages(args.calibration) if args.calibration else []

    skipped: list[str] = []
    items: list[dict] = []
    key_map: dict[str, dict] = {}
    page_types: dict[str, str] = {}

    def process(page: dict, *, calibration: bool) -> None:
        html_path = Path(page["html"])
        if not html_path.is_absolute():
            html_path = (ROOT / html_path).resolve() if not html_path.exists() else html_path.resolve()
        html = html_path.read_text(encoding="utf-8")
        url = page.get("url") or ""
        outs = extract_outputs(html, url, tools, rag)
        if any(len(v.split()) < _MIN_WORDS for v in outs.values()):
            skipped.append(page.get("id", str(html_path)))
            print(f"skip (short output): {page.get('id')}", file=sys.stderr)
            return
        clean = sanitise(html, url)
        n = 1 if calibration else max(1, args.repeats)
        for rep in range(n):
            iid = page["id"] if (calibration or n == 1) else f"{page['id']}__r{rep+1}"
            item, key = make_item(
                item_id=iid, url=url, page_html=clean, outs=outs, tools=tools, rng=rng
            )
            if calibration:
                # collected by caller
                process.cal_items.append(item)  # type: ignore[attr-defined]
            else:
                items.append(item)
            key_map[iid] = key
            page_types[iid] = page.get("page_type") or ""

    process.cal_items = []  # type: ignore[attr-defined]
    for page in cal_pages:
        process(page, calibration=True)
    for page in pages:
        process(page, calibration=False)

    rng.shuffle(items)
    bundle_id = args.bundle_id or f"bundle-{args.seed}"
    bundle = {
        "bundle_id": bundle_id,
        "calibration": process.cal_items,  # type: ignore[attr-defined]
        "items": items,
    }
    key_doc = {
        "bundle_id": bundle_id,
        "seed": args.seed,
        "tools": tools,
        "page_types": page_types,
        "key": key_map,
        "skipped_short": skipped,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.out_key.parent.mkdir(parents=True, exist_ok=True)
    args.out_key.write_text(json.dumps(key_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.out} ({len(items)} items, {len(process.cal_items)} calibration)")  # type: ignore[attr-defined]
    print(f"Wrote {args.out_key}")
    if skipped:
        print(f"Skipped {len(skipped)} pages with an output under {_MIN_WORDS} words", file=sys.stderr)


if __name__ == "__main__":
    main()
