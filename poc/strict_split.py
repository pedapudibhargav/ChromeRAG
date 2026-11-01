"""Build strict WCXB training ids: no test domains, no leaked ids, no near-duplicates of test."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from poc.psl import load_psl, registrable_domain
from poc.wcxb import load_split, tokenize

ROOT = Path(__file__).resolve().parents[1]
LEAKED = ROOT / "poc" / "wcxb_leaked_ids.json"
TRAIN_IDS_OUT = ROOT / "poc" / "wcxb_strict_train_ids.json"
MANIFEST_OUT = ROOT / "evaluations" / "2026-10-v0.1.3" / "strict_split_manifest.json"

NEAR_DUP_JACCARD = 0.8
SHINGLE_N = 5


def _shingles(text: str) -> set[tuple[str, ...]]:
    toks = tokenize(text)
    if len(toks) < SHINGLE_N:
        return {tuple(toks)} if toks else set()
    return {tuple(toks[i : i + SHINGLE_N]) for i in range(len(toks) - SHINGLE_N + 1)}


def _jaccard(a: set[tuple[str, ...]], b: set[tuple[str, ...]]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union


def page_domain(page) -> str:
    return registrable_domain(page.url or "")


def build() -> dict:
    psl = load_psl()
    dev = [p for p in load_split("dev") if len(tokenize(p.main_content)) >= 30]
    test = [p for p in load_split("test") if len(tokenize(p.main_content)) >= 30]
    leaked = frozenset(json.loads(LEAKED.read_text(encoding="utf-8")))

    counts_by_type = Counter(p.page_type for p in dev)
    start_n = len(dev)
    start_by_type = dict(counts_by_type)

    test_domains = {page_domain(p) for p in test if page_domain(p)}
    shared_domain_pages = [p for p in dev if page_domain(p) in test_domains]

    ids = {p.id for p in dev}
    after_leak = ids - leaked
    removed_leak = ids - after_leak

    after_domain = {p.id for p in dev if p.id in after_leak and page_domain(p) not in test_domains}
    removed_domain = after_leak - after_domain

    test_shingles = [(p.id, _shingles(p.main_content)) for p in test]
    near_dup_ids: list[str] = []
    kept = set(after_domain)
    for p in dev:
        if p.id not in kept:
            continue
        sh = _shingles(p.main_content)
        if any(_jaccard(sh, ts) >= NEAR_DUP_JACCARD for _tid, ts in test_shingles):
            near_dup_ids.append(p.id)
            kept.discard(p.id)
    near_dup_ids.sort()

    final_pages = [p for p in dev if p.id in kept]
    final_by_type = Counter(p.page_type for p in final_pages)

    manifest = {
        "public_suffix_list_version": psl.version_line,
        "near_duplicate_jaccard_threshold": NEAR_DUP_JACCARD,
        "counts": {
            "dev_eligible_start": start_n,
            "after_leaked_ids": len(after_leak),
            "after_test_domain_exclusion": len(after_domain),
            "after_near_duplicate_guard": len(kept),
            "removed_leaked_ids": len(removed_leak),
            "removed_test_domain": len(removed_domain),
            "removed_near_duplicate": len(near_dup_ids),
        },
        "per_page_type": {
            "start": start_by_type,
            "final": dict(final_by_type),
        },
        "test_registrable_domains": len(test_domains),
        "shared_domain_dev_pages_before_exclusion": len(shared_domain_pages),
        "near_duplicate_train_ids": near_dup_ids,
        "fitted_artifacts": [],
    }
    return manifest, sorted(kept)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    manifest, ids = build()
    if a.write:
        TRAIN_IDS_OUT.write_text(json.dumps(ids, indent=1) + "\n", encoding="utf-8")
        MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_OUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(len(ids), "train ids ->", TRAIN_IDS_OUT.name)
        print("manifest ->", MANIFEST_OUT.name)
    else:
        print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
