"""Cache per-page predictions on a WCXB split and rank where ChromeRAG loses to Trafilatura.

Dev-split tool for improvement work. Usage:
  python -m poc.wcxb_diag run --out /tmp/cr/dev.pkl
  python -m poc.wcxb_diag lines --pkl /tmp/cr/dev.pkl      # recurring noise lines in our output
  python -m poc.wcxb_diag worst --pkl /tmp/cr/dev.pkl --type documentation
"""

from __future__ import annotations

import argparse
import pickle
import re
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

from chromerag import ChromeRAG, ContentPriority, PipelineConfig
from poc.baselines import BASELINES
from poc.wcxb import load_split, strip_front_matter, tokenize, word_f1


def _one(page):
    import os

    from chromerag import density

    extra = os.environ.get("CHROMERAG_EXTRA_NOISE")
    if extra:  # experiment hook: try more chrome class words without editing the package
        density.NOISE_TOKENS = density.NOISE_TOKENS | set(extra.split(","))
    kw = {}
    if os.environ.get("CHROMERAG_LBC") == "off":
        kw["enable_lbc"] = False
    prio = ContentPriority(os.environ.get("CHROMERAG_PRIORITY", "coverage"))
    cfg = PipelineConfig.from_priority(prio, enable_dvdf=True, **kw)
    if os.environ.get("CHROMERAG_LBC_THRESHOLD"):
        cfg.lbc_threshold = float(os.environ["CHROMERAG_LBC_THRESHOLD"])
    if os.environ.get("CHROMERAG_LBC_PAGE") == "root":
        cfg.lbc_whole_page = False
    model = None
    if os.environ.get("CHROMERAG_LBC_MODEL"):
        from pathlib import Path

        from chromerag.lbc import TwoStageModel

        model = TwoStageModel.load(Path(os.environ["CHROMERAG_LBC_MODEL"]))
    try:
        ours = strip_front_matter(
            ChromeRAG(config=cfg, lbc_model=model).extract(page.html, url=page.url or None).markdown
        )
    except Exception as exc:  # noqa: BLE001
        ours = ""
        print("CRASH", page.id, exc)
    try:
        traf = strip_front_matter(BASELINES["trafilatura"](page.html))
    except Exception:  # noqa: BLE001
        traf = ""
    return page.id, page.url, page.page_type, ours, traf, page.main_content


def run(split: str, out: str, half: str = "all") -> None:
    from poc.learn_tokens import half as site_half
    from poc.learn_tokens import site_of

    pages = load_split(split)
    if half != "all":
        pages = [p for p in pages if site_half(site_of(p.url)) == half]
    with ProcessPoolExecutor() as pool:
        rows = list(pool.map(_one, pages, chunksize=8))
    pickle.dump(rows, open(out, "wb"))
    summarize(rows)


def summarize(rows) -> None:
    by = defaultdict(list)
    for pid, url, t, ours, traf, ref in rows:
        for name, pred in (("ours", ours), ("traf", traf)):
            by[(t, name)].append(word_f1(pred, ref))
            by[("ALL", name)].append(word_f1(pred, ref))
    for t in sorted({k[0] for k in by}):
        o, tr = by[(t, "ours")], by[(t, "traf")]
        m = lambda xs, i: sum(x[i] for x in xs) / len(xs)  # noqa: E731
        print(f"{t:14s} n={len(o):4d} ours P{m(o,0):.3f} R{m(o,1):.3f} F{m(o,2):.3f} | traf P{m(tr,0):.3f} R{m(tr,1):.3f} F{m(tr,2):.3f}")


def _norm(line: str) -> str:
    return " ".join(tokenize(line))


def noise_lines(rows, min_pages: int = 4):
    """Lines of our output that share almost no words with the reference, counted across pages."""
    counts: Counter[str] = Counter()
    examples: dict[str, str] = {}
    for pid, url, t, ours, traf, ref in rows:
        ref_set = set(tokenize(ref))
        seen = set()
        for line in ours.splitlines():
            toks = tokenize(line)
            if len(toks) < 2:
                continue
            hit = sum(1 for w in toks if w in ref_set) / len(toks)
            if hit < 0.3:
                key = _norm(line)[:80]
                if key not in seen:
                    seen.add(key)
                    counts[key] += 1
                    examples[key] = line[:140]
    return [(c, examples[k]) for k, c in counts.most_common() if c >= min_pages]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "lines", "worst", "summary"])
    ap.add_argument("--split", default="dev")
    ap.add_argument("--out", default="/tmp/cr/dev.pkl")
    ap.add_argument("--pkl", default="/tmp/cr/dev.pkl")
    ap.add_argument("--type", default=None)
    ap.add_argument("--half", default="all", choices=["all", "learn", "valid"])
    ap.add_argument("--n", type=int, default=15)
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.split, a.out, a.half)
        return
    rows = pickle.load(open(a.pkl, "rb"))
    if a.cmd == "summary":
        summarize(rows)
    elif a.cmd == "lines":
        for c, ex in noise_lines(rows)[:60]:
            print(f"{c:4d}  {ex}")
    else:
        sel = [r for r in rows if a.type in (None, r[2])]
        scored = sorted(sel, key=lambda r: word_f1(r[3], r[5])[2] - word_f1(r[4], r[5])[2])
        for pid, url, t, ours, traf, ref in scored[: a.n]:
            fo, ft = word_f1(ours, ref), word_f1(traf, ref)
            print(f"\n=== {pid} [{t}] ours F{fo[2]:.2f} (P{fo[0]:.2f} R{fo[1]:.2f}) traf F{ft[2]:.2f} (P{ft[0]:.2f} R{ft[1]:.2f}) {url}")


if __name__ == "__main__":
    main()
