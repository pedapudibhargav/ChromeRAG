"""Build a blind rating bundle + separate key/orders files for the author.

Folder mode (preferred for prepared corpora):

  python -m evaluators.author.build_bundle \\
    --from-dir path/to/corpus \\
    --out evaluators/bundle/bundle.json \\
    --out-key path/outside/evaluators/key.json \\
    --out-orders path/outside/evaluators/orders.json

Corpus layout:
  pages.json   list of {id, url, page_type, html}
  html/        page HTML files referenced by pages.json
  outputs/<tool>/<id>.md   (or .txt) precomputed per-tool text

Defaults: 75 stratified main pages, 5 repeat items, 5 calibration pages,
three tools, deterministic for the same input + seed. Sanitised page copies
are written under --pages-out (git-ignored local dir) and also embedded in
the bundle so raters need only bundle.json.

Legacy extract mode still accepts --pages and runs tools itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import string
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL = Path(__file__).resolve().parents[1]
DEFAULT_TOOLS = ("chromerag", "trafilatura", "readability")
DEFAULT_N_PAGES = 75
DEFAULT_N_REPEATS = 5
DEFAULT_N_CALIBRATION = 5
_FRONT = re.compile(r"\A---\n.*?\n---\n+", re.S)
_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_EMPH = re.compile(r"(\*\*|__)(.+?)\1")
_REMOTE_ATTRS = frozenset(
    "href src srcset lowsrc dynsrc action formaction poster data background cite longdesc ping usemap manifest".split()
)
_ADDRESS_VALUE = re.compile(r"(?:[a-z][a-z0-9+.-]*:)?//|%3A%2F%2F", re.I)
# Full addresses shown as text become one mark, the same way for pages and for every tool.
_ADDRESS_TEXT = re.compile(r"\b(?:https?://|www\.)[^\s<>()\[\]\"']+", re.I)
_HIDDEN_STYLE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.I)


def normalise(text: str) -> str:
    text = _FRONT.sub("", text or "")
    text = _IMG.sub("", text)
    text = _LINK.sub(r"\1", text)
    text = _EMPH.sub(r"\2", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = _ADDRESS_TEXT.sub("[link]", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def sanitise(html: str, url: str = "") -> str:
    """Saved page for raters: no scripts and nothing that can reach another site."""
    from bs4 import BeautifulSoup, Comment

    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript", "iframe", "object", "embed", "template", "link", "base", "meta"]):
        t.decompose()
    for c in soup.find_all(string=lambda x: isinstance(x, Comment)):
        c.extract()
    for node in soup.find_all(string=True):
        if _ADDRESS_TEXT.search(node):
            node.replace_with(_ADDRESS_TEXT.sub("[link]", str(node)))
    for tag in soup.find_all(True):
        if _HIDDEN_STYLE.search(str(tag.get("style") or "")):
            tag["hidden"] = ""
        for attr in list(tag.attrs):
            name = attr.lower()
            value = tag.get(attr)
            value = " ".join(value) if isinstance(value, list) else str(value)
            if (
                name == "style"
                or name.startswith("on")
                or name.split(":")[-1] in _REMOTE_ATTRS
                or _ADDRESS_VALUE.search(value)
                or _ADDRESS_TEXT.search(value)
            ):
                del tag[attr]
    # Page styles are gone, so icons would otherwise fill the preview.
    limit = soup.new_tag("style")
    limit.string = "svg,img{max-width:48px;max-height:48px}"
    (soup.head or soup).insert(0, limit)
    return str(soup)


def labels_for(n: int) -> list[str]:
    return list(string.ascii_uppercase[:n])


def forbid_key_path(path: Path) -> None:
    resolved = path.resolve()
    banned = [(EVAL / "bundle").resolve(), (EVAL / "results").resolve()]
    for b in banned:
        try:
            resolved.relative_to(b)
            raise SystemExit(
                f"Refusing to write author-private file under {b}. "
                "Pass a path outside evaluators/bundle and evaluators/results."
            )
        except ValueError:
            continue


def resolve_html_path(raw: str | Path, *, base: Path) -> Path:
    html_path = Path(raw)
    if html_path.is_absolute():
        return html_path
    candidates = [base / html_path, ROOT / html_path, Path.cwd() / html_path]
    for c in candidates:
        if c.exists():
            return c.resolve()
    return (base / html_path).resolve()


def load_pages(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("pages JSON must be a list of {id, url, html, page_type}")
    return raw


def read_tool_output(corpus: Path, tool: str, page_id: str) -> str:
    base = corpus / "outputs" / tool
    for ext in (".md", ".txt", ".markdown"):
        path = base / f"{page_id}{ext}"
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"missing output for tool={tool!r} page={page_id!r} under {base}")


def extract_outputs_live(html: str, url: str, tools: list[str]) -> dict[str, str]:
    from chromerag import ChromeRAG, ContentPriority, PipelineConfig
    from poc.baselines import BASELINES

    rag = ChromeRAG(config=PipelineConfig.from_priority(ContentPriority.BALANCED))
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


def load_outputs_from_dir(corpus: Path, page_id: str, tools: list[str]) -> dict[str, str]:
    return {t: normalise(read_tool_output(corpus, t, page_id)) for t in tools}


def allocate_quotas(counts: dict[str, int], n: int) -> dict[str, int]:
    """Proportional integer quotas that sum to n (largest-remainder)."""
    types = sorted(counts)
    total = sum(counts[t] for t in types)
    if total == 0 or n <= 0:
        return {t: 0 for t in types}
    n = min(n, total)
    raw = {t: (counts[t] / total) * n for t in types}
    floors = {t: int(raw[t]) for t in types}
    rem = n - sum(floors.values())
    order = sorted(types, key=lambda t: (raw[t] - floors[t], counts[t], t), reverse=True)
    for t in order[:rem]:
        floors[t] += 1
    # Cap by availability
    for t in types:
        floors[t] = min(floors[t], counts[t])
    # Top up if capping reduced the sum
    deficit = n - sum(floors.values())
    if deficit > 0:
        for t in sorted(types, key=lambda x: counts[x] - floors[x], reverse=True):
            take = min(deficit, counts[t] - floors[t])
            floors[t] += take
            deficit -= take
            if deficit == 0:
                break
    return floors


def stratified_sample(
    pages: list[dict], n: int, rng: random.Random, fixed: dict[str, int] | None = None
) -> list[dict]:
    by_type: dict[str, list[dict]] = defaultdict(list)
    for p in pages:
        by_type[p.get("page_type") or "unknown"].append(p)
    for t in by_type:
        by_type[t] = sorted(by_type[t], key=lambda p: str(p.get("id")))
        rng.shuffle(by_type[t])
    set_quota = {t: min(k, len(by_type[t])) for t, k in (fixed or {}).items() if t in by_type}
    rest = {t: len(v) for t, v in by_type.items() if t not in set_quota}
    quotas = {**allocate_quotas(rest, n - sum(set_quota.values())), **set_quota}
    chosen: list[dict] = []
    for t in sorted(quotas):
        chosen.extend(by_type[t][: quotas[t]])
    rng.shuffle(chosen)
    return chosen


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
        "page_html": page_html,
        "outputs": {lab: outs[tool] for lab, tool in key.items()},
    }
    return item, key


def _seed_rng(rater: str, bundle_id: str) -> random.Random:
    digest = hashlib.sha256(f"{rater}\0{bundle_id}".encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def plan_rater_orders(bundle: dict, raters: list[str]) -> dict[str, dict]:
    """Per-rater item order and label display order (author-private)."""
    out: dict[str, dict] = {}
    cal = [it["item_id"] for it in bundle.get("calibration", [])]
    main_ids = [it["item_id"] for it in bundle.get("items", [])]
    by_id = {it["item_id"]: it for it in list(bundle.get("calibration", [])) + list(bundle.get("items", []))}
    for rater in raters:
        rng = _seed_rng(rater, bundle["bundle_id"])
        main = list(main_ids)
        rng.shuffle(main)
        order = cal + main
        shown: dict[str, list[str]] = {}
        for iid in order:
            labs = sorted(by_id[iid]["outputs"].keys())
            rng.shuffle(labs)
            shown[iid] = labs
        out[rater] = {"item_order": order, "shown_order": shown}
    return out


def prepare_page_record(
    page: dict,
    *,
    tools: list[str],
    corpus: Path | None,
    pages_out: Path | None,
    live: bool,
) -> tuple[dict[str, str], str] | None:
    """Return (normalised outs, sanitised html) or None if short."""
    base = corpus if corpus is not None else ROOT
    html_path = resolve_html_path(page["html"], base=base)
    html = html_path.read_text(encoding="utf-8")
    url = page.get("url") or ""
    if live:
        outs = extract_outputs_live(html, url, tools)
    else:
        assert corpus is not None
        outs = load_outputs_from_dir(corpus, str(page["id"]), tools)
    clean = sanitise(html, url)
    if pages_out is not None:
        pages_out.mkdir(parents=True, exist_ok=True)
        (pages_out / f"{page['id']}.html").write_text(clean, encoding="utf-8")
    return outs, clean


def _unmarked_id(pid: str, taken: set[str], rng: random.Random) -> str:
    """A repeat's id looks like any page id but is above every id ever collected, so it names no real page."""
    prefix = re.sub(r"\d+$", "", pid)
    numbers = [int(m.group()) for t in taken if (m := re.search(r"\d+$", t))]
    width = len(pid) - len(prefix) or 4
    top = max(numbers, default=0)
    free = [i for i in range(top + 1, top + 400) if f"{prefix}{i:0{width}d}" not in taken]
    return f"{prefix}{rng.choice(free):0{width}d}"


def build_from_records(
    *,
    main_pages: list[dict],
    cal_pages: list[dict],
    prepared: dict[str, tuple[dict[str, str], str]],
    tools: list[str],
    seed: int,
    n_repeats: int,
    bundle_id: str,
    raters: list[str],
) -> tuple[dict, dict, dict]:
    rng = random.Random(seed)
    items: list[dict] = []
    cal_items: list[dict] = []
    key_map: dict[str, dict] = {}
    page_types: dict[str, str] = {}

    for page in cal_pages:
        pid = str(page["id"])
        outs, clean = prepared[pid]
        item, key = make_item(item_id=pid, url=page.get("url") or "", page_html=clean, outs=outs, tools=tools, rng=rng)
        cal_items.append(item)
        key_map[pid] = key
        page_types[pid] = page.get("page_type") or ""

    for page in main_pages:
        pid = str(page["id"])
        outs, clean = prepared[pid]
        item, key = make_item(item_id=pid, url=page.get("url") or "", page_html=clean, outs=outs, tools=tools, rng=rng)
        items.append(item)
        key_map[pid] = key
        page_types[pid] = page.get("page_type") or ""

    # Reliability repeats: duplicate n_repeats distinct main pages under new ids.
    repeat_of: dict[str, str] = {}
    if n_repeats > 0 and main_pages:
        pool = list(main_pages)
        rng.shuffle(pool)
        taken = {str(p["id"]) for p in [*main_pages, *cal_pages]} | set(prepared)
        for page in pool[: min(n_repeats, len(pool))]:
            pid = str(page["id"])
            rid = _unmarked_id(pid, taken, rng)
            taken.add(rid)
            outs, clean = prepared[pid]
            item, key = make_item(
                item_id=rid, url=page.get("url") or "", page_html=clean, outs=outs, tools=tools, rng=rng
            )
            items.append(item)
            key_map[rid] = key
            page_types[rid] = page.get("page_type") or ""
            repeat_of[rid] = pid

    rng.shuffle(items)
    bundle = {
        "bundle_id": bundle_id,
        "calibration": cal_items,
        "items": items,
    }
    key_doc = {
        "bundle_id": bundle_id,
        "seed": seed,
        "tools": tools,
        "page_types": page_types,
        "key": key_map,
        "repeat_of": repeat_of,
        "n_main": len(main_pages),
        "n_repeats": len(repeat_of),
        "n_calibration": len(cal_items),
    }
    orders = plan_rater_orders(bundle, raters)
    return bundle, key_doc, orders


def build_bundle_from_dir(
    corpus: Path,
    *,
    tools: list[str] | None = None,
    seed: int = 20261002,
    n_pages: int = DEFAULT_N_PAGES,
    n_repeats: int = DEFAULT_N_REPEATS,
    n_calibration: int = DEFAULT_N_CALIBRATION,
    bundle_id: str | None = None,
    pages_out: Path | None = None,
    raters: list[str] | None = None,
    fixed_quota: dict[str, int] | None = None,
) -> tuple[dict, dict, dict]:
    tools = list(tools or DEFAULT_TOOLS)
    if len(tools) != 3:
        raise SystemExit("folder mode expects exactly three tools (blinded as A/B/C)")
    pages_path = corpus / "pages.json"
    if not pages_path.exists():
        raise SystemExit(f"missing {pages_path}")
    pages = load_pages(pages_path)
    rng = random.Random(seed)

    prepared: dict[str, tuple[dict[str, str], str]] = {}
    eligible: list[dict] = []
    skipped: list[str] = []
    for page in pages:
        pid = str(page["id"])
        try:
            rec = prepare_page_record(page, tools=tools, corpus=corpus, pages_out=pages_out, live=False)
        except FileNotFoundError as exc:
            skipped.append(pid)
            print(f"skip (missing output): {exc}", file=sys.stderr)
            continue
        if rec is None:
            skipped.append(pid)
            print(f"skip (short output): {pid}", file=sys.stderr)
            continue
        prepared[pid] = rec
        eligible.append(page)

    if len(eligible) < n_pages + n_calibration:
        raise SystemExit(f"need at least {n_pages + n_calibration} eligible pages, have {len(eligible)}")

    main = stratified_sample(eligible, n_pages, rng, fixed_quota)
    main_ids = {str(p["id"]) for p in main}
    leftover = [p for p in eligible if str(p["id"]) not in main_ids]
    if len(leftover) < n_calibration:
        raise SystemExit(f"need {n_calibration} leftover pages for calibration, have {len(leftover)}")
    cal = stratified_sample(leftover, n_calibration, rng)

    bid = bundle_id or "bundle-" + hashlib.sha256(str(seed).encode()).hexdigest()[:12]
    rater_ids = list(raters or ["rater-a", "rater-b", "rater-c"])
    bundle, key_doc, orders = build_from_records(
        main_pages=main,
        cal_pages=cal,
        prepared=prepared,
        tools=tools,
        seed=seed,
        n_repeats=n_repeats,
        bundle_id=bid,
        raters=rater_ids,
    )
    key_doc["skipped_short"] = skipped
    key_doc["source"] = "from-dir"
    return bundle, key_doc, orders


def write_outputs(bundle: dict, key_doc: dict, orders: dict, out: Path, out_key: Path, out_orders: Path) -> None:
    forbid_key_path(out_key)
    forbid_key_path(out_orders)
    out.parent.mkdir(parents=True, exist_ok=True)
    out_key.parent.mkdir(parents=True, exist_ok=True)
    out_orders.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out_key.write_text(json.dumps(key_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out_orders.write_text(json.dumps(orders, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # Sanity: labels the app shows must not name tools. Page text may use these as ordinary words.
    names = {t.lower() for t in key_doc.get("tools") or []}
    visible = {str(bundle["bundle_id"]).lower()}
    for item in [*bundle["items"], *bundle["calibration"]]:
        visible |= {str(item["item_id"]).lower(), *(str(k).lower() for k in item), *(str(k).lower() for k in item["outputs"])}
    for tool in names:
        if any(tool in v for v in visible):
            raise SystemExit(f"tool name {tool!r} leaked into bundle")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Build blind rating bundle + key + orders")
    p.add_argument("--from-dir", type=Path, default=None, help="Corpus folder (pages.json + html/ + outputs/)")
    p.add_argument("--pages", type=Path, default=None, help="Legacy: JSON list of pages to extract")
    p.add_argument("--calibration", type=Path, default=None, help="Legacy: calibration page list")
    p.add_argument("--tools", nargs="+", default=list(DEFAULT_TOOLS))
    p.add_argument("--seed", type=int, default=20261002)
    p.add_argument("--n-pages", type=int, default=DEFAULT_N_PAGES, help="Stratified main pages (folder mode)")
    p.add_argument("--n-repeats", type=int, default=DEFAULT_N_REPEATS, help="Extra repeat items (folder mode)")
    p.add_argument("--fixed-quota", nargs="*", default=[], help="Page type counts set in advance, e.g. forum=10")
    p.add_argument("--n-calibration", type=int, default=DEFAULT_N_CALIBRATION, help="Calibration pages")
    p.add_argument(
        "--repeats",
        type=int,
        default=None,
        help="Legacy extract mode: duplicate each page this many times (default 5)",
    )
    p.add_argument("--bundle-id", default=None)
    p.add_argument("--raters", nargs="+", default=["rater-a", "rater-b", "rater-c"])
    p.add_argument("--out", type=Path, default=EVAL / "bundle" / "bundle.json")
    p.add_argument("--out-key", type=Path, required=True, help="Path for key.json (outside bundle/results)")
    p.add_argument(
        "--out-orders",
        type=Path,
        default=None,
        help="Per-rater display orders (default: sibling of --out-key named orders.json)",
    )
    p.add_argument(
        "--pages-out",
        type=Path,
        default=ROOT / "data" / "human_eval" / "html",
        help="Local directory for sanitised page copies (not for raters; git-ignored)",
    )
    args = p.parse_args(argv)

    out_orders = args.out_orders or (args.out_key.parent / "orders.json")
    forbid_key_path(args.out_key)
    forbid_key_path(out_orders)

    if args.from_dir:
        bundle, key_doc, orders = build_bundle_from_dir(
            args.from_dir,
            tools=list(args.tools),
            seed=args.seed,
            n_pages=args.n_pages,
            n_repeats=args.n_repeats,
            n_calibration=args.n_calibration,
            fixed_quota={k: int(v) for k, v in (x.split("=") for x in args.fixed_quota)},
            bundle_id=args.bundle_id,
            pages_out=args.pages_out,
            raters=list(args.raters),
        )
        write_outputs(bundle, key_doc, orders, args.out, args.out_key, out_orders)
        print(f"Wrote {args.out} ({len(bundle['items'])} items, {len(bundle['calibration'])} calibration)")
        print(f"Wrote {args.out_key}")
        print(f"Wrote {out_orders}")
        return

    if not args.pages:
        raise SystemExit("pass --from-dir or --pages")

    # Legacy extract path
    tools = list(args.tools)
    repeats = 5 if args.repeats is None else args.repeats
    rng = random.Random(args.seed)
    pages = load_pages(args.pages)
    cal_pages = load_pages(args.calibration) if args.calibration else []
    skipped: list[str] = []
    items: list[dict] = []
    cal_items: list[dict] = []
    key_map: dict[str, dict] = {}
    page_types: dict[str, str] = {}

    def process(page: dict, *, calibration: bool) -> None:
        rec = prepare_page_record(page, tools=tools, corpus=None, pages_out=args.pages_out, live=True)
        if rec is None:
            skipped.append(page.get("id", "?"))
            print(f"skip (short output): {page.get('id')}", file=sys.stderr)
            return
        outs, clean = rec
        n = 1 if calibration else max(1, repeats)
        for rep in range(n):
            iid = page["id"] if (calibration or n == 1) else f"{page['id']}__r{rep + 1}"
            item, key = make_item(
                item_id=iid, url=page.get("url") or "", page_html=clean, outs=outs, tools=tools, rng=rng
            )
            if calibration:
                cal_items.append(item)
            else:
                items.append(item)
            key_map[iid] = key
            page_types[iid] = page.get("page_type") or ""

    for page in cal_pages:
        process(page, calibration=True)
    for page in pages:
        process(page, calibration=False)

    rng.shuffle(items)
    bundle_id = args.bundle_id or "bundle-" + hashlib.sha256(str(args.seed).encode()).hexdigest()[:12]
    bundle = {"bundle_id": bundle_id, "calibration": cal_items, "items": items}
    key_doc = {
        "bundle_id": bundle_id,
        "seed": args.seed,
        "tools": tools,
        "page_types": page_types,
        "key": key_map,
        "skipped_short": skipped,
        "source": "extract",
    }
    orders = plan_rater_orders(bundle, list(args.raters))
    write_outputs(bundle, key_doc, orders, args.out, args.out_key, out_orders)
    print(f"Wrote {args.out} ({len(items)} items, {len(cal_items)} calibration)")
    print(f"Wrote {args.out_key}")
    print(f"Wrote {out_orders}")
    if skipped:
        print(f"Skipped {len(skipped)} pages with an output under {_MIN_WORDS} words", file=sys.stderr)


if __name__ == "__main__":
    main()
